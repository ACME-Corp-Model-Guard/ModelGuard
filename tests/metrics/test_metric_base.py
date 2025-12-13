"""
Tests for the Metric abstract base class.
"""

import pytest
from typing import Dict, Union

from src.metrics.metric import Metric
from src.artifacts.model_artifact import ModelArtifact


# =============================================================================
# Concrete Implementation for Testing
# =============================================================================


class ConcreteMetric(Metric):
    """Concrete implementation of Metric for testing."""

    def __init__(self, return_value: Union[float, Dict[str, float]] = 0.5):
        self.return_value = return_value

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        return self.return_value


class FailingMetric(Metric):
    """Metric that raises an exception."""

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        raise ValueError("Scoring failed")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def model_artifact():
    """Create a basic model artifact for testing."""
    return ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        size=1000,
        license="MIT",
    )


# =============================================================================
# Metric Abstract Class Tests
# =============================================================================


def test_metric_cannot_be_instantiated():
    """Metric abstract class should not be directly instantiable."""
    with pytest.raises(TypeError):
        Metric()  # type: ignore


def test_concrete_metric_returns_float(model_artifact):
    """Concrete metric should return float score."""
    metric = ConcreteMetric(return_value=0.85)
    result = metric.score(model_artifact)
    assert result == 0.85


def test_concrete_metric_returns_dict(model_artifact):
    """Concrete metric can return dict of scores."""
    scores = {"platform_a": 0.7, "platform_b": 0.9}
    metric = ConcreteMetric(return_value=scores)
    result = metric.score(model_artifact)
    assert result == scores


def test_concrete_metric_is_instance_of_metric():
    """Concrete metric should be instance of Metric."""
    metric = ConcreteMetric()
    assert isinstance(metric, Metric)


def test_failing_metric_raises_exception(model_artifact):
    """Metric exceptions should propagate."""
    metric = FailingMetric()
    with pytest.raises(ValueError, match="Scoring failed"):
        metric.score(model_artifact)


def test_metric_score_method_signature():
    """Verify score method accepts ModelArtifact."""
    import inspect

    sig = inspect.signature(Metric.score)
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "model" in params
