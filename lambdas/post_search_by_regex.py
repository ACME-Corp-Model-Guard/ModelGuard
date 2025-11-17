"""
Lambda function for POST /artifact/byRegEx endpoint
Search artifacts using regular expressions
"""

import json
import re
from typing import Any, Dict, List, Optional

import boto3
from loguru import logger

# DynamoDB table configuration
TABLE_NAME = "ModelGuard-Artifacts-Metadata"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

ArtifactMetadata = Dict[str, Any]

#--------------------------------------------------------------------------
# COMMENETED OUT THIS EXISTING SECTION IN CASE NEEDED LATER.
#
# def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
#     """
#     Stub handler for POST /artifact/byRegEx - Search by regex
#     Search for artifacts using regular expression over names and READMEs
#     """
#     return {
#         "statusCode": 200,
#         "headers": {"Content-Type": "application/json"},
#         "body": json.dumps(
#             [
#                 {"name": "audience-classifier", "id": "3847247294", "type": "model"},
#                 {"name": "bert-base-uncased", "id": "9078563412", "type": "model"},
#             ]
#         ),
#     }
#
#--------------------------------------------------------------------------


def validate_token(token: str) -> bool:
    """
    Stub AuthenticationToken validator.
    Mirrors the behavior used in GET /artifact/byName/{name}.
    """
    
    """
    TODO: replace with real Cognito / JWT validation
    """

    return token.startswith("bearer ")


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely parse the JSON body from the API Gateway event.
    Expected fields (all optional except the pattern):
      - pattern / regex: regular expression string
      - artifact_type / type: filter by artifact_type ("model", "dataset", "code")
      - limit: maximum number of results to return
    """
    raw_body = event.get("body") or "{}"

    if isinstance(raw_body, dict):
        return raw_body

    if isinstance(raw_body, str):
        try:
            return json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            logger.warning("Invalid JSON body for /artifact/byRegEx; using empty body")

    return {}


def search_artifacts_by_regex(  
    pattern: str, artifact_type_filter: Optional[str] = None, limit: int = 50
) -> List[ArtifactMetadata]:
    """
    Scan the DynamoDB table and return artifacts whose name/metadata  
    match the provided regular expression.  
    """  
    try:  
        regex = re.compile(pattern, re.IGNORECASE)  
    except re.error as exc:  
        raise ValueError(f"Invalid regular expression: {exc}") from exc  

    results: List[ArtifactMetadata] = []  
    scan_kwargs: Dict[str, Any] = {}  

    try:  
        while True:  
            response = table.scan(**scan_kwargs)  
            items = response.get("Items", [])  

            for item in items:  
                artifact_type = item.get("artifact_type")  
                if artifact_type not in {"model", "dataset", "code"}:  
                    continue  # Skip unsupported/invalid types  

                if artifact_type_filter and artifact_type != artifact_type_filter:  
                    continue  # Filter by artifact_type if provided  

                # Build a searchable text blob from name + any string metadata  
                name = str(item.get("name", ""))  
                searchable_parts = [name]  

                metadata = item.get("metadata")  
                if isinstance(metadata, dict):  
                    for value in metadata.values():  
                        if isinstance(value, str):  
                            searchable_parts.append(value)  

                searchable_text = "\n".join(searchable_parts)  

                if not regex.search(searchable_text):  
                    continue  

                artifact_id = item.get("artifact_id")  
                if not artifact_id:  
                    continue  

                results.append(  
                    {  
                        "name": name,  
                        "id": artifact_id,  # Map artifact_id -> id for API response  
                        "type": artifact_type,  
                    }  
                )  

                if len(results) >= limit:  
                    return results  

            # Handle pagination  
            last_key = response.get("LastEvaluatedKey")  
            if not last_key:  
                break  
            scan_kwargs["ExclusiveStartKey"] = last_key  

    except Exception as e:  
        logger.warning(f"DynamoDB scan failed during regex search: {e}")

    return results


