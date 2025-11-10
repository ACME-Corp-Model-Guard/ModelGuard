"""
Lambda function for PUT /authenticate endpoint
Authenticate user and return token
"""

import json
import os
import hashlib
import time
import base64
import hmac
from typing import Any, Dict, Optional

try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.logger import logger

# Environment variables
USERS_TABLE = os.environ.get("USERS_TABLE", "ModelGuard-Users")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
JWT_SECRET_PARAM = os.environ.get("JWT_SECRET_PARAM", "/modelguard/jwt-secret")

# Initialize AWS clients
dynamodb_resource = None


def _get_users_table() -> Any:
    """Get Users DynamoDB table resource."""
    global dynamodb_resource
    if boto3 is None:
        return None  # type: ignore[return-value]
    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)  # type: ignore
    try:
        return dynamodb_resource.Table(USERS_TABLE)  # type: ignore
    except Exception:
        return None


def _create_response(
    status_code: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Create a standardized API Gateway response."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }
    if headers:
        default_headers.update(headers)
    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body),
    }


def _error_response(
    status_code: int, message: str, error_code: Optional[str] = None
) -> Dict[str, Any]:
    """Create an error response."""
    body = {"error": message}
    if error_code:
        body["error_code"] = error_code
    return _create_response(status_code, body)


def _hash_password(password: str) -> str:
    """Hash password using SHA-256 (for MVP - use bcrypt in production)."""
    return hashlib.sha256(password.encode()).hexdigest()


def _get_jwt_secret() -> str:
    """Get JWT secret from SSM Parameter Store or environment."""
    # Try to get from SSM Parameter Store
    try:
        if boto3:
            ssm = boto3.client("ssm", region_name=AWS_REGION)  # type: ignore
            response = ssm.get_parameter(Name=JWT_SECRET_PARAM, WithDecryption=True)
            return response["Parameter"]["Value"]
    except Exception:
        pass

    # Fallback to environment variable or default
    return os.environ.get("JWT_SECRET", "modelguard-secret-key-change-in-production")


def _generate_jwt_token(
    username: str, is_admin: bool, permissions: Dict[str, bool]
) -> str:
    """
    Generate a simple JWT token (for MVP).

    In production, use a proper JWT library like PyJWT.
    """
    jwt_secret = _get_jwt_secret()

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "username": username,
        "is_admin": is_admin,
        "permissions": permissions,
        "iat": int(time.time()),
        "exp": int(time.time()) + (24 * 60 * 60),  # 24 hours
    }

    # Encode header and payload
    header_b64 = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    )
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )

    # Create signature
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(jwt_secret.encode(), message.encode(), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    # Return JWT token
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user and return user data if valid."""
    users_table = _get_users_table()
    if users_table is None:
        logger.error("Users table not available")
        return None

    try:
        response = users_table.get_item(Key={"username": username})
        if "Item" not in response:
            logger.warning(f"User not found: {username}")
            return None

        user = response["Item"]
        stored_password_hash = user.get("password_hash", "")

        # Verify password
        password_hash = _hash_password(password)
        if password_hash != stored_password_hash:
            logger.warning(f"Invalid password for user: {username}")
            return None

        # Return user data
        return {
            "username": user.get("username", username),
            "is_admin": user.get("is_admin", False),
            "permissions": user.get(
                "permissions", {"upload": False, "search": False, "download": False}
            ),
        }
    except Exception as e:
        logger.error(f"Failed to authenticate user: {e}", exc_info=True)
        return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for PUT /authenticate.

    Authenticates user and returns a JWT token.
    Expected request body: {"user":{"name":<>, "is_admin":<>}, "secret":{"password":<>}}
    """
    logger.info("Processing PUT /authenticate")

    try:
        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)
        elif not isinstance(body, dict):
            return _error_response(400, "Invalid request body", "INVALID_BODY")

        # Extract user and secret
        user_data = body.get("user", {})
        secret_data = body.get("secret", {})

        username = user_data.get("name", "")
        is_admin = user_data.get("is_admin", False)
        password = secret_data.get("password", "")

        if not username or not password:
            logger.warning("Missing username or password")
            return _error_response(
                400, "Username and password are required", "MISSING_CREDENTIALS"
            )

        # Authenticate user
        user = _authenticate_user(username, password)
        if user is None:
            logger.warning(f"Authentication failed for user: {username}")
            return _error_response(401, "Invalid credentials", "AUTHENTICATION_FAILED")

        # Verify is_admin matches (if provided)
        if is_admin != user["is_admin"]:
            logger.warning(f"is_admin mismatch for user: {username}")
            return _error_response(401, "Invalid credentials", "AUTHENTICATION_FAILED")

        # Generate JWT token
        token = _generate_jwt_token(
            user["username"], user["is_admin"], user["permissions"]
        )

        logger.info(f"Successfully authenticated user: {username}")
        return _create_response(
            200,
            {
                "token": token,
                "username": user["username"],
                "is_admin": user["is_admin"],
                "permissions": user["permissions"],
            },
        )
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return _error_response(400, "Invalid JSON in request body", "INVALID_JSON")
    except Exception as e:
        logger.error(f"Failed to authenticate: {e}", exc_info=True)
        return _error_response(
            500, f"Authentication failed: {str(e)}", "INTERNAL_ERROR"
        )
