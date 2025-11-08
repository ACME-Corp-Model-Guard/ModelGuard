"""
Lambda function for POST /artifact/{artifact_type} endpoint
Upload/Create new artifact
"""

import base64
import json
import os
import uuid
from typing import Any, Dict, Optional

try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.model import Model  # type: ignore[import-not-found]
from src.logger import logger
from src.artifacts import BaseArtifact
from src.artifacts.utils.types import ArtifactType
from src.artifacts.utils.file_storage import upload_artifact_to_s3
from src.artifacts.utils.metadata_storage import save_artifact_to_dynamodb
from src.artifacts.utils.api_ingestion import IngestionError

# Environment variables
S3_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "modelguard-artifacts-files")
DYNAMODB_TABLE = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize AWS clients
s3_client = None
dynamodb_client = None


def _get_aws_clients() -> tuple[Any, Any]:
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


def _parse_body(event: Dict[str, Any]) -> tuple[bytes, Optional[str]]:
    """Parse the request body from API Gateway event."""
    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)
    content_type = event.get("headers", {}).get(
        "content-type", event.get("headers", {}).get("Content-Type", "")
    )

    if is_base64 and body:
        try:
            body_bytes = base64.b64decode(body)
        except Exception:
            return b"", None
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    return body_bytes, content_type


def _parse_multipart_form_data(body: bytes, content_type: str) -> Dict[str, Any]:
    """Parse multipart/form-data request body."""
    if not content_type or "multipart/form-data" not in content_type:
        return {}

    try:
        boundary = None
        for content_part in content_type.split(";"):
            content_part = content_part.strip()
            if content_part.startswith("boundary="):
                boundary = content_part.split("=", 1)[1].strip('"')
                break

        if not boundary:
            return {}

        parts = body.split(f"--{boundary}".encode())
        result: Dict[str, Any] = {"fields": {}, "files": {}}

        for part_raw in parts[1:-1]:
            part: bytes = part_raw.strip()
            if not part:
                continue

            if b"\r\n\r\n" in part:
                headers_bytes, data = part.split(b"\r\n\r\n", 1)
            elif b"\n\n" in part:
                headers_bytes, data = part.split(b"\n\n", 1)
            else:
                continue

            headers = headers_bytes.decode("utf-8", errors="ignore")
            name = None
            filename = None

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
                    result["fields"][name] = data.decode(
                        "utf-8", errors="ignore"
                    ).strip()

        return result
    except Exception:
        return {}


def _upload_to_s3(
    artifact_type: str,
    model_name: str,
    file_content: bytes,
    filename: Optional[str] = None,
) -> str:
    """Upload artifact file to S3."""
    s3_client, _ = _get_aws_clients()
    if s3_client is None:
        raise RuntimeError("S3 client not available. boto3 required for S3 operations.")

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
    """Save model metadata to DynamoDB."""
    _, dynamodb = _get_aws_clients()
    if dynamodb is None:
        raise RuntimeError(
            "DynamoDB client not available. boto3 required for DynamoDB operations."
        )

    model_dict = model.to_dict()

    dynamodb_item = {
        "artifact_id": {"S": model.name},  # Using artifact_id as primary key
        "name": {"S": model_dict["name"]},
        "size": {"N": str(model_dict["size"])},
        "license": {"S": model_dict["license"]},
        "model_key": {"S": model_dict.get("model_key", "")},
        "code_key": {"S": model_dict.get("code_key", "")},
        "dataset_key": {"S": model_dict.get("dataset_key", "")},
    }

    if model_dict.get("parent_model_key"):
        dynamodb_item["parent_model_key"] = {"S": model_dict["parent_model_key"]}

    if model_dict.get("scores"):
        dynamodb_item["scores"] = {"S": json.dumps(model_dict["scores"])}

    if model_dict.get("scores_latency"):
        dynamodb_item["scores_latency"] = {
            "S": json.dumps(model_dict["scores_latency"])
        }

    try:
        dynamodb.put_item(TableName=DYNAMODB_TABLE, Item=dynamodb_item)
    except ClientError as e:
        raise RuntimeError(f"Failed to save to DynamoDB: {str(e)}")


