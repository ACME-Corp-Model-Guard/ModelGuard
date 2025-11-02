"""
Lambda function for GET /artifact/byName/{name} endpoint
Search artifacts by name
"""

import json
from typing import Any, Dict, List

import boto3
from boto3.dynamodb.conditions import Key
from loguru import logger

# DynamoDB Table
TABLE_NAME = "ModelGuard-Artifacts-Metadata"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

ArtifactMetadata = Dict[
    str, Any
]  # TODO: Decide type: could be a TypedDict or Pydantic model


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GET /artifact/byName/{name}.
    Returns artifact metadata entries that match the provided name.
    """
    # Extract Path Parameters
    path_params = event.get("pathParameters") or {}
    name = path_params.get("name")
    if not name:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing or invalid artifact name"}),
        }

    # Extract Headers
    headers = event.get("headers") or {}
    auth_token = headers.get("X-Authorization")
    if not auth_token or not validate_token(auth_token):
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Authentication failed"}),
        }

    # Query DynamoDB
    artifacts: List[ArtifactMetadata] = query_artifacts_by_name(name)

    if not artifacts:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "No such artifact"}),
        }

    # Successful Response
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(artifacts),
    }


def validate_token(token: str) -> bool:
    """
    Validate the AuthenticationToken (stub implementation)
    """
    # TODO: Replace with real Cognito / JWT validation
    return token.startswith("bearer ")


def query_artifacts_by_name(name: str) -> List[ArtifactMetadata]:
    """
    Query DynamoDB table for artifacts matching the given name.
    Returns a list of ArtifactMetadata dicts matching the OpenAPI schema.
    Assumes `id` is stored as a string.
    """
    try:
        response = table.query(
            IndexName='NameIndex',  # Specify the GSI
            KeyConditionExpression=Key("name").eq(name)
        )
        items = response.get("Items", [])
        artifacts: List[ArtifactMetadata] = []

        for item in items:
            # Validate Required Fields
            if "name" in item and "artifact_id" in item and "artifact_type" in item:
                artifact_type = item["artifact_type"]
                if artifact_type not in {"model", "dataset", "code"}:
                    continue  # Skip Invalid Type
                artifacts.append(
                    {
                        "name": item["name"],
                        "id": item["artifact_id"],  # Map artifact_id to id for API response
                        "type": artifact_type
                    }
                )

        return artifacts

    except Exception as e:
        logger.warning(f"DynamoDB query failed: {e}")
        return []
