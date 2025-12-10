"""
HuggingFace artifact download utilities.

This module downloads a HuggingFace model or dataset snapshot, bundles it
into a local .tar.gz archive, and returns the path to that temporary file.

It is used during artifact ingestion before uploading artifacts to S3.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Optional

import requests

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
    """
    Download a HuggingFace model/dataset and package it into a tar.gz archive.

    Args:
        source_url: HuggingFace URL (e.g., "https://huggingface.co/owner/repo")
        artifact_id: Artifact ID for logging
        artifact_type: "model" or "dataset" (NOT "code")

    Returns:
        str: Local path to temporary .tar.gz file

    Raises:
        FileDownloadError: If URL parsing fails, HF download fails, or packaging fails
    """

    logger.info(f"[HF] Downloading artifact {artifact_id} from {source_url}")

    if artifact_type == "code":
        raise FileDownloadError("Code artifacts cannot be downloaded from HuggingFace")

    cache_dir: Optional[str] = None

    try:
        # Import huggingface_hub lazily
        try:
            from huggingface_hub import snapshot_download  # type: ignore
            from huggingface_hub.errors import (  # type: ignore
                RepositoryNotFoundError,
                RevisionNotFoundError,
            )
        except ImportError:
            raise FileDownloadError(
                "huggingface_hub is required. Install via: pip install huggingface_hub"
            )

        # Configure HuggingFace to use /tmp for all caching and logging
        # This prevents "Read-only file system" errors in Lambda environment
        os.environ["HF_HOME"] = "/tmp/.cache/huggingface"

        # ------------------------------------------------------------
        # Parse HuggingFace repo ID from URL
        # ------------------------------------------------------------
        # URL examples:
        #   https://huggingface.co/owner/model
        #   https://huggingface.co/owner/dataset
        #
        # We want: "owner/model"
        # ------------------------------------------------------------
        parts = source_url.rstrip("/").split("huggingface.co/")
        if len(parts) < 2:
            raise FileDownloadError(f"Invalid HuggingFace URL: {source_url}")

        repo_path = parts[1].split("/")
        if len(repo_path) < 2:
            raise FileDownloadError(f"Invalid HuggingFace repository URL: {source_url}")

        repo_id = f"{repo_path[0]}/{repo_path[1]}"

        logger.debug(f"[HF] Parsed repo_id={repo_id} from source={source_url}")

        # Download HF snapshot into temporary directory (explicitly use /tmp for Lambda)
        cache_dir = tempfile.mkdtemp(dir="/tmp", prefix=f"hf_{artifact_id}_")

        snapshot_path = snapshot_download(
            repo_id=repo_id,
            repo_type=artifact_type,  # "model" or "dataset"
            cache_dir=cache_dir,
            local_dir=cache_dir,
        )

        # Package into tar archive (explicitly use /tmp for Lambda)
        import tarfile

        tar_path = tempfile.NamedTemporaryFile(
            delete=False, suffix=".tar.gz", dir="/tmp"
        ).name

        logger.debug(f"[HF] Packaging snapshot into tar archive: {tar_path}")

        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(snapshot_path, arcname=os.path.basename(snapshot_path))

        logger.info(f"[HF] Successfully downloaded {artifact_id} → {tar_path}")

        return tar_path

    except RepositoryNotFoundError:
        raise FileDownloadError(f"HuggingFace repository '{repo_id}' not found")

    except RevisionNotFoundError as e:
        raise FileDownloadError(f"HuggingFace revision not found: {e}")

    except Exception as e:
        logger.error(f"[HF] Download failed: {e}")
        raise FileDownloadError(f"HuggingFace download failed: {e}")

    finally:
        # Clean up temporary cache directory
        if cache_dir and os.path.exists(cache_dir):
            try:
                import shutil

                shutil.rmtree(cache_dir)
                logger.debug(f"[HF] Cleaned up HF cache: {cache_dir}")
            except Exception as cleanup_err:
                logger.warning(
                    f"[HF] Failed to clean up HF cache dir {cache_dir}: {cleanup_err}"
                )


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
