"""
DELETE /users/{username}
Delete a user account. Self-deletion or admin deletion.

Security Track: User-based access control
- Users can delete their own accounts
- Administrators can delete any account
"""

from __future__ import annotations

from typing import Any, Dict

from botocore.exceptions import ClientError

from src.auth import AuthContext, auth_required
from src.logutil import clogger, log_lambda_handler
from src.users.user_service import delete_user, user_exists
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


@translate_exceptions
@log_lambda_handler("DELETE /users/{username}")
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    """
    Delete a user account.

    Authorization:
        - Self-deletion: Any authenticated user can delete their own account
        - Admin deletion: Admins can delete any account

    Path parameters:
        username: The username to delete

    Responses:
        200 OK - User deleted successfully
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

    # Authorization check: self-deletion or admin
    caller_username = auth["username"]
    is_admin = "Admin" in auth.get("groups", [])

    if target_username != caller_username and not is_admin:
        clogger.warning(
            f"[delete_users] Permission denied: {caller_username} tried to delete {target_username}"
        )
        return error_response(
            403,
            "Permission denied: can only delete own account or must be admin",
            error_code="PERMISSION_DENIED",
        )

    # Check if user exists
    if not user_exists(target_username):
        return error_response(
            404,
            f"User '{target_username}' not found",
            error_code="USER_NOT_FOUND",
        )

    # Delete the user
    try:
        delete_user(target_username)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "UserNotFoundException":
            return error_response(
                404,
                f"User '{target_username}' not found",
                error_code="USER_NOT_FOUND",
            )

        clogger.exception(f"[delete_users] Failed to delete user: {e}")
        return error_response(
            500,
            f"Failed to delete user: {error_message}",
            error_code="USER_DELETION_FAILED",
        )

    clogger.info(
        f"[delete_users] User '{target_username}' deleted by '{caller_username}'",
        extra={
            "deleted_user": target_username,
            "deleted_by": caller_username,
            "was_self_deletion": target_username == caller_username,
        },
    )

    return json_response(
        200,
        {"message": f"User '{target_username}' deleted successfully"},
    )
