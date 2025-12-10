from __future__ import annotations

import os
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypedDict

import boto3
import urllib3
from botocore.exceptions import ClientError
from jose import jwk, jwt
from jose.utils import base64url_decode

from src.logger import logger
from src.replay_prevention import (
    extract_resource_path,
    is_request_replayed,
    record_request_fingerprint,
)
from src.utils.http import LambdaResponse, error_response

# ====================================================================================
# ENVIRONMENT CONFIG
# ====================================================================================

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["USER_POOL_ID"]
USER_POOL_CLIENT_ID = os.environ["USER_POOL_CLIENT_ID"]
TOKENS_TABLE = os.environ["TOKENS_TABLE"]

ddb = boto3.resource("dynamodb")
tokens_table = ddb.Table(TOKENS_TABLE)

cognito = boto3.client("cognito-idp")
http = urllib3.PoolManager()

# ====================================================================================
# SECURITY TRACK CONSTANTS
# ====================================================================================

API_TOKEN_TIME_TO_LIVE = 60 * 60 * 10  # 10 hours
API_TOKEN_CALL_LIMIT = 1000  # 1000 API calls per token

# ====================================================================================
# JWKS LOADING (COLD START)
# ====================================================================================

JWKS_URL = (
    f"https://cognito-idp.{REGION}.amazonaws.com/"
    f"{USER_POOL_ID}/.well-known/jwks.json"
)

logger.info(f"[auth] Loading JWKS keys from {JWKS_URL}")
jwks = http.request("GET", JWKS_URL).json()["keys"]


# ====================================================================================
# PRECISE TYPING FOR TOKEN RECORD
# ====================================================================================


class TokenRecord(TypedDict):
    token: str
    username: str
    issued_at: int
    uses: int


# ====================================================================================
# AUTHENTICATE USER (for /authenticate endpoint)
# ====================================================================================


def authenticate_user(username: str, password: str) -> dict:
    """Authenticate via Cognito USER_PASSWORD_AUTH and store token with TTL."""
    try:
        logger.info(f"[auth] Authenticating user {username} via Cognito")

        resp = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=USER_POOL_CLIENT_ID,
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        auth = resp["AuthenticationResult"]
        access_token = auth["AccessToken"]

        current_time = int(time.time())

        # Store token with DynamoDB TTL
        tokens_table.put_item(
            Item={
                "token": access_token,
                "username": username,
                "issued_at": current_time,
                "uses": 0,
                "ttl_expiry": current_time + API_TOKEN_TIME_TO_LIVE,
            }
        )

        return {
            "access_token": access_token,
            "id_token": auth.get("IdToken"),
            "refresh_token": auth.get("RefreshToken"),
            "expires_in": auth.get("ExpiresIn"),
        }

    except ClientError as e:
        logger.error(f"[auth] Cognito authentication failed: {e}")
        raise


# ====================================================================================
# VERIFY TOKEN (signature, exp, TTL, usage count)
# ====================================================================================


