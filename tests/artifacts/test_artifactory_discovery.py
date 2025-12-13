"""
Unit tests for src/artifacts/artifactory/discovery.py

Tests helper functions extracted during refactoring to reduce complexity
from 15 to ~3-5 per function and improve testability.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.artifacts.artifactory.discovery import (
    _find_connected_artifact_names,
    _download_and_extract_files,
    _llm_extract_fields,
    _update_connection_fields,
)
from src.artifacts.model_artifact import ModelArtifact


# =============================================================================
# Test: _download_and_extract_files() - S3 download and file extraction
# =============================================================================


@patch("src.artifacts.artifactory.discovery.extract_relevant_files")
@patch("src.artifacts.artifactory.discovery.download_artifact_from_s3")
def test_download_and_extract_files_calls_download(mock_download, mock_extract):
    """Test that S3 download is called with correct parameters."""
    artifact = ModelArtifact(
        artifact_id="test-id",
        name="test-model",
        source_url="https://example.com",
        s3_key="models/test-id",
    )

    mock_extract.return_value = {"README.md": "content"}

    _download_and_extract_files(artifact)

    # Verify download was called with correct artifact_id and s3_key
    # The local_path is now a dynamically generated temp file
    mock_download.assert_called_once()
    call_kwargs = mock_download.call_args.kwargs
    assert call_kwargs["artifact_id"] == "test-id"
    assert call_kwargs["s3_key"] == "models/test-id"
    assert call_kwargs["local_path"].startswith("/tmp/discovery_test-id_")
    assert call_kwargs["local_path"].endswith(".tar.gz")


@patch("src.artifacts.artifactory.discovery.extract_relevant_files")
@patch("src.artifacts.artifactory.discovery.download_artifact_from_s3")
def test_download_and_extract_files_calls_extract(mock_download, mock_extract):
    """Test that file extraction is called with correct parameters."""
    artifact = ModelArtifact(
        artifact_id="test-id",
        name="test-model",
        source_url="https://example.com",
        s3_key="models/test-id",
    )

    mock_extract.return_value = {"README.md": "content"}

    _download_and_extract_files(artifact)

    # Verify extract was called with correct params (tar_path is dynamic)
    mock_extract.assert_called_once()
    call_kwargs = mock_extract.call_args.kwargs
    assert call_kwargs["tar_path"].startswith("/tmp/discovery_test-id_")
    assert call_kwargs["tar_path"].endswith(".tar.gz")
    assert call_kwargs["include_ext"] == {".json", ".md", ".txt"}
    assert call_kwargs["max_files"] == 10
    assert call_kwargs["prioritize_readme"] is True


@patch("src.artifacts.artifactory.discovery.extract_relevant_files")
@patch("src.artifacts.artifactory.discovery.download_artifact_from_s3")
def test_download_and_extract_files_returns_files_dict(mock_download, mock_extract):
    """Test that extracted files dictionary is returned along with temp path."""
    artifact = ModelArtifact(
        artifact_id="test-id",
        name="test-model",
        source_url="https://example.com",
        s3_key="models/test-id",
    )

    expected_files = {
        "README.md": "Model documentation",
        "config.json": '{"model_type": "bert"}',
    }
    mock_extract.return_value = expected_files

    tmp_path, result = _download_and_extract_files(artifact)

    # Function now returns tuple of (tmp_path, files_dict)
    assert tmp_path.startswith("/tmp/discovery_test-id_")
    assert tmp_path.endswith(".tar.gz")
    assert result == expected_files


@patch("src.artifacts.artifactory.discovery.extract_relevant_files")
@patch("src.artifacts.artifactory.discovery.download_artifact_from_s3")
def test_download_and_extract_files_download_before_extract(mock_download, mock_extract):
    """Test that download happens before extraction."""
    artifact = ModelArtifact(
        artifact_id="test-id",
        name="test",
        source_url="https://example.com",
        s3_key="models/test-id",
    )

    mock_extract.return_value = {}

    _download_and_extract_files(artifact)

    # Verify both were called
    assert mock_download.call_count == 1
    assert mock_extract.call_count == 1

    # Download should be called first
    manager = MagicMock()
    manager.attach_mock(mock_download, "download")
    manager.attach_mock(mock_extract, "extract")


@patch("src.artifacts.artifactory.discovery.extract_relevant_files")
@patch("src.artifacts.artifactory.discovery.download_artifact_from_s3")
def test_download_and_extract_files_propagates_download_error(mock_download, mock_extract):
    """Test that download errors are propagated."""
    artifact = ModelArtifact(
        artifact_id="test-id",
        name="test",
        source_url="https://example.com",
        s3_key="models/test-id",
    )

    mock_download.side_effect = Exception("S3 download failed")

    with pytest.raises(Exception, match="S3 download failed"):
        _download_and_extract_files(artifact)


@patch("src.artifacts.artifactory.discovery.extract_relevant_files")
@patch("src.artifacts.artifactory.discovery.download_artifact_from_s3")
def test_download_and_extract_files_propagates_extract_error(mock_download, mock_extract):
    """Test that extraction errors are propagated."""
    artifact = ModelArtifact(
        artifact_id="test-id",
        name="test",
        source_url="https://example.com",
        s3_key="models/test-id",
    )

    mock_extract.side_effect = Exception("Extraction failed")

    with pytest.raises(Exception, match="Extraction failed"):
        _download_and_extract_files(artifact)


# =============================================================================
# Test: _llm_extract_fields() - LLM-based field extraction
# =============================================================================


@patch("src.artifacts.artifactory.discovery.ask_llm")
@patch("src.artifacts.artifactory.discovery.build_extract_fields_from_files_prompt")
def test_llm_extract_fields_builds_prompt(mock_build_prompt, mock_ask_llm):
    """Test that LLM prompt is built with correct parameters."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    files = {"README.md": "content"}
    mock_build_prompt.return_value = "test prompt"
    mock_ask_llm.return_value = {"code_name": "test-code"}

    _llm_extract_fields(artifact, files)

    # Verify prompt builder was called with correct fields and files
    mock_build_prompt.assert_called_once_with(
        fields={
            "code_name": "Name of the code artifact",
            "dataset_name": "Name of the dataset artifact",
            "parent_model_name": "Name of the parent model",
            "parent_model_source": "File name where parent model was found (if any)",
            "parent_model_relationship": "Relationship to the parent model (if any)",
        },
        files=files,
    )


