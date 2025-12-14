import pytest
from unittest.mock import patch, MagicMock
from src.artifacts.artifactory import package_confusion
from src.artifacts.model_artifact import ModelArtifact


@pytest.fixture
def mock_popular_models():
    return ["bert-base-uncased", "gpt2", "roberta-base"]


@pytest.fixture
def canonical_model():
    return ModelArtifact(
        artifact_id="bert-base-uncased",
        name="bert-base-uncased",
        metadata={"downloads": 2000000, "likes": 5000, "created_at": "2023-01-01T00:00:00Z"},
    )


@pytest.fixture
def suspicious_model():
    return ModelArtifact(
        artifact_id="bert-base-uncased-fake",
        name="bert-base-uncased-fake",
        metadata={"downloads": 150, "likes": 1, "created_at": "2025-12-13T00:00:00Z"},
    )


@pytest.fixture
def normal_model():
    return ModelArtifact(
        artifact_id="my-cool-model",
        name="my-cool-model",
        metadata={"downloads": 10, "likes": 0, "created_at": "2025-12-01T00:00:00Z"},
    )


def test_is_canonical_true(canonical_model, mock_popular_models):
    assert package_confusion.is_canonical(canonical_model, mock_popular_models)


def test_is_canonical_false(normal_model, mock_popular_models):
    assert not package_confusion.is_canonical(normal_model, mock_popular_models)


@patch("src.artifacts.artifactory.package_confusion._get_popular_models")
def test_is_suspected_package_confusion_similarity(
    mock_get_popular, suspicious_model, mock_popular_models
):
    mock_get_popular.return_value = mock_popular_models
    # Should be suspected due to high similarity
    assert package_confusion.is_suspected_package_confusion(suspicious_model)


@patch("src.artifacts.artifactory.package_confusion._get_popular_models")
def test_is_suspected_package_confusion_not_suspected(
    mock_get_popular, normal_model, mock_popular_models
):
    mock_get_popular.return_value = mock_popular_models
    # Should not be suspected
    assert not package_confusion.is_suspected_package_confusion(normal_model)


@patch("src.artifacts.artifactory.package_confusion._get_popular_models")
def test_is_suspected_package_confusion_canonical(
    mock_get_popular, canonical_model, mock_popular_models
):
    mock_get_popular.return_value = mock_popular_models
    # Canonical models should not be suspected
    assert not package_confusion.is_suspected_package_confusion(canonical_model)
