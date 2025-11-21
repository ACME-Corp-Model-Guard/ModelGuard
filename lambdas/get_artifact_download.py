"""
Lambda function for GET /artifacts/{artifact_type}/{id} endpoint
Download/Retrieve artifact by type and ID
"""

import base64
import json
import os
from typing import Any, Dict, Optional, Tuple

try:
    import boto3  # type: ignore[import-untyped]
    from botocore.exceptions import ClientError  # type: ignore[import-not-found,import-untyped]
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.logger import logger

# Environment variables
S3_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "modelguard-artifacts-files")
DYNAMODB_TABLE = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")

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


def _create_binary_response(
    status_code: int,
    body: bytes,
    content_type: str = "application/octet-stream",
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a standardized API Gateway response with binary body."""
    default_headers = {
        "Content-Type": content_type,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }
    if headers:
        default_headers.update(headers)

    body_base64 = base64.b64encode(body).decode("utf-8")

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": body_base64,
        "isBase64Encoded": True,
    }


def _download_from_s3(s3_key: str) -> Tuple[bytes, Optional[str]]:
    """Download artifact file from S3."""
    s3 = _get_s3_client()
    if s3 is None:
        raise RuntimeError("S3 client not available. boto3 required for S3 operations.")

    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        file_content = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")
        return file_content, content_type
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "NoSuchKey":
            raise RuntimeError(f"Artifact not found: {s3_key}")
        raise RuntimeError(f"Failed to download from S3: {str(e)}")


def _load_artifact_from_dynamodb(artifact_id: str) -> Optional[Dict[str, Any]]:
    """Load artifact metadata from DynamoDB."""
    table = _get_dynamodb_table()
    if table is None:
        logger.error("DynamoDB table not available")
        return None

    try:
        response = table.get_item(Key={"artifact_id": artifact_id})
        if "Item" not in response:
            return None

        artifact_dict = response["Item"]

        # Ensure JSON fields are parsed
        if "scores" in artifact_dict and isinstance(artifact_dict["scores"], str):
            try:
                artifact_dict["scores"] = json.loads(artifact_dict["scores"])
            except json.JSONDecodeError:
                artifact_dict["scores"] = {}

        if "scores_latency" in artifact_dict and isinstance(
            artifact_dict["scores_latency"], str
        ):
            try:
                artifact_dict["scores_latency"] = json.loads(
                    artifact_dict["scores_latency"]
                )
            except json.JSONDecodeError:
                artifact_dict["scores_latency"] = {}

        if "metadata" in artifact_dict and isinstance(artifact_dict["metadata"], str):
            try:
                artifact_dict["metadata"] = json.loads(artifact_dict["metadata"])
            except json.JSONDecodeError:
                artifact_dict["metadata"] = {}

        return artifact_dict
    except (ClientError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load artifact from DynamoDB: {e}", exc_info=True)
        return None


def _get_s3_key_for_artifact_type(
    artifact_dict: Dict[str, Any], artifact_type: str
) -> Optional[str]:
    """
    Get S3 key for the requested artifact type.

    For model artifacts, supports model_key, code_key, dataset_key.
    For other artifact types, uses s3_key field.
    """
    artifact_dict_type = artifact_dict.get("artifact_type", "").lower()

    # If this is a model artifact, check for specific keys
    if artifact_dict_type == "model":
        if artifact_type == "model":
            return artifact_dict.get("model_key") or artifact_dict.get("s3_key")
        elif artifact_type == "code":
            return artifact_dict.get("code_key")
        elif artifact_type == "dataset":
            return artifact_dict.get("dataset_key")

    # For non-model artifacts or if s3_key is used
    # Check if the artifact_type matches
    if artifact_dict_type == artifact_type:
        return artifact_dict.get("s3_key")

    # Fallback: return s3_key if available
    return artifact_dict.get("s3_key")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /artifacts/{artifact_type}/{id}.

    Retrieves artifacts (model, code, or dataset) from S3 based on artifact ID.
    Supports metadata_only query parameter to return metadata without file content.
    """
    path_params = event.get("pathParameters") or {}
    artifact_type_str = path_params.get("artifact_type", "unknown")
    artifact_id_str = path_params.get("id", "unknown")
    logger.info(f"Processing GET /artifacts/{artifact_type_str}/{artifact_id_str}")
    artifact_type = artifact_type_str.lower()
    artifact_id = path_params.get("id", "")

    valid_types = {"model", "code", "dataset"}
    if artifact_type not in valid_types:
        return _error_response(
            400,
            f"Invalid artifact_type. Must be one of: {', '.join(valid_types)}",
            "INVALID_ARTIFACT_TYPE",
        )

    if not artifact_id:
        return _error_response(400, "Artifact ID is required", "MISSING_ID")

    query_params = event.get("queryStringParameters") or {}
    metadata_only = query_params.get("metadata_only", "").lower() in (
        "true",
        "1",
        "yes",
    )

    if metadata_only:
        logger.info(f"Requesting metadata only for {artifact_id}")

    # Load artifact from DynamoDB
    artifact_dict = _load_artifact_from_dynamodb(artifact_id)
    if artifact_dict is None:
        logger.warning(f"Artifact not found: {artifact_id}")
        return _error_response(
            404, f"Artifact not found: {artifact_id}", "ARTIFACT_NOT_FOUND"
        )

    # Get S3 key for the requested artifact type
    s3_key = _get_s3_key_for_artifact_type(artifact_dict, artifact_type)

    if not s3_key:
        logger.warning(
            f"{artifact_type} artifact not found for artifact: {artifact_id}"
        )
        return _error_response(
            404,
            f"{artifact_type.capitalize()} artifact not found for artifact: {artifact_id}",
            "ARTIFACT_NOT_FOUND",
        )

    # If metadata_only, return metadata without downloading file
    if metadata_only:
        logger.info(f"Returning metadata for {artifact_id}, type: {artifact_type}")
        artifact_info = {
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "s3_key": s3_key,
            "artifact": artifact_dict,
        }
        return _create_response(200, artifact_info)

    # Download file from S3
    try:
        file_content, content_type = _download_from_s3(s3_key)
        logger.info(f"Downloaded from S3: {s3_key}, size: {len(file_content)} bytes")
    except RuntimeError as e:
        logger.error(f"S3 download failed: {e}")
        return _error_response(500, str(e), "S3_DOWNLOAD_ERROR")

    # Determine content type based on file extension if not set
    if not content_type or content_type == "application/octet-stream":
        file_ext = os.path.splitext(s3_key)[1].lower()
        content_type_map = {
            ".pkl": "application/octet-stream",
            ".pt": "application/octet-stream",
            ".h5": "application/octet-stream",
            ".onnx": "application/octet-stream",
            ".pb": "application/octet-stream",
            ".py": "text/x-python",
            ".pyc": "application/octet-stream",
            ".zip": "application/zip",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".json": "application/json",
            ".csv": "text/csv",
            ".txt": "text/plain",
        }
        content_type = content_type_map.get(
            file_ext, content_type or "application/octet-stream"
        )

    logger.info(
        f"Successfully downloaded artifact: {artifact_id}, type: {artifact_type},
        size: {len(file_content)} bytes"
    )
    return _create_binary_response(200, file_content, content_type)
