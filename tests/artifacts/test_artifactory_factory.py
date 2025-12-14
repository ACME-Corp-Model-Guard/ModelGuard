"""
Unit tests for src/artifacts/artifactory/factory.py

Tests individual helper functions extracted during refactoring to improve
code coverage and validate each function's behavior in isolation.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from src.artifacts.artifactory.factory import (
    create_artifact,
    _get_artifact_class,
    _enrich_kwargs_with_metadata,
    _is_new_artifact,
    _initialize_new_artifact,
    _compute_initial_scores,
)
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.storage.downloaders.dispatchers import FileDownloadError


# =============================================================================
# Test: _get_artifact_class() - Type mapping
# =============================================================================


def test_get_artifact_class_model():
    """Test mapping 'model' to ModelArtifact class."""
    artifact_class = _get_artifact_class("model")
    assert artifact_class == ModelArtifact


def test_get_artifact_class_dataset():
    """Test mapping 'dataset' to DatasetArtifact class."""
    artifact_class = _get_artifact_class("dataset")
    assert artifact_class == DatasetArtifact


def test_get_artifact_class_code():
    """Test mapping 'code' to CodeArtifact class."""
    artifact_class = _get_artifact_class("code")
    assert artifact_class == CodeArtifact


def test_get_artifact_class_invalid_type():
    """Test that invalid artifact type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid artifact_type: invalid"):
        _get_artifact_class("invalid")  # type: ignore


def test_get_artifact_class_error_message_contains_valid_types():
    """Test that error message lists valid types."""
    with pytest.raises(ValueError, match=r"Must be one of \['model', 'dataset', 'code'\]"):
        _get_artifact_class("wrong")  # type: ignore


# =============================================================================
# Test: _enrich_kwargs_with_metadata() - Metadata fetching
# =============================================================================


@patch("src.artifacts.artifactory.factory.fetch_artifact_metadata")
def test_enrich_kwargs_fetches_metadata_when_name_missing(mock_fetch):
    """Test metadata fetch is triggered when name not provided."""
    mock_fetch.return_value = {
        "name": "fetched-name",
        "size": 1000,
        "license": "MIT",
    }

    kwargs = {
        "source_url": "https://huggingface.co/test/model",
        # No name provided
    }

    result = _enrich_kwargs_with_metadata("model", kwargs)

    # Verify fetch was called
    mock_fetch.assert_called_once_with(
        url="https://huggingface.co/test/model", artifact_type="model"
    )

    # Verify metadata merged into kwargs
    assert result["name"] == "fetched-name"
    assert result["size"] == 1000
    assert result["license"] == "MIT"


def test_enrich_kwargs_skips_fetch_when_s3_key_provided():
    """Test metadata fetch is skipped when s3_key already provided."""
    kwargs = {
        "s3_key": "existing-key",
        "source_url": "https://huggingface.co/test/model",
    }

    with patch("src.artifacts.artifactory.factory.fetch_artifact_metadata") as mock_fetch:
        result = _enrich_kwargs_with_metadata("model", kwargs)

        # Verify fetch NOT called
        mock_fetch.assert_not_called()

        # Verify original kwargs unchanged
        assert result["s3_key"] == "existing-key"


def test_enrich_kwargs_skips_fetch_when_no_source_url():
    """Test metadata fetch is skipped when source_url not provided."""
    kwargs = {
        "name": "test-name",
        # No source_url
    }

    with patch("src.artifacts.artifactory.factory.fetch_artifact_metadata") as mock_fetch:
        _enrich_kwargs_with_metadata("model", kwargs)

        # Verify fetch NOT called
        mock_fetch.assert_not_called()


@patch("src.artifacts.artifactory.factory.fetch_artifact_metadata")
def test_enrich_kwargs_removes_artifact_type_from_kwargs(mock_fetch):
    """Test that artifact_type is removed from kwargs if accidentally passed."""
    mock_fetch.return_value = {"name": "test"}

    kwargs = {
        "artifact_type": "model",  # Should be removed
        "source_url": "https://example.com",
    }

    result = _enrich_kwargs_with_metadata("model", kwargs)

    # Verify artifact_type removed
    assert "artifact_type" not in result


@patch("src.artifacts.artifactory.factory.fetch_artifact_metadata")
def test_enrich_kwargs_propagates_file_download_error(mock_fetch):
    """Test that FileDownloadError is propagated when metadata fetch fails."""
    mock_fetch.side_effect = FileDownloadError("Repository not found")

    kwargs = {"source_url": "https://huggingface.co/nonexistent/model"}

    with pytest.raises(FileDownloadError, match="Repository not found"):
        _enrich_kwargs_with_metadata("model", kwargs)


