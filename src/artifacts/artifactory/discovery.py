"""
Artifact discovery using LLM-based analysis.

This module contains functions for extracting connected artifact names from
model files using LLM (Large Language Model) analysis. The LLM reads README files,
configuration files, and other metadata to discover relationships like:
- Code repositories used to train the model
- Datasets used for training
- Parent models (if this is a fine-tuned model)
"""

import os
import tempfile
from typing import Any, Dict, Optional, Union

from src.artifacts.model_artifact import ModelArtifact
from src.logutil import clogger
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

    This function orchestrates the discovery process by:
    1. Downloading and extracting files from S3
    2. Using LLM to analyze files and extract connection information
    3. Updating the artifact's connection fields

    Side Effects:
        Modifies the artifact instance to populate:
        - code_name: Name of code repository
        - dataset_name: Name of training dataset
        - parent_model_name: Name of parent model (if fine-tuned)
        - parent_model_source: Where parent model was found
        - parent_model_relationship: Relationship type (fine-tuned, distilled, etc.)

    Args:
        artifact: The model artifact to analyze
    """
    tmp_path: Optional[str] = None

    try:
        # Step 1: Download artifact and extract relevant files
        tmp_path, files = _download_and_extract_files(artifact)

        # Step 2: Use LLM to extract connection fields from files
        extracted_data = _llm_extract_fields(artifact, files)
        if not extracted_data:
            return  # LLM extraction failed, already logged

        # Step 3: Update artifact fields with extracted data
        _update_connection_fields(artifact, extracted_data)

        clogger.info(
            f"Extracted code_name='{artifact.code_name}', dataset_name='{artifact.dataset_name}', "
            f"parent_model_name='{artifact.parent_model_name}' "
            f"for model artifact: {artifact.artifact_id}"
        )
    except Exception as e:
        clogger.error(f"Failed to extract connected artifact names for {artifact.artifact_id}: {e}")
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
                clogger.debug(f"[discovery] Cleaned up temp file: {tmp_path}")
            except Exception as cleanup_err:
                clogger.warning(
                    f"[discovery] Failed to clean up temp file {tmp_path}: {cleanup_err}"
                )


# =============================================================================
# Helper Functions (Internal)
# =============================================================================


def _download_and_extract_files(
    artifact: ModelArtifact,
) -> tuple[str, Dict[str, str]]:
    """
    Download artifact from S3 and extract relevant files for analysis.

    Downloads the artifact tar file from S3 to a temporary location and
    extracts relevant files (README, JSON configs, etc.) for LLM analysis.

    Args:
        artifact: The model artifact to download

    Returns:
        Tuple of (temp_file_path, files_dict) where:
        - temp_file_path: Path to the downloaded temp file (caller must clean up)
        - files_dict: Dictionary mapping filenames to their contents (limited to 10 files)

    Raises:
        Exception: If download or extraction fails
    """
    # Create a unique temp file for this artifact
    tmp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".tar.gz",
        prefix=f"discovery_{artifact.artifact_id}_",
        dir="/tmp",
    )
    tmp_path = tmp_file.name
    tmp_file.close()  # Close so download_artifact_from_s3 can write to it

    # Download artifact from S3 to temp location
    download_artifact_from_s3(
        artifact_id=artifact.artifact_id,
        s3_key=artifact.s3_key,
        local_path=tmp_path,
    )

    # Extract relevant files for analysis
    files: Dict[str, str] = extract_relevant_files(
        tar_path=tmp_path,
        include_ext={".json", ".md", ".txt"},
        max_files=10,
        prioritize_readme=True,
    )

    return tmp_path, files


def _llm_extract_fields(artifact: ModelArtifact, files: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Use LLM to analyze files and extract connection field values.

    Builds a prompt asking the LLM to extract artifact connection information
    from the provided files, then calls the LLM and validates the response.

    Args:
        artifact: The model artifact being analyzed (for logging)
        files: Dictionary of filename -> content to analyze

    Returns:
        Dictionary with extracted field values, or None if extraction failed
    """
    # Build LLM prompt to extract connection fields
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

    # Call LLM to analyze files
    response: Optional[Union[str, Dict[str, Any]]] = ask_llm(prompt, return_json=True)

    # Validate response
    if not response or not isinstance(response, dict):
        clogger.warning(
            f"LLM failed to extract connected artifact names for {artifact.artifact_id}"
        )
        return None

    return response


def _update_connection_fields(artifact: ModelArtifact, extracted_data: Dict[str, Any]) -> None:
    """
    Update artifact connection fields with extracted data.

    Only updates fields that are not already set, respecting user-provided values.
    This ensures manual overrides are not overwritten by LLM extraction.

    Args:
        artifact: The model artifact to update (modified in-place)
        extracted_data: Dictionary of field values extracted by LLM

    Side Effects:
        Modifies artifact instance fields: code_name, dataset_name,
        parent_model_name, parent_model_source, parent_model_relationship
    """
    # Update fields only if not already set (respects user-provided values)
    if not artifact.code_name:
        artifact.code_name = extracted_data.get("code_name")

    if not artifact.dataset_name:
        artifact.dataset_name = extracted_data.get("dataset_name")

    if not artifact.parent_model_name:
        artifact.parent_model_name = extracted_data.get("parent_model_name")

    if not artifact.parent_model_source:
        artifact.parent_model_source = extracted_data.get("parent_model_source")

    if not artifact.parent_model_relationship:
        artifact.parent_model_relationship = extracted_data.get("parent_model_relationship")
