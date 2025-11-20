"""
Lambda function for DELETE /reset endpoint
Resets the system state to initial baseline and recreates default admin user.
"""

import json
import os
from typing import Any, Dict, Optional, TypedDict

try:
    import boto3  # type: ignore[import-untyped]
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.auth import authorize
from src.logger import logger

# ====================================================================================
# Environment Variables
# ====================================================================================
DYNAMODB_TABLE = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
TOKENS_TABLE = os.environ.get("TOKENS_TABLE", "ModelGuard-Tokens")
S3_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "modelguard-artifacts-files")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
USER_POOL_ID = os.environ["USER_POOL_ID"]  # MUST exist

# Default admin user required after reset
DEFAULT_USERNAME = "ece30861defaultadminuser"
DEFAULT_PASSWORD = "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
DEFAULT_GROUP = "Admin"

# Lazy init AWS clients
dynamodb_resource = None
s3_client = None
cognito_client = None


# ====================================================================================
# Response typing for mypy
# ====================================================================================
class LambdaResponse(TypedDict):
    statusCode: int
    headers: Dict[str, str]
    body: str


# ====================================================================================
# HTTP Helpers
# ====================================================================================
def _create_response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> LambdaResponse:
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, X-Authorization, Authorization",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }
    if headers:
        default_headers.update(headers)
    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body),
    }


def _error_response(status: int, message: str) -> LambdaResponse:
    return _create_response(status, {"error": message})


# ====================================================================================
# AWS Helpers
# ====================================================================================
def _get_dynamodb_resource() -> Any:
    """Lazy init DynamoDB resource."""
    global dynamodb_resource
    if boto3 is None:
        return None
    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
    return dynamodb_resource


def _get_s3_client() -> Any:
    """Lazy init S3."""
    global s3_client
    if boto3 is None:
        return None
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=AWS_REGION)
    return s3_client


def _get_cognito_client() -> Any:
    """Lazy init Cognito."""
    global cognito_client
    if boto3 is None:
        return None
    if cognito_client is None:
        cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)
    return cognito_client


# ====================================================================================
# Core Reset Logic
# ====================================================================================
def _reset_dynamodb() -> None:
    """Clear ARTIFACTS_TABLE."""
    dynamo = _get_dynamodb_resource()
    if dynamo is None:
        logger.warning("DynamoDB unavailable")
        return

    table = dynamo.Table(DYNAMODB_TABLE)
    response = table.scan()
    items = response.get("Items", [])

    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"artifact_id": item["artifact_id"]})

    logger.info(f"Deleted {len(items)} items from DynamoDB")


def _reset_tokens_table() -> None:
    """Clear TOKENS_TABLE (Security track requirement)."""
    dynamo = _get_dynamodb_resource()
    if dynamo is None:
        logger.warning("DynamoDB unavailable")
        return

    table = dynamo.Table(TOKENS_TABLE)
    response = table.scan()
    items = response.get("Items", [])

    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"token": item["token"]})

    logger.info(f"Deleted {len(items)} tokens from DynamoDB token table")


def _reset_s3() -> None:
    """Clear S3 artifact bucket."""
    s3 = _get_s3_client()
    if s3 is None:
        logger.warning("S3 unavailable")
        return

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_BUCKET)

    deleted = 0
    for page in pages:
        if "Contents" in page:
            objs = [{"Key": obj["Key"]} for obj in page["Contents"]]
            s3.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": objs})
            deleted += len(objs)

    logger.info(f"Deleted {deleted} objects from S3")


def _reset_default_admin_user() -> None:
    """Recreate required default admin Cognito user."""
    cognito = _get_cognito_client()
    if cognito is None:
        logger.warning("Cognito unavailable")
        return

    # Delete user if present
    try:
        cognito.admin_delete_user(UserPoolId=USER_POOL_ID, Username=DEFAULT_USERNAME)
    except ClientError:
        pass  # user didn't exist

    # Create user with temporary password
    cognito.admin_create_user(
        UserPoolId=USER_POOL_ID,
        Username=DEFAULT_USERNAME,
        TemporaryPassword=DEFAULT_PASSWORD,
        MessageAction="SUPPRESS",
    )

    # Set permanent password
    cognito.admin_set_user_password(
        UserPoolId=USER_POOL_ID,
        Username=DEFAULT_USERNAME,
        Password=DEFAULT_PASSWORD,
        Permanent=True,
    )

    # Add to Admin group
    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=DEFAULT_USERNAME,
        GroupName=DEFAULT_GROUP,
    )

    logger.info("Default admin user recreated successfully")


# ====================================================================================
# Lambda Handler
# ====================================================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> LambdaResponse:
    """
    DELETE /reset
    Spec:
      200 — reset completed
      401 — authenticated but forbidden (not admin)
      403 — authentication failure
    """
    logger.info("Processing DELETE /reset")

    # Step 1: Authenticate and enforce Admin role
    try:
        authorize(event, allowed_roles=["Admin"])
    except Exception as e:
        msg = str(e).lower()

        # 403 — Authentication failure (invalid, missing, expired token, etc.)
        auth_failures = [
            "missing x-authorization",
            "malformed token",
            "invalid token",
            "expired",
        ]
        if any(x in msg for x in auth_failures):
            return _error_response(
                403,
                "Authentication failed due to invalid or missing AuthenticationToken",
            )

        # 401 — Authenticated but not in Admin group
        if "permission denied" in msg:
            return _error_response(
                401, "You do not have permission to reset the registry."
            )

        # Default to 403
        return _error_response(403, "Authentication failed.")

    # Step 2: Perform reset
    try:
        logger.info("Resetting DynamoDB...")
        _reset_dynamodb()

        logger.info("Resetting token table...")
        _reset_tokens_table()

        logger.info("Resetting S3...")
        _reset_s3()

        logger.info("Recreating default admin user...")
        _reset_default_admin_user()

        logger.info("System reset successfully completed.")
        return _create_response(
            200, {"message": "System reset successfully", "status": "ok"}
        )

    except Exception as e:
        logger.error(f"Failure during reset: {e}", exc_info=True)
        return _error_response(500, f"Failed to reset system: {str(e)}")
