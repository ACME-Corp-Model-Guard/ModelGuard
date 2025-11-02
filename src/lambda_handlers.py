#!/usr/bin/env python3
"""
Lambda handlers for ModelGuard API endpoints.
Handles artifact uploads and model management via API Gateway.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from typing import Any, Dict, Optional, Tuple

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    # Allow running without boto3 in local dev/testing
    boto3 = None
    ClientError = Exception

from src.model import Model
from src.logging_utils import setup_logging

# Initialize AWS clients
s3_client = None
dynamodb_client = None

# Environment variables
S3_BUCKET = os.environ.get("S3_BUCKET", "modelguard-artifacts")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "ModelGuard-Models")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _get_aws_clients():
    """Initialize AWS clients if boto3 is available."""
    global s3_client, dynamodb_client
    if boto3 is None:
        return None, None
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=AWS_REGION)
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)
    return s3_client, dynamodb_client


def _create_response(
    status_code: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a standardized API Gateway response.

    Args:
        status_code: HTTP status code
        body: Response body as dictionary
        headers: Optional headers dictionary

    Returns:
        API Gateway response format
    """
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


def _error_response(status_code: int, message: str, error_code: Optional[str] = None) -> Dict[str, Any]:
    """Create an error response."""
    body = {"error": message}
    if error_code:
        body["error_code"] = error_code
    return _create_response(status_code, body)


def _parse_body(event: Dict[str, Any]) -> Tuple[bytes, Optional[str]]:
    """
    Parse the request body from API Gateway event.

    Handles both base64 encoded and plain text bodies.

    Args:
        event: API Gateway event

    Returns:
        Tuple of (body_bytes, content_type)
    """
    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)
    content_type = event.get("headers", {}).get("content-type", event.get("headers", {}).get("Content-Type", ""))

    if is_base64 and body:
        try:
            body_bytes = base64.b64decode(body)
        except Exception:
            return b"", None
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    return body_bytes, content_type


def _parse_multipart_form_data(body: bytes, content_type: str) -> Dict[str, Any]:
    """
    Parse multipart/form-data request body.

    Args:
        body: Request body bytes
        content_type: Content-Type header value

    Returns:
        Dictionary with form fields and files
    """
    if not content_type or "multipart/form-data" not in content_type:
        return {}

    try:
        # Extract boundary from content-type
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1].strip('"')
                break

        if not boundary:
            return {}

        # Parse multipart data
        parts = body.split(f"--{boundary}".encode())
        result = {"fields": {}, "files": {}}

        for part in parts[1:-1]:  # Skip first and last empty parts
            part = part.strip()
            if not part:
                continue

            # Split headers and body
            if b"\r\n\r\n" in part:
                headers_bytes, data = part.split(b"\r\n\r\n", 1)
            elif b"\n\n" in part:
                headers_bytes, data = part.split(b"\n\n", 1)
            else:
                continue

            headers = headers_bytes.decode("utf-8", errors="ignore")
            name = None
            filename = None

            # Extract name and filename from headers
            for line in headers.split("\n"):
                line = line.strip()
                if line.startswith("Content-Disposition:"):
                    for item in line.split(";")[1:]:
                        item = item.strip()
                        if item.startswith('name="'):
                            name = item.split('"')[1]
                        elif item.startswith('filename="'):
                            filename = item.split('"')[1]

            if name:
                if filename:
                    result["files"][name] = {"filename": filename, "content": data}
                else:
                    result["fields"][name] = data.decode("utf-8", errors="ignore").strip()

        return result
    except Exception:
        return {}


def _upload_to_s3(
    artifact_type: str, model_name: str, file_content: bytes, filename: Optional[str] = None
) -> str:
    """
    Upload artifact file to S3.

    Args:
        artifact_type: Type of artifact (model, code, dataset)
        model_name: Name of the model
        file_content: File content as bytes
        filename: Original filename (optional)

    Returns:
        S3 key where the file was uploaded
    """
    s3_client, _ = _get_aws_clients()
    if s3_client is None:
        raise RuntimeError("S3 client not available. boto3 required for S3 operations.")

    # Generate S3 key: artifact_type/model_name/unique_id/filename
    file_id = str(uuid.uuid4())
    safe_model_name = model_name.lower().replace(" ", "-").replace("_", "-")
    file_extension = os.path.splitext(filename)[1] if filename else ""
    s3_key = f"{artifact_type}/{safe_model_name}/{file_id}{file_extension}"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType="application/octet-stream",
        )
        return s3_key
    except ClientError as e:
        raise RuntimeError(f"Failed to upload to S3: {str(e)}")


