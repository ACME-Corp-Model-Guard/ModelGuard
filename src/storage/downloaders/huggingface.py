"""
HuggingFace artifact download utilities.

This module downloads a HuggingFace model or dataset snapshot, bundles it
into a local .tar.gz archive, and returns the path to that temporary file.

It is used during artifact ingestion before uploading artifacts to S3.
"""

from __future__ import annotations

import os
import requests
import shutil
import sys
import tarfile
import tempfile
from typing import Any, Dict
from huggingface_hub import snapshot_download
from huggingface_hub.errors import RepositoryNotFoundError, RevisionNotFoundError

from src.artifacts.types import ArtifactType
from src.logger import logger


class FileDownloadError(Exception):
    """Raised when a HuggingFace download fails."""

    pass


# =====================================================================================
# Model/Dataset Download
# =====================================================================================
def download_from_huggingface(
    source_url: str,
    artifact_id: str,
    artifact_type: ArtifactType,
) -> str:
    """Download a HuggingFace model/dataset and package it into a tar.gz archive."""

    logger.info(f"[HF] Downloading artifact {artifact_id} from {source_url}")

    if artifact_type == "code":
        raise FileDownloadError("Code artifacts cannot be downloaded from HuggingFace")

    # Parse repository ID from URL
    parts = source_url.rstrip("/").split("huggingface.co/")
    if len(parts) < 2:
        raise FileDownloadError(f"Invalid HuggingFace URL: {source_url}")

    repo_path_parts = parts[1].split("/")
    if len(repo_path_parts) >= 2:
        repo_id = f"{repo_path_parts[0]}/{repo_path_parts[1]}"
    elif len(repo_path_parts) == 1:
        repo_id = repo_path_parts[0]
    else:
        raise FileDownloadError(f"Invalid HuggingFace repository URL: {source_url}")

    download_dir = None
    tar_path = None

    try:
        # Create temporary download directory
        download_dir = tempfile.mkdtemp(prefix=f"hf_{artifact_id}_", dir="/tmp")

        # Download the repository
        snapshot_download(
            repo_id=repo_id,
            repo_type=artifact_type,
            local_dir=download_dir,
            local_files_only=False,
            ignore_patterns=["*.git*", "*.DS_Store", "*.tmp"],
        )

        # Check download size
        download_size = sum(
            os.path.getsize(os.path.join(root, file))
            for root, _, files in os.walk(download_dir)
            for file in files
        )
        download_size_mb = download_size // (1024**2)

        if download_size_mb > 1000:
            raise FileDownloadError(
                f"Downloaded artifact too large: {download_size_mb}MB (max 1000MB)"
            )

        # Create tar.gz archive
        tar_path = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        with tarfile.open(tar_path, "w:gz") as tar:
            for root, _, files in os.walk(download_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, download_dir)
                    tar.add(file_path, arcname=arcname)

        tar_size_mb = os.path.getsize(tar_path) // (1024**2)
        logger.info(f"Successfully packaged {artifact_id} ({tar_size_mb}MB)")

        return tar_path

    except RepositoryNotFoundError:
        raise FileDownloadError(f"HuggingFace repository '{repo_id}' not found")
    except RevisionNotFoundError as e:
        raise FileDownloadError(f"HuggingFace revision not found: {e}")
    except Exception as e:
        raise FileDownloadError(f"HuggingFace download failed: {e}")

    finally:
        # Clean up download directory
        if download_dir and os.path.exists(download_dir):
            try:
                shutil.rmtree(download_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up download directory: {e}")

        # Clean up tar file on error - sys is now available at module level
        if tar_path and os.path.exists(tar_path) and sys.exc_info()[0] is not None:
            try:
                os.unlink(tar_path)
            except Exception:
                pass


# =====================================================================================
# Model Metadata Download
# =====================================================================================
def fetch_huggingface_model_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch model metadata from HuggingFace Hub API.
    """
    logger.info(f"[HF] Fetching model metadata: {url}")

    try:
        parts = url.rstrip("/").split("huggingface.co/")
        if len(parts) < 2:
            raise ValueError(f"Invalid HuggingFace model URL: {url}")

        model_id = parts[1]
        api_url = f"https://huggingface.co/api/models/{model_id}"

        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        metadata = {
            "name": model_id.split("/")[-1],
            "size": data.get("safetensors", {}).get("total", 0),
            "license": data.get("cardData", {}).get("license", "unknown"),
            "metadata": {
                "downloads": data.get("downloads", 0),
                "likes": data.get("likes", 0),
            },
        }

        return metadata

    except Exception as e:
        logger.error(f"[HF] Failed to fetch model metadata: {e}")
        raise


# =====================================================================================
# Dataset Metadata Download
# =====================================================================================
def fetch_huggingface_dataset_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch dataset metadata from HuggingFace Hub API.
    """
    logger.info(f"[HF] Fetching dataset metadata: {url}")

    try:
        parts = url.rstrip("/").split("huggingface.co/datasets/")
        if len(parts) < 2:
            raise ValueError(f"Invalid HuggingFace dataset URL: {url}")

        dataset_id = parts[1]
        api_url = f"https://huggingface.co/api/datasets/{dataset_id}"

        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        metadata = {
            "name": dataset_id.split("/")[-1],
            "metadata": {
                "downloads": data.get("downloads", 0),
                "likes": data.get("likes", 0),
                "cardData": data.get("cardData", {}),
            },
        }

        return metadata

    except Exception as e:
        logger.error(f"[HF] Failed to fetch dataset metadata: {e}")
        raise
