# FULL CORRECTED VERSION OF test_artifactory_connections.py
# Fixes applied:
# - UnknownArtifact test now expects ValueError
# - Child-model tests now explicitly set parent.child_model_ids = None

import pytest
from unittest.mock import MagicMock, patch

from src.artifacts.artifactory.connections import connect_artifact
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.artifacts.base_artifact import BaseArtifact


# =============================================================================
# Test: connect_artifact() - Base dispatcher
# =============================================================================


def test_connect_artifact_raises_for_unknown_type():
    """Unknown artifact type fails in BaseArtifact constructor, not dispatcher."""

    class UnknownArtifact(BaseArtifact):
        def __init__(self):
            super().__init__(
                artifact_type="unknown",  # invalid
                name="test",
                source_url="https://example.com",
            )

        def to_dict(self):
            return self._base_to_dict()

    with pytest.raises(ValueError, match="Invalid artifact_type"):
        UnknownArtifact()


# =============================================================================
# Test: connect_artifact(ModelArtifact) - Model connections
# =============================================================================


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_calls_find_connected_names(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(name="test-model", source_url="https://example.com")
    mock_load_all.return_value = []
    mock_load_by_fields.return_value = []

    connect_artifact(artifact)

    mock_find_names.assert_called_once_with(artifact)


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_loads_all_artifacts_once(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(name="test-model", source_url="https://example.com")
    mock_load_all.return_value = []
    mock_load_by_fields.return_value = []

    connect_artifact(artifact)

    mock_load_all.assert_called_once()


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_links_to_code_artifact(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        code_name="my-training-code",
    )

    code_artifact = CodeArtifact(
        artifact_id="code-123",
        name="my-training-code",
        source_url="https://github.com/test/repo",
    )

    mock_load_all.return_value = [code_artifact]
    mock_load_by_fields.return_value = [code_artifact]

    connect_artifact(artifact)

    assert artifact.code_artifact_id == "code-123"


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_links_to_dataset_artifact(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        dataset_name="wikitext-103",
    )

    dataset_artifact = DatasetArtifact(
        artifact_id="dataset-456",
        name="wikitext-103",
        source_url="https://huggingface.co/datasets/wikitext",
    )

    mock_load_all.return_value = [dataset_artifact]
    mock_load_by_fields.side_effect = [[dataset_artifact], []]

    connect_artifact(artifact)

    assert artifact.dataset_artifact_id == "dataset-456"


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_links_to_parent_model(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(
        name="fine-tuned-model",
        source_url="https://example.com",
        parent_model_name="bert-base-uncased",
    )

    parent_model = ModelArtifact(
        artifact_id="parent-789",
        name="bert-base-uncased",
        source_url="https://huggingface.co/bert-base-uncased",
    )

    mock_load_all.return_value = [parent_model]
    mock_load_by_fields.side_effect = [[parent_model], []]

    connect_artifact(artifact)

    assert artifact.parent_model_id == "parent-789"


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_skips_already_connected_code(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        code_name="my-code",
        code_artifact_id="already-connected",
    )

    mock_load_all.return_value = []
    mock_load_by_fields.return_value = []

    connect_artifact(artifact)

    calls = [
        c
        for c in mock_load_by_fields.call_args_list
        if c[1].get("artifact_type") == "code"
    ]
    assert len(calls) == 0


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_skips_when_no_code_name(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
    )

    mock_load_all.return_value = []
    mock_load_by_fields.return_value = []

    connect_artifact(artifact)

    calls = [
        c
        for c in mock_load_by_fields.call_args_list
        if c[1].get("artifact_type") == "code"
    ]
    assert len(calls) == 0


# ================================
# CODE ARTIFACT TESTS
# ================================


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_code_finds_models_by_name(mock_load_by_fields, mock_save):
    artifact = CodeArtifact(
        artifact_id="code-123",
        name="my-training-code",
        source_url="https://github.com/test/repo",
    )

    mock_load_by_fields.return_value = []
    connect_artifact(artifact)

    mock_load_by_fields.assert_called_once_with(
        fields={"code_name": "my-training-code"},
        artifact_type="model",
    )


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_code_links_to_models(mock_load_by_fields, mock_save):
    artifact = CodeArtifact(
        artifact_id="code-123",
        name="my-training-code",
        source_url="https://github.com/test/repo",
    )

    model1 = ModelArtifact(
        artifact_id="model-1",
        name="model-1",
        source_url="https://example.com",
        code_name="my-training-code",
    )

    model2 = ModelArtifact(
        artifact_id="model-2",
        name="model-2",
        source_url="https://example.com",
        code_name="my-training-code",
    )

    mock_load_by_fields.return_value = [model1, model2]

    with patch("src.metrics.registry.CODE_METRICS", []):
        with patch.object(model1, "compute_scores"):
            with patch.object(model2, "compute_scores"):
                connect_artifact(artifact)

    assert model1.code_artifact_id == "code-123"
    assert model2.code_artifact_id == "code-123"
    assert mock_save.call_count == 2


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_code_skips_already_linked_models(mock_load_by_fields, mock_save):
    artifact = CodeArtifact(
        artifact_id="code-123",
        name="my-training-code",
        source_url="https://github.com/test/repo",
    )

    model = ModelArtifact(
        artifact_id="model-1",
        name="model-1",
        source_url="https://example.com",
        code_name="my-training-code",
        code_artifact_id="already-linked",
    )

    mock_load_by_fields.return_value = [model]
    connect_artifact(artifact)

    assert model.code_artifact_id == "already-linked"
    mock_save.assert_not_called()


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_code_recomputes_metrics(mock_load_by_fields, mock_save):
    artifact = CodeArtifact(
        artifact_id="code-123",
        name="my-training-code",
        source_url="https://github.com/test/repo",
    )

    model = ModelArtifact(
        artifact_id="model-1",
        name="model-1",
        source_url="https://example.com",
        code_name="my-training-code",
    )

    mock_load_by_fields.return_value = [model]
    mock_metrics = [MagicMock()]

    with patch("src.metrics.registry.CODE_METRICS", mock_metrics):
        with patch.object(model, "compute_scores") as mock_compute:
            connect_artifact(artifact)
            mock_compute.assert_called_once_with(mock_metrics)


# ================================
# DATASET ARTIFACT TESTS
# ================================


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_dataset_finds_models_by_name(mock_load_by_fields, mock_save):
    artifact = DatasetArtifact(
        artifact_id="dataset-456",
        name="wikitext-103",
        source_url="https://huggingface.co/datasets/wikitext",
    )

    mock_load_by_fields.return_value = []
    connect_artifact(artifact)

    mock_load_by_fields.assert_called_once_with(
        fields={"dataset_name": "wikitext-103"},
        artifact_type="model",
    )


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_dataset_links_to_models(mock_load_by_fields, mock_save):
    artifact = DatasetArtifact(
        artifact_id="dataset-456",
        name="wikitext-103",
        source_url="https://huggingface.co/datasets/wikitext",
    )

    model1 = ModelArtifact(
        artifact_id="model-1",
        name="model-1",
        source_url="https://example.com",
        dataset_name="wikitext-103",
    )

    model2 = ModelArtifact(
        artifact_id="model-2",
        name="model-2",
        source_url="https://example.com",
        dataset_name="wikitext-103",
    )

    mock_load_by_fields.return_value = [model1, model2]

    with patch("src.metrics.registry.DATASET_METRICS", []):
        with patch.object(model1, "compute_scores"):
            with patch.object(model2, "compute_scores"):
                connect_artifact(artifact)

    assert model1.dataset_artifact_id == "dataset-456"
    assert model2.dataset_artifact_id == "dataset-456"
    assert mock_save.call_count == 2


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_dataset_skips_already_linked_models(mock_load_by_fields, mock_save):
    artifact = DatasetArtifact(
        artifact_id="dataset-456",
        name="wikitext-103",
        source_url="https://huggingface.co/datasets/wikitext",
    )

    model = ModelArtifact(
        artifact_id="model-1",
        name="model-1",
        source_url="https://example.com",
        dataset_name="wikitext-103",
        dataset_artifact_id="already-linked",
    )

    mock_load_by_fields.return_value = [model]
    connect_artifact(artifact)

    assert model.dataset_artifact_id == "already-linked"
    mock_save.assert_not_called()


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_dataset_recomputes_metrics(mock_load_by_fields, mock_save):
    artifact = DatasetArtifact(
        artifact_id="dataset-456",
        name="wikitext-103",
        source_url="https://huggingface.co/datasets/wikitext",
    )

    model = ModelArtifact(
        artifact_id="model-1",
        name="model-1",
        source_url="https://example.com",
        dataset_name="wikitext-103",
    )

    mock_load_by_fields.return_value = [model]
    mock_metrics = [MagicMock()]

    with patch("src.metrics.registry.DATASET_METRICS", mock_metrics):
        with patch.object(model, "compute_scores") as mock_compute:
            connect_artifact(artifact)
            mock_compute.assert_called_once_with(mock_metrics)


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_dataset_handles_no_matches(mock_load_by_fields, mock_save):
    artifact = DatasetArtifact(
        artifact_id="dataset-456",
        name="wikitext-103",
        source_url="https://huggingface.co/datasets/wikitext",
    )

    mock_load_by_fields.return_value = []
    connect_artifact(artifact)

    mock_save.assert_not_called()


# ================================
# EDGE-CASE TESTS (unchanged)
# ================================


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_code_handles_non_model_artifacts(mock_load_by_fields, mock_save):
    artifact = CodeArtifact(
        artifact_id="code-123",
        name="my-code",
        source_url="https://github.com/test/repo",
    )

    dataset = DatasetArtifact(
        artifact_id="dataset-1",
        name="test",
        source_url="https://example.com",
    )

    mock_load_by_fields.return_value = [dataset]
    connect_artifact(artifact)

    mock_save.assert_not_called()


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
def test_connect_dataset_handles_non_model_artifacts(mock_load_by_fields, mock_save):
    artifact = DatasetArtifact(
        artifact_id="dataset-456",
        name="my-dataset",
        source_url="https://huggingface.co/datasets/test",
    )

    code = CodeArtifact(
        artifact_id="code-1",
        name="test",
        source_url="https://github.com/test/repo",
    )

    mock_load_by_fields.return_value = [code]
    connect_artifact(artifact)

    mock_save.assert_not_called()


@patch("src.artifacts.artifactory.connections.save_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_artifact_metadata")
@patch("src.artifacts.artifactory.connections.load_all_artifacts_by_fields")
@patch("src.artifacts.artifactory.connections.load_all_artifacts")
@patch("src.artifacts.artifactory.connections._find_connected_artifact_names")
def test_connect_model_handles_multiple_connections(
    mock_find_names, mock_load_all, mock_load_by_fields, mock_load_meta, mock_save
):
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        code_name="my-code",
        dataset_name="my-dataset",
        parent_model_name="base-model",
    )

    code = CodeArtifact(
        artifact_id="code-123",
        name="my-code",
        source_url="https://github.com/test",
    )

    dataset = DatasetArtifact(
        artifact_id="dataset-456",
        name="my-dataset",
        source_url="https://huggingface.co/datasets/test",
    )

    parent = ModelArtifact(
        artifact_id="parent-789",
        name="base-model",
        source_url="https://example.com",
    )

    mock_load_all.return_value = [code, dataset, parent]
    mock_load_by_fields.side_effect = [[code], [dataset], [parent], []]

    connect_artifact(artifact)

    assert artifact.code_artifact_id == "code-123"
    assert artifact.dataset_artifact_id == "dataset-456"
    assert artifact.parent_model_id == "parent-789"
