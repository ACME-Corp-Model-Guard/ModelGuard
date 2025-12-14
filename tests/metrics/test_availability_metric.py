import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.metrics.availability_metric import AvailabilityMetric


# =====================================================================================
# FIXTURES
# =====================================================================================


@pytest.fixture
def model_artifact():
    """ModelArtifact with full linkability and links for availability testing."""
    return ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        size=123,
        license="MIT",
        artifact_id="m-12345",
        # Linkable names (0.25 each)
        dataset_name="test-dataset",
        code_name="test-code",
        # Actual links (0.25 each)
        dataset_artifact_id="ds-111",
        code_artifact_id="cd-222",
        s3_key="models/test.tar.gz",
    )


@pytest.fixture
def metric():
    return AvailabilityMetric()


# =====================================================================================
# SUCCESS: both names and links present → 1.0
# (dataset_name + dataset_artifact_id + code_name + code_artifact_id = 4 * 0.25)
# =====================================================================================


def test_availability_metric_both_present(metric, model_artifact):
    result = metric.score(model_artifact)

    assert "availability" in result
    assert result["availability"] == 1.0


# =====================================================================================
# dataset linked only (name + artifact_id) → 0.5
# =====================================================================================


def test_availability_metric_dataset_only(metric, model_artifact):
    model_artifact.code_name = None  # remove code linkability
    model_artifact.code_artifact_id = None  # remove code link

    result = metric.score(model_artifact)
    assert result["availability"] == 0.5


# =====================================================================================
# code linked only (name + artifact_id) → 0.5
# =====================================================================================


def test_availability_metric_code_only(metric, model_artifact):
    model_artifact.dataset_name = None  # remove dataset linkability
    model_artifact.dataset_artifact_id = None  # remove dataset link

    result = metric.score(model_artifact)
    assert result["availability"] == 0.5


# =====================================================================================
# neither names nor links → 0.0
# =====================================================================================


def test_availability_metric_neither(metric, model_artifact):
    model_artifact.dataset_name = None
    model_artifact.dataset_artifact_id = None
    model_artifact.code_name = None
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


# =====================================================================================
# linkable but not linked → partial credit
# =====================================================================================


def test_availability_metric_names_only(metric):
    """
    Model has names but no actual artifact links.
    Should get partial credit for linkability (0.25 * 2 = 0.5).
    """
    model = ModelArtifact(
        name="linkable-model",
        source_url="https://example.com/model",
        size=10,
        license="MIT",
        dataset_name="some-dataset",
        code_name="some-repo",
    )

    result = metric.score(model)
    assert result["availability"] == 0.5


def test_availability_metric_links_only(metric):
    """
    Model has artifact links but no names.
    Should get credit for actual links (0.25 * 2 = 0.5).
    """
    model = ModelArtifact(
        name="linked-model",
        source_url="https://example.com/model",
        size=10,
        license="MIT",
        dataset_artifact_id="ds-123",
        code_artifact_id="cd-456",
    )

    result = metric.score(model)
    assert result["availability"] == 0.5
