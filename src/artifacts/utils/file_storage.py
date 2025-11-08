"""
S3 storage utilities for artifact files.
Handles platform-specific download mechanisms (HuggingFace, GitHub, direct URLs).

TODO: For model downloads, we need to support both:
1. Download locally to Lambda for processing/analysis
2. Generate presigned URLs for API users to download directly from S3
"""

import os
import tempfile
import subprocess
import requests
import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from typing import Optional

from src.logger import logger
from .types import ArtifactType


class FileDownloadError(Exception):
    """Raised when file download fails."""

    pass


def _download_from_huggingface(source_url: str, artifact_id: str, artifact_type: ArtifactType) -> str:
    """
    Download artifact from HuggingFace Hub.
    Uses huggingface_hub library for proper authentication and caching.

    Args:
        source_url: HuggingFace URL (e.g., "https://huggingface.co/bert-base-uncased")
        artifact_id: Artifact ID for logging
        artifact_type: Should be "model" or "dataset", not "code"

    Returns:
        Path to downloaded temporary file

    Raises:
        FileDownloadError: If download fails or artifact_type is "code"
    """
    logger.info(f"Downloading artifact {artifact_id} from HuggingFace: {source_url}")

    # Validate artifact type for HuggingFace
    if artifact_type == "code":
        logger.error("Cannot download code artifacts from HuggingFace")
        raise FileDownloadError("Code artifacts should be downloaded from GitHub, not HuggingFace")

    cache_dir = None
    try:
        from huggingface_hub import snapshot_download # type: ignore[import-untyped]
        from huggingface_hub.errors import RepositoryNotFoundError, RevisionNotFoundError

        # Parse model ID from URL
        parts = source_url.rstrip("/").split("huggingface.co/")
        if len(parts) < 2:
            raise FileDownloadError(f"Invalid HuggingFace URL: {source_url}")

        model_id = parts[1]  # Get the part after "huggingface.co/"
        # Remove any trailing path after model ID (like /tree/main or /blob/main/config.json)
        model_id = "/".join(model_id.split("/")[:2])  # Keep only owner/repo

        logger.debug(f"Parsed HuggingFace model ID: {model_id}")
        
        # Download with specific error handling
        cache_dir = tempfile.mkdtemp(prefix=f"hf_{artifact_id}_")
        snapshot_path = snapshot_download(
            repo_id=model_id,
            repo_type=artifact_type, # "model" or "dataset"
            cache_dir=cache_dir,
            local_dir=cache_dir,
            local_dir_use_symlinks=False,
        )

        # Create a tar archive of the snapshot
        import tarfile
        tar_path = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name
        
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(snapshot_path, arcname=os.path.basename(snapshot_path))

        logger.info(f"Successfully downloaded HuggingFace artifact {artifact_id} to {tar_path}")
        return tar_path

    except ImportError:
        logger.error("huggingface_hub library not installed")
        raise FileDownloadError(
            "huggingface_hub library required for HuggingFace downloads. Install with: pip install huggingface_hub"
        )
    except RepositoryNotFoundError:
        logger.error(f"HuggingFace model not found: {model_id}")
        raise FileDownloadError(f"Model '{model_id}' not found on HuggingFace Hub")
    except RevisionNotFoundError as e:
        logger.error(f"HuggingFace model: {model_id} revision not found: {e}")
        raise FileDownloadError(f"Model: {model_id} revision not found: {e}")
    except ValueError as e:
        logger.error(f"ValueError during HuggingFace download: {e}")
        raise FileDownloadError(f"HuggingFace download failed: {e}")
    except Exception as e:
        logger.error(f"Failed to download from HuggingFace: {e}", exc_info=True)
        raise FileDownloadError(f"HuggingFace download failed: {e}")
    finally:
        # Critical: Always clean up cache directory
        if cache_dir and os.path.exists(cache_dir):
            try:
                import shutil
                shutil.rmtree(cache_dir)
                logger.debug(f"Cleaned up HuggingFace cache directory: {cache_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up cache directory {cache_dir}: {cleanup_error}")


