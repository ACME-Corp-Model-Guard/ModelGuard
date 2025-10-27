"""
Tests for metrics modules.
"""

import tempfile
from pathlib import Path
from typing import Optional

from src.metrics.availability_metric import AvailabilityMetric
from src.metrics.bus_factor_metric import BusFactorMetric
from src.metrics.dataset_quality_metric import DatasetQualityMetric
from src.metrics.license_metric import LicenseMetric
from src.metrics.performance_claims_metric import PerformanceClaimsMetric
from src.metrics.ramp_up_metric import RampUpMetric
from src.metrics.size_metric import SizeMetric


# Base class for testing metrics
class MetricTester:
    def _as_path(self, path_or_url: str) -> Optional[Path]:
        return Path(path_or_url)

    def _glob(self, base, patterns):
        return []

    def _clamp01(self, x: float) -> float:
        return max(0.0, min(1.0, x))


# Test for AvailabilityMetric
class TestAvailabilityMetric(AvailabilityMetric, MetricTester):
    pass


def test_availability_metric_url():
    """Test availability metric with URL."""
    metric = TestAvailabilityMetric()
    result = metric.score("https://example.com")
    assert "availability" in result
    assert isinstance(result["availability"], float)
    assert 0.0 <= result["availability"] <= 1.0


def test_availability_metric_path():
    """Test availability metric with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric = TestAvailabilityMetric()
        result = metric.score(tmpdir)
        assert "availability" in result


def test_availability_metric_no_files(tmp_path):
    from src.metrics.availability_metric import AvailabilityMetric

    metric = AvailabilityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["availability"] <= 1.0


def test_availability_metric_unreadable_file(tmp_path):
    from src.metrics.availability_metric import AvailabilityMetric

    file_path = tmp_path / "file.txt"
    file_path.write_text("data")
    file_path.chmod(0)
    metric = AvailabilityMetric()
    try:
        result = metric.score(str(tmp_path))
        assert 0.0 <= result["availability"] <= 1.0
    finally:
        file_path.chmod(0o600)


def test_availability_metric_readable_file(tmp_path):
    from src.metrics.availability_metric import AvailabilityMetric

    file_path = tmp_path / "file.txt"
    file_path.write_text("data")
    metric = AvailabilityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["availability"] <= 1.0


# Test for BusFactorMetric
class TestBusFactorMetric(BusFactorMetric, MetricTester):
    pass


def test_bus_factor_metric_url():
    """Test bus factor metric with URL."""
    metric = TestBusFactorMetric()
    result = metric.score("https://example.com")
    assert "bus_factor" in result
    assert isinstance(result["bus_factor"], float)
    assert 0.0 <= result["bus_factor"] <= 1.0


def test_bus_factor_metric_path():
    """Test bus factor metric with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric = TestBusFactorMetric()
        result = metric.score(tmpdir)
        assert "bus_factor" in result


def test_bus_factor_metric_no_files(tmp_path):
    from src.metrics.bus_factor_metric import BusFactorMetric

    metric = BusFactorMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["bus_factor"] <= 1.0


def test_bus_factor_metric_with_file(tmp_path):
    from src.metrics.bus_factor_metric import BusFactorMetric

    file_path = tmp_path / "file.txt"
    file_path.write_text("data")
    metric = BusFactorMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["bus_factor"] <= 1.0


# Test for DatasetQualityMetric
class TestDatasetQualityMetric(DatasetQualityMetric, MetricTester):
    pass


