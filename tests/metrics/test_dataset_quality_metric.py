from unittest.mock import patch

import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.metrics.dataset_quality_metric import DatasetQualityMetric


# =====================================================================================
# FIXTURES
# =====================================================================================


@pytest.fixture
def model_artifact():
    """Minimal ModelArtifact that references a dataset artifact."""
    return ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        size=123,
        license="MIT",
        artifact_id="model-12345",
        dataset_artifact_id="ds-abcde",
        s3_key="models/test.tar.gz",
    )


@pytest.fixture
def dataset_artifact():
    """Simple DatasetArtifact used as side-effect of load_artifact_metadata()."""
    return DatasetArtifact(
        name="test-dataset",
        source_url="https://example.com/dataset",
        artifact_id="ds-abcde",
        s3_key="datasets/test-dataset.tar.gz",
    )


@pytest.fixture
def metric():
    return DatasetQualityMetric()


# =====================================================================================
# SUCCESS CASE
# =====================================================================================


def test_dataset_quality_success(metric, model_artifact, dataset_artifact):

    fake_files = {
        "data.csv": "a,b,c\n1,2,3",
        "README.md": "# dataset",
    }

    with (
        patch(
            "src.metrics.dataset_quality_metric.load_artifact_metadata",
            return_value=dataset_artifact,
        ),
        patch("src.metrics.dataset_quality_metric.download_artifact_from_s3") as mock_dl,
        patch(
            "src.metrics.dataset_quality_metric.extract_relevant_files",
            return_value=fake_files,
        ),
        patch(
            "src.metrics.dataset_quality_metric.build_file_analysis_prompt",
            return_value="PROMPT",
        ),
        patch(
            "src.metrics.dataset_quality_metric.ask_llm",
            return_value={"dataset_quality": 0.91},
        ),
    ):
        result = metric.score(model_artifact)

    assert "dataset_quality" in result
    assert result["dataset_quality"] == 0.91
    mock_dl.assert_called_once()


# =====================================================================================
# NO DATASET ARTIFACT: Model has no dataset_artifact_id → expect neutral 0.5
# =====================================================================================


def test_dataset_quality_no_dataset_artifact_id(metric, model_artifact):

    model_artifact.dataset_artifact_id = None

    with patch("src.metrics.dataset_quality_metric.load_artifact_metadata") as mock_load:
        result = metric.score(model_artifact)

    assert result["dataset_quality"] == 0.5  # Neutral score when no artifact linked
    mock_load.assert_not_called()


# =====================================================================================
# NEUTRAL: Invalid dataset artifact in Dynamo (None) → expect neutral 0.5
# =====================================================================================


def test_dataset_quality_invalid_dataset_artifact(metric, model_artifact):

    with (
        patch(
            "src.metrics.dataset_quality_metric.load_artifact_metadata",
            return_value=None,
        ),
        patch("src.metrics.dataset_quality_metric.download_artifact_from_s3") as mock_dl,
    ):
        result = metric.score(model_artifact)

    assert result["dataset_quality"] == 0.5  # Neutral score when artifact can't be evaluated
    mock_dl.assert_not_called()


# =====================================================================================
# NEUTRAL: No files extracted → expect neutral 0.5
# =====================================================================================


def test_dataset_quality_no_files(metric, model_artifact, dataset_artifact):

    with (
        patch(
            "src.metrics.dataset_quality_metric.load_artifact_metadata",
            return_value=dataset_artifact,
        ),
        patch("src.metrics.dataset_quality_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.dataset_quality_metric.extract_relevant_files",
            return_value={},
        ),
    ):
        result = metric.score(model_artifact)

    assert result["dataset_quality"] == 0.5  # Neutral score when no files to analyze


# =====================================================================================
# NEUTRAL: LLM returns None → neutral 0.5
# =====================================================================================


def test_dataset_quality_llm_failure(metric, model_artifact, dataset_artifact):

    fake_files = {"data.csv": "a,b,c"}

    with (
        patch(
            "src.metrics.dataset_quality_metric.load_artifact_metadata",
            return_value=dataset_artifact,
        ),
        patch("src.metrics.dataset_quality_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.dataset_quality_metric.extract_relevant_files",
            return_value=fake_files,
        ),
        patch(
            "src.metrics.dataset_quality_metric.build_file_analysis_prompt",
            return_value="PROMPT",
        ),
        patch(
            "src.metrics.dataset_quality_metric.ask_llm",
            return_value=None,
        ),
    ):
        result = metric.score(model_artifact)

    assert result["dataset_quality"] == 0.5  # Neutral score when LLM returns None


# =====================================================================================
# NEUTRAL: LLM returns wrong JSON key → neutral 0.5
# =====================================================================================


def test_dataset_quality_bad_llm_json(metric, model_artifact, dataset_artifact):

    fake_files = {"data.csv": "a,b,c"}

    with (
        patch(
            "src.metrics.dataset_quality_metric.load_artifact_metadata",
            return_value=dataset_artifact,
        ),
        patch("src.metrics.dataset_quality_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.dataset_quality_metric.extract_relevant_files",
            return_value=fake_files,
        ),
        patch("src.metrics.dataset_quality_metric.build_file_analysis_prompt"),
        patch(
            "src.metrics.dataset_quality_metric.ask_llm",
            return_value={"not_dataset_quality": 1.0},
        ),
    ):
        result = metric.score(model_artifact)

    assert result["dataset_quality"] == 0.5  # Neutral score when LLM returns invalid JSON


# =====================================================================================
# NEUTRAL: Exception anywhere → neutral 0.5
# =====================================================================================


def test_dataset_quality_exception(metric, model_artifact, dataset_artifact):

    with (
        patch(
            "src.metrics.dataset_quality_metric.load_artifact_metadata",
            return_value=dataset_artifact,
        ),
        patch(
            "src.metrics.dataset_quality_metric.download_artifact_from_s3",
            side_effect=RuntimeError("boom"),
        ),
    ):
        result = metric.score(model_artifact)

    assert result["dataset_quality"] == 0.5  # Neutral score on evaluation error


# =====================================================================================
# TEMP FILE CLEANUP — ensure unlink() is invoked
# =====================================================================================


def test_dataset_quality_tempfile_cleanup(metric, model_artifact, dataset_artifact):

    fake_files = {"data.csv": "1,2,3"}

    with (
        patch(
            "src.metrics.dataset_quality_metric.load_artifact_metadata",
            return_value=dataset_artifact,
        ),
        patch("src.metrics.dataset_quality_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.dataset_quality_metric.extract_relevant_files",
            return_value=fake_files,
        ),
        patch(
            "src.metrics.dataset_quality_metric.build_file_analysis_prompt",
            return_value="PROMPT",
        ),
        patch(
            "src.metrics.dataset_quality_metric.ask_llm",
            return_value={"dataset_quality": 0.5},
        ),
        patch("os.unlink") as mock_unlink,
    ):
        metric.score(model_artifact)

    assert mock_unlink.called
