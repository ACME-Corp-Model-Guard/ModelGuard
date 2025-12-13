"""
Smoke tests to ensure artifactory refactoring didn't break core flows.

These tests verify that the basic artifact creation, save, and load operations
still work after splitting artifactory.py into a multi-file module.
"""

import pytest
from unittest.mock import patch

from src.artifacts.artifactory import (
    create_artifact,
    save_artifact_metadata,
    load_artifact_metadata,
    load_all_artifacts,
    load_all_artifacts_by_fields,
)
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact


# =============================================================================
# Fixture: Mock DynamoDB Operations
# =============================================================================


@pytest.fixture
def mock_dynamo_save():
    """Mock DynamoDB save operation."""
    with patch("src.artifacts.artifactory.persistence.save_item_to_table") as mock:
        yield mock


@pytest.fixture
def mock_dynamo_load():
    """Mock DynamoDB load operation."""
    with patch("src.artifacts.artifactory.persistence.load_item_from_key") as mock:
        yield mock


@pytest.fixture
def mock_dynamo_scan():
    """Mock DynamoDB scan operation."""
    with patch("src.artifacts.artifactory.persistence.scan_table") as mock:
        yield mock


# =============================================================================
# Test: Artifact Creation (Factory Functions)
# =============================================================================


def test_create_model_artifact_with_metadata():
    """Test model creation with all metadata provided (no fetching)."""
    artifact = create_artifact(
        artifact_type="model",
        name="test-model",
        source_url="https://huggingface.co/test/model",
        size=1000,
        license="MIT",
        s3_key="models/test-123",  # Existing artifact (skips S3 upload)
    )

    assert isinstance(artifact, ModelArtifact)
    assert artifact.name == "test-model"
    assert artifact.size == 1000
    assert artifact.license == "MIT"
    assert artifact.s3_key == "models/test-123"


def test_create_dataset_artifact():
    """Test dataset creation."""
    artifact = create_artifact(
        artifact_type="dataset",
        name="test-dataset",
        source_url="https://huggingface.co/datasets/test",
        s3_key="datasets/test-456",
    )

    assert isinstance(artifact, DatasetArtifact)
    assert artifact.name == "test-dataset"
    assert artifact.artifact_type == "dataset"


def test_create_code_artifact():
    """Test code artifact creation."""
    artifact = create_artifact(
        artifact_type="code",
        name="test-code",
        source_url="https://github.com/test/repo",
        s3_key="code/test-789",
    )

    assert isinstance(artifact, CodeArtifact)
    assert artifact.name == "test-code"
    assert artifact.artifact_type == "code"


