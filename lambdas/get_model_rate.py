"""
Lambda function for GET /artifact/model/{id}/rate endpoint
Get ratings for model artifacts
"""

import json
import os
from typing import Any, Dict, Optional

try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]

from src.artifacts import ModelArtifact  # type: ignore[import-not-found]
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
        return None


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

        # Ensure scores and scores_latency are dicts (they might be stored as JSON strings)
        if "scores" in artifact_dict and isinstance(artifact_dict["scores"], str):
            try:
                artifact_dict["scores"] = json.loads(artifact_dict["scores"])
            except json.JSONDecodeError:
                artifact_dict["scores"] = {}
        elif "scores" not in artifact_dict:
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
        elif "scores_latency" not in artifact_dict:
            artifact_dict["scores_latency"] = {}

        if "metadata" in artifact_dict and isinstance(artifact_dict["metadata"], str):
            try:
                artifact_dict["metadata"] = json.loads(artifact_dict["metadata"])
            except json.JSONDecodeError:
                artifact_dict["metadata"] = {}
        elif "metadata" not in artifact_dict:
            artifact_dict["metadata"] = {}

        return artifact_dict
    except (ClientError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load artifact from DynamoDB: {e}", exc_info=True)
        return None


def _format_rate_response(artifact_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format artifact data into the rate response structure.

    Maps scores and scores_latency to the expected API format.
    """
    scores = artifact_dict.get("scores", {})
    scores_latency = artifact_dict.get("scores_latency", {})

    # Extract category from metadata if available
    metadata = artifact_dict.get("metadata", {})
    category = (
        metadata.get("category", "unknown") if isinstance(metadata, dict) else "unknown"
    )

    # Build response with all metric scores
    response: Dict[str, Any] = {
        "name": artifact_dict.get("name", "unknown"),
        "category": category,
    }

    # Add NetScore
    if "NetScore" in scores:
        response["net_score"] = scores["NetScore"]
    if "NetScore" in scores_latency:
        response["net_score_latency"] = scores_latency["NetScore"]

    # Map metric names to API format (camelCase with underscores)
    metric_mapping = {
        "RampUp": ("ramp_up_time", "ramp_up_time_latency"),
        "BusFactor": ("bus_factor", "bus_factor_latency"),
        "PerformanceClaims": ("performance_claims", "performance_claims_latency"),
        "License": ("license", "license_latency"),
        "DatasetQuality": ("dataset_quality", "dataset_quality_latency"),
        "CodeQuality": ("code_quality", "code_quality_latency"),
        "Reproducibility": ("reproducibility", "reproducibility_latency"),
        "Reviewedness": ("reviewedness", "reviewedness_latency"),
        "Treescore": ("tree_score", "tree_score_latency"),
    }

    # Add individual metric scores
    for metric_name, (score_key, latency_key) in metric_mapping.items():
        if metric_name in scores:
            response[score_key] = scores[metric_name]
        if metric_name in scores_latency:
            response[latency_key] = scores_latency[metric_name]

    # Handle Size metric (special case - can be a dict)
    if "Size" in scores:
        size_score = scores["Size"]
        if isinstance(size_score, dict):
            # Map platform names to API format
            size_dict: Dict[str, float] = {}
            platform_mapping = {
                "raspberry_pi": "raspberry_pi",
                "jetson_nano": "jetson_nano",
                "desktop_pc": "desktop_pc",
                "aws_server": "aws_server",
            }
            for platform, api_name in platform_mapping.items():
                if platform in size_score:
                    size_dict[api_name] = size_score[platform]
            response["size_score"] = size_dict if size_dict else size_score
        else:
            response["size_score"] = size_score

    if "Size" in scores_latency:
        response["size_score_latency"] = scores_latency["Size"]

    # Handle dataset_and_code_score (if available)
    if "DatasetAndCode" in scores:
        response["dataset_and_code_score"] = scores["DatasetAndCode"]
    if "DatasetAndCode" in scores_latency:
        response["dataset_and_code_score_latency"] = scores_latency["DatasetAndCode"]

    return response


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /artifact/model/{id}/rate.

    Returns model rating with all metric scores and latencies.
    """
    path_params = event.get("pathParameters") or {}
    model_id = path_params.get("id", "")

    logger.info(f"Processing GET /artifact/model/{model_id}/rate")

    if not model_id:
        logger.warning("Model ID is missing")
        return _error_response(400, "Model ID is required", "MISSING_ID")

    # Load artifact from DynamoDB
    artifact_dict = _load_artifact_from_dynamodb(model_id)
    if artifact_dict is None:
        logger.warning(f"Model not found: {model_id}")
        return _error_response(404, f"Model not found: {model_id}", "MODEL_NOT_FOUND")

    # Verify it's a model artifact
    artifact_type = artifact_dict.get("artifact_type", "")
    if artifact_type != "model":
        logger.warning(f"Artifact {model_id} is not a model (type: {artifact_type})")
        return _error_response(
            400, f"Artifact {model_id} is not a model", "INVALID_ARTIFACT_TYPE"
        )

    # Format and return rate response
    try:
        rate_data = _format_rate_response(artifact_dict)
        logger.info(f"Successfully retrieved rate for model: {model_id}")
        return _create_response(200, rate_data)
    except Exception as e:
        logger.error(f"Failed to format rate response: {e}", exc_info=True)
        return _error_response(
            500, f"Failed to format rate data: {str(e)}", "INTERNAL_ERROR"
        )
