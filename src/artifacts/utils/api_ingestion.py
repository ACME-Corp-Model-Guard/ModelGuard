"""
Artifact ingestion utilities for fetching metadata from external sources.
Supports HuggingFace Hub (models/datasets) and GitHub (code).
"""

from typing import Dict, Any, Optional, List
import requests
from src.logger import logger
from .types import ArtifactType


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

        try:
            card_data = data.get("cardData", {})
        except (AttributeError, TypeError):
            logger.warning(f"Could not parse cardData for model: {model_id}")
            card_data = {}

        metadata = {
            "name": name,
            "size": size,
            "license": license,
            "metadata": {
                "downloads": downloads,
                "likes": likes,
                "cardData": card_data,
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


def fetch_artifact_metadata(url: str, artifact_type: ArtifactType) -> Dict[str, Any]:
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


def extract_github_url_from_huggingface_metadata(
    metadata: Dict[str, Any],
) -> Optional[str]:
    """
    Extract GitHub repository URL from HuggingFace model metadata.

    Checks various fields where GitHub URL might be stored in the metadata.

    Args:
        metadata: Model metadata dictionary (from artifact.metadata or API response)

    Returns:
        GitHub repository URL if found, None otherwise
    """
    if not metadata:
        return None

    # Check top-level metadata fields
    github_url = (
        metadata.get("github_url")
        or metadata.get("github")
        or metadata.get("code_repository")
        or metadata.get("repository")
    )
    if github_url and "github.com" in str(github_url):
        return str(github_url)

    # Check nested metadata.cardData
    card_data = metadata.get("metadata", {}).get("cardData", {})
    if isinstance(card_data, dict):
        github_url = (
            card_data.get("github")
            or card_data.get("code_repository")
            or card_data.get("repository")
        )
        if github_url and "github.com" in str(github_url):
            return str(github_url)

    # Check direct cardData (if metadata structure is different)
    card_data = metadata.get("cardData", {})
    if isinstance(card_data, dict):
        github_url = (
            card_data.get("github")
            or card_data.get("code_repository")
            or card_data.get("repository")
        )
        if github_url and "github.com" in str(github_url):
            return str(github_url)

    return None


def fetch_github_contributors(github_url: str) -> List[Dict[str, int]]:
    """
    Fetch contributor statistics from GitHub API.

    Args:
        github_url: GitHub repository URL (e.g., "https://github.com/owner/repo")

    Returns:
        List of contributor dictionaries with 'contributions' field.
        Empty list if fetching fails or URL is invalid.

    Raises:
        IngestionError: If URL format is invalid
    """
    logger.info(f"Fetching GitHub contributors from: {github_url}")

    try:
        # Parse owner/repo from URL
        parts = github_url.rstrip("/").split("github.com/")
        if len(parts) < 2:
            raise IngestionError(f"Invalid GitHub URL format: {github_url}")

        repo_path = parts[1].split("/")[:2]  # Get owner/repo, ignore subdirs
        if len(repo_path) < 2:
            raise IngestionError(f"Invalid GitHub repository URL: {github_url}")

        owner, repo = repo_path
        logger.debug(f"Parsed GitHub repo: {owner}/{repo}")

        # GitHub API endpoint for contributors
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
        response = requests.get(api_url, timeout=10, params={"per_page": 100})

        # Handle rate limiting
        if response.status_code == 403:
            logger.warning("GitHub API rate limit exceeded")
            return []

        response.raise_for_status()
        contributors = response.json()

        # Extract contribution counts
        result = []
        for contrib in contributors:
            if isinstance(contrib, dict) and "contributions" in contrib:
                result.append({"contributions": contrib["contributions"]})

        logger.info(
            f"Successfully fetched {len(result)} contributors for {owner}/{repo}"
        )
        return result

    except requests.RequestException as e:
        logger.error(
            f"Failed to fetch contributors from GitHub API for {github_url}: {e}",
            exc_info=True,
        )
        return []
    except IngestionError:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error fetching GitHub contributors: {e}", exc_info=True
        )
        return []


def extract_performance_claims_from_metadata(
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract performance claims and metrics from model metadata.

    Checks various fields where performance information might be stored,
    including HuggingFace model card data. Uses structured field checking
    to avoid false positives from keyword matching.

    Args:
        metadata: Model metadata dictionary (from artifact.metadata or API response)

    Returns:
        Dictionary with performance claims information:
        - has_metrics: bool - whether any performance metrics were found
        - metrics: list - list of found metric names
        - has_benchmarks: bool - whether benchmark results were found
        - has_papers: bool - whether papers are cited
        - metric_count: int - number of distinct metrics found
        - has_structured_metrics: bool - whether metrics are in structured format
        - card_data: dict - raw cardData if available
    """
    result = {
        "has_metrics": False,
        "metrics": [],
        "has_benchmarks": False,
        "has_papers": False,
        "metric_count": 0,
        "has_structured_metrics": False,
        "card_data": {},
    }

    if not metadata:
        return result

    # Get cardData from various possible locations
    card_data = (
        metadata.get("metadata", {}).get("cardData", {})
        or metadata.get("cardData", {})
        or {}
    )

    result["card_data"] = card_data

    if not card_data:
        return result

    # Primary: Check HuggingFace model-index structure (most reliable)
    if isinstance(card_data, dict):
        model_index = card_data.get("model-index", {})
        if model_index and isinstance(model_index, dict):
            results = model_index.get("results", [])
            if results and isinstance(results, list):
                result["has_benchmarks"] = True
                result["has_structured_metrics"] = True

                # Extract metrics from structured results
                for result_item in results:
                    if isinstance(result_item, dict):
                        # Check for task type (indicates proper benchmark structure)
                        task_type = result_item.get("task", {})
                        if task_type:
                            result["has_benchmarks"] = True

                        # Extract metrics from results
                        metrics = result_item.get("metrics", [])
                        if metrics and isinstance(metrics, list):
                            result["has_metrics"] = True
                            for metric in metrics:
                                if isinstance(metric, dict):
                                    metric_name = metric.get("name", "")
                                    metric_value = metric.get("value")
                                    # Only count if it has both name and value (actual metric)
                                    if metric_name and metric_value is not None:
                                        result["metrics"].append(metric_name.lower())

    # Secondary: Check for performance-related fields in cardData
    if isinstance(card_data, dict):
        # Check for explicit performance/evaluation sections
        performance_fields = [
            "performance",
            "evaluation",
            "metrics",
            "results",
            "benchmarks",
            "scores",
        ]

        for field in performance_fields:
            if field in card_data:
                field_value = card_data[field]
                if isinstance(field_value, (dict, list)) and field_value:
                    result["has_benchmarks"] = True
                    # Try to extract metrics from these fields
                    if isinstance(field_value, dict):
                        for key, value in field_value.items():
                            if isinstance(value, (int, float)) and key.lower() in [
                                "accuracy",
                                "f1",
                                "precision",
                                "recall",
                                "bleu",
                                "rouge",
                                "perplexity",
                                "auc",
                            ]:
                                result["has_metrics"] = True
                                result["metrics"].append(key.lower())

    # Tertiary: Check for paper citations (more reliable than keyword matching)
    if isinstance(card_data, dict):
        # Check for paper-related fields
        paper_fields = ["paperswithcode", "arxiv", "citation", "bibtex", "paper"]
        for field in paper_fields:
            if field in card_data:
                field_value = card_data[field]
                if field_value and (
                    isinstance(field_value, str)
                    or (isinstance(field_value, list) and len(field_value) > 0)
                    or (isinstance(field_value, dict) and len(field_value) > 0)
                ):
                    result["has_papers"] = True
                    break

        # Check for model card text fields that might contain citations
        text_fields = ["model_card", "readme", "description", "summary"]
        for field in text_fields:
            if field in card_data:
                field_value = str(card_data[field]).lower()
                # Look for arxiv links or DOI patterns (more reliable than keywords)
                if "arxiv.org" in field_value or "doi.org" in field_value:
                    result["has_papers"] = True
                    break

    # Remove duplicates and set count
    result["metrics"] = list(set(result["metrics"]))
    result["metric_count"] = len(result["metrics"])

    return result
