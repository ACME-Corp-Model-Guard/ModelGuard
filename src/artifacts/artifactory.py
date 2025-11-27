"""
Artifactory: Centralized artifact creation and loading

Provides:
- create_artifact: Factory method to create Model, Dataset, or Code artifacts, handles metadata fetching, artifact connection, and S3 upload for newly created artifacts.
- Artifact-specific metadata storage operations: save_artifact_metadata, load_artifact_metadata, load_all_artifacts, load_all_artifacts_by_fields
"""

from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.artifacts.types import ArtifactType
from src.logger import logger
from src.settings import ARTIFACTS_TABLE
from src.storage.downloaders.dispatchers import (
    fetch_artifact_metadata,
    FileDownloadError,
)
from src.storage.dynamo_utils import save_item_to_table, load_item_from_key, scan_table
from src.storage.s3_utils import (
    upload_artifact_to_s3,
    download_artifact_from_s3,
)
from src.storage.file_extraction import extract_relevant_files
from src.utils.llm_analysis import (
    build_extract_fields_from_files_prompt,
    ask_llm,
)
from functools import singledispatch
from typing import Any, Dict, List, Optional, Union

# =============================================================================
# Artifact Creation
# =============================================================================


def create_artifact(artifact_type: ArtifactType, **kwargs: Any) -> BaseArtifact:
    """
    Create the appropriate artifact subclass and handle metadata fetching, artifact connection, and S3 upload for newly created artifacts.

    Args:
        artifact_type: One of 'model', 'dataset', 'code'
        **kwargs: Arguments specific to the artifact type's constructor
    Returns:
        BaseArtifact: Instance of the created artifact subclass
    """
    logger.debug(f"Creating artifact of type: {artifact_type}")

    # Determine artifact class based on type
    artifact_map = {
        "model": ModelArtifact,
        "dataset": DatasetArtifact,
        "code": CodeArtifact,
    }
    if artifact_type not in artifact_map:
        logger.error(f"Invalid artifact_type in factory: {artifact_type}")
        raise ValueError(
            f"Invalid artifact_type: {artifact_type}. Must be one of {list(artifact_map.keys())}"
        )
    artifact_class = artifact_map[artifact_type]
    kwargs.pop("artifact_type", None)  # Remove if accidentally passed

    # if not name, then this model has no metadata yet; fetch it
    url = kwargs.get("source_url")
    if not kwargs.get("name") and isinstance(url, str):
        try:
            metadata = fetch_artifact_metadata(url=url, artifact_type=artifact_type)
            kwargs.update(metadata)
        except FileDownloadError as e:
            logger.error(f"Failed to fetch metadata for artifact creation: {e}")
            raise
        except KeyError as e:
            logger.error(
                f"Missing expected metadata field during artifact creation: {e}"
            )
            raise

    # Create artifact instance
    artifact = artifact_class(artifact_type=artifact_type, **kwargs)

    # Only upload/connect if s3_key was not provided (new artifact)
    if not kwargs.get("s3_key"):
        upload_artifact_to_s3(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            s3_key=artifact.s3_key,
            source_url=artifact.source_url,
        )
        connect_artifact(artifact)

    # If it's a model artifact, compute scores if metrics provided
    if isinstance(artifact, ModelArtifact):
        from src.metrics.registry import (
            METRICS,
        )  # Lazy import to avoid circular dependency

        artifact.compute_scores(METRICS)  # Compute scores with provided metrics

    logger.info(f"Created {artifact_type} artifact: {artifact.artifact_id}")
    return artifact


# =============================================================================
# Artifact-Specific Metadata Storage Operations
# =============================================================================
def save_artifact_metadata(artifact: BaseArtifact) -> None:
    """
    Store artifact metadata in DynamoDB.
    """
    save_item_to_table(ARTIFACTS_TABLE, artifact.to_dict())


def load_artifact_metadata(artifact_id: str) -> Optional[BaseArtifact]:
    """
    Retrieve artifact metadata from DynamoDB and build a BaseArtifact instance.

    Returns:
        BaseArtifact instance or None if not found.
    """
    item = load_item_from_key(ARTIFACTS_TABLE, {"artifact_id": artifact_id})
    if not item:
        logger.warning(f"Artifact {artifact_id} not found")
        return None

    artifact_type = item.get("artifact_type")
    if not artifact_type:
        raise ValueError(f"Artifact {artifact_id} missing artifact_type field")

    # Don't pass artifact_type twice
    kwargs = dict(item)
    kwargs.pop("artifact_type", None)

    artifact = create_artifact(artifact_type, **kwargs)
    logger.info(f"Loaded {artifact_type} artifact {artifact_id}")
    return artifact


