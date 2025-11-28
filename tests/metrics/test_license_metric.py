import pytest

from src.metrics.license_metric import LicenseMetric
from src.artifacts.model_artifact import ModelArtifact


@pytest.fixture
def metric():
    return LicenseMetric()


def make_model(license_str: str | None):
    """Helper to build a minimal ModelArtifact with override license."""
    return ModelArtifact(
        name="test-model",
        source_url="http://example.com/model",
        license=license_str,
        auto_score=False,  # prevent scoring during initialization
    )


# =============================================================================
# BASIC SCORING TESTS
# =============================================================================


def test_license_metric_permissive_mit(metric):
    model = make_model("MIT")
    result = metric.score(model)
    assert result == {"license": 1.0}


def test_license_metric_permissive_apache(metric):
    model = make_model("Apache License 2.0")
    result = metric.score(model)
    assert result == {"license": 1.0}


def test_license_metric_permissive_bsd(metric):
    model = make_model("BSD-3-Clause")
    result = metric.score(model)
    assert result == {"license": 1.0}


# =============================================================================
# AMBIGUOUS OR UNKNOWN LICENSES
# =============================================================================


def test_license_metric_unknown(metric):
    model = make_model("unknown")
    result = metric.score(model)
    assert result == {"license": 0.5}


def test_license_metric_empty_string(metric):
    model = make_model("")
    result = metric.score(model)
    assert result == {"license": 0.5}


def test_license_metric_none(metric):
    model = make_model(None)
    result = metric.score(model)
    assert result == {"license": 0.5}


def test_license_metric_unrecognized_string(metric):
    model = make_model("not-a-real-license")
    result = metric.score(model)
    assert result == {"license": 0.5}


def test_license_metric_unlicense(metric):
    model = make_model("Unlicense")
    result = metric.score(model)
    assert result == {"license": 0.5}


# =============================================================================
# RESTRICTIVE LICENSES
# =============================================================================


def test_license_metric_gpl3(metric):
    model = make_model("GPL-3.0")
    result = metric.score(model)
    assert result == {"license": 0.0}


def test_license_metric_agpl3(metric):
    model = make_model("AGPL-3.0")
    result = metric.score(model)
    assert result == {"license": 0.0}


def test_license_metric_proprietary(metric):
    model = make_model("Proprietary")
    result = metric.score(model)
    assert result == {"license": 0.0}


# =============================================================================
# NORMALIZATION CASES
# =============================================================================


def test_license_metric_normalizes_spaces(metric):
    model = make_model("Apache License Version 2.0")
    result = metric.score(model)
    assert result == {"license": 1.0}


def test_license_metric_normalizes_parentheses(metric):
    model = make_model("(MIT License)")
    result = metric.score(model)
    assert result == {"license": 1.0}


def test_license_metric_normalizes_bsd_variants(metric):
    model = make_model("bsd 2 clause license")
    result = metric.score(model)
    assert result == {"license": 1.0}


def test_license_metric_normalizes_case(metric):
    model = make_model("mIt")
    result = metric.score(model)
    assert result == {"license": 1.0}


# =============================================================================
# ERROR HANDLING
# =============================================================================


def test_license_metric_catches_exception(monkeypatch, metric):
    """Force the metric to throw inside score() so the fallback is triggered."""

    def bad_normalize(_):
        raise RuntimeError("boom!")

    monkeypatch.setattr(metric, "_normalize_license", bad_normalize)

    model = make_model("MIT")
    result = metric.score(model)

    # Should return default score 0.5
    assert result == {"license": 0.5}
