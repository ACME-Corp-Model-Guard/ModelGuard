"""
POST /users
Register a new user with specified permissions. Admin only.

Security Track: User-based access control
- Only administrators can register new users
- Admin specifies permissions (upload, search, download) at registration
"""

from __future__ import annotations

import json
from typing import Any, Dict

from botocore.exceptions import ClientError

from src.auth import AuthContext, roles_required
from src.logutil import clogger, log_lambda_handler
from src.users.user_service import create_user, user_exists
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


@translate_exceptions
@log_lambda_handler("POST /users", log_request_body=True)
@roles_required(["Admin"])
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    """
    Register a new user with specified permissions.

    Request body:
    {
        "user": { "name": "username", "is_admin": false },
        "secret": { "password": "SecurePassword123!" },
        "permissions": { "can_upload": true, "can_search": true, "can_download": false }
    }

    Responses:
        201 Created - User created successfully
        400 Bad Request - Invalid request body or weak password
        403 Forbidden - Not authenticated or not admin
        409 Conflict - User already exists
    """
    # Parse request body
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error_response(400, "Invalid JSON", error_code="INVALID_JSON")

    # Extract and validate required fields
    user_data = body.get("user", {})
    secret_data = body.get("secret", {})
    permissions_data = body.get("permissions", {})

    username = user_data.get("name")
    password = secret_data.get("password")
    is_admin = user_data.get("is_admin", False)

    if not username:
        return error_response(
            400,
            "Missing required field: user.name",
            error_code="MISSING_FIELD",
        )

    if not password:
        return error_response(
            400,
            "Missing required field: secret.password",
            error_code="MISSING_FIELD",
        )

    # Validate username format (basic check)
    if len(username) < 3:
        return error_response(
            400,
            "Username must be at least 3 characters",
            error_code="INVALID_USERNAME",
        )

    # Check if user already exists
    if user_exists(username):
        return error_response(
            409,
            f"User '{username}' already exists",
            error_code="USER_EXISTS",
        )

    # Create the user
    try:
        result = create_user(
            username=username,
            password=password,
            is_admin=is_admin,
            permissions=permissions_data,
            created_by=auth["username"] or "unknown",
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "InvalidPasswordException":
            return error_response(
                400,
                f"Password does not meet requirements: {error_message}",
                error_code="WEAK_PASSWORD",
            )

        if error_code == "UsernameExistsException":
            return error_response(
                409,
                f"User '{username}' already exists",
                error_code="USER_EXISTS",
            )

        clogger.exception(f"[post_users] Failed to create user: {e}")
        return error_response(
            500,
            f"Failed to create user: {error_message}",
            error_code="USER_CREATION_FAILED",
        )

    clogger.info(
        f"[post_users] User '{username}' created by '{auth['username']}'",
        extra={"new_user": username, "created_by": auth["username"], "is_admin": is_admin},
    )

    return json_response(201, result)
