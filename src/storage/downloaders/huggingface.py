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

# Force HuggingFace to use /tmp for caching in Lambda
os.environ["HF_HOME"] = "/tmp/huggingface"
os.environ["HF_HUB_CACHE"] = "/tmp/huggingface"

from huggingface_hub import snapshot_download  # noqa: E402
from huggingface_hub.errors import (RepositoryNotFoundError)  # noqa: E402
from huggingface_hub.errors import (RevisionNotFoundError)  # noqa: E402
from src.artifacts.types import ArtifactType  # noqa: E402
from src.logger import logger  # noqa: E402


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

    # Clean up /tmp at start to ensure space
    _cleanup_tmp_space()

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
        # Check available space before starting
        free_mb = _get_free_space_mb()
        if free_mb < 100:
            raise FileDownloadError(f"Insufficient disk space: {free_mb}MB available")

        # Create unique cache directory per invocation
        unique_cache_dir = f"/tmp/hf_cache_{artifact_id}_{os.getpid()}"
        os.makedirs(unique_cache_dir, exist_ok=True)

        # Create temporary download directory
        download_dir = tempfile.mkdtemp(prefix=f"hf_{artifact_id}_", dir="/tmp")

        # Download the repository with isolated cache
        snapshot_download(
            repo_id=repo_id,
            repo_type=artifact_type,
            local_dir=download_dir,
            local_files_only=False,
            ignore_patterns=["*.git*", "*.DS_Store", "*.tmp"],
            cache_dir=unique_cache_dir,
        )

        # Check download size
        download_size = sum(
            os.path.getsize(os.path.join(root, file))
            for root, _, files in os.walk(download_dir)
            for file in files
        )
        download_size_mb = download_size // (1024**2)

        # Reduced limit for Lambda constraints
        if download_size_mb > 350:
            raise FileDownloadError(
                f"Downloaded artifact too large: {download_size_mb}MB (max 350MB for Lambda)"
            )

        # Create tar.gz archive
        tar_path = tempfile.NamedTemporaryFile(
            delete=False, suffix=".tar.gz", dir="/tmp"
        ).name

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
        # ALWAYS clean up, regardless of success/failure
        _cleanup_download_artifacts(
            download_dir,
            unique_cache_dir if "unique_cache_dir" in locals() else None,
            tar_path if sys.exc_info()[0] is not None else None,
        )


def _cleanup_tmp_space():
    """Clean up /tmp directory to ensure available space."""
    try:
        # Remove old HuggingFace cache directories
        import glob

        for old_cache in glob.glob("/tmp/hf_cache_*"):
            try:
                shutil.rmtree(old_cache)
                logger.debug(f"Cleaned up old cache: {old_cache}")
            except Exception:
                pass

        # Remove old temp directories
        for old_temp in glob.glob("/tmp/hf_*"):
            try:
                if os.path.isdir(old_temp):
                    shutil.rmtree(old_temp)
                else:
                    os.unlink(old_temp)
            except Exception:
                pass

        # Clean up global HF cache if it exists and is large
        global_hf_cache = "/tmp/huggingface"
        if os.path.exists(global_hf_cache):
            try:
                cache_size = sum(
                    os.path.getsize(os.path.join(root, file))
                    for root, _, files in os.walk(global_hf_cache)
                    for file in files
                ) // (1024 * 1024)

                if cache_size > 50:  # If > 50MB, remove it
                    shutil.rmtree(global_hf_cache)
                    logger.info(f"Cleaned up large global HF cache: {cache_size}MB")
            except Exception as e:
                logger.warning(f"Failed to clean global HF cache: {e}")

    except Exception as e:
        logger.warning(f"Failed to clean /tmp space: {e}")


def _get_free_space_mb() -> int:
    """Get available free space in /tmp in MB."""
    try:
        total, used, free = shutil.disk_usage("/tmp")
        return free // (1024 * 1024)
    except Exception:
        return 0


def _cleanup_download_artifacts(
    download_dir: str | None, cache_dir: str | None, tar_path: str | None
):
    """Clean up all download artifacts."""
    # Clean up download directory
    if download_dir and os.path.exists(download_dir):
        try:
            shutil.rmtree(download_dir)
            logger.debug(f"Cleaned up download directory: {download_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up download directory: {e}")

    # Clean up cache directory
    if cache_dir and os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            logger.debug(f"Cleaned up cache directory: {cache_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up cache directory: {e}")

    # Clean up tar file on error
    if tar_path and os.path.exists(tar_path):
        try:
            os.unlink(tar_path)
            logger.debug(f"Cleaned up error tar file: {tar_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up tar file: {e}")


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
