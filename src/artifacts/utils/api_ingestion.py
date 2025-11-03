"""
Artifact ingestion utilities for fetching metadata from external sources.
Supports HuggingFace Hub (models/datasets) and GitHub (code).
"""

from typing import Dict, Any, Optional
import requests
from src.logger import logger


class IngestionError(Exception):
    """Raised when artifact ingestion fails."""

    pass


def fetch_huggingface_model_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch model metadata from HuggingFace Hub API.

    Args:
        url: HuggingFace model URL (e.g., "https://huggingface.co/bert-base-uncased")

    Returns:
        Dictionary containing model metadata (name, size, license, etc.)

    Raises:
        IngestionError: If fetching or parsing fails
    """
    logger.info(f"Fetching HuggingFace model metadata from: {url}")

    try:
        # Parse model ID from URL
        # URL format: https://huggingface.co/{model_id}
        parts = url.rstrip("/").split("huggingface.co/")
        if len(parts) < 2:
            raise IngestionError(f"Invalid HuggingFace URL format: {url}")

        model_id = parts[1]
        logger.debug(f"Parsed model ID: {model_id}")

        # Call HuggingFace API
        api_url = f"https://huggingface.co/api/models/{model_id}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Extract relevant metadata with robust error handling
        try:
            name = model_id.split("/")[-1]
        except (IndexError, AttributeError):
            logger.warning(f"Could not parse model name from ID: {model_id}")
            name = "unknown"

        try:
            size = data.get("safetensors", {}).get("total", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse size for model: {model_id}")
            size = 0

        try:
            license = data.get("cardData", {}).get("license", "unknown")
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse license for model: {model_id}")
            license = "unknown"

        try:
            downloads = data.get("downloads", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse downloads for model: {model_id}")
            downloads = 0

        try:
            likes = data.get("likes", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse likes for model: {model_id}")
            likes = 0

        metadata = {
            "name": name,
            "size": size,
            "license": license,
            "metadata": {
                "downloads": downloads,
                "likes": likes,
            },
        }

        logger.info(f"Successfully fetched metadata for model: {model_id}")
        return metadata

    except requests.RequestException as e:
        logger.error(f"Failed to fetch HuggingFace model metadata: {e}", exc_info=True)
        raise IngestionError(f"Failed to fetch model metadata from HuggingFace: {e}")


def fetch_huggingface_dataset_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch dataset metadata from HuggingFace Hub API.

    Args:
        url: HuggingFace dataset URL (e.g., "https://huggingface.co/datasets/squad")

    Returns:
        Dictionary containing dataset metadata (name, size, etc.)

    Raises:
        IngestionError: If fetching or parsing fails
    """
    logger.info(f"Fetching HuggingFace dataset metadata from: {url}")

    try:
        # Parse dataset ID from URL
        # URL format: https://huggingface.co/datasets/{dataset_id}
        parts = url.rstrip("/").split("huggingface.co/datasets/")
        if len(parts) < 2:
            raise IngestionError(f"Invalid HuggingFace dataset URL format: {url}")

        dataset_id = parts[1]
        logger.debug(f"Parsed dataset ID: {dataset_id}")

        # Call HuggingFace API
        api_url = f"https://huggingface.co/api/datasets/{dataset_id}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Extract relevant metadata with robust error handling
        try:
            name = dataset_id.split("/")[-1]
        except (IndexError, AttributeError):
            logger.warning(f"Could not parse dataset name from ID: {dataset_id}")
            name = "unknown"

        try:
            downloads = data.get("downloads", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse downloads for dataset: {dataset_id}")
            downloads = 0

        try:
            likes = data.get("likes", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse likes for dataset: {dataset_id}")
            likes = 0

        try:
            card_data = data.get("cardData", {})
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse cardData for dataset: {dataset_id}")
            card_data = {}

        metadata = {
            "name": name,
            "metadata": {
                "downloads": downloads,
                "likes": likes,
                "cardData": card_data,
            },
        }

        logger.info(f"Successfully fetched metadata for dataset: {dataset_id}")
        return metadata

    except requests.RequestException as e:
        logger.error(
            f"Failed to fetch HuggingFace dataset metadata: {e}", exc_info=True
        )
        raise IngestionError(f"Failed to fetch dataset metadata from HuggingFace: {e}")


def fetch_github_code_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch code repository metadata from GitHub API.

    Args:
        url: GitHub repository URL (e.g., "https://github.com/owner/repo")

    Returns:
        Dictionary containing repository metadata (name, size, license, etc.)

    Raises:
        IngestionError: If fetching or parsing fails
    """
    logger.info(f"Fetching GitHub repository metadata from: {url}")

    try:
        # Parse owner/repo from URL
        # URL format: https://github.com/{owner}/{repo}
        parts = url.rstrip("/").split("github.com/")
        if len(parts) < 2:
            raise IngestionError(f"Invalid GitHub URL format: {url}")

        repo_path = parts[1].split("/")[:2]  # Get owner/repo, ignore subdirs
        if len(repo_path) < 2:
            raise IngestionError(f"Invalid GitHub repository URL: {url}")

        owner, repo = repo_path
        logger.debug(f"Parsed GitHub repo: {owner}/{repo}")

        # Call GitHub API
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Extract relevant metadata with robust error handling for each field
        try:
            name = data.get("name", repo)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse name for repo: {owner}/{repo}")
            name = repo

        try:
            description = data.get("description")
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse description for repo: {owner}/{repo}")
            description = None

        try:
            language = data.get("language")
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse language for repo: {owner}/{repo}")
            language = None

        try:
            size = data.get("size", 0) * 1024
        except (AttributeError, TypeError, ValueError):
            logger.warning(f"Could not parse size for repo: {owner}/{repo}")
            size = 0

        try:
            license_data = data.get("license", {})
            license = (
                license_data.get("spdx_id", "unknown")
                if isinstance(license_data, dict)
                else "unknown"
            )
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse license for repo: {owner}/{repo}")
            license = "unknown"

        try:
            stars = data.get("stargazers_count", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse stars for repo: {owner}/{repo}")
            stars = 0

        try:
            forks = data.get("forks_count", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse forks for repo: {owner}/{repo}")
            forks = 0

        try:
            open_issues = data.get("open_issues_count", 0)
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse open_issues for repo: {owner}/{repo}")
            open_issues = 0

        try:
            default_branch = data.get("default_branch", "main")
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse default_branch for repo: {owner}/{repo}")
            default_branch = "main"

        try:
            clone_url = data.get("clone_url")
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse clone_url for repo: {owner}/{repo}")
            clone_url = None

        metadata = {
            "name": name,
            "metadata": {
                "description": description,
                "language": language,
                "size": size,
                "license": license,
                "stars": stars,
                "forks": forks,
                "open_issues": open_issues,
                "default_branch": default_branch,
                "clone_url": clone_url,
            },
        }

        logger.info(f"Successfully fetched metadata for GitHub repo: {owner}/{repo}")
        return metadata

    except requests.RequestException as e:
        logger.error(f"Failed to fetch GitHub repository metadata: {e}", exc_info=True)
        raise IngestionError(f"Failed to fetch repository metadata from GitHub: {e}")


def fetch_artifact_metadata(url: str, artifact_type: str) -> Dict[str, Any]:
    """
    Fetch artifact metadata from URL based on artifact type.
    Delegates to appropriate fetcher function.

    Args:
        url: URL to artifact (HuggingFace or GitHub)
        artifact_type: One of 'model', 'dataset', 'code'

    Returns:
        Dictionary containing artifact metadata

    Raises:
        IngestionError: If fetching fails or artifact_type is invalid
    """
    logger.info(f"Fetching {artifact_type} metadata from URL: {url}")

    if artifact_type == "model":
        if "huggingface.co" not in url:
            raise IngestionError(f"Model URL must be from HuggingFace Hub: {url}")
        return fetch_huggingface_model_metadata(url)

    elif artifact_type == "dataset":
        if "huggingface.co" not in url:
            raise IngestionError(f"Dataset URL must be from HuggingFace Hub: {url}")
        return fetch_huggingface_dataset_metadata(url)

    elif artifact_type == "code":
        if "github.com" not in url:
            raise IngestionError(f"Code URL must be from GitHub: {url}")
        return fetch_github_code_metadata(url)

    else:
        raise IngestionError(
            f"Invalid artifact_type: {artifact_type}. Must be 'model', 'dataset', or 'code'"
        )