def verify_token(token: str) -> dict:
    """Validate Cognito JWT + ModelGuard token-lifecycle rules."""

    # Step 1 — Signature validation
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")

    key = next((k for k in jwks if k["kid"] == kid), None)
    if not key:
        raise Exception("Invalid token: unknown kid")

    public_key = jwk.construct(key)

    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode())

    if not public_key.verify(message.encode(), decoded_sig):
        raise Exception("Invalid token signature")

    # Step 2 — Decode claims
    claims = jwt.get_unverified_claims(token)
    now = time.time()

    if now > claims["exp"]:
        raise Exception("Token expired (JWT exp claim)")

    # Step 3 — Atomic usage limit check + increment (TTL handled by DynamoDB)
    current_timestamp = int(time.time())

    try:
        tokens_table.update_item(
            Key={"token": token},
            UpdateExpression="ADD uses :inc",
            ConditionExpression=(
                "attribute_exists(#token) AND "
                "uses < :limit AND "
                "ttl_expiry > :current_time"
            ),
            ExpressionAttributeNames={"#token": "token"},
            ExpressionAttributeValues={
                ":inc": 1,
                ":limit": API_TOKEN_CALL_LIMIT,
                ":current_time": current_timestamp,
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise Exception("Token expired, over limit, or invalid")
        raise Exception(f"Token validation failed: {e}")

    return claims


# ====================================================================================
# RBAC Helpers
# ====================================================================================


def require_roles(claims: dict, allowed_roles: list) -> None:
    """Raise if the caller does not have one of the required roles."""
    groups = claims.get("cognito:groups", [])

    if not groups:
        raise Exception("User has no assigned roles/groups")

    if any(role in groups for role in allowed_roles):
        return

    raise Exception(
        f"Permission denied — required={allowed_roles}, user_groups={groups}"
    )


def get_username(claims: dict) -> str | None:
    return claims.get("username") or claims.get("cognito:username")


# ====================================================================================
# AUTHORIZE()
# ====================================================================================


class AuthContext(TypedDict):
    username: Optional[str]
    claims: Dict[str, Any]
    groups: List[str]
    token: str


def authorize(
    event: Dict[str, Any], allowed_roles: Optional[List[str]] = None
) -> AuthContext:
    """Authenticate + authorize request via headers and custom rules."""
    headers = event.get("headers", {}) or {}
    token_header = headers.get("X-Authorization")

    if not token_header:
        raise Exception("Missing X-Authorization header")

    if not token_header.lower().startswith("bearer "):
        raise Exception("Malformed token (must start with 'bearer ')")

    raw_token = token_header.split(" ", 1)[1].strip()

    claims = verify_token(raw_token)

    # Replay detection
    http_method = event.get("httpMethod", "GET")
    resource_path = extract_resource_path(event)
    request_body = event.get("body")

    if is_request_replayed(raw_token, http_method, resource_path, request_body):
        raise Exception("Replay attack detected: duplicate request within 60s window")

    record_request_fingerprint(raw_token, http_method, resource_path, request_body)

    if allowed_roles:
        require_roles(claims, allowed_roles)

    return {
        "username": get_username(claims),
        "claims": claims,
        "groups": claims.get("cognito:groups", []),
        "token": raw_token,
    }


# ====================================================================================
# AUTH REQUIRED DECORATOR
# ====================================================================================
# Enforces authentication (no RBAC).
#
# This decorator wraps any Lambda handler and:
#   1. Extracts the Bearer token from the X-Authorization header
#   2. Verifies signature, expiration, TTL, and usage rules via authorize()
#   3. Injects `auth` into the handler
#
# If verification fails:
#   - Logs the failure
#   - Returns a 401 Unauthorized error response
#
# Usage:
#     @auth_required
#     def lambda_handler(event, context, auth):
#         ...
# ------------------------------------------------------------------------------------


def auth_required(
    func: Callable[..., Any],
) -> Callable[[Dict[str, Any], Any], LambdaResponse]:
    """Require authentication only."""

    @wraps(func)
    def wrapper(event: Dict[str, Any], context: Any) -> LambdaResponse:
        try:
            auth: AuthContext = authorize(event)
            return func(event, context, auth=auth)
        except Exception as e:
            logger.error(f"[auth_required] Unauthorized: {e}")
            return error_response(
                401,
                f"Unauthorized: {e}",
                error_code="UNAUTHORIZED",
            )

    return wrapper


# ====================================================================================
# ROLES REQUIRED DECORATOR (AUTH + RBAC)
# ====================================================================================
# Enforces authentication AND Cognito RBAC.
#
# This decorator wraps any Lambda handler and:
#   1. Extracts the Bearer token from X-Authorization
#   2. Verifies the JWT signature + ModelGuard TTL/usage rules
#   3. Ensures the caller belongs to at least one of the allowed Cognito groups
#   4. Injects `auth` into the handler
#
# If authentication fails → returns 401 Unauthorized
# If role check fails     → returns 403 Forbidden
#
# Usage:
#     @roles_required(["Admin"])
#     def lambda_handler(event, context, auth):
#         ...
# ------------------------------------------------------------------------------------


def roles_required(
    allowed_roles: List[str],
) -> Callable[[Callable[..., Any]], Callable[[Dict[str, Any], Any], LambdaResponse]]:
    """Require authentication + explicit RBAC roles."""

    def decorator(
        func: Callable[..., Any],
    ) -> Callable[[Dict[str, Any], Any], LambdaResponse]:
        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> LambdaResponse:
            try:
                auth: AuthContext = authorize(event, allowed_roles=allowed_roles)
                return func(event, context, auth=auth)
            except Exception as e:
                logger.error(f"[roles_required] Forbidden: {e}")
                return error_response(
                    403,
                    f"Forbidden: {e}",
                    error_code="FORBIDDEN",
                )

        return wrapper

    return decorator
