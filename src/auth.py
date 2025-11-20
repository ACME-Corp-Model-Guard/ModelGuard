import logging
import os
import time

import boto3
import urllib3
from botocore.exceptions import ClientError
from jose import jwk, jwt
from jose.utils import base64url_decode

# ------------------------------------------------------------------------------------
# Environment Variables (based on template.yaml)
# ------------------------------------------------------------------------------------
REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["USER_POOL_ID"]
USER_POOL_CLIENT_ID = os.environ["USER_POOL_CLIENT_ID"]

# Added for token-lifetime tracking
TOKENS_TABLE = os.environ["TOKENS_TABLE"]

ddb = boto3.resource("dynamodb")
tokens_table = ddb.Table(TOKENS_TABLE)

cognito = boto3.client("cognito-idp")

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

http = urllib3.PoolManager()


# ------------------------------------------------------------------------------------
# Authorization Constants
# ------------------------------------------------------------------------------------

API_TOKEN_TIME_TO_LIVE = 60 * 60 * 10  # Default: 10 Hours
API_TOKEN_CALL_LIMIT = 1000  # Default: 1000 API Calls


# ------------------------------------------------------------------------------------
# Load JWKS at cold start
# ------------------------------------------------------------------------------------
JWKS_URL = (
    f"https://cognito-idp.{REGION}.amazonaws.com/"
    f"{USER_POOL_ID}/.well-known/jwks.json"
)

jwks = http.request("GET", JWKS_URL).json()["keys"]


# ------------------------------------------------------------------------------------
# Authenticate Username + Password (for /authenticate endpoint)
# ------------------------------------------------------------------------------------
def authenticate_user(username: str, password: str) -> dict:
    """
    Calls Cognito's USER_PASSWORD_AUTH auth-flow.
    Returns dict of tokens for the client.
    Also registers token in DynamoDB for TTL and usage-limit tracking.
    """
    try:
        resp = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=USER_POOL_CLIENT_ID,
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        auth = resp.get("AuthenticationResult", {})
        access_token = auth.get("AccessToken")

        # Store token tracking record
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
        log.error(f"Cognito authentication failed: {str(e)}")
        raise


# ------------------------------------------------------------------------------------
# Verify Token Signature + Claims + TTL + Use Count
# ------------------------------------------------------------------------------------
def verify_token(token: str) -> dict:
    """
    Validates Cognito JWT:
     - signature via JWKS
     - expiration via JWT exp claim
     - 10-hour ModelGuard rule
     - <= 1000 API calls rule
    Returns decoded claims dict.
    """
    # Choose correct key from kid
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    key = next((k for k in jwks if k["kid"] == kid), None)
    if not key:
        raise Exception("Invalid token: unknown kid")

    # Verify signature
    public_key = jwk.construct(key)

    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode())

    if not public_key.verify(message.encode(), decoded_sig):
        raise Exception("Invalid token signature")

    # Decode claims—unverified because signature is manually checked above
    claims = jwt.get_unverified_claims(token)

    # Standard Cognito expiry
    now = time.time()
    if now > claims["exp"]:
        raise Exception("Token expired (JWT exp claim)")

    # ModelGuard-specific TTL and call-limit rules
    record = tokens_table.get_item(Key={"token": token}).get("Item")
    if not record:
        raise Exception("Token not registered or invalid")

    # Limit 1: 10 hours since original issuance
    if now - record["issued_at"] > API_TOKEN_TIME_TO_LIVE:
        raise Exception("Token expired (time-to-live exceeded)")

    # Limit 2: 1000 API calls
    if record["uses"] >= API_TOKEN_CALL_LIMIT:
        raise Exception("Token expired (call limit exceeded)")

    # Increment token usage count
    tokens_table.update_item(
        Key={"token": token},
        UpdateExpression="SET uses = uses + :inc",
        ExpressionAttributeValues={":inc": 1},
    )

    return claims


# ------------------------------------------------------------------------------------
# Role-Based Access Enforcement Using Cognito Groups
# ------------------------------------------------------------------------------------
def require_roles(claims: dict, allowed_groups: list) -> None:
    """
    Ensures the Cognito-token's user is in an allowed group.
    Groups come from the "cognito:groups" claim.
    """
    groups = claims.get("cognito:groups", [])

    if not groups:
        raise Exception("User has no assigned roles/groups")

    for g in allowed_groups:
        if g in groups:
            return

    raise Exception(
        f"Permission denied. Required: {allowed_groups}, User groups: {groups}"
    )


# ------------------------------------------------------------------------------------
# Extract Username
# ------------------------------------------------------------------------------------
def get_username(claims: dict) -> str | None:
    return claims.get("username") or claims.get("cognito:username")
