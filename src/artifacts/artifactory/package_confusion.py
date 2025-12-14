"""
Package confusion detection logic for model artifacts.
"""

from src.artifacts.model_artifact import ModelArtifact
from huggingface_hub import list_models
from src.logutil import clogger

from difflib import SequenceMatcher
from typing import List
from datetime import datetime, timezone

# =============================================================================
# Public API
# =============================================================================


SIMILARITY_SUSPICION_THRESHOLD = 0.8


def is_suspected_package_confusion(model: ModelArtifact) -> bool:
    """
    Determine if a model artifact is suspected of package confusion
    based on its name similarity to popular models.

    Args:
        Model: The ModelArtifact instance to evaluate.
    """

    # Canonical models are not suspected
    popular_models = set(_get_popular_models())
    if is_canonical(model, popular_models):
        clogger.debug(
            f"Model {model.artifact_id} ('{model.name}') is canonical, "
            f"not suspected of package confusion"
        )
        return False

    # Similarity testing
    similarity_score = _max_similarity_to_popular_models(model.name, popular_models)
    clogger.debug(
        f"Model {model.artifact_id} ('{model.name}') similarity score to popular models: "
        f"{similarity_score:.2f}"
    )

    if similarity_score >= SIMILARITY_SUSPICION_THRESHOLD:
        clogger.info(
            f"Model {model.artifact_id} ('{model.name}') suspected of package confusion "
            f"with similarity score {similarity_score:.2f}"
        )
        return True

    # Anomalous download rate testing
    # Sucpicious if 100 downloads in 3 days, 300 in 7 days, or 1000 in 30 days
    if (
        _has_anomalous_downloads(model, test_age=3, test_downloads=100)
        or _has_anomalous_downloads(model, test_age=7, test_downloads=300)
        or _has_anomalous_downloads(model, test_age=30, test_downloads=1000)
    ):
        clogger.info(
            f"Model {model.artifact_id} ('{model.name}') suspected of package confusion "
            f"due to anomalous download patterns"
        )
        return True


# ============================================================================
# Helpers
# ============================================================================


def is_canonical(model: ModelArtifact, popular_models: List[str]):
    """
    Determine if a model is canonical based on its ID and stats.

    Args:
        model: The ModelArtifact instance
        popular_models: List of popular model IDs
    """
    return (
        model.artifact_id in popular_models
        or model.metadata.get("downloads", 0) > 1_000_000
        or model.metadata.get("likes", 0) > 1_000
    )


# =============================================================================
# Similarity to Popular Models Helpers
# =============================================================================


def _get_popular_models(limit=500):
    """
    Get a list of popular model IDs from Hugging Face Hub.
    """
    return [m.modelId for m in list_models(sort="downloads", direction=-1, limit=limit)]


def _similarity(a: str, b: str) -> float:
    """
    Compute similarity ratio between two strings.

    Args:
        a: First string
        b: Second string
    """
    return SequenceMatcher(None, a, b).ratio()


def _max_similarity_to_popular_models(model_name: str, popular_models: list) -> float:
    """
    Compute the maximum similarity of the given model name to a list of popular model names.

    Args:
        model_name: The model name to compare
        popular_models: List of popular model names
    """
    return max(_similarity(model_name, popular) for popular in popular_models)


# =============================================================================
# Anomalous Download Detection Helpers
# =============================================================================


def _parse_iso_date(date_str: str) -> datetime:
    """
    Parse ISO 8601 string into a timezone-aware UTC datetime.
    """
    if not date_str:
        raise ValueError("Missing created_at timestamp")

    # Handle trailing Z
    if date_str.endswith("Z"):
        dt = datetime.fromisoformat(date_str[:-1])
        return dt.replace(tzinfo=timezone.utc)

    dt = datetime.fromisoformat(date_str)

    # Normalize to UTC if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _get_model_age_days(model: ModelArtifact) -> int:
    """
    Estimate average downloads per day for the model.

    Args:
        model: The ModelArtifact instance
    """
    created_at = model.metadata.get("created_at")

    try:
        created = _parse_iso_date(created_at)
    except ValueError:
        clogger.debug(f"Model {model.artifact_id} has invalid or missing created_at '{created_at}'")
        return 0.0

    now = datetime.now(timezone.utc)
    age_days = max((now - created).days, 1)

    return age_days


def _has_anomalous_downloads(model: ModelArtifact, test_age: int, test_downloads: int) -> bool:
    """
    Determine if a model has anomalous download patterns.

    Args:
        model: The ModelArtifact instance
    """
    model_age = _get_model_age_days(model)
    downloads = model.metadata.get("downloads", 0)

    if model_age <= test_age and downloads >= test_downloads:
        return True

    return False
