"""
Lambda function for POST /artifacts endpoint
Enumerate/List artifacts from the registry
"""

import json
from typing import Any, Dict, List

import boto3  # type: ignore[import-untyped]
from loguru import logger

# DynamoDB Table configuration
TABLE_NAME = "ModelGuard-Artifacts-Metadata"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)  

ArtifactMetadata = Dict[str, Any]  


def validate_token(token: str) -> bool:  
    """
    Validate the AuthenticationToken (stub implementation).  
    Mirrors the behavior of the GET /artifact/byName/{name} lambda.  
    """  
    # TODO: Replace with real Cognito / JWT validation  
    return token.startswith("bearer ")  


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
                # Validate required fields before mapping  
                if (  
                    "name" in item  
                    and "artifact_id" in item  
                    and "artifact_type" in item  
                ):  
                    artifact_type = item["artifact_type"]  
                    if artifact_type not in {"model", "dataset", "code"}:  
                        continue  # Skip invalid / unsupported types  

                    artifacts.append(  
                        {  
                            "name": item["name"],  
                            "id": item["artifact_id"],  # Map artifact_id -> id  
                            "type": artifact_type,  
                        }  
                    )  

            # Handle pagination if the scan is larger than 1 MB  
            last_key = response.get("LastEvaluatedKey")  
            if not last_key:  
                break  
            scan_kwargs["ExclusiveStartKey"] = last_key  

    except Exception as e:  
        logger.warning(f"DynamoDB scan failed: {e}")  

    return artifacts  


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for POST /artifacts - Enumerate artifacts.
    Returns a list of artifacts from the registry.
    """
    logger.info("Received POST /artifacts request")  

    # Extract headers and validate AuthenticationToken  
    headers = event.get("headers") or {}  
    auth_token = headers.get("X-Authorization")  

    if not auth_token or not validate_token(auth_token):  
        return {  
            "statusCode": 403,  
            "headers": {"Content-Type": "application/json"},  
            "body": json.dumps({"error": "Authentication failed"}),  
        }  

    # For now we ignore the request body and simply enumerate all artifacts.  
    artifacts = list_artifacts()  

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(artifacts),
    }
