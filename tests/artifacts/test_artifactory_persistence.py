"""
Unit tests for src/artifacts/artifactory/persistence.py

Tests helper functions for filtering and case-insensitive matching that were
extracted during refactoring to reduce complexity.
"""

import pytest
from unittest.mock import patch
from typing import List

from src.artifacts.artifactory.persistence import (
    save_artifact_metadata,
    load_artifact_metadata,
    load_all_artifacts,
    load_all_artifacts_by_fields,
    _filter_by_type,
    _filter_by_fields,
    _matches_all_fields,
    _values_equal_ignoring_case,
)
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.artifacts.base_artifact import BaseArtifact


# =============================================================================
# Test: _values_equal_ignoring_case() - Case-insensitive comparison
# =============================================================================


def test_values_equal_ignoring_case_strings_match():
    """Test case-insensitive string matching."""
    assert _values_equal_ignoring_case("MIT", "mit") is True
    assert _values_equal_ignoring_case("Apache-2.0", "apache-2.0") is True
    assert _values_equal_ignoring_case("TEST", "test") is True


def test_values_equal_ignoring_case_strings_dont_match():
    """Test case-insensitive string non-matching."""
    assert _values_equal_ignoring_case("MIT", "apache") is False
    assert _values_equal_ignoring_case("hello", "world") is False


def test_values_equal_ignoring_case_exact_match():
    """Test exact string matches."""
    assert _values_equal_ignoring_case("MIT", "MIT") is True
    assert _values_equal_ignoring_case("test", "test") is True


def test_values_equal_ignoring_case_numbers():
    """Test numeric comparison."""
    assert _values_equal_ignoring_case(123, 123) is True
    assert _values_equal_ignoring_case(123, 456) is False
    assert _values_equal_ignoring_case(0, 0) is True


def test_values_equal_ignoring_case_mixed_types():
    """Test comparison between different types."""
    assert _values_equal_ignoring_case("123", 123) is False
    assert _values_equal_ignoring_case(True, "true") is False


def test_values_equal_ignoring_case_none_values():
    """Test None handling."""
    assert _values_equal_ignoring_case(None, None) is True
    assert _values_equal_ignoring_case(None, "test") is False
    assert _values_equal_ignoring_case("test", None) is False


def test_values_equal_ignoring_case_empty_strings():
    """Test empty string handling."""
    assert _values_equal_ignoring_case("", "") is True
    assert _values_equal_ignoring_case("", "test") is False


def test_values_equal_ignoring_case_boolean():
    """Test boolean comparison."""
    assert _values_equal_ignoring_case(True, True) is True
    assert _values_equal_ignoring_case(False, False) is True
    assert _values_equal_ignoring_case(True, False) is False


def test_values_equal_ignoring_case_list():
    """Test list comparison (uses standard equality)."""
    assert _values_equal_ignoring_case([1, 2, 3], [1, 2, 3]) is True
    assert _values_equal_ignoring_case([1, 2], [1, 2, 3]) is False


# =============================================================================
# Test: _matches_all_fields() - Field matching logic
# =============================================================================


def test_matches_all_fields_single_field_match():
    """Test matching single field."""
    artifact = ModelArtifact(name="test-model", source_url="https://example.com")
    fields = {"name": "test-model"}

    assert _matches_all_fields(artifact, fields) is True


def test_matches_all_fields_single_field_no_match():
    """Test non-matching single field."""
    artifact = ModelArtifact(name="test-model", source_url="https://example.com")
    fields = {"name": "different-model"}

    assert _matches_all_fields(artifact, fields) is False


def test_matches_all_fields_multiple_fields_all_match():
    """Test matching multiple fields."""
    artifact = ModelArtifact(
        name="test-model", source_url="https://example.com", license="MIT", size=1000
    )
    fields = {"name": "test-model", "license": "MIT"}

    assert _matches_all_fields(artifact, fields) is True


def test_matches_all_fields_multiple_fields_partial_match():
    """Test partial match fails (all must match)."""
    artifact = ModelArtifact(name="test-model", source_url="https://example.com", license="MIT")
    fields = {"name": "test-model", "license": "Apache-2.0"}  # Second field wrong

    assert _matches_all_fields(artifact, fields) is False


def test_matches_all_fields_case_insensitive_match():
    """Test case-insensitive string matching."""
    artifact = ModelArtifact(name="TEST-Model", source_url="https://example.com", license="MIT")
    fields = {"name": "test-model", "license": "mit"}

    assert _matches_all_fields(artifact, fields) is True


