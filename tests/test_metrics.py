"""Tests for metric classes."""

import pytest
from src.model import Model
from src.metrics.metric import Metric
from src.metrics.availability_metric import AvailabilityMetric
from src.metrics.bus_factor_metric import BusFactorMetric


def test_metric_is_abstract():
    """Test that Metric cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Metric()


def test_availability_metric():
    """Test availability metric."""
    metric = AvailabilityMetric()
    model = Model(
        name="test_model",
        model_key="models/test_model/model",
        code_key="models/test_model/code",
        dataset_key="models/test_model/dataset"
    )
    
    result = metric.score(model)
    assert isinstance(result, dict)
    assert "availability" in result
    assert result["availability"] == 0.5


def test_bus_factor_metric():
    """Test bus factor metric."""
    metric = BusFactorMetric()
    model = Model(
        name="test_model",
        model_key="models/test_model/model",
        code_key="models/test_model/code",
        dataset_key="models/test_model/dataset"
    )
    
    result = metric.score(model)
    assert isinstance(result, dict)
    assert "bus_factor" in result
    assert result["bus_factor"] == 0.5