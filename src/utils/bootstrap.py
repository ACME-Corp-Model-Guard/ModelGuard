"""
System bootstrap utilities.

This module is invoked after /reset to recreate initial state
required by the specification — starting with the default Admin user.

Current responsibilities:
- Create the default Admin user in Cognito if missing
- Ensure the user is added to the Admin group
- Mark user as confirmed

Future responsibilities:
- Seed default artifacts
- Populate sample datasets
- Additional environment-specific initialization
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient

from src.logger import logger
from src.settings import (
    DEFAULT_ADMIN_GROUP,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    USER_POOL_ID,
)


# =====================================================================================
# Helpers
# =====================================================================================


def _ensure_cognito_group_exists(
    cognito: CognitoIdentityProviderClient, group_name: str
) -> None:
    """
    Ensure a Cognito group exists. Creates it if missing.
    """
    try:
        cognito.get_group(GroupName=group_name, UserPoolId=USER_POOL_ID)
        logger.debug(f"[bootstrap] Cognito group already exists: {group_name}")
    except ClientError:
        logger.info(f"[bootstrap] Creating Cognito group: {group_name}")
        cognito.create_group(
            GroupName=group_name,
            UserPoolId=USER_POOL_ID,
            Description=f"Autocreated group: {group_name}",
        )


def _ensure_user_exists(
    cognito: CognitoIdentityProviderClient,
    username: str,
    password: str,
    admin_group: str,
) -> None:
    """
    Create the default admin user if missing, confirm the user, and ensure
    they are in the proper group.
    """
    try:
        cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
        logger.info(f"[bootstrap] User already exists: {username}")

    except ClientError:
        logger.info(f"[bootstrap] Creating default admin user: {username}")

        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=username,
            TemporaryPassword=password,
            UserAttributes=[
                {"Name": "email_verified", "Value": "true"},
                {"Name": "email", "Value": f"{username}@example.com"},
            ],
            MessageAction="SUPPRESS",  # do not send email invite
        )

        # Set password as permanent to avoid FORCE_CHANGE_PASSWORD state
        cognito.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=username,
            Password=password,
            Permanent=True,
        )
        logger.info(f"[bootstrap] Set permanent password for user: {username}")

    # Confirm the user
    try:
        cognito.admin_confirm_sign_up(UserPoolId=USER_POOL_ID, Username=username)
        logger.debug(f"[bootstrap] User confirmed: {username}")
    except ClientError as e:
        # If already confirmed, ignore
        if "NotAuthorizedException" in str(e):
            pass
        else:
            raise

    # Add to admin group
    try:
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=username,
            GroupName=admin_group,
        )
        logger.info(f"[bootstrap] Added user {username} → group {admin_group}")
    except ClientError as e:
        if "UserAlreadyInGroupException" in str(e):
            logger.debug(
                f"[bootstrap] User {username} already in {admin_group}, ignoring"
            )
        else:
            raise


# =====================================================================================
# Public Bootstrap Entry Point
# =====================================================================================


def bootstrap_system() -> None:
    """
    Initialize the system with required default state.

    Current actions:
        1. Ensure default admin group exists
        2. Create & confirm default admin user
        3. Associate admin user with Admin group

    Future:
        - Seed default artifacts
        - Initialize other required metadata
    """
    logger.info("[bootstrap] Running system bootstrap initialization...")

    cognito = boto3.client("cognito-idp")

    # Ensure group exists
    _ensure_cognito_group_exists(cognito, DEFAULT_ADMIN_GROUP)

    # Ensure default admin user exists + confirmed
    _ensure_user_exists(
        cognito,
        username=DEFAULT_ADMIN_USERNAME,
        password=DEFAULT_ADMIN_PASSWORD,
        admin_group=DEFAULT_ADMIN_GROUP,
    )

    logger.info("[bootstrap] System bootstrap completed")