def _save_model_to_dynamodb(model: Model) -> None:
    """
    Save model metadata to DynamoDB.

    Args:
        model: Model instance to save
    """
    _, dynamodb = _get_aws_clients()
    if dynamodb is None:
        raise RuntimeError("DynamoDB client not available. boto3 required for DynamoDB operations.")

    model_dict = model.to_dict()

    # Convert to DynamoDB format
    dynamodb_item = {
        "name": {"S": model_dict["name"]},
        "size": {"N": str(model_dict["size"])},
        "license": {"S": model_dict["license"]},
        "model_key": {"S": model_dict.get("model_key", "")},
        "code_key": {"S": model_dict.get("code_key", "")},
        "dataset_key": {"S": model_dict.get("dataset_key", "")},
    }

    if model_dict.get("parent_model_key"):
        dynamodb_item["parent_model_key"] = {"S": model_dict["parent_model_key"]}

    # Add scores as JSON string (DynamoDB doesn't support nested dicts directly)
    if model_dict.get("scores"):
        dynamodb_item["scores"] = {"S": json.dumps(model_dict["scores"])}

    if model_dict.get("scores_latency"):
        dynamodb_item["scores_latency"] = {"S": json.dumps(model_dict["scores_latency"])}

    try:
        dynamodb.put_item(TableName=DYNAMODB_TABLE, Item=dynamodb_item)
    except ClientError as e:
        raise RuntimeError(f"Failed to save to DynamoDB: {str(e)}")


