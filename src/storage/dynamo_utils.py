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

# This is likely innefficient
def search_table_by_field(table_name: str, field_name: str, field_value: Any) -> List[Dict[str, Any]]:
    rows = scan_table(table_name=table_name)
    match: Optional[Dict[str, Any]] = None

    for row in rows:
        if row.get(field_name) == field_value:
            match = row
            break

    return match

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
