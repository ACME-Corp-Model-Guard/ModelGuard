"""
Lambda function for PUT /artifacts/{artifact_type}/{id} endpoint
Update an existing artifact in the registry
"""

import json
import os
from typing import Any, Dict, Optional


try:
    import boto3  # type: ignore[import-untyped]
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.logger import logger


# Environmental Variables
DYNAMODB_TABLE = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")

dynamodb_resource = None


def _get_dynamodb_table() -> Any:
    """
    Obtain the DynamoDB table resource.
    """
    global dynamodb_resource

    if boto3 is None:
        logger.error("boto3 is not available in this environment")
        return None

    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)

    return dynamodb_resource.Table(DYNAMODB_TABLE)


def _create_response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Create a standardized API Gateway response.
    """
    default_headers: Dict[str, str] = {
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
    """
    Helper to return an error response with a consistent shape.
    """

    body: Dict[str, Any] = {"error", message}
    if error_code:
        body["error_code"] = error_code
    return _create_response(status_code, body)


def validate_token(token: str) -> bool:
    """
    Stub auth validator for X-Authorization header.
    """
    return bool(token) and token.lower().startswith("bearer: ")


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely parse JSON body from the event.

    The body is treated as a set of fields to update
    on the artifact(hname, metadata, description, etc..)
    """

    raw_body = event.get("body") or "{}"

    if isinstance(raw_body, dict):
        return raw_body

    if isinstance(raw_body, str):
        try:
            return json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            logger.warning("Invalid JSON body for PUT /artifacts; using empty body")

    return {}


def _apply_updates(
    existing_item: Dict[str, Any], updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply the requested updates to the existing item.

    Note:
    - 'artifact_id' cannot be changed.
    - 'artifact_type' cannot be chaned -> it is controlled by the path parameter.
    - If 'metadata' is a dict, it is shallow-merged with the existing metadata.
    """
    updates = dict(updates)

    # DO NOT allow primary key or artifact_type to be modified via body.
    updates.pop("artifact_id", None)
    updates.pop("artifact_type", None)

    for key, value in updates.items():
        if key == "metadata" and isinstance(value, dict):
            existing_metadata = existing_item.get("metadata")
            if isinstance(existing_metadata, dict):
                existing_metadata.update(value)
                existing_item["metadata"] = existing_metadata
            else:
                existing_item["metadata"] = value
        else:
            existing_item[key] = value

    return existing_item


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for PUT /artifacts/{artifact_type}{id} - Update artifact.
    """
    logger.info("Received PUT /artifacts request: %s", event)

    headers = event.get("headers") or {}
    auth_token = headers.get("X-Authorization")

    if not auth_token or not validate_token(auth_token):
        return _error_response(403, "Authentication failed", "AUTH_FAILED")

    path_params = event.get("pathParameters") or {}
    artifact_id = path_params.get("id") or path_params.get("artifact_id")
    artifact_type_raw = path_params.get("artifact_type")

    if not artifact_id:
        return _error_response(400, "Missing artifact id in path", "MISSING_ID")

    if not artifact_type_raw:
        return _error_response(400, "Missing artifact_type in path", "MISSING_TYPE")

    artifact_type = artifact_type_raw.lower()
    if artifact_type not in {"model", "dataset", "code"}:
        return _error_response(
            400, f"Invalid artifact_type: {artifact_type_raw}", "INVALID_TYPE"
        )

    updates = _parse_body(event)
    if not updates:
        return _error_response(
            400, "Request body must contain fields to update", "EMPTY_UPDATE"
        )

    table = _get_dynamodb_table()
    if table is None:
        return _error_response(500, "DynamoDB table not available", "DDB_NOT_AVAILABLE")

    # Load Existing Artifact
    try:
        response = table.get_item(Key={"artifact_id": artifact_id})
    except ClientError as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Failed to load artifact %s from DynamoDB: %s",
            artifact_id,
            exc,
            exc_info=True,
        )

        return _error_response(500, "Failed to load artifact", "DDB_GET_FAILED")

    item = response.get("Item")
    if not item:
        return _error_response(404, f"Artifact {artifact_id} not found", "NOT_FOUND")

    stored_type = (item.get("artifact_type") or "").lower()
    if stored_type and stored_type != artifact_type:
        return _error_response(
            409,
            f"Artifact type mismatch. Stored type is '{stored_type}',"
            f"but '{artifact_type}' was requested.",
            "TYPE_MISMATCH",
        )

    updated_item = _apply_updates(item, updates)

    # Persist updated item
    try:
        table.put_item(Item=updated_item)
    except ClientError as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Failed to update artifact %s in DynamoDB: %s",
            artifact_id,
            exc,
            exc_info=True,
        )

        return _error_response(500, "Failed to update artifact", "DDB_PUT_FAILED")

    response_body: Dict[str, Any] = {
        "message": "Artifact updated successfully",
        "artifact": {
            "id": artifact_id,
            "name": updated_item.get("name"),
            "type": updated_item.get("artifact_type"),
            "metadata": updated_item.get("metadata"),
        },
    }

    return _create_response(200, response_body)
