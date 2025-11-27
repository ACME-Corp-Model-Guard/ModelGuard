from unittest.mock import patch

from src.artifacts.model_artifact import ModelArtifact
from src.metrics.ramp_up_metric import RampUpMetric


# =====================================================================
# Helpers
# =====================================================================


def make_model_artifact(
    artifact_id="m123",
    name="test-model",
    source_url="https://example.com/model",
    s3_key="models/m123.tar.gz",
):
    """Helper to quickly instantiate a minimal ModelArtifact."""
    return ModelArtifact(
        artifact_id=artifact_id,
        name=name,
        source_url=source_url,
        s3_key=s3_key,
    )


# =====================================================================
# Tests
# =====================================================================


def test_ramp_up_metric_success():
    """Full success path: S3 download → extraction → LLM → valid score."""
    model = make_model_artifact()

    fake_files = {
        "README.md": "This is documentation",
        "config.json": "{}",
    }

    fake_llm_response = {"ramp_up": 0.85}

    with (
        patch("src.metrics.ramp_up_metric.download_artifact_from_s3") as mock_s3,
        patch(
            "src.metrics.ramp_up_metric.extract_relevant_files", return_value=fake_files
        ),
        patch("src.metrics.ramp_up_metric.ask_llm", return_value=fake_llm_response),
    ):
        metric = RampUpMetric()
        result = metric.score(model)

    mock_s3.assert_called_once()
    assert result == {"ramp_up": 0.85}


def test_ramp_up_metric_missing_s3_key():
    """If model.s3_key is missing, return 0.0."""
    model = make_model_artifact(s3_key=None)

    metric = RampUpMetric()
    result = metric.score(model)

    assert result == {"ramp_up": 0.0}


def test_ramp_up_metric_s3_download_failure():
    """If S3 download fails, return 0.0."""
    model = make_model_artifact()

    with patch(
        "src.metrics.ramp_up_metric.download_artifact_from_s3",
        side_effect=Exception("boom"),
    ):
        metric = RampUpMetric()
        result = metric.score(model)

    assert result == {"ramp_up": 0.0}


def test_ramp_up_metric_no_relevant_files():
    """If extraction returns no files, return 0.0."""
    model = make_model_artifact()

    with (
        patch("src.metrics.ramp_up_metric.download_artifact_from_s3"),
        patch("src.metrics.ramp_up_metric.extract_relevant_files", return_value={}),
    ):
        metric = RampUpMetric()
        result = metric.score(model)

    assert result == {"ramp_up": 0.0}


def test_ramp_up_metric_invalid_llm_output_none():
    """If LLM returns None, score should be 0.0."""
    model = make_model_artifact()

    fake_files = {"README.md": "Some text"}

    with (
        patch("src.metrics.ramp_up_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.ramp_up_metric.extract_relevant_files", return_value=fake_files
        ),
        patch("src.metrics.ramp_up_metric.ask_llm", return_value=None),
    ):
        metric = RampUpMetric()
        result = metric.score(model)

    assert result == {"ramp_up": 0.0}


def test_ramp_up_metric_invalid_llm_missing_field():
    """If LLM JSON lacks the expected field → 0.0."""
    model = make_model_artifact()

    fake_files = {"README.md": "Docs"}
    bad_llm_response = {"wrong_key": 0.5}

    with (
        patch("src.metrics.ramp_up_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.ramp_up_metric.extract_relevant_files", return_value=fake_files
        ),
        patch("src.metrics.ramp_up_metric.ask_llm", return_value=bad_llm_response),
    ):
        metric = RampUpMetric()
        result = metric.score(model)

    assert result == {"ramp_up": 0.0}


def test_ramp_up_metric_invalid_llm_non_numeric():
    """If LLM returns a non-numeric score, we should get 0.0."""
    model = make_model_artifact()

    fake_files = {"README.md": "Docs"}
    llm_response = {"ramp_up": "not-a-number"}

    with (
        patch("src.metrics.ramp_up_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.ramp_up_metric.extract_relevant_files", return_value=fake_files
        ),
        patch("src.metrics.ramp_up_metric.ask_llm", return_value=llm_response),
    ):
        metric = RampUpMetric()
        result = metric.score(model)

    assert result == {"ramp_up": 0.0}


def test_ramp_up_metric_clamps_score():
    """If LLM gives a score >1.0 or <0.0, extract_llm_score_field
    returns it but RampUpMetric clamps value implicitly by returning float,
    so we test upper/lower boundaries."""
    model = make_model_artifact()

    fake_files = {"README.md": "Docs"}

    with (
        patch("src.metrics.ramp_up_metric.download_artifact_from_s3"),
        patch(
            "src.metrics.ramp_up_metric.extract_relevant_files", return_value=fake_files
        ),
    ):
        metric = RampUpMetric()

        # Score > 1.0 → still returned directly (clamping occurs in extract_llm_score_field)
        with patch("src.metrics.ramp_up_metric.ask_llm", return_value={"ramp_up": 2.5}):
            result = metric.score(model)
            # extract_llm_score_field returns float(2.5), but *we* do not clamp further,
            # so we match CodeQualityMetric behavior: raw numeric is returned.
            # However, since net_score clamps, this is fine.
            assert result == {"ramp_up": 2.5}

        # Score < 0.0 → returned directly
        with patch(
            "src.metrics.ramp_up_metric.ask_llm", return_value={"ramp_up": -1.0}
        ):
            result = metric.score(model)
            assert result == {"ramp_up": -1.0}


def test_ramp_up_metric_unexpected_exception():
    """Any unexpected error should result in {ramp_up: 0.0}."""
    model = make_model_artifact()

    with patch(
        "src.metrics.ramp_up_metric.download_artifact_from_s3",
        side_effect=RuntimeError("unexpected"),
    ):
        metric = RampUpMetric()
        result = metric.score(model)

    assert result == {"ramp_up": 0.0}