@patch("src.artifacts.artifactory.discovery.ask_llm")
@patch("src.artifacts.artifactory.discovery.build_extract_fields_from_files_prompt")
def test_llm_extract_fields_calls_llm(mock_build_prompt, mock_ask_llm):
    """Test that LLM is called with built prompt."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    files = {"README.md": "content"}
    mock_build_prompt.return_value = "test prompt"
    mock_ask_llm.return_value = {"code_name": "test-code"}

    _llm_extract_fields(artifact, files)

    # Verify LLM was called with prompt and return_json=True
    mock_ask_llm.assert_called_once_with("test prompt", return_json=True)


@patch("src.artifacts.artifactory.discovery.ask_llm")
@patch("src.artifacts.artifactory.discovery.build_extract_fields_from_files_prompt")
def test_llm_extract_fields_returns_extracted_data(mock_build_prompt, mock_ask_llm):
    """Test that extracted data dictionary is returned."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    files = {"README.md": "content"}
    mock_build_prompt.return_value = "test prompt"

    expected_data = {
        "code_name": "test-code",
        "dataset_name": "test-dataset",
        "parent_model_name": "bert-base",
    }
    mock_ask_llm.return_value = expected_data

    result = _llm_extract_fields(artifact, files)

    assert result == expected_data


@patch("src.artifacts.artifactory.discovery.ask_llm")
@patch("src.artifacts.artifactory.discovery.build_extract_fields_from_files_prompt")
def test_llm_extract_fields_returns_none_when_llm_returns_none(mock_build_prompt, mock_ask_llm):
    """Test that None is returned when LLM returns None."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    files = {"README.md": "content"}
    mock_build_prompt.return_value = "test prompt"
    mock_ask_llm.return_value = None

    result = _llm_extract_fields(artifact, files)

    assert result is None


@patch("src.artifacts.artifactory.discovery.ask_llm")
@patch("src.artifacts.artifactory.discovery.build_extract_fields_from_files_prompt")
def test_llm_extract_fields_returns_none_when_llm_returns_string(mock_build_prompt, mock_ask_llm):
    """Test that None is returned when LLM returns string instead of dict."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    files = {"README.md": "content"}
    mock_build_prompt.return_value = "test prompt"
    mock_ask_llm.return_value = "not a dict"  # Invalid response type

    result = _llm_extract_fields(artifact, files)

    assert result is None