def test_matches_all_fields_missing_attribute():
    """Test matching when artifact missing field (treats as None)."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    fields = {"nonexistent_field": "value"}

    # getattr returns None for missing attributes
    assert _matches_all_fields(artifact, fields) is False


def test_matches_all_fields_empty_fields():
    """Test matching with empty fields dict (all match)."""
    artifact = ModelArtifact(name="test", source_url="https://example.com")
    fields = {}

    # No fields to check = all match
    assert _matches_all_fields(artifact, fields) is True


def test_matches_all_fields_numeric_field():
    """Test matching numeric fields."""
    artifact = ModelArtifact(name="test", source_url="https://example.com", size=5000)
    fields = {"size": 5000}

    assert _matches_all_fields(artifact, fields) is True


# =============================================================================
# Test: _filter_by_fields() - List filtering
# =============================================================================


def test_filter_by_fields_returns_matches():
    """Test filtering returns only matching artifacts."""
    artifact1 = ModelArtifact(name="model-1", source_url="https://example.com/1")
    artifact2 = ModelArtifact(name="model-2", source_url="https://example.com/2")
    artifact3 = ModelArtifact(name="model-1", source_url="https://example.com/3")

    artifacts = [artifact1, artifact2, artifact3]
    fields = {"name": "model-1"}

    result = _filter_by_fields(artifacts, fields)

    assert len(result) == 2
    assert artifact1 in result
    assert artifact3 in result
    assert artifact2 not in result


def test_filter_by_fields_no_matches():
    """Test filtering with no matches returns empty list."""
    artifact1 = ModelArtifact(name="model-1", source_url="https://example.com/1")
    artifact2 = ModelArtifact(name="model-2", source_url="https://example.com/2")

    artifacts = [artifact1, artifact2]
    fields = {"name": "nonexistent"}

    result = _filter_by_fields(artifacts, fields)

    assert len(result) == 0


def test_filter_by_fields_empty_list():
    """Test filtering empty list returns empty list."""
    artifacts: List[BaseArtifact] = []
    fields = {"name": "test"}

    result = _filter_by_fields(artifacts, fields)

    assert len(result) == 0


def test_filter_by_fields_multiple_criteria():
    """Test filtering with multiple field criteria."""
    artifact1 = ModelArtifact(name="test", source_url="https://example.com", license="MIT")
    artifact2 = ModelArtifact(name="test", source_url="https://example.com", license="Apache-2.0")
    artifact3 = ModelArtifact(name="other", source_url="https://example.com", license="MIT")

    artifacts = [artifact1, artifact2, artifact3]
    fields = {"name": "test", "license": "MIT"}

    result = _filter_by_fields(artifacts, fields)

    assert len(result) == 1
    assert artifact1 in result


# =============================================================================
# Test: _filter_by_type() - Type filtering
# =============================================================================


def test_filter_by_type_returns_only_models():
    """Test filtering returns only model artifacts."""
    model1 = ModelArtifact(name="model-1", source_url="https://example.com/1")
    model2 = ModelArtifact(name="model-2", source_url="https://example.com/2")
    dataset = DatasetArtifact(name="dataset-1", source_url="https://example.com/3")
    code = CodeArtifact(name="code-1", source_url="https://github.com/test/repo")

    artifacts = [model1, dataset, model2, code]

    result = _filter_by_type(artifacts, "model")

    assert len(result) == 2
    assert model1 in result
    assert model2 in result
    assert dataset not in result
    assert code not in result


def test_filter_by_type_returns_only_datasets():
    """Test filtering returns only dataset artifacts."""
    model = ModelArtifact(name="model-1", source_url="https://example.com/1")
    dataset1 = DatasetArtifact(name="dataset-1", source_url="https://example.com/2")
    dataset2 = DatasetArtifact(name="dataset-2", source_url="https://example.com/3")
    code = CodeArtifact(name="code-1", source_url="https://github.com/test/repo")

    artifacts = [model, dataset1, code, dataset2]

    result = _filter_by_type(artifacts, "dataset")

    assert len(result) == 2
    assert dataset1 in result
    assert dataset2 in result
    assert model not in result
    assert code not in result


def test_filter_by_type_returns_only_code():
    """Test filtering returns only code artifacts."""
    model = ModelArtifact(name="model-1", source_url="https://example.com/1")
    dataset = DatasetArtifact(name="dataset-1", source_url="https://example.com/2")
    code1 = CodeArtifact(name="code-1", source_url="https://github.com/test/repo1")
    code2 = CodeArtifact(name="code-2", source_url="https://github.com/test/repo2")

    artifacts = [model, code1, dataset, code2]

    result = _filter_by_type(artifacts, "code")

    assert len(result) == 2
    assert code1 in result
    assert code2 in result
    assert model not in result
    assert dataset not in result


def test_filter_by_type_empty_list():
    """Test filtering empty list returns empty list."""
    artifacts: List[BaseArtifact] = []

    result = _filter_by_type(artifacts, "model")

    assert len(result) == 0


def test_filter_by_type_no_matches():
    """Test filtering with no matching type returns empty list."""
    dataset = DatasetArtifact(name="dataset-1", source_url="https://example.com")
    code = CodeArtifact(name="code-1", source_url="https://github.com/test/repo")

    artifacts = [dataset, code]

    result = _filter_by_type(artifacts, "model")

    assert len(result) == 0


# =============================================================================
# Test: save_artifact_metadata() - DynamoDB save
# =============================================================================


@patch("src.artifacts.artifactory.persistence.save_item_to_table")
def test_save_artifact_metadata_calls_dynamo(mock_save):
    """Test save calls DynamoDB with artifact dict."""
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        size=1000,
        license="MIT",
    )

    save_artifact_metadata(artifact)

    # Verify DynamoDB save was called
    mock_save.assert_called_once()

    # Verify table name and artifact dict passed
    call_args = mock_save.call_args
    table_name = call_args[0][0]
    artifact_dict = call_args[0][1]

    assert "artifacts" in table_name.lower()  # Table name contains "artifacts"
    assert artifact_dict["name"] == "test-model"
    assert artifact_dict["artifact_type"] == "model"
    assert artifact_dict["size"] == 1000


@patch("src.artifacts.artifactory.persistence.save_item_to_table")
def test_save_artifact_metadata_includes_all_fields(mock_save):
    """Test save includes all artifact fields in dict."""
    artifact = ModelArtifact(
        name="test",
        source_url="https://example.com",
        size=5000,
        license="Apache-2.0",
        code_name="test-code",
        dataset_name="test-dataset",
    )

    save_artifact_metadata(artifact)

    artifact_dict = mock_save.call_args[0][1]

    assert artifact_dict["code_name"] == "test-code"
    assert artifact_dict["dataset_name"] == "test-dataset"
    assert artifact_dict["license"] == "Apache-2.0"


# =============================================================================
# Test: load_artifact_metadata() - DynamoDB load
# =============================================================================


@patch("src.artifacts.artifactory.persistence.load_item_from_key")
def test_load_artifact_metadata_returns_artifact(mock_load):
    """Test loading artifact from DynamoDB reconstructs object."""
    mock_load.return_value = {
        "artifact_id": "test-id-123",
        "artifact_type": "model",
        "name": "loaded-model",
        "source_url": "https://example.com",
        "s3_key": "models/test-id-123",
        "size": 5000,
        "license": "MIT",
    }

    artifact = load_artifact_metadata("test-id-123")

    assert artifact is not None
    assert isinstance(artifact, ModelArtifact)
    assert artifact.name == "loaded-model"
    assert artifact.size == 5000
    assert artifact.license == "MIT"


@patch("src.artifacts.artifactory.persistence.load_item_from_key")
def test_load_artifact_metadata_returns_none_when_not_found(mock_load):
    """Test loading non-existent artifact returns None."""
    mock_load.return_value = None

    artifact = load_artifact_metadata("nonexistent-id")

    assert artifact is None


@patch("src.artifacts.artifactory.persistence.load_item_from_key")
def test_load_artifact_metadata_raises_on_missing_type(mock_load):
    """Test loading artifact without artifact_type raises ValueError."""
    mock_load.return_value = {
        "artifact_id": "test-id",
        # Missing artifact_type
        "name": "test",
        "source_url": "https://example.com",
    }

    with pytest.raises(ValueError, match="missing artifact_type"):
        load_artifact_metadata("test-id")


# =============================================================================
# Test: load_all_artifacts() - Table scan
# =============================================================================


@patch("src.artifacts.artifactory.persistence.scan_table")
def test_load_all_artifacts_returns_all_types(mock_scan):
    """Test loading all artifacts returns mixed types."""
    mock_scan.return_value = [
        {
            "artifact_id": "model-1",
            "artifact_type": "model",
            "name": "model-1",
            "source_url": "https://example.com/1",
            "s3_key": "models/1",
        },
        {
            "artifact_id": "dataset-1",
            "artifact_type": "dataset",
            "name": "dataset-1",
            "source_url": "https://example.com/2",
            "s3_key": "datasets/1",
        },
        {
            "artifact_id": "code-1",
            "artifact_type": "code",
            "name": "code-1",
            "source_url": "https://github.com/test/repo",
            "s3_key": "code/1",
        },
    ]

    artifacts = load_all_artifacts()

    assert len(artifacts) == 3
    assert isinstance(artifacts[0], ModelArtifact)
    assert isinstance(artifacts[1], DatasetArtifact)
    assert isinstance(artifacts[2], CodeArtifact)


@patch("src.artifacts.artifactory.persistence.scan_table")
def test_load_all_artifacts_skips_invalid_items(mock_scan):
    """Test loading skips items with missing artifact_type."""
    mock_scan.return_value = [
        {
            "artifact_id": "valid-1",
            "artifact_type": "model",
            "name": "valid",
            "source_url": "https://example.com",
            "s3_key": "models/valid-1",  # Existing artifact - skip upload
        },
        {
            "artifact_id": "invalid-1",
            # Missing artifact_type
            "name": "invalid",
            "source_url": "https://example.com",
            "s3_key": "models/invalid-1",
        },
        {
            "artifact_id": "valid-2",
            "artifact_type": "dataset",
            "name": "valid-2",
            "source_url": "https://example.com",
            "s3_key": "datasets/valid-2",  # Existing artifact - skip upload
        },
    ]

    artifacts = load_all_artifacts()

    # Should only return 2 valid artifacts
    assert len(artifacts) == 2
    assert all(hasattr(a, "artifact_type") for a in artifacts)


@patch("src.artifacts.artifactory.persistence.scan_table")
def test_load_all_artifacts_returns_empty_for_empty_table(mock_scan):
    """Test loading from empty table returns empty list."""
    mock_scan.return_value = []

    artifacts = load_all_artifacts()

    assert len(artifacts) == 0


# =============================================================================
# Test: load_all_artifacts_by_fields() - Integration with helpers
# =============================================================================


@patch("src.artifacts.artifactory.persistence.load_all_artifacts")
def test_load_all_artifacts_by_fields_loads_when_no_list_provided(mock_load_all):
    """Test function loads all artifacts when artifact_list not provided."""
    mock_artifacts = [
        ModelArtifact(name="test", source_url="https://example.com"),
    ]
    mock_load_all.return_value = mock_artifacts

    load_all_artifacts_by_fields(fields={"name": "test"})

    # Should call load_all_artifacts
    mock_load_all.assert_called_once()


def test_load_all_artifacts_by_fields_uses_provided_list():
    """Test function uses provided artifact_list without loading."""
    artifacts = [
        ModelArtifact(name="test-1", source_url="https://example.com/1"),
        ModelArtifact(name="test-2", source_url="https://example.com/2"),
    ]

    with patch("src.artifacts.artifactory.persistence.load_all_artifacts") as mock_load_all:
        result = load_all_artifacts_by_fields(fields={"name": "test-1"}, artifact_list=artifacts)

        # Should NOT call load_all_artifacts
        mock_load_all.assert_not_called()

        assert len(result) == 1
        assert result[0].name == "test-1"


def test_load_all_artifacts_by_fields_filters_by_type():
    """Test filtering by artifact_type."""
    artifacts = [
        ModelArtifact(name="test", source_url="https://example.com/1"),
        DatasetArtifact(name="test", source_url="https://example.com/2"),
        CodeArtifact(name="test", source_url="https://github.com/test/repo"),
    ]

    result = load_all_artifacts_by_fields(
        fields={"name": "test"}, artifact_type="model", artifact_list=artifacts
    )

    assert len(result) == 1
    assert isinstance(result[0], ModelArtifact)


def test_load_all_artifacts_by_fields_filters_by_fields():
    """Test filtering by field values."""
    artifacts = [
        ModelArtifact(name="test-1", source_url="https://example.com", license="MIT"),
        ModelArtifact(name="test-2", source_url="https://example.com", license="Apache-2.0"),
        ModelArtifact(name="test-3", source_url="https://example.com", license="MIT"),
    ]

    result = load_all_artifacts_by_fields(fields={"license": "MIT"}, artifact_list=artifacts)

    assert len(result) == 2
    assert all(a.license == "MIT" for a in result)


def test_load_all_artifacts_by_fields_combines_type_and_field_filters():
    """Test combining type and field filters."""
    artifacts = [
        ModelArtifact(name="model-1", source_url="https://example.com", license="MIT"),
        ModelArtifact(name="model-2", source_url="https://example.com", license="Apache-2.0"),
        DatasetArtifact(name="dataset-1", source_url="https://example.com"),
    ]

    result = load_all_artifacts_by_fields(
        fields={"license": "MIT"}, artifact_type="model", artifact_list=artifacts
    )

    assert len(result) == 1
    assert result[0].name == "model-1"
    assert isinstance(result[0], ModelArtifact)