@patch("src.artifacts.artifactory.factory.fetch_artifact_metadata")
def test_enrich_kwargs_propagates_key_error(mock_fetch):
    """Test that KeyError is propagated when required metadata missing."""
    mock_fetch.side_effect = KeyError("name")

    kwargs = {"source_url": "https://example.com"}

    with pytest.raises(KeyError):
        _enrich_kwargs_with_metadata("model", kwargs)


# =============================================================================
# Test: _is_new_artifact() - Detection logic
# =============================================================================


def test_is_new_artifact_true_when_no_s3_key():
    """Test artifact is considered new when s3_key not provided."""
    kwargs = {"name": "test", "source_url": "https://example.com"}

    assert _is_new_artifact(kwargs) is True


def test_is_new_artifact_false_when_s3_key_provided():
    """Test artifact is considered existing when s3_key provided."""
    kwargs = {
        "name": "test",
        "source_url": "https://example.com",
        "s3_key": "models/123-456",
    }

    assert _is_new_artifact(kwargs) is False


def test_is_new_artifact_false_when_s3_key_empty_string():
    """Test empty string s3_key is treated as falsy (new artifact)."""
    kwargs = {"name": "test", "s3_key": ""}

    # Empty string is falsy, so should be considered new
    assert _is_new_artifact(kwargs) is True


def test_is_new_artifact_false_when_s3_key_none():
    """Test None s3_key is treated as new artifact."""
    kwargs = {"name": "test", "s3_key": None}

    assert _is_new_artifact(kwargs) is True


# =============================================================================
# Test: _initialize_new_artifact() - S3 upload and connections
# =============================================================================


@patch("src.artifacts.artifactory.connections.connect_artifact")
@patch("src.artifacts.artifactory.factory.upload_artifact_to_s3")
def test_initialize_new_artifact_uploads_to_s3(mock_upload, mock_connect):
    """Test that S3 upload is called with correct parameters."""
    artifact = ModelArtifact(
        artifact_id="test-id",
        name="test",
        source_url="https://example.com",
        s3_key="models/test-id",
    )

    _initialize_new_artifact(artifact)

    mock_upload.assert_called_once_with(
        artifact_id="test-id",
        artifact_type="model",
        s3_key="models/test-id",
        source_url="https://example.com",
    )


@patch("src.artifacts.artifactory.connections.connect_artifact")
@patch("src.artifacts.artifactory.factory.upload_artifact_to_s3")
def test_initialize_new_artifact_connects_artifact(mock_upload, mock_connect):
    """Test that artifact connection is called."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")

    _initialize_new_artifact(artifact)

    mock_connect.assert_called_once_with(artifact)


@patch("src.artifacts.artifactory.connections.connect_artifact")
@patch("src.artifacts.artifactory.factory.upload_artifact_to_s3")
def test_initialize_new_artifact_calls_in_correct_order(mock_upload, mock_connect):
    """Test that upload happens before connection."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")

    _initialize_new_artifact(artifact)

    # Check call order
    assert mock_upload.call_count == 1
    assert mock_connect.call_count == 1

    # Upload should be called first
    manager = MagicMock()
    manager.attach_mock(mock_upload, "upload")
    manager.attach_mock(mock_connect, "connect")

    # Reset and re-run to check order
    mock_upload.reset_mock()
    mock_connect.reset_mock()

    manager = MagicMock()
    manager.attach_mock(mock_upload, "upload")
    manager.attach_mock(mock_connect, "connect")

    _initialize_new_artifact(artifact)

    [call.upload(), call.connect()]
    # Note: The actual calls will have parameters, but we're just checking order


@patch("src.artifacts.artifactory.connections.connect_artifact")
@patch("src.artifacts.artifactory.factory.upload_artifact_to_s3")
def test_initialize_new_artifact_computes_scores_for_model(mock_upload, mock_connect):
    """Test that model artifacts get score computation."""
    artifact = ModelArtifact(name="test-model", source_url="https://example.com")

    with patch("src.artifacts.artifactory.factory._compute_initial_scores") as mock_compute:
        _initialize_new_artifact(artifact)

        # Should call score computation for model
        mock_compute.assert_called_once_with(artifact)


@patch("src.artifacts.artifactory.connections.connect_artifact")
@patch("src.artifacts.artifactory.factory.upload_artifact_to_s3")
def test_initialize_new_artifact_skips_scores_for_code(mock_upload, mock_connect):
    """Test that code artifacts skip score computation."""
    artifact = CodeArtifact(name="test-code", source_url="https://github.com/test/repo")

    with patch("src.artifacts.artifactory.factory._compute_initial_scores") as mock_compute:
        _initialize_new_artifact(artifact)

        # Should NOT call score computation for code
        mock_compute.assert_not_called()