@patch("src.artifacts.artifactory.discovery.ask_llm")
@patch("src.artifacts.artifactory.discovery.build_extract_fields_from_files_prompt")
def test_llm_extract_fields_returns_none_when_llm_returns_empty_dict(
    mock_build_prompt, mock_ask_llm
):
    """Test that None is returned when LLM returns empty dict (falsy value)."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    files = {"README.md": "content"}
    mock_build_prompt.return_value = "test prompt"
    mock_ask_llm.return_value = {}  # Empty dict is falsy

    result = _llm_extract_fields(artifact, files)

    # Empty dict is treated as falsy, so returns None
    assert result is None


# =============================================================================
# Test: _update_connection_fields() - Artifact field updates
# =============================================================================


def test_update_connection_fields_updates_code_name():
    """Test that code_name is updated from extracted data."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {"code_name": "my-training-code"}

    _update_connection_fields(artifact, extracted_data)

    assert artifact.code_name == "my-training-code"


def test_update_connection_fields_updates_dataset_name():
    """Test that dataset_name is updated from extracted data."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {"dataset_name": "wikitext-103"}

    _update_connection_fields(artifact, extracted_data)

    assert artifact.dataset_name == "wikitext-103"


def test_update_connection_fields_updates_parent_model_name():
    """Test that parent_model_name is updated from extracted data."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {"parent_model_name": "bert-base-uncased"}

    _update_connection_fields(artifact, extracted_data)

    assert artifact.parent_model_name == "bert-base-uncased"


def test_update_connection_fields_updates_parent_model_source():
    """Test that parent_model_source is updated from extracted data."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {"parent_model_source": "config.json"}

    _update_connection_fields(artifact, extracted_data)

    assert artifact.parent_model_source == "config.json"


def test_update_connection_fields_updates_parent_model_relationship():
    """Test that parent_model_relationship is updated from extracted data."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {"parent_model_relationship": "fine-tuned"}

    _update_connection_fields(artifact, extracted_data)

    assert artifact.parent_model_relationship == "fine-tuned"


def test_update_connection_fields_updates_multiple_fields():
    """Test that multiple fields are updated simultaneously."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {
        "code_name": "training-code",
        "dataset_name": "my-dataset",
        "parent_model_name": "base-model",
        "parent_model_source": "README.md",
        "parent_model_relationship": "distilled",
    }

    _update_connection_fields(artifact, extracted_data)

    assert artifact.code_name == "training-code"
    assert artifact.dataset_name == "my-dataset"
    assert artifact.parent_model_name == "base-model"
    assert artifact.parent_model_source == "README.md"
    assert artifact.parent_model_relationship == "distilled"


def test_update_connection_fields_skips_already_set_code_name():
    """Test that existing code_name is not overwritten."""
    artifact = ModelArtifact(
        name="test",
        source_url="https://example.com",
        code_name="user-provided-code",  # Pre-existing value
    )
    extracted_data = {"code_name": "llm-extracted-code"}

    _update_connection_fields(artifact, extracted_data)

    # Should keep user-provided value
    assert artifact.code_name == "user-provided-code"


def test_update_connection_fields_skips_already_set_dataset_name():
    """Test that existing dataset_name is not overwritten."""
    artifact = ModelArtifact(
        name="test",
        source_url="https://example.com",
        dataset_name="user-dataset",  # Pre-existing value
    )
    extracted_data = {"dataset_name": "llm-dataset"}

    _update_connection_fields(artifact, extracted_data)

    # Should keep user-provided value
    assert artifact.dataset_name == "user-dataset"


def test_update_connection_fields_handles_missing_fields():
    """Test that missing fields in extracted_data don't cause errors."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {}  # No fields provided

    _update_connection_fields(artifact, extracted_data)

    # All fields should remain None
    assert artifact.code_name is None
    assert artifact.dataset_name is None
    assert artifact.parent_model_name is None


