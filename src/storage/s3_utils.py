"""
Utility functions for interacting with S3, including bulk deletion,
prefix-based deletion, and paginated listing.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

from botocore.client import BaseClient

from src.aws.clients import get_s3


# -----------------------------------------------------------------------------
# Delete ALL objects in an S3 bucket
# -----------------------------------------------------------------------------
def clear_bucket(bucket_name: str) -> int:
    """
    Delete all objects in an S3 bucket.

    Returns:
        int: Number of objects deleted.

    Raises:
        RuntimeError: If S3 client is unavailable.
    """
    s3: BaseClient = get_s3()

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name)

    delete_count = 0

    for page in pages:
        contents = page.get("Contents", [])
        if not contents:
            continue

        objects: List[Dict[str, str]] = [{"Key": obj["Key"]} for obj in contents]

        s3.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": objects},
        )

        delete_count += len(objects)

    return delete_count


# -----------------------------------------------------------------------------
# Delete all objects with a given prefix
# -----------------------------------------------------------------------------
def delete_prefix(bucket_name: str, prefix: str) -> int:
    """
    Delete all objects in a bucket that begin with the specified prefix.

    Returns:
        int: Number of objects deleted.
    """
    s3: BaseClient = get_s3()

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    delete_count = 0

    for page in pages:
        contents = page.get("Contents", [])
        if not contents:
            continue

        objects: List[Dict[str, str]] = [{"Key": obj["Key"]} for obj in contents]

        s3.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": objects},
        )

        delete_count += len(objects)

    return delete_count


# -----------------------------------------------------------------------------
# Delete an explicit list of keys
# -----------------------------------------------------------------------------
def delete_objects(bucket_name: str, keys: Iterable[str]) -> int:
    """
    Delete a specific iterable of object keys from an S3 bucket.

    Args:
        bucket_name: The name of the S3 bucket.
        keys: Iterable of object key strings.

    Returns:
        int: Number of objects deleted (length of the iterable).

    Raises:
        RuntimeError: If S3 client is unavailable.
    """
    s3: BaseClient = get_s3()

    key_list: List[Dict[str, str]] = [{"Key": key} for key in keys]

    if not key_list:
        return 0

    s3.delete_objects(
        Bucket=bucket_name,
        Delete={"Objects": key_list},
    )

    return len(key_list)
