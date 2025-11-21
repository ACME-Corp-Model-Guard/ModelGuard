"""
Lambda function for PUT /artifacts/{artifact_type}/{id} endpoint
Update existing artifact
"""

import json
from typing import Any, Dict

# --------------------------------------------------------------------------
# COMMENETED OUT THIS EXISTING SECTION IN CASE NEEDED LATER.
# def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
#     """
#     Stub handler for PUT /artifacts/{artifact_type}/{id} - Update artifact
#     Update the content of an existing artifact
#     """
#     return {
#         "statusCode": 200,
#         "headers": {"Content-Type": "application/json"},
#         "body": json.dumps({"message": "Artifact updated successfully"}),
#     }
# --------------------------------------------------------------------------

"""
Lambda function for PUT /artifacts/{artifact_type}/{id} endpoint
Update existing artifact
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

# Environment variables
DYNAMODB_TABLE = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize AWS clients
dynamodb_resource = None


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
        return None  # type: ignore[return-value]


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
    body: Dict[str, Any] = {"error": message}
    if error_code:
        body["error_code"] = error_code
    return _create_response(status_code, body)


def validate_token(token: str) -> bool:
    """
    Validate the AuthenticationToken (stub implementation).
    Mirrors the behavior of the GET /artifact/byName/{name} lambda.
    """
    # TODO: Replace with real Cognito / JWT validation
    return token.startswith("bearer ")


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate the JSON body for the update request.
    Returns an empty dict if parsing fails.
    """
    raw_body = event.get("body")
    if raw_body is None:
        return {}
    if isinstance(raw_body, dict):
        return raw_body
    if isinstance(raw_body, str):
        try:
            return json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON in request body for artifact update")
            return {}
    return {}


def _apply_updates(
    existing_item: Dict[str, Any], updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    - `artifact_id` cannot be changed.
    - `artifact_type` cannot be changed (path parameter controls type).
    - `metadata` is shallow-merged if both old and new values are dicts.
    """
    # Do not allow changing primary key or artifact_type via request body
    updates = dict(updates)  # shallow copy
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
    Handler for PUT /artifacts/{artifact_type}/{id} - Update artifact.
    Updates fields of an existing artifact in the metadata store.
    """
    # Extract path parameters
    path_params = event.get("pathParameters") or {}
    artifact_type = (path_params.get("artifact_type") or "").lower()
    artifact_id = path_params.get("id")

    if not artifact_type or not artifact_id:
        return _error_response(
            400,
            "artifact_type and id are required path parameters",
            "MISSING_PATH_PARAMS",
        )

    valid_types = {"model", "dataset", "code"}
    if artifact_type not in valid_types:
        return _error_response(
            400, f"Invalid artifact_type: {artifact_type}", "INVALID_ARTIFACT_TYPE"
        )

    # Authenticate request (same style as GET /artifact/byName/{name})
    headers = event.get("headers") or {}
    auth_token = headers.get("X-Authorization") or headers.get("AuthenticationToken")
    if not auth_token or not validate_token(auth_token):
        return _error_response(403, "Authentication failed", "AUTHENTICATION_FAILED")

    # Parse update body
    updates = _parse_body(event)
    if not updates:
        return _error_response(
            400, "Request body must contain fields to update", "EMPTY_UPDATE"
        )

    table = _get_dynamodb_table()
    if table is None:
        logger.error("DynamoDB table not available")
        return _error_response(500, "DynamoDB table not available", "DDB_NOT_AVAILABLE")

    # Load existing artifact
    try:
        response = table.get_item(Key={"artifact_id": artifact_id})
    except ClientError as e:
        logger.error(
            f"Failed to load artifact {artifact_id} from DynamoDB: {e}", exc_info=True
        )
        return _error_response(500, "Failed to load artifact", "DDB_GET_FAILED")

    item = response.get("Item")
    if not item:
        return _error_response(404, f"Artifact {artifact_id} not found", "NOT_FOUND")

    stored_type = (item.get("artifact_type") or "").lower()
    if stored_type and stored_type != artifact_type:
        return _error_response(
            400,
            f"Artifact {artifact_id} is of type '{stored_type}', not '{artifact_type}'",
            "TYPE_MISMATCH",
        )

    # Apply updates and save back to DynamoDB
    updated_item = _apply_updates(item, updates)

    try:
        table.put_item(Item=updated_item)
    except ClientError as e:
        logger.error(
            f"Failed to update artifact {artifact_id} in DynamoDB: {e}", exc_info=True
        )
        return _error_response(500, "Failed to update artifact", "DDB_PUT_FAILED")

    response_body = {
        "message": "Artifact updated successfully",
        "artifact": {
            "id": artifact_id,
            "name": updated_item.get("name"),
            "type": updated_item.get("artifact_type"),
            "metadata": updated_item.get("metadata"),
        },
    }

    return _create_response(200, response_body)