def _download_from_github(source_url: str, artifact_id: str, artifact_type: ArtifactType) -> str:
    """
    Download artifact from GitHub.
    Clones the repository and creates a tar archive.

    Args:
        source_url: GitHub URL (e.g., "https://github.com/owner/repo")
        artifact_id: Artifact ID for logging
        artifact_type: Must be "code" for GitHub downloads

    Returns:
        Path to downloaded temporary file (tar.gz of repo)

    Raises:
        FileDownloadError: If download fails
    """
    logger.info(f"Downloading artifact {artifact_id} from GitHub: {source_url}")

    if artifact_type != "code":
        logger.error("Only code artifacts can be downloaded from GitHub")
        raise FileDownloadError("Only code artifacts can be downloaded from GitHub")

    temp_dir = None
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

        # Run git clone with timeout
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, clone_path],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown git error"
            raise FileDownloadError(f"Git clone failed: {error_msg}")

        # Create tar archive directly from clone
        import tarfile
        tar_path = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name
        
        with tarfile.open(tar_path, "w:gz") as tar:
            # Add files but exclude .git directory for efficiency
            for root, dirs, files in os.walk(clone_path):
                # Skip .git directory entirely
                if '.git' in dirs:
                    dirs.remove('.git')
                
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate archive name relative to clone_path
                    archive_name = os.path.join(repo, os.path.relpath(file_path, clone_path))
                    tar.add(file_path, arcname=archive_name)

        logger.info(f"Successfully downloaded GitHub artifact {artifact_id} to {tar_path}")
        return tar_path

    except subprocess.TimeoutExpired:
        logger.error(f"Git clone timed out for {source_url}")
        raise FileDownloadError("GitHub clone timed out after 300 seconds")
    except Exception as e:
        logger.error(f"Failed to download from GitHub: {e}", exc_info=True)
        raise FileDownloadError(f"GitHub download failed: {e}")
    finally:
        # Critical: Always clean up temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temp directory: {temp_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temp directory {temp_dir}: {cleanup_error}")


def upload_artifact_to_s3(artifact_id: str, artifact_type: ArtifactType, s3_key: str, source_url: str) -> None:
    """
    Download artifact from source URL and upload to S3.
    Automatically detects platform (HuggingFace, GitHub, direct URL) and uses appropriate download method.
    Uses ARTIFACTS_BUCKET environment variable for bucket name.

    Args:
        artifact_id: Artifact ID for logging
        artifact_type: One of 'model', 'dataset', 'code'
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
            tmp_path = _download_from_huggingface(source_url, artifact_id, artifact_type)
        elif "github.com" in source_url:
            tmp_path = _download_from_github(source_url, artifact_id, artifact_type)
        else:
            # TODO: Add support for direct URL downloads (HTTP/HTTPS)
            logger.error(f"Unsupported source URL: {source_url}")
            raise FileDownloadError(f"Unsupported source URL format: {source_url}. Only HuggingFace and GitHub URLs are supported.")

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


def generate_s3_download_url(artifact_id: str, s3_key: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for downloading an artifact from S3.
    This allows API users to download artifacts directly without going through Lambda.
    
    Args:
        artifact_id: Artifact ID for logging
        s3_key: S3 key to generate URL for
        expiration: URL expiration time in seconds (default: 1 hour)
    
    Returns:
        Presigned URL string
        
    Raises:
        ValueError: If ARTIFACTS_BUCKET env var not set
        ClientError: If presigned URL generation fails
    """
    bucket_name = os.getenv("ARTIFACTS_BUCKET")
    if not bucket_name:
        logger.error("ARTIFACTS_BUCKET env var not set")
        raise ValueError("ARTIFACTS_BUCKET env var must be set")

    logger.debug(f"Generating download URL for artifact {artifact_id}: s3://{bucket_name}/{s3_key}")

    try:
        s3 = boto3.client("s3")
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=expiration
        )
        logger.info(f"Generated presigned URL for artifact {artifact_id} (expires in {expiration}s)")
        return presigned_url
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for artifact {artifact_id}: {e}", exc_info=True)
        raise
