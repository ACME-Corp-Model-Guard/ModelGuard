"""
Artifact connection logic for linking related artifacts.

This module uses Python's singledispatch to implement type-specific connection logic:
- ModelArtifact: Links to code, dataset, parent models, and child models
- CodeArtifact: Links to models that use this code
- DatasetArtifact: Links to models that use this dataset

Connections are bidirectional - when a code artifact is uploaded, it automatically
links to existing models that reference it by name, and vice versa.
"""

from functools import singledispatch
from typing import List

from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.logutil import clogger
from .discovery import _find_connected_artifact_names
from .persistence import (
    load_all_artifacts,
    load_all_artifacts_by_fields,
    load_artifact_metadata,
    save_artifact_metadata,
)
from .rejection import scores_below_threshold, promote


# =============================================================================
# Public API (Internal to artifactory module)
# =============================================================================


@singledispatch
def connect_artifact(artifact: BaseArtifact) -> None:
    """
    Artifact connection dispatcher using singledispatch.

    Routes to the appropriate type-specific connection implementation based
    on the artifact's concrete type (ModelArtifact, CodeArtifact, DatasetArtifact).

    Args:
        artifact: The artifact to connect

    Raises:
        NotImplementedError: If no implementation exists for the artifact type
    """
    raise NotImplementedError(f"No connector logic for artifact type: {artifact.artifact_type}")


@connect_artifact.register
def _(artifact: ModelArtifact) -> None:
    """
    Connect model artifact to related artifacts (code, dataset, parent/child models).

    This function:
    1. Uses LLM to extract connected artifact names from model files
    2. Searches for matching code/dataset/parent model artifacts by name
    3. Links them by setting artifact IDs (code_artifact_id, dataset_artifact_id, etc.)
    4. Handles bidirectional parent-child relationships
    5. Triggers metric recomputation for affected models

    Side Effects:
        - Modifies artifact to add connection IDs
        - May modify child models to link to this parent
        - Saves updated child models to DynamoDB
        - Triggers metric recomputation on child models

    Args:
        artifact: The model artifact to connect
    """
    # Step 1: Extract connected artifact names using LLM
    _find_connected_artifact_names(artifact)

    # Step 2: Load all artifacts once (optimization - reuse for multiple searches)
    all_artifacts: List[BaseArtifact] = load_all_artifacts()

    # Step 3: Connect to code artifact if name was found
    if artifact.code_name and not artifact.code_artifact_id:
        code_artifacts = load_all_artifacts_by_fields(
            fields={"name": artifact.code_name},
            artifact_type="code",
            artifact_list=all_artifacts,
        )
        if code_artifacts:
            code_artifact = code_artifacts[0]
            if isinstance(code_artifact, CodeArtifact):
                artifact.code_artifact_id = code_artifact.artifact_id

    # Step 4: Connect to dataset artifact if name was found
    if artifact.dataset_name and not artifact.dataset_artifact_id:
        dataset_artifacts = load_all_artifacts_by_fields(
            fields={"name": artifact.dataset_name},
            artifact_type="dataset",
            artifact_list=all_artifacts,
        )
        if dataset_artifacts:
            dataset_artifact = dataset_artifacts[0]
            if isinstance(dataset_artifact, DatasetArtifact):
                artifact.dataset_artifact_id = dataset_artifact.artifact_id

    # Step 5: Connect to parent model if name was found
    parent_model_artifact: BaseArtifact | None = None
    if artifact.parent_model_name and not artifact.parent_model_id:
        parent_model_artifacts = load_all_artifacts_by_fields(
            fields={"name": artifact.parent_model_name},
            artifact_type="model",
            artifact_list=all_artifacts,
        )
        if parent_model_artifacts:
            parent_model_artifact = parent_model_artifacts[0]
            if isinstance(parent_model_artifact, ModelArtifact):
                artifact.parent_model_id = parent_model_artifact.artifact_id

    # Step 6: Check if this model is the parent of any existing models
    def update_child_models(artifact_list: List[BaseArtifact]) -> List[BaseArtifact]:
        if artifact.child_model_ids is None:
            artifact.child_model_ids = []
            model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
                fields={"parent_model_name": artifact.name},
                artifact_type="model",
                artifact_list=artifact_list,
            )

            # Update child model artifacts to link to this parent model
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

                child_model_artifact.compute_scores(LINEAGE_METRICS)  # recompute relevant scores

                save_artifact_metadata(child_model_artifact)  # save updated child model
                artifact.child_model_ids.append(
                    child_model_artifact.artifact_id
                )  # update this model for lineage
            return model_artifacts
        return []

    # Update ingested child models
    child_models = update_child_models(all_artifacts)

    # Do the same, but for rejected artifacts.
    # If scores valid, ingest.
    all_rejected_artifacts: List[BaseArtifact] = load_all_artifacts(rejected=True)
    rejected_child_models = update_child_models(all_rejected_artifacts)

    for child_model in rejected_child_models:
        if isinstance(child_model, ModelArtifact):
            failing_metrics = scores_below_threshold(child_model)
            if not failing_metrics:
                promote(child_model)

    clogger.info(
        f"Connected artifact {artifact.artifact_id} ({artifact.artifact_type}) "
        f"to Parent {parent_model_artifact}, existing children {child_models}, "
        f"and rejected children {rejected_child_models}"
    )