def _load_model_from_dynamodb(model_name: str) -> Optional[Model]:
    """
    Load model metadata from DynamoDB.

    Args:
        model_name: Name of the model to load

    Returns:
        Model instance or None if not found
    """
    _, dynamodb = _get_aws_clients()
    if dynamodb is None:
        return None

    try:
        response = dynamodb.get_item(
            TableName=DYNAMODB_TABLE, Key={"name": {"S": model_name}}
        )
        if "Item" not in response:
            return None

        item = response["Item"]
        model_dict = {
            "name": item["name"]["S"],
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

        # Use create_with_scores for pre-existing models (scores already computed)
        return Model.create_with_scores(model_dict)
    except (ClientError, KeyError, json.JSONDecodeError):
        return None


def _download_from_s3(s3_key: str) -> Tuple[bytes, Optional[str]]:
    """
    Download artifact file from S3.

    Args:
        s3_key: S3 key of the file to download

    Returns:
        Tuple of (file_content, content_type)
    """
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


def _create_binary_response(
    status_code: int, body: bytes, content_type: str = "application/octet-stream", headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a standardized API Gateway response with binary body.

    Args:
        status_code: HTTP status code
        body: Response body as bytes
        content_type: Content type of the response
        headers: Optional headers dictionary

    Returns:
        API Gateway response format with base64-encoded body
    """
    default_headers = {
        "Content-Type": content_type,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }
    if headers:
        default_headers.update(headers)

    # Encode body as base64 for binary content
    body_base64 = base64.b64encode(body).decode("utf-8")

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": body_base64,
        "isBase64Encoded": True,
    }


def get_artifact_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /artifacts/{artifact_type}/{id}.

    Retrieves artifacts (model, code, or dataset) from S3 based on model ID.

    Expected request format:
    - Path parameter: artifact_type (model, code, or dataset)
    - Path parameter: id (model name or identifier)

    Query parameters:
    - metadata_only: If true, returns only metadata without downloading the file

    Returns:
    - 200 OK: Artifact file (binary) or metadata (JSON if metadata_only=true)
    - 400 Bad Request: Invalid artifact type
    - 404 Not Found: Model or artifact not found
    - 500 Internal Server Error: S3 download failure
    """
    try:
        setup_logging()
    except Exception:
        pass

    # Extract path parameters
    path_params = event.get("pathParameters") or {}
    artifact_type = path_params.get("artifact_type", "").lower()
    artifact_id = path_params.get("id", "")

    # Validate artifact type
    valid_types = {"model", "code", "dataset"}
    if artifact_type not in valid_types:
        return _error_response(
            400, f"Invalid artifact_type. Must be one of: {', '.join(valid_types)}", "INVALID_ARTIFACT_TYPE"
        )

    # Validate artifact ID
    if not artifact_id:
        return _error_response(400, "Artifact ID is required", "MISSING_ID")

    # Check query parameters
    query_params = event.get("queryStringParameters") or {}
    metadata_only = query_params.get("metadata_only", "").lower() in ("true", "1", "yes")

    # Load model from DynamoDB
    model = _load_model_from_dynamodb(artifact_id)
    if model is None:
        return _error_response(404, f"Model not found: {artifact_id}", "MODEL_NOT_FOUND")

    # Get S3 key based on artifact type
    s3_key = None
    if artifact_type == "model":
        s3_key = model.model_key
    elif artifact_type == "code":
        s3_key = model.code_key
    elif artifact_type == "dataset":
        s3_key = model.dataset_key

    # Check if artifact exists
    if not s3_key:
        return _error_response(
            404, f"{artifact_type.capitalize()} artifact not found for model: {artifact_id}", "ARTIFACT_NOT_FOUND"
        )

    # If metadata only, return metadata without downloading
    if metadata_only:
        artifact_info = {
            "artifact_type": artifact_type,
            "model_name": artifact_id,
            "s3_key": s3_key,
            "model": model.to_dict(),
        }
        return _create_response(200, artifact_info)

    # Download file from S3
    try:
        file_content, content_type = _download_from_s3(s3_key)
    except RuntimeError as e:
        return _error_response(500, str(e), "S3_DOWNLOAD_ERROR")

    # Determine content type based on file extension if not already set properly
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
        content_type = content_type_map.get(file_ext, content_type or "application/octet-stream")

    # Return binary file
    return _create_binary_response(200, file_content, content_type)


def upload_artifact_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for POST /artifact/{artifact_type}.

    Uploads artifacts (model, code, or dataset) to S3 and updates model metadata in DynamoDB.

    Expected request format:
    - Path parameter: artifact_type (model, code, or dataset)
    - Body: multipart/form-data or binary file
        - For multipart: 'file' field with the file, 'model_name' field with model name
        - For binary: file content directly

    Returns:
        API Gateway response with model metadata or error
    """
    try:
        setup_logging()
    except Exception:
        pass

    # Extract path parameters
    path_params = event.get("pathParameters") or {}
    artifact_type = path_params.get("artifact_type", "").lower()

    # Validate artifact type
    valid_types = {"model", "code", "dataset"}
    if artifact_type not in valid_types:
        return _error_response(
            400, f"Invalid artifact_type. Must be one of: {', '.join(valid_types)}", "INVALID_ARTIFACT_TYPE"
        )

    # Parse request body
    body_bytes, content_type = _parse_body(event)
    if not body_bytes:
        return _error_response(400, "Request body is required", "MISSING_BODY")

    # Handle multipart/form-data
    model_name = None
    file_content = body_bytes
    filename = None

    if content_type and "multipart/form-data" in content_type:
        multipart_data = _parse_multipart_form_data(body_bytes, content_type)
        if "files" in multipart_data and "file" in multipart_data["files"]:
            file_info = multipart_data["files"]["file"]
            file_content = file_info["content"]
            filename = file_info.get("filename", "upload.bin")
        if "fields" in multipart_data and "model_name" in multipart_data["fields"]:
            model_name = multipart_data["fields"]["model_name"]
    elif "headers" in event:
        # Try to extract model name from headers
        headers = event.get("headers", {})
        model_name = headers.get("X-Model-Name") or headers.get("x-model-name")

    # If model name not provided, try to extract from filename or use default
    if not model_name:
        if filename:
            model_name = os.path.splitext(filename)[0]
        else:
            model_name = f"model-{uuid.uuid4().hex[:8]}"

    # Upload file to S3
    try:
        s3_key = _upload_to_s3(artifact_type, model_name, file_content, filename)
    except RuntimeError as e:
        return _error_response(500, str(e), "S3_UPLOAD_ERROR")

    # Load or create model
    model = _load_model_from_dynamodb(model_name)
    is_new_model = model is None
    if is_new_model:
        # Create new model (scores will be computed automatically in __init__)
        model = Model(
            name=model_name,
            model_key="",
            code_key="",
            dataset_key="",
            size=len(file_content),
            license="unknown",
        )

    # Update model with new artifact key
    if artifact_type == "model":
        model.model_key = s3_key
        model.size = len(file_content)
    elif artifact_type == "code":
        model.code_key = s3_key
    elif artifact_type == "dataset":
        model.dataset_key = s3_key

    # Recompute scores for new models after updating artifact keys
    # (Pre-existing models keep their existing scores from DynamoDB)
    if is_new_model:
        model._compute_scores()

    # Save model to DynamoDB
    try:
        _save_model_to_dynamodb(model)
    except RuntimeError as e:
        return _error_response(500, str(e), "DYNAMODB_SAVE_ERROR")

    # Return success response
    return _create_response(
        200,
        {
            "message": f"Artifact uploaded successfully",
            "artifact_type": artifact_type,
            "model_name": model_name,
            "s3_key": s3_key,
            "model": model.to_dict(),
        },
    )


# Lambda entry point
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler that routes requests based on HTTP method and path.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    http_method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "GET"))
    path = event.get("path", event.get("requestContext", {}).get("path", "/"))

    # Route to appropriate handler
    if http_method == "GET" and "/artifacts/" in path:
        return get_artifact_handler(event, context)
    elif http_method == "POST" and "/artifact/" in path:
        return upload_artifact_handler(event, context)

    # Default 404 for unmatched routes
    return _error_response(404, f"Not found: {http_method} {path}", "NOT_FOUND")

