"""
GitHub artifact download utilities.

This module downloads a GitHub repository and bundles it into a local .tar.gz
archive, returning the path to that temporary file.

Used during artifact ingestion before uploading artifacts to S3.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Tuple

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


def _download_repo_tarball(
    owner: str, repo: str, dest_dir: str, branch: str = "main"
) -> str:
    """
    Download repository as tarball from GitHub.

    Uses GitHub's archive API which doesn't require git binary.
    Returns the path to the downloaded tarball file.
    """
    # Try main branch first, fall back to master if it fails
    for branch_name in [branch, "main", "master"]:
        tarball_url = (
            f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch_name}.tar.gz"
        )

        logger.debug(
            f"[GitHub] Attempting to download from branch '{branch_name}': {tarball_url}"
        )

        try:
            response = requests.get(tarball_url, timeout=300, stream=True)

            if response.status_code == 404:
                # Branch doesn't exist, try next one
                continue

            response.raise_for_status()

            # Download tarball directly to /tmp
            tarball_path = os.path.join(dest_dir, f"{repo}-{branch_name}.tar.gz")
            with open(tarball_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.debug(f"[GitHub] Successfully downloaded tarball to {tarball_path}")
            return tarball_path

        except requests.RequestException as e:
            if branch_name == "master":  # Last attempt
                raise FileDownloadError(f"Failed to download repository: {e}")
            continue

    raise FileDownloadError(
        f"Repository {owner}/{repo} not found or no valid branch (tried: main, master)"
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

    Downloads the repository as a tarball directly using GitHub's archive API.
    This approach doesn't require the git binary, making it suitable for
    Lambda environments.
    """
    logger.info(f"[GitHub] Downloading artifact {artifact_id} from {source_url}")

    if artifact_type != "code":
        raise FileDownloadError("Only 'code' artifacts may be downloaded from GitHub")

    try:
        # Step 1 — Parse repo identifier
        owner, repo = _parse_github_url(source_url)

        # Step 2 — Download tarball directly to /tmp (use /tmp for Lambda)
        temp_dir = tempfile.mkdtemp(dir="/tmp", prefix=f"gh_{artifact_id}_")

        logger.debug(f"[GitHub] Downloading {owner}/{repo} as tarball")
        tar_path = _download_repo_tarball(owner, repo, temp_dir)

        logger.info(f"[GitHub] Successfully downloaded {artifact_id} → {tar_path}")
        return tar_path

    except Exception as e:
        logger.error(f"[GitHub] Download failed: {e}")
        raise FileDownloadError(f"GitHub download failed: {e}")


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
