"""Tests for metrics registry."""

from src.metrics.registry import (
    METRICS,
    LINEAGE_METRICS,
    CODE_METRICS,
    DATASET_METRICS,
)
from src.metrics.availability_metric import AvailabilityMetric
from src.metrics.bus_factor_metric import BusFactorMetric
from src.metrics.code_quality_metric import CodeQualityMetric
from src.metrics.dataset_quality_metric import DatasetQualityMetric
from src.metrics.license_metric import LicenseMetric
from src.metrics.performance_claims_metric import PerformanceClaimsMetric
from src.metrics.ramp_up_metric import RampUpMetric
from src.metrics.size_metric import SizeMetric
from src.metrics.treescore_metric import TreescoreMetric
from src.metrics.metric import Metric


def test_metrics_list_contains_all_metrics():
    """Test that METRICS list contains all expected metric types."""
    assert len(METRICS) == 9

    metric_types = {type(metric) for metric in METRICS}

    expected_types = {
        AvailabilityMetric,
        BusFactorMetric,
        CodeQualityMetric,
        DatasetQualityMetric,
        LicenseMetric,
        PerformanceClaimsMetric,
        RampUpMetric,
        SizeMetric,
        TreescoreMetric,
    }

    assert metric_types == expected_types


def test_all_metrics_are_metric_instances():
    """Test that all items in METRICS list are Metric instances."""
    for metric in METRICS:
        assert isinstance(metric, Metric)


def test_lineage_metrics_list():
    """Test LINEAGE_METRICS contains only treescore metric."""
    assert len(LINEAGE_METRICS) == 1
    assert isinstance(LINEAGE_METRICS[0], TreescoreMetric)


def test_code_metrics_list():
    """Test CODE_METRICS contains code quality and availability metrics."""
    assert len(CODE_METRICS) == 2

    metric_types = {type(metric) for metric in CODE_METRICS}
    expected_types = {CodeQualityMetric, AvailabilityMetric}

    assert metric_types == expected_types


def test_dataset_metrics_list():
    """Test DATASET_METRICS contains dataset quality and availability metrics."""
    assert len(DATASET_METRICS) == 2

    metric_types = {type(metric) for metric in DATASET_METRICS}
    expected_types = {DatasetQualityMetric, AvailabilityMetric}

    assert metric_types == expected_types


def test_categorized_metrics_are_subsets_of_all_metrics():
    """Test that categorized metrics are all included in main METRICS list."""
    all_metric_types = {type(metric) for metric in METRICS}

    for metric in LINEAGE_METRICS:
        assert type(metric) in all_metric_types

    for metric in CODE_METRICS:
        assert type(metric) in all_metric_types

    for metric in DATASET_METRICS:
        assert type(metric) in all_metric_types
