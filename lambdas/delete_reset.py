"""
Lambda function for DELETE /reset endpoint
Reset the system to default state and create superuser
"""

import json
import os
import hashlib
import secrets
from typing import Any, Dict, Optional

try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.logger import logger

# Environment variables
DYNAMODB_TABLE = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
S3_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "modelguard-artifacts-files")
USERS_TABLE = os.environ.get("USERS_TABLE", "ModelGuard-Users")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize AWS clients
dynamodb_resource = None
s3_client = None


def _get_dynamodb_table() -> Any:
    """Get DynamoDB table resource."""
    global dynamodb_resource
    if boto3 is None:
        return None  # type: ignore[return-value]
    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)  # type: ignore
    try:
        return dynamodb_resource.Table(DYNAMODB_TABLE)  # type: ignore
    except Exception:
        return None


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


def _get_s3_client() -> Any:
    """Get S3 client."""
    global s3_client
    if boto3 is None:
        return None  # type: ignore[return-value]
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=AWS_REGION)  # type: ignore
    return s3_client


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


def _create_superuser() -> None:
    """Create a default superuser/admin account internally."""
    users_table = _get_users_table()
    if users_table is None:
        logger.warning("Users table not available, skipping superuser creation")
        return

    # Default superuser credentials
    superuser_name = "admin"
    superuser_password = "admin123"  # Should be changed in production
    hashed_password = _hash_password(superuser_password)

    try:
        users_table.put_item(
            Item={
                "username": superuser_name,
                "password_hash": hashed_password,
                "is_admin": True,
                "permissions": {
                    "upload": True,
                    "search": True,
                    "download": True,
                },
            }
        )
        logger.info(f"Created superuser: {superuser_name}")
    except Exception as e:
        logger.error(f"Failed to create superuser: {e}", exc_info=True)
        raise


def _reset_dynamodb() -> None:
    """Clear all artifacts from DynamoDB."""
    table = _get_dynamodb_table()
    if table is None:
        logger.warning("DynamoDB table not available")
        return

    try:
        # Scan and delete all items
        response = table.scan()
        items = response.get("Items", [])

        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"artifact_id": item["artifact_id"]})

        logger.info(f"Deleted {len(items)} items from DynamoDB")
    except Exception as e:
        logger.error(f"Failed to reset DynamoDB: {e}", exc_info=True)
        raise


def _reset_s3() -> None:
    """Clear all objects from S3 bucket."""
    s3 = _get_s3_client()
    if s3 is None:
        logger.warning("S3 client not available")
        return

    try:
        # List and delete all objects
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=S3_BUCKET)

        delete_count = 0
        for page in pages:
            if "Contents" in page:
                objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                if objects:
                    s3.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": objects})
                    delete_count += len(objects)

        logger.info(f"Deleted {delete_count} objects from S3")
    except Exception as e:
        logger.error(f"Failed to reset S3: {e}", exc_info=True)
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for DELETE /reset.

    Resets the system to default state:
    - Clears all artifacts from DynamoDB
    - Clears all objects from S3
    - Creates a default superuser/admin account internally
    """
    logger.info("Processing DELETE /reset")

    try:
        # Reset DynamoDB
        logger.info("Resetting DynamoDB...")
        _reset_dynamodb()

        # Reset S3
        logger.info("Resetting S3...")
        _reset_s3()

        # Create superuser
        logger.info("Creating superuser...")
        _create_superuser()

        logger.info("System reset completed successfully")
        return _create_response(
            200,
            {
                "message": "System reset successfully",
                "status": "ok",
            },
        )
    except Exception as e:
        logger.error(f"Failed to reset system: {e}", exc_info=True)
        return _error_response(500, f"Failed to reset system: {str(e)}", "RESET_ERROR")
