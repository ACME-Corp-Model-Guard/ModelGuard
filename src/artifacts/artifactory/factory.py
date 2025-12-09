"""
Artifact factory functions for creating new artifacts.

This module contains the create_artifact() factory method and its helper functions.
The factory handles:
- Type-based artifact instantiation (Model/Dataset/Code)
- Metadata fetching from external sources (HuggingFace, GitHub, npm, PyPI)
- S3 upload orchestration for new artifacts
- Artifact connection (linking models to datasets/code)
- Metric computation for model artifacts

Complexity reduced: Original create_artifact() had complexity 21, now split into
functions with complexity ~5 each for better debugging and maintainability.
"""

from typing import Any, Dict

from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.artifacts.types import ArtifactType
from src.logger import logger
from src.storage.downloaders.dispatchers import (
    fetch_artifact_metadata,
    FileDownloadError,
)
from src.storage.s3_utils import upload_artifact_to_s3


# =============================================================================
# Public API
# =============================================================================


def create_artifact(artifact_type: ArtifactType, **kwargs: Any) -> BaseArtifact:
    """
    Create the appropriate artifact subclass and handle metadata fetching,
    artifact connection, and S3 upload for newly created artifacts.

    This is the main factory entry point used by Lambda handlers. The signature
    must remain stable as it's part of the public API.

    Args:
        artifact_type: One of 'model', 'dataset', 'code'
        **kwargs: Arguments specific to the artifact type's constructor
            Common kwargs: name, source_url, s3_key, metadata
            Model kwargs: size, license, scores, code_artifact_id, etc.

    Returns:
        BaseArtifact: Instance of ModelArtifact, DatasetArtifact, or CodeArtifact

    Raises:
        ValueError: If artifact_type is invalid
        FileDownloadError: If metadata fetch from upstream source fails
        KeyError: If required metadata fields are missing

    Example:
        # Create new model from HuggingFace (fetches metadata automatically)
        artifact = create_artifact(
            artifact_type="model",
            source_url="https://huggingface.co/bert-base-uncased"
        )

        # Recreate existing artifact from DynamoDB (no fetching/upload)
        artifact = create_artifact(
            artifact_type="model",
            name="bert-base-uncased",
            source_url="https://huggingface.co/bert-base-uncased",
            s3_key="models/abc-123-def",
            size=440000000,
            license="apache-2.0"
        )
    """
    logger.debug(f"Creating artifact of type: {artifact_type}")

    # Step 1: Get artifact class (factory pattern)
    artifact_class = _get_artifact_class(artifact_type)

    # Step 2: Enrich kwargs with external metadata if needed
    kwargs = _enrich_kwargs_with_metadata(artifact_type, kwargs)

    # Step 3: Instantiate artifact
    artifact = artifact_class(**kwargs)

    # Step 4: Initialize new artifacts (S3 upload, connections, scoring)
    if _is_new_artifact(kwargs):
        _initialize_new_artifact(artifact)

    logger.info(f"Created {artifact_type} artifact: {artifact.artifact_id}")
    return artifact


# =============================================================================
# Helper Functions (Internal)
# =============================================================================


def _get_artifact_class(artifact_type: ArtifactType) -> type[BaseArtifact]:
    """
    Map artifact type string to the appropriate artifact class.

    This is the factory pattern implementation that determines which
    concrete class to instantiate based on the artifact type.

    Args:
        artifact_type: One of 'model', 'dataset', 'code'

    Returns:
        The artifact class (ModelArtifact, DatasetArtifact, or CodeArtifact)

    Raises:
        ValueError: If artifact_type is not one of the valid types

    Extracted from: create_artifact() lines 54-64
    Complexity: 2 (was part of complexity 21 function)
    """
    artifact_map: Dict[str, type[BaseArtifact]] = {
        "model": ModelArtifact,
        "dataset": DatasetArtifact,
        "code": CodeArtifact,
    }

    if artifact_type not in artifact_map:
        logger.error(f"Invalid artifact_type in factory: {artifact_type}")
        raise ValueError(
            f"Invalid artifact_type: {artifact_type}. Must be one of {list(artifact_map.keys())}"
        )

    return artifact_map[artifact_type]


