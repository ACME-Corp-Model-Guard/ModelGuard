

"""
Lambda function for POST /artifact/byRegEx endpoint
Search artifacts using regular expressions.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

import boto3 # type: ignore[import-untyped]
# from loguru import logger
from src.logger import logger

# DynamoDB table configuration
TABLE_NAME = os.environ.get("ARTIFACTS_TABLE", "ModelGuard-Artifacts-Metadata")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

ArtifactMetadata = Dict[str, Any]


def validate_token(token: str) -> bool:
    """
    Stub AuthenticationToken validator.
    Just checks that the header is present and looks like a bearer token.
    """
    return bool(token) and token.lower().startwith("bearer: ")


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
            logger.warning("Invalid JSON body for /artifact/byRegEx; using empty body instead")

    return {}


def search_artifacts_by_regex(
        pattern: str,
        artifact_type_filter: Optional[str] = None,
        limit: int = 50
) -> List[ArtifactMetadata]:
    """
    Scan the DynamoDB table and return artifacts whose name/metadata 
    match the provided information/regular expression
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
            name = item.get("name")
            artifact_id = item.get("artifact_id")
            artifact_type = (item.get("artifact_type") or "").lower()

            if not (name and artifact_id and artifact_type):
                continue

            if artifact_type_filter:
                if artifact_type != artifact_type_filter.lower():
                    continue

            # Create a searchable string from name + metadata values
            searchable_parts = [name]
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
                    "type": artifact_type
                }
            )

            if len(results) >= limit:
                return results
        
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return results
    
def lambda_handler(event: Dict[str, Any], contect: Any) -> Dict[str, Any]:
    """
    Handler for POST /artifact/byRegEx - Search for artifacts by regex.
    """
    logger.info("Received POST /artifact/byRegEx request")

    headers = event.get("headers") or {}
    auth_token = headers.get("X-Authorization")

    if not auth_token or not validate_token(auth_token):
        return {
            "statusCCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Authentication failed"})
        }
    
    body = _parse_body(event)

    pattern = body.get("pattern") or body.get("regex")
    if not pattern:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing regex pattern in request body"})
        }
    
    artifact_type_filter = body.get("artifact_type") or body.get("type")



    #### OPTIONAL LIMIT PARAMETER - REMOVE IF NOT NECESSARY ####
    limit_raw = body.get("limit", 50)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 50

    try:
        artifacts = search_artifacts_by_regex(
            str(pattern),
            artifact_type_filter = artifact_type_filter,
            limit = limit
        )
    except ValueError as exc:
        # Invalid regex pattern
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(exc)})
        }
    
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(artifacts)
    }