def _handle_url_ingestion(artifact_type: ArtifactType, url: str) -> Dict[str, Any]:
    """
    Handle URL-based artifact ingestion using the new artifact system.

    Args:
        artifact_type: One of 'model', 'dataset', 'code'
        url: URL to artifact (HuggingFace or GitHub)

    Returns:
        API Gateway response with artifact metadata
    """
    try:
        logger.info(f"Creating {artifact_type} artifact from URL: {url}")

        # Create artifact from URL (fetches metadata automatically)
        artifact = BaseArtifact.from_url(url, artifact_type)

        logger.info(f"Created artifact: {artifact.artifact_id}, name: {artifact.name}")

        # Upload artifact file to S3 (downloads from source and uploads)
        try:
            upload_artifact_to_s3(
                artifact.artifact_id, artifact_type, artifact.s3_key, url
            )
            logger.info(f"Successfully uploaded artifact {artifact.artifact_id} to S3")
        except Exception as e:
            logger.error(f"Failed to upload artifact to S3: {e}", exc_info=True)
            return _error_response(
                500, f"Failed to upload artifact: {str(e)}", "S3_UPLOAD_ERROR"
            )

        # Save artifact metadata to DynamoDB
        try:
            save_artifact_to_dynamodb(artifact.to_dict())
            logger.info(
                f"Successfully saved artifact {artifact.artifact_id} to DynamoDB"
            )
        except Exception as e:
            logger.error(f"Failed to save artifact to DynamoDB: {e}", exc_info=True)
            return _error_response(
                500, f"Failed to save artifact: {str(e)}", "DYNAMODB_SAVE_ERROR"
            )

        logger.info(
            f"Successfully ingested {artifact_type} artifact from URL: {artifact.artifact_id}"
        )

        return _create_response(
            200,
            {
                "message": "Artifact ingested successfully from URL",
                "artifact_type": artifact_type,
                "artifact_id": artifact.artifact_id,
                "name": artifact.name,
                "s3_key": artifact.s3_key,
                "artifact": artifact.to_dict(),
            },
        )

    except IngestionError as e:
        logger.error(f"Artifact ingestion failed: {e}", exc_info=True)
        return _error_response(
            400, f"Failed to ingest artifact: {str(e)}", "INGESTION_ERROR"
        )
    except Exception as e:
        logger.error(f"Unexpected error during artifact ingestion: {e}", exc_info=True)
        return _error_response(500, f"Unexpected error: {str(e)}", "INTERNAL_ERROR")


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
    Lambda handler for POST /artifact/{artifact_type}.

    Uploads artifacts (model, code, or dataset) to S3 and updates model metadata in DynamoDB.
    """
    path_params = event.get("pathParameters") or {}
    logger.info(
        f"Processing POST /artifact/{path_params.get('artifact_type', 'unknown')}"
    )
    artifact_type_str = path_params.get("artifact_type", "").lower()

    valid_types = {"model", "code", "dataset"}
    if artifact_type_str not in valid_types:
        logger.warning(f"Invalid artifact_type: {artifact_type_str}")
        return _error_response(
            400,
            f"Invalid artifact_type. Must be one of: {', '.join(valid_types)}",
            "INVALID_ARTIFACT_TYPE",
        )

    # Cast to proper type after validation
    artifact_type: ArtifactType = artifact_type_str  # type: ignore[assignment]

    body_bytes, content_type = _parse_body(event)
    if not body_bytes:
        logger.warning("Request body is missing")
        return _error_response(400, "Request body is required", "MISSING_BODY")

    # Check if this is a URL-based ingestion (JSON body with 'url' field)
    try:
        if content_type and "application/json" in content_type:
            body_json = json.loads(body_bytes.decode("utf-8"))
            if "url" in body_json:
                logger.info(
                    f"Processing URL-based ingestion for {artifact_type}: {body_json['url']}"
                )
                return _handle_url_ingestion(artifact_type, body_json["url"])
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
        # Not JSON or missing url field, treat as file upload
        pass

    # Handle file upload (multipart/form-data)
    logger.info(f"Processing file upload for {artifact_type}")
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
        headers = event.get("headers", {})
        model_name = headers.get("X-Model-Name") or headers.get("x-model-name")

    if not model_name:
        if filename:
            model_name = os.path.splitext(filename)[0]
        else:
            model_name = f"model-{uuid.uuid4().hex[:8]}"
        logger.info(f"Generated model_name: {model_name}")

    try:
        s3_key = _upload_to_s3(artifact_type, model_name, file_content, filename)
        logger.info(f"Uploaded to S3: {s3_key}, size: {len(file_content)} bytes")
    except RuntimeError as e:
        logger.error(f"S3 upload failed: {e}")
        return _error_response(500, str(e), "S3_UPLOAD_ERROR")

    model = _load_model_from_dynamodb(model_name)
    is_new_model = model is None
    if is_new_model:
        logger.info(f"Creating new model: {model_name}")
        model = Model(
            name=model_name,
            model_key="",
            code_key="",
            dataset_key="",
            size=len(file_content),
            license="unknown",
        )
    else:
        logger.info(f"Updating existing model: {model_name}")

    # Type narrowing: model is guaranteed to be Model here
    assert model is not None, "Model should not be None at this point"

    if artifact_type == "model":
        model.model_key = s3_key
        model.size = len(file_content)
    elif artifact_type == "code":
        model.code_key = s3_key
    elif artifact_type == "dataset":
        model.dataset_key = s3_key

    if is_new_model:
        logger.info(f"Computing scores for new model: {model_name}")
        model._compute_scores()

    try:
        _save_model_to_dynamodb(model)
        logger.info(f"Saved model to DynamoDB: {model_name}")
    except RuntimeError as e:
        logger.error(f"DynamoDB save failed: {e}")
        return _error_response(500, str(e), "DYNAMODB_SAVE_ERROR")

    logger.info(
        f"Successfully processed upload: {model_name}, type: {artifact_type}, s3_key: {s3_key}"
    )
    return _create_response(
        200,
        {
            "message": "Artifact uploaded successfully",
            "artifact_type": artifact_type,
            "model_name": model_name,
            "s3_key": s3_key,
            "model": model.to_dict(),
        },
    )
