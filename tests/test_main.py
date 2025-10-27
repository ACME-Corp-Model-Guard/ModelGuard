"""
Tests for the main module.
"""

import tempfile
from pathlib import Path

from src.main import (
    _name_from_url,
    _record,
    _size_detail,
    _size_scalar,
    _unit,
    compute_all,
    iter_urls,
)


def test_name_from_url():
    """Test extracting name from URL."""
    assert _name_from_url("https://github.com/user/repo") == "repo"
    assert _name_from_url("https://github.com/user/repo/") == "repo"
    assert _name_from_url("") == "artifact"


def test_unit_function():
    """Test the _unit function returns values between 0 and 1."""
    url = "https://example.com"
    salt = "test_salt"
    result = _unit(url, salt)
    assert 0.0 <= result <= 1.0


def test_size_detail():
    """Test the _size_detail function returns expected keys."""
    url = "https://example.com"
    detail = _size_detail(url)
    expected_keys = {"raspberry_pi", "jetson_nano", "desktop_pc", "aws_server"}
    assert set(detail.keys()) == expected_keys
    assert all(0.0 <= v <= 1.0 for v in detail.values())


def test_size_scalar():
    """Test the _size_scalar function."""
    # Test normal case
    detail = {"a": 0.1, "b": 0.3, "c": 0.5}
    assert _size_scalar(detail) == 0.3  # Mean of values

    # Test empty dict
    assert _size_scalar({}) == 0.0

    # Test with values outside range
    detail = {"a": -0.5, "b": 1.5}
    scalar = _size_scalar(detail)
    assert 0.0 <= scalar <= 1.0  # Should be clamped


def test_record():
    """Test the _record function generates expected keys."""
    import unittest.mock as mock

    from src.metrics.net_score import NetScore

    url = "https://example.com"
    ns = NetScore(url)

    # Mock NetScore.combine to avoid the actual implementation
    with mock.patch.object(ns, "combine", return_value=0.5):
        record = _record(ns, url)

        expected_keys = {
            "url",
            "name",
            "category",
            "net_score",
            "net_score_latency",
            "ramp_up_time",
            "ramp_up_time_latency",
            "bus_factor",
            "bus_factor_latency",
            "performance_claims",
            "performance_claims_latency",
            "license",
            "license_latency",
            "size_score",
            "size_score_latency",
            "dataset_and_code_score",
            "dataset_and_code_score_latency",
            "dataset_quality",
            "dataset_quality_latency",
            "code_quality",
            "code_quality_latency",
        }
        assert set(record.keys()) == expected_keys
        assert record["url"] == url
        assert record["name"] == "example.com"
        assert record["category"] == "CODE"


def test_iter_urls():
    """Test the iter_urls function."""
    with tempfile.NamedTemporaryFile(mode="w+") as tmp:
        tmp.write("https://example.com/repo1\n")
        tmp.write("# Comment line\n")
        tmp.write("\n")  # Empty line
        tmp.write("https://example.com/repo2\n")
        tmp.flush()

        urls = list(iter_urls(Path(tmp.name)))
        assert urls == ["https://example.com/repo1", "https://example.com/repo2"]


def test_compute_all():
    """Test the compute_all function."""
    with tempfile.NamedTemporaryFile(mode="w+") as tmp:
        tmp.write("https://example.com/repo1\n")
        tmp.write("https://example.com/repo2\n")
        tmp.flush()

        # Mock _record to avoid actual implementation
        import unittest.mock as mock

        with mock.patch(
            "src.main._record",
            side_effect=lambda ns, url: {"url": url, "name": url.split("/")[-1]},
        ):
            results = compute_all(Path(tmp.name))
            assert len(results) == 2
            assert results[0]["url"] == "https://example.com/repo1"
            assert results[1]["url"] == "https://example.com/repo2"
