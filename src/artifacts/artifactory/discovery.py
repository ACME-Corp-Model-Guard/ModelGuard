"""
Artifact discovery using LLM-based analysis.

This module contains functions for extracting connected artifact names from
model files using LLM (Large Language Model) analysis. The LLM reads README files,
configuration files, and other metadata to discover relationships like:
- Code repositories used to train the model
- Datasets used for training
- Parent models (if this is a fine-tuned model)

NOTE: This module will be refactored on Day 2 to reduce complexity from 15 → ~5 per function.
For Day 1, moved as-is to complete module split quickly.
"""

from typing import Any, Dict, Optional, Union

from src.artifacts.model_artifact import ModelArtifact
from src.logger import logger
from src.storage.s3_utils import download_artifact_from_s3
from src.storage.file_extraction import extract_relevant_files
from src.utils.llm_analysis import (
    build_extract_fields_from_files_prompt,
    ask_llm,
)


# =============================================================================
# Internal Functions (used by connections.py)
# =============================================================================


def _find_connected_artifact_names(artifact: ModelArtifact) -> None:
    """
    Use LLM to extract connected artifact names from model files.

    This function:
    1. Downloads the model artifact from S3
    2. Extracts relevant files (README, config.json, etc.)
    3. Uses LLM to analyze the files and extract connection information
    4. Populates the artifact's connection fields if not already set

    Side Effects:
        Modifies the artifact instance to populate:
        - code_name: Name of code repository
        - dataset_name: Name of training dataset
        - parent_model_name: Name of parent model (if fine-tuned)
        - parent_model_source: Where parent model was found
        - parent_model_relationship: Relationship type (fine-tuned, distilled, etc.)

    Args:
        artifact: The model artifact to analyze

    TODO (Day 2 refactoring):
        Extract into helper functions:
        - _download_and_extract_files()
        - _llm_extract_fields()
        - _update_connection_fields()
    """
    try:
        # Step 1: Download artifact from S3 to temp location
        download_artifact_from_s3(
            artifact_id=artifact.artifact_id,
            s3_key=artifact.s3_key,
            local_path="/tmp/model_artifact_files",
        )

        # Step 2: Extract relevant files for analysis
        files: Dict[str, str] = extract_relevant_files(
            tar_path="/tmp/model_artifact_files",
            include_ext={".json", ".md", ".txt"},
            max_files=10,
            prioritize_readme=True,
        )

        # Step 3: Build LLM prompt to extract connection fields
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

        # Step 4: Call LLM to analyze files
        response: Optional[Union[str, Dict[str, Any]]] = ask_llm(
            prompt, return_json=True
        )
        if not response or not isinstance(response, dict):
            logger.warning(
                f"LLM failed to extract connected artifact names for {artifact.artifact_id}"
            )
            return

        # Step 5: Update artifact fields only if not already set
        # (respects user-provided values)
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
            f"Extracted code_name='{artifact.code_name}', dataset_name='{artifact.dataset_name}', "
            f"parent_model_name='{artifact.parent_model_name}' "
            f"for model artifact: {artifact.artifact_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to extract connected artifact names for {artifact.artifact_id}: {e}"
        )