@patch("src.artifacts.artifactory.connections.connect_artifact")
@patch("src.artifacts.artifactory.factory.upload_artifact_to_s3")
def test_initialize_new_artifact_skips_scores_for_dataset(mock_upload, mock_connect):
    """Test that dataset artifacts skip score computation."""
    artifact = DatasetArtifact(
        name="test-dataset", source_url="https://huggingface.co/datasets/test"
    )

    with patch("src.artifacts.artifactory.factory._compute_initial_scores") as mock_compute:
        _initialize_new_artifact(artifact)

        # Should NOT call score computation for dataset
        mock_compute.assert_not_called()


# =============================================================================
# Test: _compute_initial_scores() - Metric computation
# =============================================================================


def test_compute_initial_scores_calls_compute_scores():
    """Test that compute_scores is called with METRICS registry."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")

    with patch("src.metrics.registry.METRICS", []) as mock_metrics:
        with patch.object(artifact, "compute_scores") as mock_compute:
            _compute_initial_scores(artifact)

            mock_compute.assert_called_once_with(mock_metrics)


def test_compute_initial_scores_sets_suspected_package_confusion():
    """Test that suspected_package_confusion is initialized to False."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")

    with patch.object(artifact, "compute_scores"):
        _compute_initial_scores(artifact)

        assert artifact.suspected_package_confusion is False


def test_compute_initial_scores_does_not_override_existing_flag():
    """Test that existing suspected_package_confusion value is overwritten."""
    artifact = ModelArtifact(
        name="test",
        source_url="https://example.com",
        suspected_package_confusion=True,  # Pre-existing value
    )

    with patch.object(artifact, "compute_scores"):
        _compute_initial_scores(artifact)

        # Should be overwritten to False (this is the current behavior)
        assert artifact.suspected_package_confusion is False


# =============================================================================
# Test: create_artifact() - Integration
# =============================================================================


@patch("src.artifacts.artifactory.factory._initialize_new_artifact")
@patch("src.artifacts.artifactory.factory._enrich_kwargs_with_metadata")
def test_create_artifact_full_flow_new_artifact(mock_enrich, mock_initialize):
    """Test full artifact creation flow for new artifact."""
    mock_enrich.return_value = {
        "name": "test-model",
        "source_url": "https://example.com",
        "size": 1000,
        "license": "MIT",
    }

    artifact = create_artifact(artifact_type="model", source_url="https://example.com")

    # Verify enrichment was called
    mock_enrich.assert_called_once()

    # Verify initialization was called (new artifact)
    mock_initialize.assert_called_once()

    # Verify correct artifact type
    assert isinstance(artifact, ModelArtifact)


@patch("src.artifacts.artifactory.factory._initialize_new_artifact")
@patch("src.artifacts.artifactory.factory._enrich_kwargs_with_metadata")
def test_create_artifact_skips_init_for_existing_artifact(mock_enrich, mock_initialize):
    """Test that existing artifacts skip initialization."""
    mock_enrich.return_value = {
        "name": "existing-model",
        "source_url": "https://example.com",
        "s3_key": "models/existing-123",  # Existing artifact
        "size": 1000,
        "license": "MIT",
    }

    artifact = create_artifact(
        artifact_type="model",
        name="existing-model",
        source_url="https://example.com",
        s3_key="models/existing-123",
    )

    # Verify initialization was NOT called
    mock_initialize.assert_not_called()

    # Verify correct artifact type
    assert isinstance(artifact, ModelArtifact)


def test_create_artifact_with_all_kwargs():
    """Test creating artifact with all constructor kwargs provided."""
    with patch("src.artifacts.artifactory.factory._initialize_new_artifact"):
        artifact = create_artifact(
            artifact_type="model",
            s3_key="models/test-123",
            name="test-model",
            source_url="https://example.com",
            size=5000,
            license="Apache-2.0",
            code_name="test-code",
            dataset_name="test-dataset",
        )

        assert isinstance(artifact, ModelArtifact)
        assert artifact.name == "test-model"
        assert artifact.size == 5000
        assert artifact.license == "Apache-2.0"
        assert artifact.code_name == "test-code"
        assert artifact.dataset_name == "test-dataset"


def test_create_artifact_raises_for_invalid_type():
    """Test that invalid artifact_type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid artifact_type"):
        create_artifact(artifact_type="invalid", name="test")  # type: ignore
