"""
Artifact connection and upload manager for ModelGuard.

Provides:
- artifact_connector: Connects an artifact to related artifacts (code, dataset, parent/child models)
- artifact_uploader: Uploads an artifact to S3
"""

from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.storage.dynamo_utils import (
    load_all_artifacts,
    load_all_artifacts_by_fields,
    save_artifact_metadata,
)
from src.storage.s3_utils import (
    upload_artifact_to_s3,
    download_artifact_from_s3,
)
from src.utils.llm_analysis import (
    build_extract_fields_from_files_prompt,
    ask_llm,
)
from src.storage.file_extraction import extract_relevant_files
from src.logger import logger
from typing import List, Dict, Any, overload
from functools import singledispatch

# ============================================================================
# Helpers
# ============================================================================

def _find_connected_artifact_names(artifact: BaseArtifact) -> None:
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
                "parent_model_relationship"
            ],
            files=files,
        )

        response: Optional[Union[str, Dict[str, Any]]] = ask_llm(prompt, return_json=True)

        if not artifact.code_name:
            artifact.code_name = response.get("code_name")
        if not artifact.dataset_name:
            artifact.dataset_name = response.get("dataset_name")
        if not artifact.parent_model_name:
            artifact.parent_model_name = response.get("parent_model_name")
        if not artifact.parent_model_source:
            artifact.parent_model_source = response.get("parent_model_source")
        if not artifact.parent_model_relationship:
            artifact.parent_model_relationship = response.get("parent_model_relationship")
        logger.info(
            f"Extracted code_name='{artifact.code_name}', dataset_name='{artifact.dataset_name}', parent_model_name='{artifact.parent_model_name}' "
            f"for model artifact: {artifact.artifact_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to extract connected artifact names for {artifact.artifact_id}: {e}",
            exc_info=True,
        )

# ============================================================================
# Artifact Connectors
# ============================================================================

@overload
def artifact_connector(artifact: BaseArtifact) -> None:
    ...

@overload
def artifact_connector(artifact: ModelArtifact) -> None:
    ...

@overload
def artifact_connector(artifact: CodeArtifact) -> None:
    ...

@overload
def artifact_connector(artifact: DatasetArtifact) -> None:
    ...

@singledispatch
def artifact_connector(artifact: BaseArtifact) -> None:
    """
    Artifact dispatcher. Calls the appropriate connector function based on artifact type.
    """
    raise NotImplementedError(f"No connector logic for artifact type: {artifact.artifact_type}")

@artifact_connector.register
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
            child_model_artifact: BaseArtifact | None = load_artifact_metadata(model_artifact.artifact_id)
            if not isinstance(child_model_artifact, ModelArtifact):
                continue
            child_model_artifact.parent_model_id = artifact.artifact_id # link to this parent model
            child_model_artifact._compute_scores() # recompute scores (only affects treescore/net score)
            save_artifact_metadata(child_model_artifact) # save updated child model
            artifact.child_model_ids.append(child_model_artifact.artifact_id) # update this model for lineage
    logger.info(f"Connected artifact {artifact.artifact_id} ({artifact.artifact_type})")

@artifact_connector.register
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
        if not isinstance(model_artifact, ModelArtifact) or model_artifact.code_artifact_id:
            continue
        model_artifact.code_artifact_id = artifact.artifact_id
        model_artifact._compute_scores() # Recompute scores
        save_artifact_metadata(model_artifact)

@artifact_connector.register
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
        if not isinstance(model_artifact, ModelArtifact) or model_artifact.dataset_artifact_id:
            continue
        model_artifact.dataset_artifact_id = artifact.artifact_id
        model_artifact._compute_scores() # Recompute scores
        save_artifact_metadata(model_artifact)


# ============================================================================
# Artifact Uploader
# ============================================================================
def artifact_uploader(artifact: BaseArtifact):
    """
    Uploads the artifact to S3.
    """
    try:
        upload_artifact_to_s3(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            s3_key=artifact.s3_key,
            source_url=artifact.source_url,
        )
        logger.info(f"Uploaded artifact {artifact.artifact_id} to S3")
    except FileDownloadError:
        logger.error(f"S3 upload failed for {artifact.source_url}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during S3 upload for {artifact.source_url}: {e}", exc_info=True)
