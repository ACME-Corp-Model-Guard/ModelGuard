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

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from botocore.exceptions import ClientError
from src.aws.clients import get_ddb_table
from src.logutil import clogger


# =============================================================================
# DynamoDB Type Conversion
# =============================================================================
def _convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility.

    DynamoDB doesn't support Python float type - it requires Decimal for numbers.
    This function walks through nested dictionaries and lists, converting all
    floats to Decimal while preserving other types.

    Args:
        obj: Object to convert (can be dict, list, float, or any other type)

    Returns:
        Converted object with all floats replaced by Decimals
    """
    if isinstance(obj, float):
        # Handle special float values
        if obj != obj:  # NaN check
            return None
        if obj == float("inf") or obj == float("-inf"):
            return None
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj


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
    fields: Dict[str, Any],  # multiple fields to match
    item_list: Optional[
        List[Dict[str, Any]]
    ] = None,  # item_list can be used to avoid a full table scan
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
            if row.get(field_name) != field_value:
                break
        else:
            matches.append(row)

    return matches


def save_item_to_table(table_name: str, item: Dict[str, Any]) -> None:
    """
    Save a generic item to a DynamoDB table.

    Automatically converts all float values to Decimal for DynamoDB compatibility.
    """
    table = get_ddb_table(table_name)
    try:
        # Convert floats to Decimal before saving
        item = _convert_floats_to_decimal(item)
        table.put_item(Item=item)
        clogger.info(f"[DDB] Saved item to {table_name}")
    except ClientError as e:
        clogger.error(f"[DDB] Failed to save item to {table_name}: {e}")
        raise


def load_item_from_key(
    table_name: str, key: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Load a generic item from a DynamoDB table by its key.
    """
    table = get_ddb_table(table_name)
    try:
        response = table.get_item(Key=key)
        item = response.get("Item")
        if item:
            clogger.info(f"[DDB] Loaded item from {table_name} with key={key}")
        else:
            clogger.warning(f"[DDB] No item found in {table_name} with key={key}")
        return item
    except ClientError as e:
        clogger.error(
            f"[DDB] Failed to load item from {table_name} with key={key}: {e}"
        )
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
