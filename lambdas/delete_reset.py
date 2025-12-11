"""
DELETE /reset
Reset the system to default state:
- Clear all items from the DynamoDB artifacts table
- Clear all items from the DynamoDB tokens table
- Clear all objects from the S3 artifacts bucket
- Delete all Cognito users
- Delete all Cognito user groups
- Reinitialize required bootstrap state (default admin user, etc.)
"""

from __future__ import annotations

from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from src.auth import AuthContext, auth_required
from src.logger import clogger, log_lambda_handler
from src.settings import ARTIFACTS_BUCKET, ARTIFACTS_TABLE, USER_POOL_ID
from src.storage.dynamo_utils import clear_table
from src.storage.s3_utils import clear_bucket
from src.utils.bootstrap import bootstrap_system
from src.utils.http import LambdaResponse, json_response, translate_exceptions


# =============================================================================
# Helper Functions
# =============================================================================


def _clear_cognito_users() -> None:
    """
    Delete all users from the Cognito User Pool.
    """
    cognito = boto3.client("cognito-idp")
    clogger.info(f"Clearing all users from Cognito User Pool: {USER_POOL_ID}")

    try:
        paginator = cognito.get_paginator("list_users")
        for page in paginator.paginate(UserPoolId=USER_POOL_ID):
            for user in page.get("Users", []):
                username = user["Username"]
                try:
                    cognito.admin_delete_user(
                        UserPoolId=USER_POOL_ID, Username=username
                    )
                    clogger.debug(f"Deleted Cognito user: {username}")
                except ClientError as e:
                    clogger.warning(f"Failed to delete user {username}: {e}")
    except ClientError as e:
        clogger.error(f"Error listing users: {e}", exc_info=True)
        raise


def _clear_cognito_groups() -> None:
    """
    Delete all groups from the Cognito User Pool.
    """
    cognito = boto3.client("cognito-idp")
    clogger.info(f"Clearing all groups from Cognito User Pool: {USER_POOL_ID}")

    try:
        paginator = cognito.get_paginator("list_groups")
        for page in paginator.paginate(UserPoolId=USER_POOL_ID):
            for group in page.get("Groups", []):
                group_name = group["GroupName"]
                try:
                    cognito.delete_group(UserPoolId=USER_POOL_ID, GroupName=group_name)
                    clogger.debug(f"Deleted Cognito group: {group_name}")
                except ClientError as e:
                    clogger.warning(f"Failed to delete group {group_name}: {e}")
    except ClientError as e:
        clogger.error(f"Error listing groups: {e}", exc_info=True)
        raise


# =============================================================================
# Lambda Handler: DELETE /reset
# =============================================================================
#
# Responsibilities:
#   1. Authenticate caller
#   2. Clear DynamoDB artifacts table
#   3. Clear DynamoDB tokens table
#   4. Clear S3 bucket of all stored artifacts
#   5. Delete all Cognito users
#   6. Delete all Cognito groups
#   7. Reinitialize system bootstrap state
#   8. Return status response
#
# Error codes:
#   401 - authentication failure (handled by @auth_required)
#   500 - catch-all for unexpected errors (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@log_lambda_handler("DELETE /reset")
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    # ---------------------------------------------------------------------
    # Step 1 — Clear DynamoDB artifacts table
    # ---------------------------------------------------------------------
    clogger.info(f"Clearing DynamoDB table: {ARTIFACTS_TABLE}")
    clear_table(ARTIFACTS_TABLE, key_name="artifact_id")

    # ---------------------------------------------------------------------
    # Step 2 — Clear S3 artifacts bucket
    # ---------------------------------------------------------------------
    clogger.info(f"Clearing S3 bucket: {ARTIFACTS_BUCKET}")
    clear_bucket(ARTIFACTS_BUCKET)

    # ---------------------------------------------------------------------
    # Step 3 — Delete all Cognito users
    # ---------------------------------------------------------------------
    # _clear_cognito_users()

    # ---------------------------------------------------------------------
    # Step 4 — Delete all Cognito groups
    # ---------------------------------------------------------------------
    # _clear_cognito_groups()

    # ---------------------------------------------------------------------
    # Step 5 — Run system bootstrap initialization
    # ---------------------------------------------------------------------
    clogger.info("Running system bootstrap...")
    bootstrap_system()

    # ---------------------------------------------------------------------
    # Step 6 — Success response
    # ---------------------------------------------------------------------
    return json_response(
        status_code=200,
        body={
            "message": "System reset and bootstrapped successfully",
            "status": "ok",
        },
    )
