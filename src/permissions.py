"""
User permissions management for ModelGuard.

This module handles:
- Loading/saving user permissions from/to DynamoDB
- Permission checking decorators
- Permission enforcement utilities

Permissions are stored in the UserPermissionsTable with the following schema:
- username (PK): Cognito username
- can_upload: Boolean - permission to upload artifacts
- can_search: Boolean - permission to search/enumerate artifacts
- can_download: Boolean - permission to download artifacts
- created_at: ISO-8601 timestamp
- created_by: Admin username who created this user
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypedDict

from src.aws.clients import get_ddb_table
from src.logutil import clogger
from src.settings import USER_PERMISSIONS_TABLE
from src.utils.http import LambdaResponse, error_response


# =============================================================================
# Type Definitions
# =============================================================================


class UserPermissions(TypedDict):
    """Type definition for user permission records in DynamoDB."""

    username: str
    can_upload: bool
    can_search: bool
    can_download: bool
    created_at: str
    created_by: str
    updated_at: Optional[str]


# =============================================================================
# Permission Storage Operations
# =============================================================================


def load_user_permissions(username: str) -> Optional[UserPermissions]:
    """
    Load permissions for a user from DynamoDB.

    Args:
        username: The Cognito username to load permissions for.

    Returns:
        UserPermissions dict if found, None otherwise.
    """
    table = get_ddb_table(USER_PERMISSIONS_TABLE)
    response = table.get_item(Key={"username": username})
    item = response.get("Item")

    if item:
        clogger.debug(f"[permissions] Loaded permissions for user {username}")
        return item  # type: ignore[return-value]

    clogger.debug(f"[permissions] No permissions found for user {username}")
    return None


def save_user_permissions(permissions: UserPermissions) -> None:
    """
    Save user permissions to DynamoDB.

    Args:
        permissions: The UserPermissions dict to save.
    """
    table = get_ddb_table(USER_PERMISSIONS_TABLE)
    table.put_item(Item=permissions)
    clogger.info(f"[permissions] Saved permissions for user {permissions['username']}")


def delete_user_permissions(username: str) -> bool:
    """
    Delete user permissions from DynamoDB.

    Args:
        username: The username whose permissions should be deleted.

    Returns:
        True if deletion was attempted (DynamoDB delete is idempotent).
    """
    table = get_ddb_table(USER_PERMISSIONS_TABLE)
    table.delete_item(Key={"username": username})
    clogger.info(f"[permissions] Deleted permissions for user {username}")
    return True


# =============================================================================
# Permission Checking
# =============================================================================


def check_permission(
    auth_context: Dict[str, Any],
    required_permission: str,
) -> bool:
    """
    Check if user has the required permission.

    Admins (users in the Admin Cognito group) bypass all permission checks.

    Args:
        auth_context: The AuthContext dict from authentication.
        required_permission: The permission to check (e.g., "can_upload").

    Returns:
        True if the user has the permission, False otherwise.
    """
    # Admin bypass - Admins have all permissions
    if "Admin" in auth_context.get("groups", []):
        clogger.debug(
            f"[permissions] Admin bypass for {auth_context.get('username')} "
            f"on {required_permission}"
        )
        return True

    username = auth_context.get("username")
    if not username:
        clogger.warning("[permissions] No username in auth context")
        return False

    permissions = load_user_permissions(username)
    if not permissions:
        clogger.warning(f"[permissions] No permissions record for user {username}")
        return False

    has_permission = bool(permissions.get(required_permission, False))  # type: ignore[arg-type]
    if not has_permission:
        clogger.info(f"[permissions] User {username} denied: lacks {required_permission}")
    return has_permission


def get_user_permission_flags(username: str) -> Dict[str, bool]:
    """
    Get all permission flags for a user.

    Args:
        username: The username to get permissions for.

    Returns:
        Dict with can_upload, can_search, can_download flags.
        Returns all False if user has no permissions record.
    """
    permissions = load_user_permissions(username)
    if not permissions:
        return {
            "can_upload": False,
            "can_search": False,
            "can_download": False,
        }
    return {
        "can_upload": permissions.get("can_upload", False),
        "can_search": permissions.get("can_search", False),
        "can_download": permissions.get("can_download", False),
    }


# =============================================================================
# Permission Decorator
# =============================================================================


def permissions_required(
    required_permissions: List[str],
) -> Callable[
    [Callable[..., LambdaResponse]],
    Callable[[Dict[str, Any], Any, Dict[str, Any]], LambdaResponse],
]:
    """
    Decorator that enforces specific permissions.

    Must be used AFTER @auth_required or @roles_required decorators.
    Admins bypass all permission checks.

    Args:
        required_permissions: List of permission names to require.
            Valid values: "can_upload", "can_search", "can_download"

    Usage:
        @auth_required
        @permissions_required(["can_upload"])
        def lambda_handler(event, context, auth):
            ...

    Returns:
        Decorator function.
    """

    def decorator(
        func: Callable[..., LambdaResponse],
    ) -> Callable[[Dict[str, Any], Any, Dict[str, Any]], LambdaResponse]:
        @wraps(func)
        def wrapper(
            event: Dict[str, Any],
            context: Any,
            auth: Dict[str, Any],
        ) -> LambdaResponse:
            # Admin bypass - Admins have all permissions
            if "Admin" in auth.get("groups", []):
                clogger.debug(f"[permissions_required] Admin bypass for {auth.get('username')}")
                return func(event, context, auth=auth)

            # Check each required permission
            for perm in required_permissions:
                if not check_permission(auth, perm):
                    clogger.warning(
                        f"[permissions_required] Permission denied: "
                        f"{auth.get('username')} lacks {perm}"
                    )
                    return error_response(
                        403,
                        f"Permission denied: requires {perm}",
                        error_code="PERMISSION_DENIED",
                    )

            return func(event, context, auth=auth)

        return wrapper

    return decorator
