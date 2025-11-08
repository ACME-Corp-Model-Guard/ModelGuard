import pytest
import time
from unittest.mock import patch, MagicMock

from src.artifacts.model_artifact import ModelArtifact


@pytest.fixture
def mock_metric_class():
    """Create a dummy metric with a .score() method."""
    class DummyMetric:
        def __init__(self, name="DummyMetric", value=1.0):
            self._name = name
            self._value = value

        def score(self, model_artifact):
            time.sleep(0.01)  # simulate latency
            return self._value

        def __class__(self):
            return type(self)

        @property
        def __name__(self):
            return self._name

    return DummyMetric


@pytest.fixture
def mock_metrics(mock_metric_class):
    """Return a small set of dummy metrics."""
    return [
        mock_metric_class(name="A", value=1.0),
        mock_metric_class(name="B", value=0.5),
        mock_metric_class(name="C", value=0.8),
    ]


@pytest.fixture
def model_artifact():
    """Return a baseline ModelArtifact instance (auto_score disabled)."""
    return ModelArtifact(
        name="demo-model",
        source_url="https://example.com/model",
        size=12345,
        license="MIT",
        auto_score=False,
    )


def test_init_without_autoscore(model_artifact):
    """Ensure scores are not computed automatically when auto_score=False."""
    assert model_artifact.scores == {}
    assert model_artifact.scores_latency == {}


def test_compute_scores_parallel(model_artifact, mock_metrics):
    """Verify that _compute_scores runs all metrics in parallel and populates scores."""
    from src.artifacts import model_artifact as ma_module

    # Patch METRICS with a non-empty list of mock metrics
    with patch.object(ma_module, "METRICS", mock_metrics):
        model_artifact._compute_scores()

    # Assert all metrics are present in scores
    for m in mock_metrics:
        metric_name = m.__class__.__name__.replace("Metric", "")
        assert metric_name in model_artifact.scores
        assert isinstance(model_artifact.scores[metric_name], float)
        assert model_artifact.scores_latency[metric_name] >= 0

    # NetScore should be computed
    assert "NetScore" in model_artifact.scores
    assert isinstance(model_artifact.scores["NetScore"], float)
    assert "NetScore" in model_artifact.scores_latency


@patch("src.artifacts.model_artifact.METRICS", new_callable=list)
def test_compute_scores_handles_exceptions(mock_metrics, model_artifact):
    """Verify that metric failures are handled gracefully."""
    good_metric = MagicMock()
    good_metric.__class__.__name__ = "GoodMetric"
    good_metric.score.return_value = 0.9

    bad_metric = MagicMock()
    bad_metric.__class__.__name__ = "BadMetric"
    bad_metric.score.side_effect = RuntimeError("Boom!")

    with patch("src.artifacts.model_artifact.METRICS", [good_metric, bad_metric]):
        model_artifact._compute_scores()

    # Good metric should have a numeric score
    assert "Good" in model_artifact.scores
    assert isinstance(model_artifact.scores["Good"], (float, int))

    # Bad metric should have defaulted to 0.0
    assert model_artifact.scores["Bad"] == 0.0
    assert model_artifact.scores_latency["Bad"] == 0.0


def test_to_dict_contains_expected_fields(model_artifact):
    """Ensure to_dict includes all fields and merges base dict."""
    model_artifact.scores = {"A": 1.0, "NetScore": 0.9}
    model_artifact.scores_latency = {"A": 10.0, "NetScore": 1.0}
    d = model_artifact.to_dict()

    for key in [
        "artifact_id",
        "name",
        "source_url",
        "size",
        "license",
        "scores",
        "scores_latency",
    ]:
        assert key in d

    # Field values should match
    assert d["size"] == 12345
    assert d["license"] == "MIT"


@patch("src.artifacts.model_artifact.calculate_net_score", return_value=0.99)
def test_net_score_called_once(mock_calc, model_artifact):
    """Verify NetScore is calculated once after metrics finish."""
    fake_metric = MagicMock()
    fake_metric.__class__.__name__ = "FakeMetric"
    fake_metric.score.return_value = 0.5

    with patch("src.artifacts.model_artifact.METRICS", [fake_metric]):
        model_artifact._compute_scores()

    mock_calc.assert_called_once()
    assert model_artifact.scores["NetScore"] == 0.99
