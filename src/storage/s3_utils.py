"""
S3 storage utilities for artifact files.
This module provides:
- Uploading local files to S3
- Downloading S3 files locally
- Generating presigned download URLs
- Bulk deletion utilities (clear_bucket, delete_prefix, delete_objects)
"""

from __future__ import annotations

import os
from typing import Iterable, Optional

from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef
from botocore.exceptions import ClientError

from src.artifacts.types import ArtifactType
from src.aws.clients import get_s3
from src.logger import logger
from src.settings import ARTIFACTS_BUCKET
from src.storage.downloaders.dispatchers import (
    FileDownloadError as SourceDownloadError,
    download_artifact,
)


# =====================================================================================
# Upload / Download
# =====================================================================================
def upload_file(s3_key: str, local_path: str) -> None:
    """
    Upload a local file to the configured S3 bucket.
    """
    s3: S3Client = get_s3()

    try:
        logger.debug(f"Uploading file to s3://{ARTIFACTS_BUCKET}/{s3_key}")
        s3.upload_file(local_path, ARTIFACTS_BUCKET, s3_key)
        logger.info(f"Upload successful: s3://{ARTIFACTS_BUCKET}/{s3_key}")
    except ClientError as e:
        logger.error(f"Failed to upload file to S3: {e}", exc_info=True)
        raise


def download_file(s3_key: str, local_path: str) -> None:
    """
    Download an S3 object to the local filesystem.
    """
    s3: S3Client = get_s3()

    logger.debug(f"Downloading s3://{ARTIFACTS_BUCKET}/{s3_key} -> {local_path}")

    try:
        s3.download_file(ARTIFACTS_BUCKET, s3_key, local_path)
        logger.info(f"Downloaded: s3://{ARTIFACTS_BUCKET}/{s3_key}")
    except ClientError as e:
        logger.error(
            f"Failed to download s3://{ARTIFACTS_BUCKET}/{s3_key}: {e}",
            exc_info=True,
        )
        raise


def generate_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for accessing an S3 object.
    """
    s3: S3Client = get_s3()

    logger.debug(
        f"Generating presigned URL for s3://{ARTIFACTS_BUCKET}/{s3_key} "
        f"(expires in {expiration}s)"
    )

    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": ARTIFACTS_BUCKET, "Key": s3_key},
            ExpiresIn=expiration,
        )
        logger.info(f"Presigned URL generated for {s3_key}, expires={expiration}s")
        return url
    except ClientError as e:
        logger.error(
            f"Failed to generate presigned URL for {s3_key}: {e}",
            exc_info=True,
        )
        raise


# =====================================================================================
# High-level: Download → Upload to S3
# =====================================================================================
def upload_artifact_to_s3(
    artifact_id: str,
    artifact_type: ArtifactType,
    s3_key: str,
    source_url: str,
) -> None:
    """
    Download an artifact from its original source and upload to S3.
    """

    if not ARTIFACTS_BUCKET:
        raise ValueError("ARTIFACTS_BUCKET environment variable not set")

    logger.info(
        f"[s3_utils] Fetching upstream artifact {artifact_id} "
        f"from {source_url} → s3://{ARTIFACTS_BUCKET}/{s3_key}"
    )

    tmp_path: Optional[str] = None

    try:
        # 1. Source download → temp tarball
        tmp_path = download_artifact(
            source_url=source_url,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
        )

        if tmp_path is None:
            raise RuntimeError("download_artifact() returned None unexpectedly")

        # 2. Upload to S3
        upload_file(s3_key, tmp_path)
        logger.info(
            f"[s3_utils] Uploaded artifact {artifact_id} "
            f"to s3://{ARTIFACTS_BUCKET}/{s3_key}"
        )

    except SourceDownloadError:
        raise
    except ClientError:
        logger.error(f"[s3_utils] Failed to upload {artifact_id} to S3", exc_info=True)
        raise
    except Exception:
        logger.error(
            f"[s3_utils] Unexpected error uploading artifact {artifact_id}",
            exc_info=True,
        )
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
                logger.debug(f"[s3_utils] Removed temp file: {tmp_path}")
            except Exception:
                logger.warning(f"[s3_utils] Failed to remove temp file: {tmp_path}")


# =====================================================================================
# High-level: S3 → Local file
# =====================================================================================
def download_artifact_from_s3(
    artifact_id: str,
    s3_key: str,
    local_path: str,
) -> None:
    """
    Download an artifact from S3 into a local file.
    """
    if not ARTIFACTS_BUCKET:
        raise ValueError("ARTIFACTS_BUCKET environment variable not set")

    logger.debug(
        f"[s3_utils] Downloading artifact {artifact_id}: "
        f"s3://{ARTIFACTS_BUCKET}/{s3_key} → {local_path}"
    )

    download_file(s3_key, local_path)


# =====================================================================================
# High-level: Generate S3 download URL
# =====================================================================================
def generate_s3_download_url(
    artifact_id: str,
    s3_key: str,
    expiration: int = 3600,
) -> str:
    """
    Generate a pre-signed URL that gives temporary access to an artifact.
    """
    if not ARTIFACTS_BUCKET:
        raise ValueError("ARTIFACTS_BUCKET environment variable not set")

    logger.debug(
        f"[s3_utils] Generating presigned URL for {artifact_id}: "
        f"s3://{ARTIFACTS_BUCKET}/{s3_key}"
    )

    return generate_presigned_url(s3_key, expiration)


# =====================================================================================
# Bulk Deletion Utilities
# =====================================================================================
def clear_bucket(bucket_name: str) -> int:
    """
    Delete *all* objects in an S3 bucket.
    Returns the number of objects deleted.
    """
    s3: S3Client = get_s3()
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name)

    delete_count = 0

    for page in pages:
        contents = page.get("Contents", [])
        if not contents:
            continue

        objects: list[ObjectIdentifierTypeDef] = [
            ObjectIdentifierTypeDef(Key=obj["Key"]) for obj in contents
        ]

        s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})
        delete_count += len(objects)

    return delete_count


def delete_prefix(bucket_name: str, prefix: str) -> int:
    """
    Delete all objects under a given prefix.
    """
    s3: S3Client = get_s3()

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    delete_count = 0

    for page in pages:
        contents = page.get("Contents", [])
        if not contents:
            continue

        objects: list[ObjectIdentifierTypeDef] = [
            ObjectIdentifierTypeDef(Key=obj["Key"]) for obj in contents
        ]

        s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})
        delete_count += len(objects)

    return delete_count


def delete_objects(bucket_name: str, keys: Iterable[str]) -> int:
    """
    Delete a specific list of S3 object keys.
    """
    s3: S3Client = get_s3()

    key_list: list[ObjectIdentifierTypeDef] = [
        ObjectIdentifierTypeDef(Key=key) for key in keys
    ]

    if not key_list:
        return 0

    s3.delete_objects(
        Bucket=bucket_name,
        Delete={"Objects": key_list},
    )

    return len(key_list)
