import logging
import os
import time
from typing import Any, Dict, List, Optional, TypedDict

import boto3
import urllib3
from botocore.exceptions import ClientError
from jose import jwk, jwt
from jose.utils import base64url_decode

# ====================================================================================
# ENVIRONMENT CONFIGURATION
# ====================================================================================
# These environment variables are injected through template.yaml and provide
# all configuration parameters required for Cognito, AWS region, and the
# DDB table storing token-lifetime metadata.
# ------------------------------------------------------------------------------------

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["USER_POOL_ID"]
USER_POOL_CLIENT_ID = os.environ["USER_POOL_CLIENT_ID"]
TOKENS_TABLE = os.environ["TOKENS_TABLE"]

ddb = boto3.resource("dynamodb")
tokens_table = ddb.Table(TOKENS_TABLE)

cognito = boto3.client("cognito-idp")

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

http = urllib3.PoolManager()

# ====================================================================================
# SECURITY TRACK CONSTANTS
# ====================================================================================
# These constants implement the required access-token restrictions for the
# ModelGuard "Other Security Track":
#   - Tokens expire after 10 hours from issuance
#   - Tokens are valid for only 1000 API interactions total
#   These rules override Cognito defaults while still using Cognito JWTs.
# ------------------------------------------------------------------------------------

API_TOKEN_TIME_TO_LIVE = 60 * 60 * 10  # 10 hours
API_TOKEN_CALL_LIMIT = 1000  # 1000 requests per token

# ====================================================================================
# JWKS LOADING (COLD START)
# ====================================================================================
# Cognito publishes JSON Web Key Sets (JWKS) for verifying access-token signatures.
# These keys rarely rotate, so we fetch them once at Lambda cold start.
# ------------------------------------------------------------------------------------

JWKS_URL = (
    f"https://cognito-idp.{REGION}.amazonaws.com/"
    f"{USER_POOL_ID}/.well-known/jwks.json"
)

jwks = http.request("GET", JWKS_URL).json()["keys"]


# ====================================================================================
# AUTHENTICATION: USERNAME + PASSWORD → COGNITO → ACCESS TOKEN
# ====================================================================================
# This function is used *only* by the /authenticate endpoint.
# It performs a USER_PASSWORD_AUTH flow against Cognito, then stores token
# metadata in DynamoDB so that our custom TTL + usage-limit rules can be enforced
# later in verify_token().
# ------------------------------------------------------------------------------------


def authenticate_user(username: str, password: str) -> dict:
    """
    Authenticate a user via Cognito USER_PASSWORD_AUTH and record issuance
    in DynamoDB for custom lifetime and usage rules.
    """
    try:
        resp = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=USER_POOL_CLIENT_ID,
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        # Pull tokens from Cognito response
        auth = resp["AuthenticationResult"]
        access_token = auth["AccessToken"]

        # Record token issuance time + usage count in DynamoDB
        tokens_table.put_item(
            Item={
                "token": access_token,
                "username": username,
                "issued_at": int(time.time()),
                "uses": 0,
            }
        )

        return {
            "access_token": access_token,
            "id_token": auth.get("IdToken"),
            "refresh_token": auth.get("RefreshToken"),
            "expires_in": auth.get("ExpiresIn"),
        }

    except ClientError as e:
        log.error(f"Cognito authentication failed: {e}")
        raise


# ====================================================================================
# TOKEN VERIFICATION: SIGNATURE • EXPIRATION • TTL • USAGE COUNT
# ====================================================================================
# This is the heart of ModelGuard’s token security mechanism. We:
#   1. Validate the JWT signature using JWKS (Cognito public keys)
#   2. Validate the Cognito `exp` claim
#   3. Enforce the 10-hour ModelGuard TTL
#   4. Enforce the 1000-call usage maximum
#   5. Increment the token's "uses" counter in DynamoDB
# ------------------------------------------------------------------------------------


