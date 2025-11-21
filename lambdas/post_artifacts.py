"""
Lambda function for POST /artifacts endpoint
Enumerate/List artifacts from the registry
"""

import json
import os
from typing import Any, Dict, List

import boto3  # type: ignore[import-untyped]

# from loguru import logger
from src.logger import logger


# DynamoDB table configuration <- comes from template.yaml
TABLE_NAME = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


ArtifactMetadata = Dict[str, Any]


def validate_token(token: str) -> bool:
    """
    Validate the AuthenticationToken (stub implementation).
    """
    return bool(token) and token.lower().startswith("bearer ")


def list_artifacts() -> List[ArtifactMetadata]:
    """
    Scan the DynamoDB table and return all artifacts in the
    simplified OpenAPI response shape.
    """
    artifacts: List[ArtifactMetadata] = []
    scan_kwargs: Dict[str, Any] = {}

    try:
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get("Items", [])

            for item in items:
                name = item.get("name")
                artifact_id = item.get("artifact_id")
                artifact_type_value = item.get("artifact_type")

                # Only accept proper strings
                if not isinstance(name, str) or not isinstance(artifact_id, str):
                    continue

                if not isinstance(artifact_type_value, str):
                    continue

                artifact_type = artifact_type_value.lower()

                if artifact_type not in {"model", "dataset", "code"}:
                    continue

                artifacts.append(
                    {
                        "name": name,
                        "id": artifact_id,
                        "type": artifact_type,
                    }
                )

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
    except Exception as exc:
        logger.warning(f"DynamoDB scan failed in POST /artifacts: {exc}")

    return artifacts


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for POST /artifacts - Enumerate artifacts.
    Returns a list of artifacts from the registry.
    """

    logger.info("received POST /artifacts request")

    # Extract headers and validate Authentication
    headers = event.get("headers") or {}
    auth_token = headers.get("X-Authorization")

    if not auth_token or not validate_token(auth_token):
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Authentication failed"}),
        }

    # Ignore the request body, only enumerate all artifacts
    artifacts = list_artifacts()

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(artifacts),
    }