def load_all_artifacts() -> List[BaseArtifact]:
    """
    Load all artifacts from the DynamoDB table.

    Returns:
        List of BaseArtifact instances.
    """
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
    artifact_type: Optional[ArtifactType] = None,  # Optional filter by artifact type
    artifact_list: Optional[
        List[BaseArtifact]
    ] = None,  # artifact_list can be used to avoid a full table scan
) -> List[BaseArtifact]:
    """
    Load all artifacts from the DynamoDB table matching a specific field value.

    Args:
        fields: Dictionary of field names and their expected values.
        artifact_type: Optional filter by artifact type.
        artifact_list: Optional list of artifacts to search within (avoids full table scan).
    """
    rows: List[BaseArtifact] = []
    if not artifact_list:
        rows = load_all_artifacts()
    else:
        rows = artifact_list
    artifacts: List[BaseArtifact] = []

    for row in rows:
        if artifact_type and row.artifact_type != artifact_type:
            continue

        for field_name, field_value in fields.items():
            attribute: Any = getattr(row, field_name, None)
            # Convert strings to lowercase for case-insensitive comparison
            if isinstance(attribute, str):
                attribute = attribute.lower()
            if isinstance(field_value, str):
                field_value = field_value.lower()
            if attribute != field_value:
                break
        else:
            artifacts.append(row)

    return artifacts


# =============================================================================
# Helpers
# =============================================================================
def _find_connected_artifact_names(artifact: ModelArtifact) -> None:
    """
    Use LLM to extract connected artifact names from model files.
    Populates code_name, dataset_name, parent_model_name, parent_model_source, parent_model_relationship fields.
    """
    try:
        download_artifact_from_s3(
            artifact_id=artifact.artifact_id,
            s3_key=artifact.s3_key,
            local_path="/tmp/model_artifact_files",
        )

        files: Dict[str, str] = extract_relevant_files(
            tar_path="/tmp/model_artifact_files",
            include_ext={".json", ".md", ".txt"},
            max_files=10,
            prioritize_readme=True,
        )

        prompt: str = build_extract_fields_from_files_prompt(
            fields=[
                "code_name",
                "dataset_name",
                "parent_model_name",
                "parent_model_source",
                "parent_model_relationship",
            ],
            files=files,
        )

        response: Optional[Union[str, Dict[str, Any]]] = ask_llm(
            prompt, return_json=True
        )
        if not response or not isinstance(response, dict):
            logger.warning(
                f"LLM failed to extract connected artifact names for {artifact.artifact_id}"
            )
            return

        if not artifact.code_name:
            artifact.code_name = response.get("code_name")
        if not artifact.dataset_name:
            artifact.dataset_name = response.get("dataset_name")
        if not artifact.parent_model_name:
            artifact.parent_model_name = response.get("parent_model_name")
        if not artifact.parent_model_source:
            artifact.parent_model_source = response.get("parent_model_source")
        if not artifact.parent_model_relationship:
            artifact.parent_model_relationship = response.get(
                "parent_model_relationship"
            )
        logger.info(
            f"Extracted code_name='{artifact.code_name}', dataset_name='{artifact.dataset_name}', parent_model_name='{artifact.parent_model_name}' "
            f"for model artifact: {artifact.artifact_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to extract connected artifact names for {artifact.artifact_id}: {e}"
        )


# ============================================================================
# Artifact Connectors
# ============================================================================


@singledispatch
def connect_artifact(artifact: BaseArtifact) -> None:
    """
    Artifact dispatcher. Calls the appropriate connector function based on artifact type.
    """
    raise NotImplementedError(
        f"No connector logic for artifact type: {artifact.artifact_type}"
    )


