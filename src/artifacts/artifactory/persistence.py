"""
Artifact persistence functions for DynamoDB storage and retrieval.

This module contains functions for:
- Saving artifacts to DynamoDB
- Loading single artifacts by ID
- Loading all artifacts (full table scan)
- Filtering artifacts by field values with case-insensitive matching
"""

from typing import Any, Dict, List, Optional

from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.types import ArtifactType
from src.logger import logger
from src.settings import ARTIFACTS_TABLE
from src.storage.dynamo_utils import save_item_to_table, load_item_from_key, scan_table


# =============================================================================
# Public API
# =============================================================================


def save_artifact_metadata(artifact: BaseArtifact) -> None:
    """
    Store artifact metadata in DynamoDB.

    Args:
        artifact: The artifact instance to save

    Raises:
        ClientError: If DynamoDB operation fails
    """
    save_item_to_table(ARTIFACTS_TABLE, artifact.to_dict())


def load_artifact_metadata(artifact_id: str) -> Optional[BaseArtifact]:
    """
    Retrieve artifact metadata from DynamoDB and reconstruct the artifact instance.

    This function loads the artifact metadata dict from DynamoDB and uses
    create_artifact() to reconstruct the full artifact object (Model/Dataset/Code).

    Args:
        artifact_id: UUID of the artifact to load

    Returns:
        BaseArtifact instance (ModelArtifact, DatasetArtifact, or CodeArtifact) or None if not found

    Raises:
        ValueError: If artifact is missing artifact_type field
    """
    from .factory import create_artifact  # Lazy import to avoid circular dependency

    item = load_item_from_key(ARTIFACTS_TABLE, {"artifact_id": artifact_id})
    if not item:
        logger.warning(f"Artifact {artifact_id} not found")
        return None

    artifact_type = item.get("artifact_type")
    if not artifact_type:
        raise ValueError(f"Artifact {artifact_id} missing artifact_type field")

    # Don't pass artifact_type twice (it's used by factory, not constructor)
    kwargs = dict(item)
    kwargs.pop("artifact_type", None)

    artifact = create_artifact(artifact_type, **kwargs)
    logger.info(f"Loaded {artifact_type} artifact {artifact_id}")
    return artifact


def load_all_artifacts() -> List[BaseArtifact]:
    """
    Load all artifacts from the DynamoDB table.

    Performs a full table scan and reconstructs all artifacts. This can be expensive
    for large tables. Consider using load_all_artifacts_by_fields() with artifact_list
    parameter if you already have artifacts loaded.

    Returns:
        List of BaseArtifact instances

    Raises:
        Exception: If table scan or artifact reconstruction fails
    """
    from .factory import create_artifact  # Lazy import to avoid circular dependency

    artifacts: List[BaseArtifact] = []

    try:
        items = scan_table(ARTIFACTS_TABLE)

        for item in items:
            artifact_id = item.get("artifact_id")
            artifact_type = item.get("artifact_type")
            if not artifact_type:
                logger.warning(f"Artifact {artifact_id} missing artifact_type field")
                continue

            # Don't pass artifact_type twice
            kwargs = dict(item)
            kwargs.pop("artifact_type", None)

            artifact = create_artifact(artifact_type, **kwargs)
            artifacts.append(artifact)

        logger.info(f"Loaded {len(artifacts)} artifacts from {ARTIFACTS_TABLE}")
        return artifacts

    except Exception as e:
        logger.error(f"Failed to load all artifacts: {e}")
        raise


def load_all_artifacts_by_fields(
    fields: Dict[str, Any],
    artifact_type: Optional[ArtifactType] = None,
    artifact_list: Optional[List[BaseArtifact]] = None,
) -> List[BaseArtifact]:
    """
    Load artifacts matching specific field criteria.

    This function filters artifacts by field values with case-insensitive string matching.
    If artifact_list is provided, searches within it. Otherwise loads all artifacts.

    Args:
        fields: Dictionary of field names and their expected values
            Example: {"name": "bert-base-uncased"} or {"license": "MIT"}
        artifact_type: Optional filter by artifact type ('model', 'dataset', 'code')
        artifact_list: Optional pre-loaded artifact list to search within (optimization)

    Returns:
        List of artifacts matching all criteria

    Example:
        # Find all MIT-licensed models
        models = load_all_artifacts_by_fields(
            fields={"license": "mit"},  # case-insensitive
            artifact_type="model"
        )

        # Find artifact by name (used by search endpoints)
        results = load_all_artifacts_by_fields(
            fields={"name": "bert-base-uncased"}
        )
    """
    # Get candidate artifacts (from provided list or load all)
    candidates = artifact_list if artifact_list else load_all_artifacts()

    # Filter by artifact type if specified
    if artifact_type:
        candidates = _filter_by_type(candidates, artifact_type)

    # Filter by field values
    return _filter_by_fields(candidates, fields)


# =============================================================================
# Helper Functions (Internal)
# =============================================================================


def _filter_by_type(
    artifacts: List[BaseArtifact], artifact_type: ArtifactType
) -> List[BaseArtifact]:
    """
    Filter artifacts to only those matching the specified type.

    Args:
        artifacts: List of artifacts to filter
        artifact_type: Type to keep ('model', 'dataset', 'code')

    Returns:
        Filtered list containing only artifacts of the specified type
    """
    return [a for a in artifacts if a.artifact_type == artifact_type]


def _filter_by_fields(
    artifacts: List[BaseArtifact], fields: Dict[str, Any]
) -> List[BaseArtifact]:
    """
    Filter artifacts to only those matching all specified field criteria.

    Args:
        artifacts: List of artifacts to filter
        fields: Dictionary of field names and expected values

    Returns:
        List of artifacts matching all field criteria
    """
    return [a for a in artifacts if _matches_all_fields(a, fields)]


def _matches_all_fields(artifact: BaseArtifact, fields: Dict[str, Any]) -> bool:
    """
    Check if an artifact matches all specified field criteria.

    Uses case-insensitive comparison for string fields.

    Args:
        artifact: Artifact to check
        fields: Dictionary of field names and expected values

    Returns:
        True if artifact matches all criteria, False otherwise
    """
    for field_name, expected_value in fields.items():
        actual_value = getattr(artifact, field_name, None)
        if not _values_equal_ignoring_case(actual_value, expected_value):
            return False
    return True


def _values_equal_ignoring_case(actual: Any, expected: Any) -> bool:
    """
    Compare two values with case-insensitive string matching.

    For non-string types, uses standard equality. For strings, converts
    to lowercase before comparing.

    Args:
        actual: Actual value from artifact
        expected: Expected value from filter criteria

    Returns:
        True if values are equal (case-insensitive for strings)

    Examples:
        >>> _values_equal_ignoring_case("MIT", "mit")
        True
        >>> _values_equal_ignoring_case(123, 123)
        True
        >>> _values_equal_ignoring_case("Apache-2.0", "apache-2.0")
        True
    """
    # Convert strings to lowercase for case-insensitive comparison
    if isinstance(actual, str):
        actual = actual.lower()
    if isinstance(expected, str):
        expected = expected.lower()

    return actual == expected
