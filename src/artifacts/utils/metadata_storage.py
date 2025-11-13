"""
DynamoDB storage utilities for artifact metadata.
"""

import os
import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from typing import Dict, Any, Optional, TYPE_CHECKING

from src.logger import logger

if TYPE_CHECKING:
    from src.artifacts.base_artifact import BaseArtifact


def save_artifact_to_dynamodb(artifact: "BaseArtifact") -> None:
    """
    Save artifact metadata to DynamoDB.
    Uses ARTIFACTS_TABLE environment variable for table name.

    Args:
        artifact: BaseArtifact instance (ModelArtifact, DatasetArtifact, or CodeArtifact)

    Raises:
        ValueError: If ARTIFACTS_TABLE env var not set
        ClientError: If DynamoDB save fails
    """
    # Import here to avoid circular imports - needed at runtime
    from src.artifacts.base_artifact import BaseArtifact

    table_name = os.getenv("ARTIFACTS_TABLE")
    if not table_name:
        logger.error("ARTIFACTS_TABLE env var not set")
        raise ValueError("ARTIFACTS_TABLE env var must be set")

    artifact_id = artifact.artifact_id
    logger.debug(f"Saving artifact {artifact_id} to DynamoDB table: {table_name}")

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # Convert artifact to dictionary for DynamoDB storage
        artifact_dict = artifact.to_dict()
        table.put_item(Item=artifact_dict)

        logger.info(f"Successfully saved artifact {artifact_id} to DynamoDB")
    except ClientError as e:
        logger.error(
            f"Failed to save artifact {artifact_id} to DynamoDB: {e}", exc_info=True
        )
        raise


def load_artifact_from_dynamodb(artifact_id: str) -> Optional["BaseArtifact"]:
    """
    Load artifact metadata from DynamoDB by artifact_id and build artifact object.
    Uses ARTIFACTS_TABLE environment variable for table name.

    Args:
        artifact_id: The ID of the artifact to load.

    Returns:
        A BaseArtifact instance (ModelArtifact, DatasetArtifact, or CodeArtifact)
        or None if artifact not found.

    Raises:
        ValueError: If ARTIFACTS_TABLE env var not set or invalid artifact_type
        ClientError: If DynamoDB load fails
    """
    # Import here to avoid circular imports
    from src.artifacts.base_artifact import BaseArtifact

    table_name = os.getenv("ARTIFACTS_TABLE")
    if not table_name:
        logger.error("ARTIFACTS_TABLE env var not set")
        raise ValueError("ARTIFACTS_TABLE env var must be set")

    logger.debug(f"Loading artifact {artifact_id} from DynamoDB table: {table_name}")

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"artifact_id": artifact_id})
        item = response.get("Item")

        if not item:
            logger.warning(f"Artifact {artifact_id} not found in DynamoDB")
            return None

        logger.info(f"Successfully loaded artifact {artifact_id} from DynamoDB")

        # Extract artifact_type and other fields
        artifact_type = item.get("artifact_type")
        if not artifact_type:
            logger.error(f"Artifact {artifact_id} missing artifact_type field")
            raise ValueError(f"Artifact {artifact_id} has no artifact_type")

        # Build artifact object using factory method
        # Remove artifact_type from kwargs since it's passed separately
        kwargs = dict(item)
        kwargs.pop("artifact_type", None)

        artifact = BaseArtifact.create(artifact_type, **kwargs)
        logger.info(f"Successfully built {artifact_type} artifact: {artifact_id}")
        return artifact

    except ClientError as e:
        logger.error(
            f"Failed to load artifact {artifact_id} from DynamoDB: {e}", exc_info=True
        )
        raise