@connect_artifact.register
def _(artifact: CodeArtifact) -> None:
    """
    Connect code artifact to related model artifacts.

    Searches for models that reference this code by name and creates bidirectional links.
    Triggers recomputation of code-quality metrics for linked models.

    Side Effects:
        - Modifies linked model artifacts to set code_artifact_id
        - Triggers CODE_METRICS recomputation for linked models
        - Saves updated model artifacts to DynamoDB

    Args:
        artifact: The code artifact to connect
    """

    def update_connected_models(artifacts: List[BaseArtifact], rejected: bool = False) -> None:
        # Update linked model artifacts to reference this code artifact
        for model_artifact in model_artifacts:
            if not isinstance(model_artifact, ModelArtifact) or model_artifact.code_artifact_id:
                model_artifacts.pop(model_artifacts.index(model_artifact))
                continue
            model_artifact.code_artifact_id = artifact.artifact_id

            from src.metrics.registry import (
                CODE_METRICS,
            )  # Lazy import to avoid circular dependency

            model_artifact.compute_scores(CODE_METRICS)  # Recompute scores

            if not rejected:
                save_artifact_metadata(model_artifact)
            elif not scores_below_threshold(model_artifact):
                promote(model_artifact)

    # Get all models (both accepted and rejected)
    model_artifacts: List[BaseArtifact] = load_all_artifacts()
    rejected_model_artifacts: List[BaseArtifact] = load_all_artifacts(rejected=True)

    # Find all models that reference this code by name (both accepted and rejected)
    connected_model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
        fields={"code_name": artifact.name},
        artifact_type="model",
        artifact_list=model_artifacts,
    )
    update_connected_models(connected_model_artifacts)

    connected_rejected_model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
        fields={"code_name": artifact.name},
        artifact_type="model",
        artifact_list=rejected_model_artifacts,
    )
    update_connected_models(connected_rejected_model_artifacts, rejected=True)

    clogger.info(
        f"Connected artifact {artifact.artifact_id} ({artifact.artifact_type}) "
        f"to Models {connected_model_artifacts} "
        f"and Rejected Models {connected_rejected_model_artifacts}"
    )


@connect_artifact.register
def _(artifact: DatasetArtifact) -> None:
    """
    Connect dataset artifact to related model artifacts.

    Searches for models that reference this dataset by name and creates bidirectional links.
    Triggers recomputation of dataset-quality metrics for linked models.

    Side Effects:
        - Modifies linked model artifacts to set dataset_artifact_id
        - Triggers DATASET_METRICS recomputation for linked models
        - Saves updated model artifacts to DynamoDB

    Args:
        artifact: The dataset artifact to connect
    """

    def update_connected_models(artifacts: List[BaseArtifact], rejected: bool = False) -> None:
        # Update linked model artifacts to reference this dataset artifact
        for model_artifact in model_artifacts:
            if not isinstance(model_artifact, ModelArtifact) or model_artifact.dataset_artifact_id:
                model_artifacts.pop(model_artifacts.index(model_artifact))
                continue
            model_artifact.dataset_artifact_id = artifact.artifact_id

            from src.metrics.registry import (
                DATASET_METRICS,
            )  # Lazy import to avoid circular dependency

            model_artifact.compute_scores(DATASET_METRICS)  # Recompute scores

            if not rejected:
                save_artifact_metadata(model_artifact)
            elif not scores_below_threshold(model_artifact):
                promote(model_artifact)

    # Get all models (both accepted and rejected)
    model_artifacts: List[BaseArtifact] = load_all_artifacts()
    rejected_model_artifacts: List[BaseArtifact] = load_all_artifacts(rejected=True)

    # Find all models that reference this dataset by name (both accepted and rejected)
    connected_model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
        fields={"dataset_name": artifact.name},
        artifact_type="model",
        artifact_list=model_artifacts,
    )
    update_connected_models(connected_model_artifacts)

    connected_rejected_model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
        fields={"dataset_name": artifact.name},
        artifact_type="model",
        artifact_list=rejected_model_artifacts,
    )
    update_connected_models(connected_rejected_model_artifacts, rejected=True)

    clogger.info(
        f"Connected artifact {artifact.artifact_id} ({artifact.artifact_type}) "
        f"to Models {connected_model_artifacts} "
        f"and Rejected Models {connected_rejected_model_artifacts}"
    )