@connect_artifact.register
def _(artifact: ModelArtifact) -> None:
    """
    Connects the given artifact to related artifacts (code, dataset, parent/child models).
    Updates references and saves changes as needed.
    """
    # Populate connected artifact names first
    _find_connected_artifact_names(artifact)

    # Get all artifacts
    all_artifacts: List[BaseArtifact] = load_all_artifacts()

    # Connect to code (first matching)
    if artifact.code_name and not artifact.code_artifact_id:
        code_artifact: BaseArtifact = load_all_artifacts_by_fields(
            fields={"name": artifact.code_name},
            artifact_type="code",
            artifact_list=all_artifacts,
        )[0]
        if code_artifact and isinstance(code_artifact, CodeArtifact):
            artifact.code_artifact_id = code_artifact.artifact_id

    # Connect to dataset (first matching)
    if artifact.dataset_name and not artifact.dataset_artifact_id:
        dataset_artifact: BaseArtifact = load_all_artifacts_by_fields(
            fields={"name": artifact.dataset_name},
            artifact_type="dataset",
            artifact_list=all_artifacts,
        )[0]
        if dataset_artifact and isinstance(dataset_artifact, DatasetArtifact):
            artifact.dataset_artifact_id = dataset_artifact.artifact_id

    # Connect to parent model (first matching)
    if artifact.parent_model_name and not artifact.parent_model_id:
        parent_model_artifact: BaseArtifact = load_all_artifacts_by_fields(
            fields={"name": artifact.parent_model_name},
            artifact_type="model",
            artifact_list=all_artifacts,
        )[0]
        if parent_model_artifact and isinstance(parent_model_artifact, ModelArtifact):
            artifact.parent_model_id = parent_model_artifact.artifact_id

    # Check if this model is the parent model of other existing models
    if artifact.child_model_ids is None:
        artifact.child_model_ids = []
        model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
            fields={"parent_model_name": artifact.name},
            artifact_type="model",
            artifact_list=all_artifacts,
        )

        # Update child model artifact to link to this parent model
        for model_artifact in model_artifacts:
            child_model_artifact: BaseArtifact | None = load_artifact_metadata(
                model_artifact.artifact_id
            )
            if not isinstance(child_model_artifact, ModelArtifact):
                continue
            child_model_artifact.parent_model_id = (
                artifact.artifact_id
            )  # link to this parent model

            from src.metrics.registry import (
                LINEAGE_METRICS,
            )  # Lazy import to avoid circular dependency

            child_model_artifact.compute_scores(
                LINEAGE_METRICS
            )  # recompute relevant scores

            save_artifact_metadata(child_model_artifact)  # save updated child model
            artifact.child_model_ids.append(
                child_model_artifact.artifact_id
            )  # update this model for lineage
    logger.info(f"Connected artifact {artifact.artifact_id} ({artifact.artifact_type})")


@connect_artifact.register
def _(artifact: CodeArtifact) -> None:
    """
    Connects the given code artifact to related model artifacts.
    Updates references and saves changes as needed.
    """
    # Check if this code is connected to any models
    model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
        fields={"code_name": artifact.name},
        artifact_type="model",
    )

    # Update linked model artifacts to reference this code artifact
    for model_artifact in model_artifacts:
        if (
            not isinstance(model_artifact, ModelArtifact)
            or model_artifact.code_artifact_id
        ):
            continue
        model_artifact.code_artifact_id = artifact.artifact_id

        from src.metrics.registry import (
            CODE_METRICS,
        )  # Lazy import to avoid circular dependency

        model_artifact.compute_scores(CODE_METRICS)  # Recompute scores

        save_artifact_metadata(model_artifact)
    logger.info(f"Connected artifact {artifact.artifact_id} ({artifact.artifact_type})")


@connect_artifact.register
def _(artifact: DatasetArtifact) -> None:
    """
    Connects the given dataset artifact to related model artifacts.
    Updates references and saves changes as needed.
    """
    # Check if this dataset is connected to any models
    model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
        fields={"dataset_name": artifact.name},
        artifact_type="model",
    )

    # Update linked model artifacts to reference this dataset artifact
    for model_artifact in model_artifacts:
        if (
            not isinstance(model_artifact, ModelArtifact)
            or model_artifact.dataset_artifact_id
        ):
            continue
        model_artifact.dataset_artifact_id = artifact.artifact_id

        from src.metrics.registry import (
            DATASET_METRICS,
        )  # Lazy import to avoid circular dependency

        model_artifact.compute_scores(DATASET_METRICS)  # Recompute scores

        save_artifact_metadata(model_artifact)
    logger.info(f"Connected artifact {artifact.artifact_id} ({artifact.artifact_type})")
