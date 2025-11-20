"""
Unified artifact download dispatcher.

This module provides a single high-level function:

    download_artifact(source_url, artifact_id, artifact_type)

which determines the correct download backend (HuggingFace, GitHub),
invokes the appropriate downloader, and returns a local .tar.gz path.

All downloaders must return a path to a temporary local file.
"""

from __future__ import annotations

from typing import Any, Dict

from src.artifacts.base_artifact import ArtifactType
from src.logger import logger
from src.storage.downloaders.github import FileDownloadError as GitHubDownloadError
from src.storage.downloaders.github import (
    download_from_github,
    fetch_github_code_metadata,
)
from src.storage.downloaders.huggingface import FileDownloadError as HFDownloadError
from src.storage.downloaders.huggingface import (
    download_from_huggingface,
    fetch_huggingface_dataset_metadata,
    fetch_huggingface_model_metadata,
)


class FileDownloadError(Exception):
    """Raised when no suitable downloader exists or a download fails."""

    pass


# =====================================================================================
# Artifact Download Dispatcher
# =====================================================================================
def download_artifact(
    source_url: str,
    artifact_id: str,
    artifact_type: ArtifactType,
) -> str:
    """
    Dispatch artifact downloads to the appropriate backend based on URL.

    Args:
        source_url: URL of upstream artifact (HuggingFace/GitHub)
        artifact_id: Artifact ID for logging
        artifact_type: "model", "dataset", or "code"

    Returns:
        Path to a tar.gz file on disk.

    Raises:
        FileDownloadError: If no backend matches or the download fails.
    """

    logger.info(
        f"[dispatcher] Selecting downloader for artifact {artifact_id}: {source_url}"
    )

    # HuggingFace
    if "huggingface.co" in source_url:
        try:
            return download_from_huggingface(source_url, artifact_id, artifact_type)
        except HFDownloadError as e:
            raise FileDownloadError(str(e)) from e

    # GitHub
    if "github.com" in source_url:
        try:
            return download_from_github(source_url, artifact_id, artifact_type)
        except GitHubDownloadError as e:
            raise FileDownloadError(str(e)) from e

    # Unsupported URL
    logger.error(f"[dispatcher] Unsupported download source: {source_url}")
    raise FileDownloadError(
        f"Unsupported source URL: {source_url}. Only HuggingFace and GitHub URLs are supported."
    )


# =====================================================================================
# Artifact Metadata Download Dispatcher
# =====================================================================================
def fetch_artifact_metadata(
    url: str,
    artifact_type: ArtifactType,
) -> Dict[str, Any]:
    """
    Unified metadata fetch interface.

    Delegates to HuggingFace or GitHub depending on artifact type and URL.
    """
    if artifact_type == "model":
        if "huggingface.co" not in url:
            raise ValueError(f"Model URL must be a HuggingFace URL: {url}")
        return fetch_huggingface_model_metadata(url)

    if artifact_type == "dataset":
        if "huggingface.co" not in url:
            raise ValueError(f"Dataset URL must be a HuggingFace URL: {url}")
        return fetch_huggingface_dataset_metadata(url)

    if artifact_type == "code":
        if "github.com" not in url:
            raise ValueError(f"Code URL must be a GitHub URL: {url}")
        return fetch_github_code_metadata(url)

    raise ValueError(f"Invalid artifact type: {artifact_type}")
