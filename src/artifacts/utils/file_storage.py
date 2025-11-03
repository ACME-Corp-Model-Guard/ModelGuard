"""
S3 storage utilities for artifact files.
Handles platform-specific download mechanisms (HuggingFace, GitHub, direct URLs).
"""

import os
import tempfile
import subprocess
import requests
import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from typing import Optional

from src.logger import logger


class FileDownloadError(Exception):
    """Raised when file download fails."""

    pass


def _download_from_huggingface(source_url: str, artifact_id: str) -> str:
    """
    Download artifact from HuggingFace Hub.
    Uses huggingface_hub library for proper authentication and caching.

    Args:
        source_url: HuggingFace URL (e.g., "https://huggingface.co/bert-base-uncased")
        artifact_id: Artifact ID for logging

    Returns:
        Path to downloaded temporary file

    Raises:
        FileDownloadError: If download fails
    """
    logger.info(f"Downloading artifact {artifact_id} from HuggingFace: {source_url}")

    try:
        from huggingface_hub import snapshot_download  # type: ignore[import-not-found]

        # Parse model ID from URL
        parts = source_url.rstrip("/").split("huggingface.co/")
        if len(parts) < 2:
            raise FileDownloadError(f"Invalid HuggingFace URL: {source_url}")

        model_id = parts[1].replace("/tree/", "/").replace("/blob/", "/")
        # Remove any trailing path after model ID
        model_id = "/".join(model_id.split("/")[:2])

        logger.debug(f"Parsed HuggingFace model ID: {model_id}")

        # Download entire model snapshot to temp directory
        cache_dir = tempfile.mkdtemp(prefix=f"hf_{artifact_id}_")
        snapshot_path = snapshot_download(
            repo_id=model_id,
            cache_dir=cache_dir,
            local_dir=cache_dir,
            local_dir_use_symlinks=False,
        )

        # Create a tar archive of the snapshot
        import tarfile

        tar_path = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(snapshot_path, arcname=os.path.basename(snapshot_path))

        logger.info(
            f"Successfully downloaded HuggingFace artifact {artifact_id} to {tar_path}"
        )
        return tar_path

    except ImportError:
        logger.error("huggingface_hub library not installed")
        raise FileDownloadError(
            "huggingface_hub library required for HuggingFace downloads. Install with: pip install huggingface_hub"
        )
    except Exception as e:
        logger.error(f"Failed to download from HuggingFace: {e}", exc_info=True)
        raise FileDownloadError(f"HuggingFace download failed: {e}")


def _download_from_github(source_url: str, artifact_id: str) -> str:
    """
    Download artifact from GitHub.
    Clones the repository and creates a tar archive.

    Args:
        source_url: GitHub URL (e.g., "https://github.com/owner/repo")
        artifact_id: Artifact ID for logging

    Returns:
        Path to downloaded temporary file (tar.gz of repo)

    Raises:
        FileDownloadError: If download fails
    """
    logger.info(f"Downloading artifact {artifact_id} from GitHub: {source_url}")

    try:
        # Parse owner/repo from URL
        parts = source_url.rstrip("/").split("github.com/")
        if len(parts) < 2:
            raise FileDownloadError(f"Invalid GitHub URL: {source_url}")

        repo_path = parts[1].split("/")[:2]
        if len(repo_path) < 2:
            raise FileDownloadError(f"Invalid GitHub repository URL: {source_url}")

        owner, repo = repo_path
        clone_url = f"https://github.com/{owner}/{repo}.git"

        logger.debug(f"Cloning GitHub repo: {clone_url}")

        # Clone to temp directory
        temp_dir = tempfile.mkdtemp(prefix=f"gh_{artifact_id}_")
        clone_path = os.path.join(temp_dir, repo)

        # Run git clone
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, clone_path],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise FileDownloadError(f"Git clone failed: {result.stderr}")

        # Remove .git directory to reduce size
        git_dir = os.path.join(clone_path, ".git")
        if os.path.exists(git_dir):
            import shutil

            shutil.rmtree(git_dir)

        # Create tar archive
        import tarfile

        tar_path = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(clone_path, arcname=repo)

        logger.info(
            f"Successfully downloaded GitHub artifact {artifact_id} to {tar_path}"
        )
        return tar_path

    except subprocess.TimeoutExpired:
        logger.error(f"Git clone timed out for {source_url}")
        raise FileDownloadError("GitHub clone timed out after 300 seconds")
    except Exception as e:
        logger.error(f"Failed to download from GitHub: {e}", exc_info=True)
        raise FileDownloadError(f"GitHub download failed: {e}")


def upload_artifact_to_s3(artifact_id: str, s3_key: str, source_url: str) -> None:
    """
    Download artifact from source URL and upload to S3.
    Automatically detects platform (HuggingFace, GitHub, direct URL) and uses appropriate download method.
    Uses ARTIFACTS_BUCKET environment variable for bucket name.

    Args:
        artifact_id: Artifact ID for logging
        s3_key: S3 key to upload to
        source_url: URL to download artifact from

    Raises:
        ValueError: If ARTIFACTS_BUCKET env var not set
        FileDownloadError: If download fails
        ClientError: If S3 upload fails
    """
    bucket_name = os.getenv("ARTIFACTS_BUCKET")
    if not bucket_name:
        logger.error("ARTIFACTS_BUCKET env var not set")
        raise ValueError("ARTIFACTS_BUCKET env var must be set")

    tmp_path = None

    try:
        # Detect platform and download
        if "huggingface.co" in source_url:
            tmp_path = _download_from_huggingface(source_url, artifact_id)
        elif "github.com" in source_url:
            tmp_path = _download_from_github(source_url, artifact_id)

        logger.debug(f"Uploading artifact {artifact_id} to s3://{bucket_name}/{s3_key}")

        # Upload to S3
        s3 = boto3.client("s3")
        s3.upload_file(tmp_path, bucket_name, s3_key)
        logger.info(f"Successfully uploaded artifact {artifact_id} to S3")

    except FileDownloadError:
        raise
    except ClientError as e:
        logger.error(
            f"Failed to upload artifact {artifact_id} to S3: {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(f"Unexpected error during artifact upload: {e}", exc_info=True)
        raise
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
                logger.debug(f"Cleaned up temporary file: {tmp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {tmp_path}: {e}")


def download_artifact_from_s3(artifact_id: str, s3_key: str, local_path: str) -> None:
    """
    Download artifact file from S3.
    Uses ARTIFACTS_BUCKET environment variable for bucket name.

    Args:
        artifact_id: Artifact ID for logging
        s3_key: S3 key to download from
        local_path: Local file path to save to

    Raises:
        ValueError: If ARTIFACTS_BUCKET env var not set
        ClientError: If S3 download fails
    """
    bucket_name = os.getenv("ARTIFACTS_BUCKET")
    if not bucket_name:
        logger.error("ARTIFACTS_BUCKET env var not set")
        raise ValueError("ARTIFACTS_BUCKET env var must be set")

    logger.debug(
        f"Downloading artifact {artifact_id} from s3://{bucket_name}/{s3_key} to {local_path}"
    )

    try:
        s3 = boto3.client("s3")
        s3.download_file(bucket_name, s3_key, local_path)
        logger.info(f"Successfully downloaded artifact {artifact_id} from S3")
    except ClientError as e:
        logger.error(
            f"Failed to download artifact {artifact_id} from S3: {e}", exc_info=True
        )
        raise
