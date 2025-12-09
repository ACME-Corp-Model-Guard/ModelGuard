"""
GitHub artifact download utilities.

This module downloads a GitHub repository and bundles it into a local .tar.gz
archive, returning the path to that temporary file.

Used during artifact ingestion before uploading artifacts to S3.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Optional, Tuple

import requests

from src.artifacts.types import ArtifactType
from src.logger import logger


class FileDownloadError(Exception):
    """Raised when a GitHub download fails."""

    pass


# ==============================================================================
# Helper Functions
# ==============================================================================
def _parse_github_url(source_url: str) -> Tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL."""
    parts = source_url.rstrip("/").split("github.com/")
    if len(parts) < 2:
        raise FileDownloadError(f"Invalid GitHub URL: {source_url}")

    repo_parts = parts[1].split("/")[:2]
    if len(repo_parts) < 2:
        raise FileDownloadError(f"Invalid GitHub repository URL: {source_url}")

    owner, repo = repo_parts

    # Strip .git suffix if present
    if repo.endswith(".git"):
        repo = repo[:-4]  # Remove last 4 characters (".git")

    return owner, repo


def _cleanup_temp_dir(temp_dir: Optional[str]) -> None:
    """Safely remove the temporary clone directory."""
    if temp_dir and os.path.exists(temp_dir):
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception as err:
            logger.warning(
                f"[GitHub] Failed to remove temp directory {temp_dir}: {err}"
            )


# ==============================================================================
# Code Repository
# ==============================================================================
def download_from_github(
    source_url: str,
    artifact_id: str,
    artifact_type: ArtifactType,
) -> str:
    """
    Download a GitHub repo as a tar.gz archive using GitHub's API.
    """
    logger.info(f"[GitHub] Downloading artifact {artifact_id} from {source_url}")

    if artifact_type != "code":
        raise FileDownloadError("Only 'code' artifacts may be downloaded from GitHub")

    tar_path: Optional[str] = None

    try:
        # Step 1 — Parse repo identifier
        owner, repo = _parse_github_url(source_url)

        # Step 2 — Download archive from GitHub API
        archive_url = f"https://api.github.com/repos/{owner}/{repo}/tarball"

        logger.debug(f"[GitHub] Downloading archive from {archive_url}")

        response = requests.get(archive_url, timeout=300, stream=True)
        response.raise_for_status()

        # Step 3 — Save to temporary file
        tar_path = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        with open(tar_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"[GitHub] Successfully downloaded {artifact_id} → {tar_path}")
        return tar_path

    except requests.RequestException as e:
        logger.error(f"[GitHub] HTTP request failed: {e}")
        # Cleanup tar file if it was created
        if tar_path and os.path.exists(tar_path):
            try:
                os.unlink(tar_path)
                logger.debug(f"[GitHub] Cleaned up temp file: {tar_path}")
            except Exception:
                pass
        raise FileDownloadError(f"Failed to download from GitHub API: {e}")

    except Exception as e:
        logger.error(f"[GitHub] Download failed: {e}")
        # Cleanup tar file if it was created
        if tar_path and os.path.exists(tar_path):
            try:
                os.unlink(tar_path)
                logger.debug(f"[GitHub] Cleaned up temp file: {tar_path}")
            except Exception:
                pass
        raise FileDownloadError(f"GitHub download failed: {e}")


# =====================================================================================
# Code Metadata
# =====================================================================================
def fetch_github_code_metadata(url: str) -> Dict[str, Any]:
    """Fetch code repository metadata from the GitHub REST API."""
    logger.info(f"[GitHub] Fetching code metadata: {url}")

    try:
        owner, repo = _parse_github_url(url)  # ← Use the same parsing logic
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        metadata = {
            "name": data.get("name", repo),
            "metadata": {
                "description": data.get("description"),
                "language": data.get("language"),
                "size": data.get("size", 0) * 1024,
                "license": (data.get("license") or {}).get("spdx_id", "unknown"),
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "default_branch": data.get("default_branch", "main"),
                "clone_url": data.get("clone_url"),
            },
        }

        return metadata

    except Exception as e:
        logger.error(f"[GitHub] Failed to fetch repo metadata: {e}")
        raise
