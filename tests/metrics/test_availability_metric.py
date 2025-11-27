import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.metrics.availability_metric import AvailabilityMetric


# =====================================================================================
# FIXTURES
# =====================================================================================


@pytest.fixture
def model_artifact():
    """Minimal ModelArtifact for availability testing."""
    return ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        size=123,
        license="MIT",
        artifact_id="m-12345",
        dataset_artifact_id="ds-111",
        code_artifact_id="cd-222",
        s3_key="models/test.tar.gz",
    )


@pytest.fixture
def metric():
    return AvailabilityMetric()


# =====================================================================================
# SUCCESS: both dataset and code available → 1.0
# =====================================================================================


def test_availability_metric_both_present(metric, model_artifact):
    result = metric.score(model_artifact)

    assert "availability" in result
    assert result["availability"] == 1.0


# =====================================================================================
# dataset only → 0.5
# =====================================================================================


def test_availability_metric_dataset_only(metric, model_artifact):
    model_artifact.code_artifact_id = None  # remove code link

    result = metric.score(model_artifact)
    assert result["availability"] == 0.5


# =====================================================================================
# code only → 0.5
# =====================================================================================


def test_availability_metric_code_only(metric, model_artifact):
    model_artifact.dataset_artifact_id = None  # remove dataset link

    result = metric.score(model_artifact)
    assert result["availability"] == 0.5


# =====================================================================================
# neither dataset nor code → 0.0
# =====================================================================================


def test_availability_metric_neither(metric, model_artifact):
    model_artifact.dataset_artifact_id = None
    model_artifact.code_artifact_id = None

    result = metric.score(model_artifact)
    assert result["availability"] == 0.0


# =====================================================================================
# missing fields (should still work) → treat as unavailable
# =====================================================================================


def test_availability_metric_missing_fields(metric):
    """
    Construct a ModelArtifact without dataset/code fields.
    Should gracefully treat both as missing.
    """

    model = ModelArtifact(
        name="no-links",
        source_url="https://example.com/model",
        size=10,
        license="Unknown",
    )

    result = metric.score(model)
    assert result["availability"] == 0.0
