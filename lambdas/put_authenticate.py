"""
Lambda function for PUT /authenticate endpoint
Verify Cognito authentication token from request header
"""

import json
from typing import Any, Dict, Optional

from src.logger import logger


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


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for PUT /authenticate.

    Verifies Cognito authentication token from request header.
    With API Gateway Cognito authorizer, the token is already verified.
    This endpoint extracts and returns user information from the authenticated request.
    """
    logger.info("Processing PUT /authenticate")

    try:
        # Extract authentication token from request header
        headers = event.get("headers", {}) or {}
        # Check multiple possible header names
        auth_token = (
            headers.get("Authorization")
            or headers.get("authorization")
            or headers.get("X-Authorization")
            or headers.get("x-authorization")
        )

        # Remove "Bearer " prefix if present
        if auth_token and auth_token.startswith("Bearer "):
            auth_token = auth_token[7:]
        elif auth_token and auth_token.startswith("bearer "):
            auth_token = auth_token[7:]

        if not auth_token:
            logger.warning("No authentication token in request header")
            return _error_response(
                401, "Authentication token required in header", "MISSING_TOKEN"
            )

        # Verify token (with API Gateway Cognito authorizer, token is already verified)
        # Extract user info from request context if available
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        # Get user information from Cognito claims
        username = authorizer.get("claims", {}).get(
            "cognito:username"
        ) or authorizer.get("claims", {}).get("sub", "")
        groups = authorizer.get("claims", {}).get("cognito:groups", [])
        is_admin = "Admin" in groups if isinstance(groups, list) else False

        if not username:
            # If no user info in context, token was still verified by API Gateway
            logger.info("Token verified but no user info in context")
            return _create_response(
                200,
                {
                    "authenticated": True,
                    "message": "Token verified successfully",
                },
            )

        logger.info(f"Successfully verified token for user: {username}")
        return _create_response(
            200,
            {
                "authenticated": True,
                "username": username,
                "is_admin": is_admin,
                "groups": groups if isinstance(groups, list) else [],
            },
        )
    except Exception as e:
        logger.error(f"Failed to verify authentication: {e}", exc_info=True)
        return _error_response(
            500, f"Authentication verification failed: {str(e)}", "INTERNAL_ERROR"
        )
