"""
Lambda function for POST /artifact/byRegEx endpoint
Search artifacts using regular expressions.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, TypeAlias

import boto3  # type: ignore[import-untyped]
from src.logger import logger

# DynamoDB table configuration
TABLE_NAME = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

# Single, explicit type alias (only defined once)
ArtifactMetadata: TypeAlias = Dict[str, Any]


def validate_token(token: str) -> bool:
    """Stub AuthenticationToken validator."""
    return bool(token) and token.lower().startswith("bearer ")


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely parse the JSON body from the API Gateway event.

    Expected fields (All are optional except pattern):
    - pattern / regex: regular expression string (required)
    - artifact_type / type: filter by artifact_type ("model", "dataset", "code")
    - limit: maximum number of results to return
    """
    raw_body = event.get("body") or "{}"

    # Some integrations may give a dict already
    if isinstance(raw_body, dict):
        return raw_body

    if isinstance(raw_body, str):
        try:
            return json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            logger.warning(
                "Invalid JSON body for /artifact/byRegEx; using empty body instead"
            )

    return {}


def search_artifacts_by_regex(
    pattern: str,
    artifact_type_filter: Optional[str] = None,
    limit: int = 50,
) -> List[ArtifactMetadata]:
    """
    Scan the DynamoDB table and return artifacts whose name/metadata
    match the provided regular expression.
    """
    try:
        regex = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}") from exc

    results: List[ArtifactMetadata] = []
    scan_kwargs: Dict[str, Any] = {}

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])

        for item in items:
            # Safely pull and type-check fields
            name = item.get("name")
            artifact_id = item.get("artifact_id")
            artifact_type_value = item.get("artifact_type")

            if not isinstance(name, str) or not isinstance(artifact_id, str):
                continue

            if not isinstance(artifact_type_value, str):
                continue

            artifact_type = artifact_type_value.lower()

            if artifact_type_filter and artifact_type != artifact_type_filter:
                continue

            # Build searchable text from strings only
            searchable_parts: List[str] = [name]

            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                for value in metadata.values():
                    if isinstance(value, str):
                        searchable_parts.append(value)

            searchable_text = "\n".join(searchable_parts)

            if not regex.search(searchable_text):
                continue

            results.append(
                {
                    "name": name,
                    "id": artifact_id,
                    "type": artifact_type,
                }
            )

            if len(results) >= limit:
                return results

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return results


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for POST /artifact/byRegEx - Search for artifacts by regex.
    """
    logger.info("Received POST /artifact/byRegEx request")

    headers = event.get("headers") or {}
    auth_token = headers.get("X-Authorization")

    if not auth_token or not validate_token(auth_token):
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Authentication failed"}),
        }

    body = _parse_body(event)

    pattern_value = body.get("pattern") or body.get("regex")
    if not isinstance(pattern_value, str) or not pattern_value:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing regex pattern in request body"}),
        }

    raw_type = body.get("artifact_type") or body.get("type")
    artifact_type_filter: Optional[str] = None
    if isinstance(raw_type, str):
        artifact_type_filter = raw_type.lower()

    # OPTIONAL LIMIT PARAMETER
    limit_raw = body.get("limit", 50)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 50

    try:
        artifacts = search_artifacts_by_regex(
            pattern_value,
            artifact_type_filter=artifact_type_filter,
            limit=limit,
        )
    except ValueError as exc:
        # Invalid regex pattern
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(exc)}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(artifacts),
    }