def test_update_connection_fields_handles_none_values():
    """Test that None values in extracted_data are handled correctly."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    extracted_data = {
        "code_name": None,
        "dataset_name": None,
        "parent_model_name": None,
    }

    _update_connection_fields(artifact, extracted_data)

    # Should set to None (which is what get() returns)
    assert artifact.code_name is None
    assert artifact.dataset_name is None
    assert artifact.parent_model_name is None


# =============================================================================
# Test: _find_connected_artifact_names() - Integration
# =============================================================================


@patch("src.artifacts.artifactory.discovery._update_connection_fields")
@patch("src.artifacts.artifactory.discovery._llm_extract_fields")
@patch("src.artifacts.artifactory.discovery._download_and_extract_files")
def test_find_connected_artifact_names_full_flow(mock_download, mock_llm, mock_update):
    """Test full discovery flow with successful extraction."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    # Mock successful flow - now returns tuple of (tmp_path, files)
    mock_download.return_value = ("/tmp/test.tar.gz", {"README.md": "content"})
    mock_llm.return_value = {"code_name": "test-code"}

    _find_connected_artifact_names(artifact)

    # Verify all steps were called
    mock_download.assert_called_once_with(artifact)
    mock_llm.assert_called_once_with(artifact, {"README.md": "content"})
    mock_update.assert_called_once_with(artifact, {"code_name": "test-code"})


@patch("src.artifacts.artifactory.discovery._update_connection_fields")
@patch("src.artifacts.artifactory.discovery._llm_extract_fields")
@patch("src.artifacts.artifactory.discovery._download_and_extract_files")
def test_find_connected_artifact_names_skips_update_when_llm_fails(
    mock_download, mock_llm, mock_update
):
    """Test that field update is skipped when LLM extraction fails."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    # Now returns tuple of (tmp_path, files)
    mock_download.return_value = ("/tmp/test.tar.gz", {"README.md": "content"})
    mock_llm.return_value = None  # LLM failed

    _find_connected_artifact_names(artifact)

    # Verify download and LLM were called, but not update
    mock_download.assert_called_once()
    mock_llm.assert_called_once()
    mock_update.assert_not_called()


@patch("src.artifacts.artifactory.discovery._update_connection_fields")
@patch("src.artifacts.artifactory.discovery._llm_extract_fields")
@patch("src.artifacts.artifactory.discovery._download_and_extract_files")
def test_find_connected_artifact_names_handles_download_error(mock_download, mock_llm, mock_update):
    """Test that download errors are caught and logged."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    mock_download.side_effect = Exception("S3 error")

    # Should not raise, but log error
    _find_connected_artifact_names(artifact)

    # Verify download was attempted, but LLM and update were not called
    mock_download.assert_called_once()
    mock_llm.assert_not_called()
    mock_update.assert_not_called()


@patch("src.artifacts.artifactory.discovery._update_connection_fields")
@patch("src.artifacts.artifactory.discovery._llm_extract_fields")
@patch("src.artifacts.artifactory.discovery._download_and_extract_files")
def test_find_connected_artifact_names_handles_llm_error(mock_download, mock_llm, mock_update):
    """Test that LLM errors are caught and logged."""
    artifact = ModelArtifact(artifact_id="test-id", name="test", source_url="https://example.com")

    # Now returns tuple of (tmp_path, files)
    mock_download.return_value = ("/tmp/test.tar.gz", {"README.md": "content"})
    mock_llm.side_effect = Exception("LLM error")

    # Should not raise, but log error
    _find_connected_artifact_names(artifact)

    # Verify download and LLM were attempted, but not update
    mock_download.assert_called_once()
    mock_llm.assert_called_once()
    mock_update.assert_not_called()
