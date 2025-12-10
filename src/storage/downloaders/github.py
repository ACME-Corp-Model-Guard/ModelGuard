"""
GitHub artifact download utilities.

This module downloads a GitHub repository and bundles it into a local .tar.gz
archive, returning the path to that temporary file.

Used during artifact ingestion before uploading artifacts to S3.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
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


def _download_repo_zip(
    owner: str, repo: str, dest_dir: str, branch: str = "main"
) -> str:
    """
    Download repository as zip archive from GitHub and extract it.

    Uses GitHub's archive API which doesn't require git binary.
    Returns the path to the extracted repository directory.
    """
    # Try main branch first, fall back to master if it fails
    for branch_name in [branch, "main", "master"]:
        zip_url = (
            f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch_name}.zip"
        )

        logger.debug(
            f"[GitHub] Attempting to download from branch '{branch_name}': {zip_url}"
        )

        try:
            response = requests.get(zip_url, timeout=300, stream=True)

            if response.status_code == 404:
                # Branch doesn't exist, try next one
                continue

            response.raise_for_status()

            # Download zip to temp file
            zip_path = os.path.join(dest_dir, f"{repo}.zip")
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract zip
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(dest_dir)

            # Remove zip file
            os.unlink(zip_path)

            # GitHub creates a directory named {repo}-{branch}
            extracted_dir = os.path.join(dest_dir, f"{repo}-{branch_name}")

            if not os.path.exists(extracted_dir):
                raise FileDownloadError(
                    f"Expected directory {extracted_dir} not found after extraction"
                )

            logger.debug(
                f"[GitHub] Successfully downloaded and extracted to {extracted_dir}"
            )
            return extracted_dir

        except requests.RequestException as e:
            if branch_name == "master":  # Last attempt
                raise FileDownloadError(f"Failed to download repository: {e}")
            continue

    raise FileDownloadError(
        f"Repository {owner}/{repo} not found or no valid branch (tried: main, master)"
    )


def _make_tarball(repo_path: str, repo_name: str) -> str:
    """Create a tar.gz archive from a downloaded repo."""
    import tarfile

    # Use /tmp for Lambda environment compatibility
    tar_path = tempfile.NamedTemporaryFile(
        delete=False, suffix=".tar.gz", dir="/tmp"
    ).name

    with tarfile.open(tar_path, "w:gz") as tar:
        for root, dirs, files in os.walk(repo_path):
            # Skip .git directory if it exists (shouldn't with zip download)
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

    Downloads the repository as a zip archive using GitHub's REST API,
    then repackages it as a tar.gz file. This approach doesn't require
    the git binary, making it suitable for Lambda environments.
    """
    logger.info(f"[GitHub] Downloading artifact {artifact_id} from {source_url}")

    if artifact_type != "code":
        raise FileDownloadError("Only 'code' artifacts may be downloaded from GitHub")

    temp_dir: Optional[str] = None

    try:
        # Step 1 — Parse repo identifier
        owner, repo = _parse_github_url(source_url)

        # Step 2 — Download zip archive to temp dir (use /tmp for Lambda)
        temp_dir = tempfile.mkdtemp(dir="/tmp", prefix=f"gh_{artifact_id}_")

        logger.debug(f"[GitHub] Downloading {owner}/{repo} as zip archive")
        extracted_path = _download_repo_zip(owner, repo, temp_dir)

        # Step 3 — Package into tar.gz
        logger.debug(f"[GitHub] Creating tar archive for {artifact_id}")
        tar_path = _make_tarball(extracted_path, repo)

        logger.info(f"[GitHub] Successfully downloaded {artifact_id} → {tar_path}")
        return tar_path

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

        # Fetch contributors for bus factor metric
        contributors = []
        try:
            contributors_url = (
                f"https://api.github.com/repos/{owner}/{repo}/contributors"
            )
            contributors_response = requests.get(
                contributors_url, timeout=10, params={"per_page": 100}
            )
            # Handle rate limiting gracefully
            if contributors_response.status_code == 403:
                logger.warning(
                    f"[GitHub] Rate limit exceeded when fetching contributors for {owner}/{repo}"
                )
            else:
                contributors_response.raise_for_status()
                contributors_data = contributors_response.json()
                # Extract contribution counts
                for contrib in contributors_data:
                    if isinstance(contrib, dict) and "contributions" in contrib:
                        contributors.append({"contributions": contrib["contributions"]})
                logger.debug(
                    f"[GitHub] Fetched {len(contributors)} contributors for {owner}/{repo}"
                )
        except Exception as e:
            logger.warning(
                f"[GitHub] Failed to fetch contributors for {owner}/{repo}: {e}"
            )

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
                "contributors": contributors,
            },
        }

        return metadata

    except Exception as e:
        logger.error(f"[GitHub] Failed to fetch repo metadata: {e}")
        raise
