"""
Unified DynamoDB utilities for ModelGuard.

This module centralizes ALL DynamoDB interactions:
- Scanning tables
- Batch deletes
- Clearing/resetting tables
- Saving and loading BaseArtifact objects
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from botocore.exceptions import ClientError

from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.types import ArtifactType
from src.aws.clients import get_ddb_table
from src.logger import logger
from src.settings import ARTIFACTS_TABLE


# =============================================================================
# Generic DynamoDB Table Utilities
# =============================================================================
def scan_table(table_name: str) -> List[Dict[str, Any]]:
    """
    Scan an entire DynamoDB table and return all items.
    Handles automatic pagination.
    """
    table = get_ddb_table(table_name)

    results: List[Dict[str, Any]] = []
    response = table.scan()
    results.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        results.extend(response.get("Items", []))

    return results


def search_table_by_field(
    table_name: str,
    field_name: str,
    field_value: Any,
    item_list: Optional[List[Dict[str, Any]]] = None, # item_list can be used to avoid a full table scan
) -> List[Dict[str, Any]]:
    if not item_list:
        rows = scan_table(table_name=table_name)
    else:
        rows = item_list
    matches: List[Dict[str, Any]] = []

    for row in rows:
        if row.get(field_name.lower()) == field_value.lower():
            matches.append(row)

    return matches


def batch_delete(
    table_name: str,
    items: Iterable[Dict[str, Any]],
    key_name: str,
) -> int:
    """
    Batch delete items from a DynamoDB table.
    """
    table = get_ddb_table(table_name)
    count = 0

    with table.batch_writer() as batch:
        for item in items:
            if key_name not in item:
                continue
            batch.delete_item(Key={key_name: item[key_name]})
            count += 1

    return count


def clear_table(table_name: str, key_name: str) -> int:
    """
    Delete all items in a DynamoDB table.
    Returns number of items deleted.
    """
    items = scan_table(table_name)
    return batch_delete(table_name, items, key_name)


# =============================================================================
# Artifact-Specific Metadata Storage Operations
# =============================================================================
def save_artifact_metadata(artifact: BaseArtifact) -> None:
    """
    Store artifact metadata in DynamoDB.
    """
    if not ARTIFACTS_TABLE:
        raise ValueError("ARTIFACTS_TABLE environment variable not set")

    artifact_id = artifact.artifact_id
    logger.debug(f"[DDB] Saving artifact {artifact_id} to {ARTIFACTS_TABLE}")

    try:
        table = get_ddb_table(ARTIFACTS_TABLE)
        table.put_item(Item=artifact.to_dict())
        logger.info(f"[DDB] Saved artifact {artifact_id}")
    except ClientError as e:
        logger.error(f"[DDB] Failed to save {artifact_id}: {e}", exc_info=True)
        raise


def load_artifact_metadata(artifact_id: str) -> Optional[BaseArtifact]:
    """
    Retrieve artifact metadata from DynamoDB and build a BaseArtifact instance.

    Returns:
        BaseArtifact instance or None if not found.
    """
    if not ARTIFACTS_TABLE:
        raise ValueError("ARTIFACTS_TABLE environment variable not set")

    logger.debug(f"[DDB] Loading artifact {artifact_id} from {ARTIFACTS_TABLE}")

    try:
        table = get_ddb_table(ARTIFACTS_TABLE)
        resp = table.get_item(Key={"artifact_id": artifact_id})
        item = resp.get("Item")

        if not item:
            logger.warning(f"[DDB] Artifact {artifact_id} not found")
            return None

        artifact_type = item.get("artifact_type")
        if not artifact_type:
            raise ValueError(f"Artifact {artifact_id} missing artifact_type field")

        # Don't pass artifact_type twice
        kwargs = dict(item)
        kwargs.pop("artifact_type", None)

        artifact = BaseArtifact.create(artifact_type, **kwargs)
        logger.info(f"[DDB] Loaded {artifact_type} artifact {artifact_id}")
        return artifact

    except ClientError as e:
        logger.error(f"[DDB] Failed to load artifact {artifact_id}: {e}", exc_info=True)
        raise

def load_all_artifacts() -> List[BaseArtifact]:
    """
    Load all artifacts from the DynamoDB table.

    Returns:
        List of BaseArtifact instances.
    """
    if not ARTIFACTS_TABLE:
        raise ValueError("ARTIFACTS_TABLE environment variable not set")

    logger.debug(f"[DDB] Loading all artifacts from {ARTIFACTS_TABLE}")

    artifacts: List[BaseArtifact] = []

    try:
        items = scan_table(ARTIFACTS_TABLE)

        for item in items:
            artifact_id = item.get("artifact_id")
            artifact_type = item.get("artifact_type")
            if not artifact_type:
                logger.warning(f"Artifact {artifact_id} missing artifact_type field")
                continue

            # Don't pass artifact_type twice
            kwargs = dict(item)
            kwargs.pop("artifact_type", None)

            artifact = BaseArtifact.create(artifact_type, **kwargs)
            artifacts.append(artifact)

        logger.info(f"[DDB] Loaded {len(artifacts)} artifacts from {ARTIFACTS_TABLE}")
        return artifacts

    except ClientError as e:
        logger.error(f"[DDB] Failed to load all artifacts: {e}", exc_info=True)
        raise

def load_all_artifacts_by_field(
    field_name: str,
    field_value: Any,
    artifact_type: Optional[ArtifactType] = None, # Optional filter by artifact type
    artifact_list: Optional[List[BaseArtifact]] = None, # artifact_list can be used to avoid a full table scan
) -> List[BaseArtifact]:
    """
    Load all artifacts from the DynamoDB table matching a specific field value.

    Args:
        field_name: The name of the field to filter by.
        field_value: The value of the field to match.
        artifact_type: Optional filter by artifact type.
        artifact_list: Optional list of artifacts to search within (avoids full table scan).
    """
    rows : List[BaseArtifact] = []
    if not artifact_list:
        rows = load_all_artifacts()
    else:
        rows = artifact_list
    artifacts: List[BaseArtifact] = []

    for row in rows:
        if artifact_type and row.artifact_type != artifact_type:
            continue

        attribute: Any = getattr(row, field_name, None)
        # Convert strings to lowercase for case-insensitive comparison
        if isinstance(attribute, str):
            attribute = attribute.lower()
        if isinstance(field_value, str):
            field_value = field_value.lower()
        if attribute == field_value:
            artifacts.append(row)
    
    return artifacts

