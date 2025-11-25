"""
Unified DynamoDB utilities for ModelGuard.

This module centralizes ALL DynamoDB interactions:
- Scanning tables
- Searching by fields
- Saving items to tables
- Loading items by key
- Batch deletes
- Clearing/resetting tables
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from botocore.exceptions import ClientError
from src.aws.clients import get_ddb_table
from src.logger import logger

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


def search_table_by_fields(
    table_name: str,
    fields: Dict[str, Any], # multiple fields to match
    item_list: Optional[List[Dict[str, Any]]] = None, # item_list can be used to avoid a full table scan
) -> List[Dict[str, Any]]:
    """
    Search a DynamoDB table for items matching specific field values.

    Args:
        table_name: Name of the DynamoDB table to search.
        fields: Dictionary of field names and their expected values.
        item_list: Optional list of items to search within (avoids full table scan).
    """
    if not item_list:
        rows = scan_table(table_name=table_name)
    else:
        rows = item_list
    matches: List[Dict[str, Any]] = []

    for row in rows:
        for field_name, field_value in fields.items():
            # Convert strings to lowercase for case-insensitive comparison
            if isinstance(field_value, str) and isinstance(row.get(field_name), str):
                field_value = field_value.lower()
                row_value = row.get(field_name).lower() 
            else:
                row_value = row.get(field_name)
            if row_value != field_value:
                break
        else:
            matches.append(row)

    return matches

def save_item_to_table(table_name: str, item: Dict[str, Any]) -> None:
    """
    Save a generic item to a DynamoDB table.
    """
    table = get_ddb_table(table_name)
    try:
        table.put_item(Item=item)
        logger.info(f"[DDB] Saved item to {table_name}")
    except ClientError as e:
        logger.error(f"[DDB] Failed to save item to {table_name}: {e}", exc_info=True)
        raise

def load_item_from_key(table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Load a generic item from a DynamoDB table by its key.
    """
    table = get_ddb_table(table_name)
    try:
        response = table.get_item(Key=key)
        item = response.get("Item")
        if item:
            logger.info(f"[DDB] Loaded item from {table_name} with key={key}")
        else:
            logger.warning(f"[DDB] No item found in {table_name} with key={key}")
        return item
    except ClientError as e:
        logger.error(f"[DDB] Failed to load item from {table_name} with key={key}: {e}", exc_info=True)
        raise

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