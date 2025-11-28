"""
GitHub artifact download utilities.

This module downloads a GitHub repository and bundles it into a local .tar.gz
archive, returning the path to that temporary file.

Used during artifact ingestion before uploading artifacts to S3.
"""

from __future__ import annotations

import os
import subprocess
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
    return owner, repo


def _clone_repo(clone_url: str, dest: str) -> None:
    """Clone the repository into dest."""
    result = subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, dest],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown Git error"
        raise FileDownloadError(f"Git clone failed: {stderr}")


def _make_tarball(repo_path: str, repo_name: str) -> str:
    """Create a tar.gz archive from a cloned repo."""
    import tarfile

    tar_path = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

    with tarfile.open(tar_path, "w:gz") as tar:
        for root, dirs, files in os.walk(repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join(repo_name, os.path.relpath(file_path, repo_path))
                tar.add(file_path, arcname=arcname)

    return tar_path


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
    High-level function that downloads a GitHub repo as a tar.gz archive.

    Orchestrates all steps using the helper functions above.
    """
    logger.info(f"[GitHub] Downloading artifact {artifact_id} from {source_url}")

    if artifact_type != "code":
        raise FileDownloadError("Only 'code' artifacts may be downloaded from GitHub")

    temp_dir: Optional[str] = None

    try:
        # Step 1 — Parse repo identifier
        owner, repo = _parse_github_url(source_url)
        clone_url = f"https://github.com/{owner}/{repo}.git"

        # Step 2 — Clone to temp dir
        temp_dir = tempfile.mkdtemp(prefix=f"gh_{artifact_id}_")
        clone_path = os.path.join(temp_dir, repo)

        logger.debug(f"[GitHub] Cloning {clone_url} → {clone_path}")
        _clone_repo(clone_url, clone_path)

        # Step 3 — Package into tar.gz
        logger.debug(f"[GitHub] Creating tar archive for {artifact_id}")
        tar_path = _make_tarball(clone_path, repo)

        logger.info(f"[GitHub] Successfully downloaded {artifact_id} → {tar_path}")
        return tar_path

    except subprocess.TimeoutExpired:
        raise FileDownloadError("GitHub clone operation timed out after 300 seconds")

    except Exception as e:
        logger.error(f"[GitHub] Download failed: {e}")
        raise FileDownloadError(f"GitHub download failed: {e}")

    finally:
        _cleanup_temp_dir(temp_dir)


# =====================================================================================
# Code Metadata
# =====================================================================================
def fetch_github_code_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch code repository metadata from the GitHub REST API.
    """
    logger.info(f"[GitHub] Fetching code metadata: {url}")

    try:
        parts = url.rstrip("/").split("github.com/")
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub URL: {url}")

        owner, repo = parts[1].split("/")[:2]
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