def verify_token(token: str) -> dict:
    """Validate Cognito JWT + custom ModelGuard token lifecycle rules."""

    # Step 1: Signature Validation
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")

    # Find the matching JWKS key by Key ID
    key = next((k for k in jwks if k["kid"] == kid), None)
    if not key:
        raise Exception("Invalid token: unknown kid")

    public_key = jwk.construct(key)

    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode())

    if not public_key.verify(message.encode(), decoded_sig):
        raise Exception("Invalid token signature")

    # Step 2: Decode Claims
    claims = jwt.get_unverified_claims(token)

    # Cognito's own expiration check
    now = time.time()
    if now > claims["exp"]:
        raise Exception("Token expired (JWT exp claim)")

    # Step 3: TTL Enforcement
    record = tokens_table.get_item(Key={"token": token}).get("Item")
    if not record:
        raise Exception("Token not registered or invalid")

    if now - record["issued_at"] > API_TOKEN_TIME_TO_LIVE:
        raise Exception("Token expired (time-to-live exceeded)")

    # Step 4: Usage Limit
    if record["uses"] >= API_TOKEN_CALL_LIMIT:
        raise Exception("Token expired (call limit exceeded)")

    # Step 5: Increment token usage
    tokens_table.update_item(
        Key={"token": token},
        UpdateExpression="SET uses = uses + :inc",
        ExpressionAttributeValues={":inc": 1},
    )

    return claims


# ====================================================================================
# ROLE-BASED ACCESS CONTROL (RBAC)
# ====================================================================================
# Cognito groups are used to implement per-endpoint RBAC. This function enforces
# that the caller belongs to at least one of the required groups.
# ------------------------------------------------------------------------------------


def require_roles(claims: dict, allowed_roles: list) -> None:
    """Raise if JWT does not contain at least one allowed Cognito group."""
    groups = claims.get("cognito:groups", [])

    if not groups:
        raise Exception("User has no assigned roles/groups")

    for r in allowed_roles:
        if r in groups:
            return  # Authorized

    raise Exception(
        f"Permission denied. Required: {allowed_roles}, user groups: {groups}"
    )


# ====================================================================================
# USERNAME EXTRACTION
# ====================================================================================
# Cognito may provide "username" or "cognito:username" depending on flow.
# This helper normalizes those differences.
# ------------------------------------------------------------------------------------


def get_username(claims: dict) -> str | None:
    return claims.get("username") or claims.get("cognito:username")


# ====================================================================================
# SHARED AUTH EXTRACTOR (MAIN INTERFACE FOR ALL ENDPOINTS)
# ====================================================================================
# This is the central function the Lambda handlers will call:
#
#     auth = authorize(event, allowed_roles=["Admin"])
#
# It performs:
#   1. Header extraction (X-Authorization preferred by spec)
#   2. Bearer-token parsing
#   3. JWT verification + ModelGuard custom rules
#   4. Optional role enforcement
#   5. Returns a normalized auth context
#
# This ensures:
#   - consistent behavior across ALL endpoints
#   - spec compliance
#   - zero duplication across Lambdas
# ------------------------------------------------------------------------------------


class AuthContext(TypedDict):
    username: Optional[str]
    claims: Dict[str, Any]
    groups: List[str]
    token: str


def authorize(
    event: Dict[str, Any], allowed_roles: Optional[List[str]] = None
) -> AuthContext:
    "Authenticate + authorize this request using headers and custom rules."

    # Step 1: Extract token header
    headers = event.get("headers", {}) or {}

    token_header = headers.get("X-Authorization")

    if not token_header:
        raise Exception("Missing X-Authorization header")

    if not token_header.lower().startswith("bearer "):
        raise Exception("Malformed token (must start with 'bearer ')")

    raw_token = token_header.split(" ", 1)[1].strip()

    # Step 2: Verify JWT + custom rules
    claims = verify_token(raw_token)

    # Step 3: Optional RBAC enforcement
    if allowed_roles:
        require_roles(claims, allowed_roles)

    # Step 4: Return unified auth context
    return {
        "username": get_username(claims),
        "claims": claims,
        "groups": claims.get("cognito:groups", []),
        "token": raw_token,
    }
