"""
DynamoDB storage utilities for artifact metadata.
"""

import os
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any

from src.logger import logger


def save_artifact_to_dynamodb(artifact_dict: Dict[str, Any]) -> None:
    """
    Save artifact metadata to DynamoDB.
    Uses ARTIFACTS_TABLE environment variable for table name.

    Args:
        artifact_dict: Artifact dictionary (from to_dict())

    Raises:
        ValueError: If ARTIFACTS_TABLE env var not set
        ClientError: If DynamoDB save fails
    """
    table_name = os.getenv("ARTIFACTS_TABLE")
    if not table_name:
        logger.error("ARTIFACTS_TABLE env var not set")
        raise ValueError("ARTIFACTS_TABLE env var must be set")

    artifact_id = artifact_dict.get("artifact_id", "unknown")
    logger.debug(f"Saving artifact {artifact_id} to DynamoDB table: {table_name}")

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        table.put_item(Item=artifact_dict)
        logger.info(f"Successfully saved artifact {artifact_id} to DynamoDB")
    except ClientError as e:
        logger.error(
            f"Failed to save artifact {artifact_id} to DynamoDB: {e}", exc_info=True
        )
        raise
