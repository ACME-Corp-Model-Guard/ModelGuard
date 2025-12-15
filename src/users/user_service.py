"""
User management service for ModelGuard.

Handles user creation, deletion, and permission management
through Cognito and DynamoDB.

This module provides the core business logic for user management,
implementing the Security Track requirements:
- Admin-only user registration
- User deletion (self or admin)
- Permission management (upload, search, download)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from src.aws.clients import get_cognito, get_ddb_table
from src.logutil import clogger
from src.permissions import (
    UserPermissions,
    delete_user_permissions,
    load_user_permissions,
    save_user_permissions,
)
from src.settings import TOKENS_TABLE, USER_POOL_ID


# =============================================================================
# User Creation
# =============================================================================


def create_user(
    username: str,
    password: str,
    is_admin: bool,
    permissions: Dict[str, bool],
    created_by: str,
) -> Dict[str, Any]:
    """
    Create a new user in Cognito and set their permissions.

    Args:
        username: The username for the new user.
        password: The initial password (must meet Cognito policy).
        is_admin: Whether to add user to Admin group.
        permissions: Dict with can_upload, can_search, can_download flags.
        created_by: Username of the admin creating this user.

    Returns:
        Dict containing user info and permissions.

    Raises:
        ClientError: If Cognito operations fail.
    """
    cognito = get_cognito()

    clogger.info(f"[user_service] Creating user: {username} (admin={is_admin})")

    # Create user in Cognito with temporary password
    cognito.admin_create_user(
        UserPoolId=USER_POOL_ID,
        Username=username,
        TemporaryPassword=password,
        UserAttributes=[
            {"Name": "email_verified", "Value": "true"},
            {"Name": "email", "Value": f"{username}@modelguard.local"},
        ],
        MessageAction="SUPPRESS",  # Do not send email invite
    )

    # Set permanent password to avoid FORCE_CHANGE_PASSWORD state
    cognito.admin_set_user_password(
        UserPoolId=USER_POOL_ID,
        Username=username,
        Password=password,
        Permanent=True,
    )

    # Confirm the user
    try:
        cognito.admin_confirm_sign_up(UserPoolId=USER_POOL_ID, Username=username)
    except ClientError as e:
        # Ignore if already confirmed
        if "NotAuthorizedException" not in str(e):
            raise

    # Add to appropriate group
    group_name = "Admin" if is_admin else "User"
    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=username,
        GroupName=group_name,
    )
    clogger.info(f"[user_service] Added user {username} to group {group_name}")

    # Save permissions to DynamoDB
    now = datetime.now(timezone.utc).isoformat()
    user_permissions: UserPermissions = {
        "username": username,
        "can_upload": permissions.get("can_upload", False),
        "can_search": permissions.get("can_search", False),
        "can_download": permissions.get("can_download", False),
        "created_at": now,
        "created_by": created_by,
        "updated_at": None,
    }
    save_user_permissions(user_permissions)

    clogger.info(f"[user_service] User {username} created successfully")

    return {
        "user": {"name": username, "is_admin": is_admin},
        "permissions": {
            "can_upload": user_permissions["can_upload"],
            "can_search": user_permissions["can_search"],
            "can_download": user_permissions["can_download"],
        },
    }


# =============================================================================
# User Deletion
# =============================================================================


def delete_user(username: str) -> None:
    """
    Delete a user from Cognito, their permissions, and invalidate tokens.

    Args:
        username: The username to delete.

    Raises:
        ClientError: If Cognito operations fail.
    """
    cognito = get_cognito()

    clogger.info(f"[user_service] Deleting user: {username}")

    # Delete from Cognito
    cognito.admin_delete_user(
        UserPoolId=USER_POOL_ID,
        Username=username,
    )
    clogger.info(f"[user_service] Deleted user {username} from Cognito")

    # Delete permissions from DynamoDB
    delete_user_permissions(username)

    # Invalidate all tokens for this user
    invalidated_count = _invalidate_user_tokens(username)
    clogger.info(
        f"[user_service] User {username} deleted, " f"{invalidated_count} tokens invalidated"
    )


def _invalidate_user_tokens(username: str) -> int:
    """
    Delete all tokens for a user from the tokens table.

    This is called when a user is deleted to ensure their tokens
    can no longer be used.

    Args:
        username: The username whose tokens should be invalidated.

    Returns:
        Number of tokens deleted.
    """
    table = get_ddb_table(TOKENS_TABLE)

    # Scan for tokens belonging to this user
    # Note: This requires a full scan, but the tokens table should be small
    # and tokens have TTL so old ones are automatically removed
    response = table.scan(
        FilterExpression="username = :u",
        ExpressionAttributeValues={":u": username},
    )

    count = 0
    for item in response.get("Items", []):
        table.delete_item(Key={"token": item["token"]})
        count += 1

    # Handle pagination for large token sets
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="username = :u",
            ExpressionAttributeValues={":u": username},
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        for item in response.get("Items", []):
            table.delete_item(Key={"token": item["token"]})
            count += 1

    clogger.debug(f"[user_service] Invalidated {count} tokens for user {username}")
    return count


# =============================================================================
# User Queries
# =============================================================================


def user_exists(username: str) -> bool:
    """
    Check if a user exists in Cognito.

    Args:
        username: The username to check.

    Returns:
        True if user exists, False otherwise.
    """
    cognito = get_cognito()
    try:
        cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "UserNotFoundException":
            return False
        raise


def get_user_info(username: str) -> Optional[Dict[str, Any]]:
    """
    Get user info including permissions.

    Args:
        username: The username to look up.

    Returns:
        Dict with user info and permissions, or None if user doesn't exist.
    """
    cognito = get_cognito()

    try:
        cognito.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=username,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "UserNotFoundException":
            return None
        raise

    # Get groups to determine admin status
    groups_response = cognito.admin_list_groups_for_user(
        UserPoolId=USER_POOL_ID,
        Username=username,
    )
    groups = [g["GroupName"] for g in groups_response.get("Groups", [])]
    is_admin = "Admin" in groups

    # Get permissions from DynamoDB
    permissions = load_user_permissions(username)

    return {
        "user": {"name": username, "is_admin": is_admin},
        "permissions": {
            "can_upload": permissions.get("can_upload", False) if permissions else False,
            "can_search": permissions.get("can_search", False) if permissions else False,
            "can_download": (permissions.get("can_download", False) if permissions else False),
        },
    }