def test_create_artifact_invalid_type():
    """Test that invalid artifact type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid artifact_type"):
        create_artifact(
            artifact_type="invalid_type",  # type: ignore
            name="test",
            source_url="https://example.com",
        )


# =============================================================================
# Test: Persistence (Save/Load)
# =============================================================================


def test_save_artifact_metadata(mock_dynamo_save):
    """Test saving artifact to DynamoDB."""
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        size=1000,
        license="MIT",
    )

    save_artifact_metadata(artifact)

    # Verify DynamoDB save was called with artifact dict
    mock_dynamo_save.assert_called_once()
    call_args = mock_dynamo_save.call_args[0]
    saved_dict = call_args[1]
    assert saved_dict["name"] == "test-model"
    assert saved_dict["artifact_type"] == "model"


def test_load_artifact_metadata_success(mock_dynamo_load):
    """Test loading existing artifact from DynamoDB."""
    # Mock DynamoDB response
    mock_dynamo_load.return_value = {
        "artifact_id": "123-456-789",
        "artifact_type": "model",
        "name": "loaded-model",
        "source_url": "https://example.com",
        "s3_key": "models/123",
        "size": 5000,
        "license": "Apache-2.0",
    }

    artifact = load_artifact_metadata("123-456-789")

    assert artifact is not None
    assert isinstance(artifact, ModelArtifact)
    assert artifact.name == "loaded-model"
    assert artifact.size == 5000


def test_load_artifact_metadata_not_found(mock_dynamo_load):
    """Test loading non-existent artifact returns None."""
    mock_dynamo_load.return_value = None

    artifact = load_artifact_metadata("nonexistent-id")

    assert artifact is None


def test_load_all_artifacts(mock_dynamo_scan):
    """Test loading all artifacts from DynamoDB."""
    # Mock DynamoDB scan response
    mock_dynamo_scan.return_value = [
        {
            "artifact_id": "model-1",
            "artifact_type": "model",
            "name": "model-1",
            "source_url": "https://example.com/1",
            "s3_key": "models/1",
            "size": 1000,
            "license": "MIT",
        },
        {
            "artifact_id": "dataset-1",
            "artifact_type": "dataset",
            "name": "dataset-1",
            "source_url": "https://example.com/2",
            "s3_key": "datasets/1",
        },
    ]

    artifacts = load_all_artifacts()

    assert len(artifacts) == 2
    assert isinstance(artifacts[0], ModelArtifact)
    assert isinstance(artifacts[1], DatasetArtifact)


# =============================================================================
# Test: Filtering (load_all_artifacts_by_fields)
# =============================================================================


def test_load_all_artifacts_by_fields_with_list():
    """Test filtering artifacts from pre-loaded list."""
    # Create test artifacts
    model1 = ModelArtifact(name="bert-base", source_url="https://example.com/1")
    model2 = ModelArtifact(name="gpt-2", source_url="https://example.com/2")
    dataset1 = DatasetArtifact(name="wikitext", source_url="https://example.com/3")

    artifact_list = [model1, model2, dataset1]

    # Filter by name
    results = load_all_artifacts_by_fields(
        fields={"name": "bert-base"}, artifact_list=artifact_list
    )

    assert len(results) == 1
    assert results[0].name == "bert-base"


def test_load_all_artifacts_by_fields_case_insensitive():
    """Test case-insensitive name matching."""
    model1 = ModelArtifact(name="BERT-Base", source_url="https://example.com/1")
    artifact_list = [model1]

    # Search with lowercase
    results = load_all_artifacts_by_fields(
        fields={"name": "bert-base"},  # lowercase
        artifact_list=artifact_list,
    )

    assert len(results) == 1
    assert results[0].name == "BERT-Base"


def test_load_all_artifacts_by_fields_with_type_filter():
    """Test filtering by artifact type."""
    model1 = ModelArtifact(name="test", source_url="https://example.com/1")
    dataset1 = DatasetArtifact(name="test", source_url="https://example.com/2")
    artifact_list = [model1, dataset1]

    # Filter by type
    results = load_all_artifacts_by_fields(
        fields={"name": "test"},
        artifact_type="model",
        artifact_list=artifact_list,
    )

    assert len(results) == 1
    assert isinstance(results[0], ModelArtifact)


# =============================================================================
# Test: Integration - Full Create/Save/Load Cycle
# =============================================================================


@patch("src.artifacts.artifactory.connections.connect_artifact")
@patch("src.artifacts.artifactory.factory.upload_artifact_to_s3")
def test_create_new_artifact_triggers_upload_and_connect(mock_upload, mock_connect):
    """Test that creating NEW artifact (no s3_key) triggers S3 upload and connection."""
    create_artifact(
        artifact_type="model",
        name="new-model",
        size=1000,
        license="MIT",
        # No s3_key = new artifact
    )

    # Verify S3 upload was called
    mock_upload.assert_called_once()

    # Verify connection was called
    mock_connect.assert_called_once()


def test_create_existing_artifact_skips_upload():
    """Test that loading existing artifact (with s3_key) skips S3 upload and connection."""
    with patch("src.artifacts.artifactory.factory.upload_artifact_to_s3") as mock_upload:
        with patch("src.artifacts.artifactory.connections.connect_artifact") as mock_connect:
            create_artifact(
                artifact_type="model",
                name="existing-model",
                source_url="https://example.com",
                s3_key="models/existing-123",  # Existing artifact
                size=1000,
                license="MIT",
            )

            # Verify S3 upload was NOT called
            mock_upload.assert_not_called()

            # Verify connection was NOT called
            mock_connect.assert_not_called()
