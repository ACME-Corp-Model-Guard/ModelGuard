from unittest.mock import patch

import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.metrics.code_quality_metric import CodeQualityMetric


@pytest.fixture
def model_artifact():
    """Minimal ModelArtifact for testing."""
    return ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        size=123,
        license="MIT",
        artifact_id="12345",
        code_artifact_id="code-abcde",
        s3_key="models/test.tar.gz",
    )


@pytest.fixture
def code_artifact():
    return CodeArtifact(
        name="test-code",
        source_url="https://example.com/code",
        artifact_id="code-abcde",
        s3_key="code/test.tar.gz",
    )


@pytest.fixture
def metric():
    return CodeQualityMetric()


# =====================================================================================
# SUCCESS CASE
# =====================================================================================


def test_code_quality_metric_success(metric, model_artifact, code_artifact):

    fake_files = {
        "main.py": "print('hello')",
        "utils.py": "def f(): pass",
    }

    # Mock all external dependencies
    with (
        patch(
            "src.metrics.code_quality_metric.load_artifact_metadata",
            return_value=code_artifact,
        ),
        patch("src.metrics.code_quality_metric.download_artifact_from_s3") as mock_dl,
        patch(
            "src.metrics.code_quality_metric.extract_relevant_files",
            return_value=fake_files,
        ),
        patch(
            "src.metrics.code_quality_metric.build_file_analysis_prompt",
            return_value="PROMPT",
        ),
        patch(
            "src.metrics.code_quality_metric.ask_llm",
            return_value={"code_quality": 0.82},
        ),
    ):
        result = metric.score(model_artifact)

    # Validate result
    assert "code_quality" in result
    assert result["code_quality"] == 0.82

    # Ensure mocks were used
    mock_dl.assert_called_once()


# =====================================================================================
# FAILURE: ModelArtifact does not have code_artifact_id → expect fallback score 0.0
# =====================================================================================
def test_code_quality_metric_no_code_artifact(metric, model_artifact, code_artifact):

    model_artifact.code_artifact_id = None  # Remove code artifact reference

    with patch(
        "src.metrics.code_quality_metric.load_artifact_metadata",
        wraps="src.metrics.code_quality_metric.load_artifact_metadata",
    ) as mock_load:
        result = metric.score(model_artifact)

    assert result["code_quality"] == 0.0
    assert not mock_load.called  # load_artifact_metadata should not be called


# =====================================================================================
# FAILURE: invalid CodeArtifact → expect fallback score 0.0
# =====================================================================================
def test_code_quality_metric_invalid_code_artifact(metric, model_artifact, code_artifact):

    with (
        patch(
            "src.metrics.code_quality_metric.load_artifact_metadata",
            return_value=None,
        ),
        patch("src.metrics.code_quality_metric.download_artifact_from_s3") as mock_dl,
    ):
        result = metric.score(model_artifact)

    assert result["code_quality"] == 0.0
    assert not mock_dl.called  # download_artifact_from_s3 should not be called


# =====================================================================================
# FAILURE: LLM returns None → expect fallback score 0.0
# =====================================================================================


def test_code_quality_metric_llm_failure(metric, model_artifact, code_artifact):

    fake_files = {"main.py": "sample code"}

    with (
        patch(
            "src.metrics.code_quality_metric.load_artifact_metadata",
            return_value=code_artifact,
        ),
        patch("src.metrics.code_quality_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.code_quality_metric.extract_relevant_files",
            return_value=fake_files,
        ),
        patch(
            "src.metrics.code_quality_metric.build_file_analysis_prompt",
            return_value="PROMPT",
        ),
        patch("src.metrics.code_quality_metric.ask_llm", return_value=None),
    ):
        result = metric.score(model_artifact)

    assert result["code_quality"] == 0.0


# =====================================================================================
# FAILURE: LLM returns wrong JSON → expect fallback 0.0
# =====================================================================================


def test_code_quality_metric_bad_llm_json(metric, model_artifact, code_artifact):

    fake_files = {"main.py": "print('x')"}

    with (
        patch(
            "src.metrics.code_quality_metric.load_artifact_metadata",
            return_value=code_artifact,
        ),
        patch("src.metrics.code_quality_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.code_quality_metric.extract_relevant_files",
            return_value=fake_files,
        ),
        patch("src.metrics.code_quality_metric.build_file_analysis_prompt"),
        patch(
            "src.metrics.code_quality_metric.ask_llm",
            return_value={"not_code_quality": 1.0},
        ),
    ):
        result = metric.score(model_artifact)

    assert result["code_quality"] == 0.0


# =====================================================================================
# FAILURE: No files extracted → expect fallback 0.0
# =====================================================================================


def test_code_quality_metric_no_files(metric, model_artifact, code_artifact):

    with (
        patch(
            "src.metrics.code_quality_metric.load_artifact_metadata",
            return_value=code_artifact,
        ),
        patch("src.metrics.code_quality_metric.download_artifact_from_s3"),
        patch("src.metrics.code_quality_metric.extract_relevant_files", return_value={}),
    ):
        result = metric.score(model_artifact)

    assert result["code_quality"] == 0.0


# =====================================================================================
# FAILURE: Exception anywhere → expect fallback 0.0
# =====================================================================================


def test_code_quality_metric_exception(metric, model_artifact, code_artifact):

    with (
        patch(
            "src.metrics.code_quality_metric.load_artifact_metadata",
            return_value=code_artifact,
        ),
        patch(
            "src.metrics.code_quality_metric.download_artifact_from_s3",
            side_effect=RuntimeError("boom"),
        ),
    ):
        result = metric.score(model_artifact)

    assert result["code_quality"] == 0.0


# =====================================================================================
# TEMP FILE CLEANUP (ensures unlink is attempted)
# =====================================================================================


def test_temp_file_cleanup(metric, model_artifact, code_artifact):

    with (
        patch(
            "src.metrics.code_quality_metric.load_artifact_metadata",
            return_value=code_artifact,
        ),
        patch("src.metrics.code_quality_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.code_quality_metric.extract_relevant_files",
            return_value={"file.py": "x"},
        ),
        patch(
            "src.metrics.code_quality_metric.build_file_analysis_prompt",
            return_value="PROMPT",
        ),
        patch(
            "src.metrics.code_quality_metric.ask_llm",
            return_value={"code_quality": 0.5},
        ),
        patch("os.unlink") as mock_unlink,
    ):
        metric.score(model_artifact)

    # The temporary tarball should be removed at end of score()
    assert mock_unlink.called
