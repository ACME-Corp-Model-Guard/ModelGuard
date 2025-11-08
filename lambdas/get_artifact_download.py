"""
Lambda function for GET /artifacts/{artifact_type}/{id} endpoint
Download/Retrieve artifact by type and ID
"""

import base64
import json
import os
from typing import Any, Dict, Optional, Tuple

try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.model import Model  # type: ignore[import-not-found]
from src.logger import logger

# Environment variables
S3_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "modelguard-artifacts-files")
DYNAMODB_TABLE = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize AWS clients
s3_client = None
dynamodb_client = None


def _get_aws_clients() -> Tuple[Any, Any]:
    """Initialize AWS clients if boto3 is available."""
    global s3_client, dynamodb_client
    if boto3 is None:
        return None, None  # type: ignore[return-value]
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=AWS_REGION)  # type: ignore
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)  # type: ignore
    return s3_client, dynamodb_client


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
    s3_client, _ = _get_aws_clients()
    if s3_client is None:
        raise RuntimeError("S3 client not available. boto3 required for S3 operations.")

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        file_content = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")
        return file_content, content_type
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "NoSuchKey":
            raise RuntimeError(f"Artifact not found: {s3_key}")
        raise RuntimeError(f"Failed to download from S3: {str(e)}")


def _load_model_from_dynamodb(model_name: str) -> Optional[Model]:
    """Load model metadata from DynamoDB."""
    _, dynamodb = _get_aws_clients()
    if dynamodb is None:
        return None

    try:
        response = dynamodb.get_item(
            TableName=DYNAMODB_TABLE, Key={"artifact_id": {"S": model_name}}
        )
        if "Item" not in response:
            return None

        item = response["Item"]
        model_dict = {
            "name": item.get("name", {}).get("S", model_name),
            "size": float(item.get("size", {}).get("N", "0")),
            "license": item.get("license", {}).get("S", "unknown"),
            "model_key": item.get("model_key", {}).get("S", ""),
            "code_key": item.get("code_key", {}).get("S", ""),
            "dataset_key": item.get("dataset_key", {}).get("S", ""),
        }

        if "parent_model_key" in item:
            model_dict["parent_model_key"] = item["parent_model_key"]["S"]

        if "scores" in item:
            model_dict["scores"] = json.loads(item["scores"]["S"])

        if "scores_latency" in item:
            model_dict["scores_latency"] = json.loads(item["scores_latency"]["S"])

        return Model.create_with_scores(model_dict)
    except (ClientError, KeyError, json.JSONDecodeError):
        return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /artifacts/{artifact_type}/{id}.

    Retrieves artifacts (model, code, or dataset) from S3 based on model ID.
    """
    path_params = event.get("pathParameters") or {}
    logger.info(
        f"Processing GET /artifacts/{path_params.get('artifact_type', 'unknown')}/{path_params.get('id', 'unknown')}"
    )
    artifact_type = path_params.get("artifact_type", "").lower()
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

    model = _load_model_from_dynamodb(artifact_id)
    if model is None:
        logger.warning(f"Model not found: {artifact_id}")
        return _error_response(
            404, f"Model not found: {artifact_id}", "MODEL_NOT_FOUND"
        )

    s3_key = None
    if artifact_type == "model":
        s3_key = model.model_key
    elif artifact_type == "code":
        s3_key = model.code_key
    elif artifact_type == "dataset":
        s3_key = model.dataset_key

    if not s3_key:
        logger.warning(f"{artifact_type} artifact not found for model: {artifact_id}")
        return _error_response(
            404,
            f"{artifact_type.capitalize()} artifact not found for model: {artifact_id}",
            "ARTIFACT_NOT_FOUND",
        )

    if metadata_only:
        logger.info(f"Returning metadata for {artifact_id}, type: {artifact_type}")
        artifact_info = {
            "artifact_type": artifact_type,
            "model_name": artifact_id,
            "s3_key": s3_key,
            "model": model.to_dict(),
        }
        return _create_response(200, artifact_info)

    try:
        file_content, content_type = _download_from_s3(s3_key)
        logger.info(f"Downloaded from S3: {s3_key}, size: {len(file_content)} bytes")
    except RuntimeError as e:
        logger.error(f"S3 download failed: {e}")
        return _error_response(500, str(e), "S3_DOWNLOAD_ERROR")

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
        f"Successfully downloaded artifact: {artifact_id}, type: {artifact_type}, size: {len(file_content)} bytes"
    )
    return _create_binary_response(200, file_content, content_type)
