"""
GET /users/{username}
Get user info and permissions. Self or admin access.

Security Track: User-based access control
- Users can view their own info
- Administrators can view any user's info
"""

from __future__ import annotations

from typing import Any, Dict

from src.auth import AuthContext, auth_required
from src.logutil import clogger, log_lambda_handler
from src.users.user_service import get_user_info
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


@translate_exceptions
@log_lambda_handler("GET /users/{username}")
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    """
    Get user info and permissions.

    Authorization:
        - Self: Any authenticated user can view their own info
        - Admin: Admins can view any user's info

    Path parameters:
        username: The username to look up

    Responses:
        200 OK - User info returned successfully
        400 Bad Request - Invalid username
        403 Forbidden - Not authenticated or insufficient permissions
        404 Not Found - User does not exist
    """
    # Extract username from path parameters
    path_params = event.get("pathParameters") or {}
    target_username = path_params.get("username")

    if not target_username:
        return error_response(
            400,
            "Missing username path parameter",
            error_code="MISSING_PARAM",
        )

    # Authorization check: self or admin
    caller_username = auth["username"]
    is_admin = "Admin" in auth.get("groups", [])

    if target_username != caller_username and not is_admin:
        clogger.warning(
            f"[get_users] Permission denied: {caller_username} tried to view {target_username}"
        )
        return error_response(
            403,
            "Permission denied: can only view own info or must be admin",
            error_code="PERMISSION_DENIED",
        )

    # Get user info
    user_info = get_user_info(target_username)

    if not user_info:
        return error_response(
            404,
            f"User '{target_username}' not found",
            error_code="USER_NOT_FOUND",
        )

    clogger.debug(f"[get_users] User info retrieved for '{target_username}' by '{caller_username}'")

    return json_response(200, user_info)