def _enrich_kwargs_with_metadata(
    artifact_type: ArtifactType, kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fetch external metadata and merge into kwargs if name not provided.

    If the caller provides a source_url but no name, this function will
    fetch metadata from the external source (HuggingFace, GitHub, npm, PyPI)
    and merge it into the kwargs dict. This allows creating artifacts with
    minimal input - just a URL.

    Args:
        artifact_type: Type of artifact being created
        kwargs: Constructor arguments (may be missing 'name')

    Returns:
        Updated kwargs dict with metadata merged in

    Raises:
        FileDownloadError: If metadata fetch fails
        KeyError: If expected metadata fields are missing

    Extracted from: create_artifact() lines 67-80
    Complexity: 4 (was part of complexity 21 function)
    """
    # Remove artifact_type from kwargs if accidentally passed
    # (it's not a constructor parameter)
    kwargs.pop("artifact_type", None)

    # Only fetch metadata if name is not provided
    url = kwargs.get("source_url")
    if not kwargs.get("name") and isinstance(url, str):
        try:
            logger.debug(f"Fetching metadata for {artifact_type} from {url}")
            metadata = fetch_artifact_metadata(url=url, artifact_type=artifact_type)
            kwargs.update(metadata)
            logger.debug(f"Enriched kwargs with metadata: {list(metadata.keys())}")
        except FileDownloadError as e:
            logger.error(f"Failed to fetch metadata for artifact creation: {e}")
            raise
        except KeyError as e:
            logger.error(
                f"Missing expected metadata field during artifact creation: {e}"
            )
            raise

    return kwargs


def _is_new_artifact(kwargs: Dict[str, Any]) -> bool:
    """
    Determine if this is a new artifact (vs loading existing from DynamoDB).

    New artifacts need S3 upload, artifact connection, and score computation.
    Existing artifacts (loaded from DynamoDB) already have s3_key and skip these steps.

    Args:
        kwargs: Constructor arguments

    Returns:
        True if this is a new artifact, False if loading existing

    Extracted from: create_artifact() line 87 check
    Complexity: 1 (was part of complexity 21 function)
    """
    return not kwargs.get("s3_key")


def _initialize_new_artifact(artifact: BaseArtifact) -> None:
    """
    Initialize a newly created artifact with S3 upload, connections, and scoring.

    This function orchestrates the post-creation steps for new artifacts:
    1. Upload artifact files to S3
    2. Connect artifact to related artifacts (models to datasets/code)
    3. Compute initial metric scores (model artifacts only)

    Args:
        artifact: The newly created artifact instance

    Side Effects:
        - Uploads artifact to S3
        - Modifies artifact to add connection IDs (code_artifact_id, etc.)
        - Computes and stores metric scores (models only)
        - May modify related artifacts (updates parent/child relationships)

    Extracted from: create_artifact() lines 86-105
    Complexity: 3 (was part of complexity 21 function)
    """
    logger.debug(f"Initializing new artifact: {artifact.artifact_id}")

    # Step 1: Upload to S3
    upload_artifact_to_s3(
        artifact_id=artifact.artifact_id,
        artifact_type=artifact.artifact_type,
        s3_key=artifact.s3_key,
        source_url=artifact.source_url,
    )

    # Step 2: Connect to related artifacts (lazy import to avoid circular dependency)
    from .connections import connect_artifact

    connect_artifact(artifact)

    # Step 3: Compute scores for model artifacts
    if isinstance(artifact, ModelArtifact):
        _compute_initial_scores(artifact)


def _compute_initial_scores(artifact: ModelArtifact) -> None:
    """
    Compute initial metric scores for a newly created model artifact.

    Uses the metrics registry to compute all configured metrics in parallel.
    Also initializes security-related fields like suspected_package_confusion.

    Args:
        artifact: The model artifact to score

    Side Effects:
        - Populates artifact.scores dict
        - Populates artifact.scores_latency dict
        - Sets artifact.suspected_package_confusion = False

    Extracted from: create_artifact() lines 97-102 + fix for unreachable code bug
    Complexity: 2 (was part of complexity 21 function)
    """
    # Lazy import to avoid circular dependency (metrics imports artifactory)
    from src.metrics.registry import METRICS

    logger.debug(f"Computing initial scores for model: {artifact.artifact_id}")
    artifact.compute_scores(METRICS)

    # Initialize security fields
    # NOTE: This was previously unreachable dead code at lines 107-110
    # Moving it here fixes the bug and ensures it actually runs
    artifact.suspected_package_confusion = False
