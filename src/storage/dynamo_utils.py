"""
Utility functions for interacting with DynamoDB, including scanning tables,
batch deleting items, and clearing entire tables.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from src.aws.clients import get_ddb_table


# -----------------------------------------------------------------------------
# Scan a table and return all items
# -----------------------------------------------------------------------------
def scan_table(table_name: str) -> List[Dict[str, Any]]:
    """
    Scan an entire DynamoDB table and return all items.

    Args:
        table_name: Name of the DynamoDB table.

    Returns:
        List of raw DynamoDB item dictionaries.
    """
    table = get_ddb_table(table_name)

    results: List[Dict[str, Any]] = []
    response = table.scan()
    items = response.get("Items", [])
    results.extend(items)

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items = response.get("Items", [])
        results.extend(items)

    return results


# -----------------------------------------------------------------------------
# Batch delete by key list
# -----------------------------------------------------------------------------
def batch_delete(
    table_name: str, items: Iterable[Dict[str, Any]], key_name: str
) -> int:
    """
    Batch delete a list of items from a DynamoDB table.

    Args:
        table_name: DynamoDB table name.
        items: Iterable of DynamoDB item dictionaries.
        key_name: Attribute name of the partition key for deletion.

    Returns:
        int: Number of items deleted.
    """
    table = get_ddb_table(table_name)
    count = 0

    with table.batch_writer() as batch:
        for item in items:
            if key_name not in item:
                # Skip malformed items instead of failing
                continue
            batch.delete_item(Key={key_name: item[key_name]})
            count += 1

    return count


# -----------------------------------------------------------------------------
# Clear an entire DynamoDB table
# -----------------------------------------------------------------------------
def clear_table(table_name: str, key_name: str) -> int:
    """
    Delete all items in a DynamoDB table.

    Args:
        table_name: DynamoDB table name.
        key_name: Attribute name of the partition key.

    Returns:
        int: Number of items deleted.
    """
    items = scan_table(table_name)
    return batch_delete(table_name, items, key_name)