def test_dataset_quality_metric_url():
    """Test dataset quality metric with URL."""
    metric = TestDatasetQualityMetric()
    result = metric.score("https://example.com")
    assert "dataset_quality" in result
    assert isinstance(result["dataset_quality"], float)
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_metric_path():
    """Test dataset quality metric with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric = TestDatasetQualityMetric()
        result = metric.score(tmpdir)
        assert "dataset_quality" in result


def test_dataset_quality_no_files(tmp_path):

    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    metric = DatasetQualityMetric()
    result = metric.score(str(tmp_path))
    assert result["dataset_quality"] == 0.5


def test_dataset_quality_valid_csv(tmp_path):
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("col1,col2\n1,2\n3,4\n")
    metric = DatasetQualityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_inconsistent_csv(tmp_path):
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("col1,col2\n1,2\n3\n4,5,6\n")
    metric = DatasetQualityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_blank_rows_csv(tmp_path):
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("col1,col2\n\n\n1,2\n,\n\n3,4\n")
    metric = DatasetQualityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_header_row_csv(tmp_path):
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b,c\n1,2,3\n4,5,6\n")
    metric = DatasetQualityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_valid_jsonl(tmp_path):
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    jsonl_path = tmp_path / "data.jsonl"
    jsonl_path.write_text('{"a":1}\n{"a":2}\n')
    metric = DatasetQualityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_malformed_jsonl(tmp_path):
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    jsonl_path = tmp_path / "data.jsonl"
    jsonl_path.write_text('{"a":1}\nnotjson\n')
    metric = DatasetQualityMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_nonexistent_path():
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    metric = DatasetQualityMetric()
    result = metric.score("/nonexistent/path/for/dataset_quality")
    assert 0.0 <= result["dataset_quality"] <= 1.0


def test_dataset_quality_url():
    from src.metrics.dataset_quality_metric import DatasetQualityMetric

    metric = DatasetQualityMetric()
    result = metric.score("https://example.com")
    assert 0.0 <= result["dataset_quality"] <= 1.0


# Test for LicenseMetric
class TestLicenseMetric(LicenseMetric, MetricTester):
    pass


def test_license_metric_url():
    """Test license metric with URL."""
    metric = TestLicenseMetric()
    result = metric.score("https://example.com")
    assert "license" in result
    assert isinstance(result["license"], float)
    assert 0.0 <= result["license"] <= 1.0


def test_license_metric_path():
    """Test license metric with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric = TestLicenseMetric()
        result = metric.score(tmpdir)
        assert "license" in result


def test_license_metric_no_license(tmp_path):
    from src.metrics.license_metric import LicenseMetric

    metric = LicenseMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["license"] <= 1.0


def test_license_metric_with_license(tmp_path):
    from src.metrics.license_metric import LicenseMetric

    license_path = tmp_path / "LICENSE"
    license_path.write_text("MIT License")
    metric = LicenseMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["license"] <= 1.0


# Test for PerformanceClaimsMetric
class TestPerformanceClaimsMetric(PerformanceClaimsMetric, MetricTester):
    pass


def test_performance_claims_metric_url():
    """Test performance claims metric with URL."""
    metric = TestPerformanceClaimsMetric()
    result = metric.score("https://example.com")
    assert "performance_claims" in result
    assert isinstance(result["performance_claims"], float)
    assert 0.0 <= result["performance_claims"] <= 1.0


def test_performance_claims_metric_path():
    """Test performance claims metric with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric = TestPerformanceClaimsMetric()
        result = metric.score(tmpdir)
        assert "performance_claims" in result


# Test for RampUpMetric
class TestRampUpMetric(RampUpMetric, MetricTester):
    pass


def test_ramp_up_metric_url():
    """Test ramp up metric with URL."""
    metric = TestRampUpMetric()
    result = metric.score("https://example.com")
    assert "ramp_up" in result
    assert isinstance(result["ramp_up"], float)
    assert 0.0 <= result["ramp_up"] <= 1.0


def test_ramp_up_metric_path():
    """Test ramp up metric with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric = TestRampUpMetric()
        result = metric.score(tmpdir)
        assert "ramp_up" in result


def test_ramp_up_metric_no_readme(tmp_path):
    from src.metrics.ramp_up_metric import RampUpMetric

    metric = RampUpMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["ramp_up"] <= 1.0


def test_ramp_up_metric_with_readme(tmp_path):
    from src.metrics.ramp_up_metric import RampUpMetric

    readme_path = tmp_path / "README.md"
    readme_path.write_text("This is a README file.")
    metric = RampUpMetric()
    result = metric.score(str(tmp_path))
    assert 0.0 <= result["ramp_up"] <= 1.0


# Test for SizeMetric
class TestSizeMetric(SizeMetric, MetricTester):
    pass


def test_size_metric_url():
    """Test size metric with URL."""
    metric = TestSizeMetric()
    result = metric.score("https://example.com")
    assert "files" in result
    assert "lines" in result
    assert "commits" in result
    assert isinstance(result["files"], float)
    assert 0.0 <= result["files"] <= 1.0


def test_size_metric_path():
    """Test size metric with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric = TestSizeMetric()
        result = metric.score(tmpdir)
        assert "files" in result
        assert "lines" in result
        assert "commits" in result
