"""Tests for performance claims metric."""

import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.metrics.performance_claims_metric import (
    PerformanceClaimsMetric,
    _extract_performance_claims_from_metadata,
)


@pytest.fixture
def performance_claims_metric():
    return PerformanceClaimsMetric()


@pytest.fixture
def model():
    return ModelArtifact(
        artifact_id="test-model-123",
        name="test-model",
        source_url="https://huggingface.co/model",
        s3_key="models/test-model-123",
        metadata={},
    )


# =============================================================================
# _extract_performance_claims_from_metadata Tests
# =============================================================================
def test_extract_empty_metadata_returns_defaults():
    """Test that empty metadata returns default values."""
    result = _extract_performance_claims_from_metadata({})

    assert result["has_metrics"] is False
    assert result["metrics"] == []
    assert result["has_benchmarks"] is False
    assert result["has_papers"] is False
    assert result["metric_count"] == 0
    assert result["has_structured_metrics"] is False
    assert result["card_data"] == {}


def test_extract_none_metadata_returns_defaults():
    """Test that None metadata returns default values."""
    result = _extract_performance_claims_from_metadata(None)

    assert result["has_metrics"] is False
    assert result["metrics"] == []
    assert result["has_benchmarks"] is False
    assert result["has_papers"] is False
    assert result["metric_count"] == 0
    assert result["has_structured_metrics"] is False


def test_extract_structured_metrics_from_model_index():
    """Test extraction of structured metrics from HuggingFace model-index."""
    metadata = {
        "cardData": {
            "model-index": {
                "results": [
                    {
                        "task": {"type": "text-classification"},
                        "metrics": [
                            {"name": "accuracy", "value": 0.95},
                            {"name": "f1", "value": 0.93},
                        ],
                    }
                ]
            }
        }
    }

    result = _extract_performance_claims_from_metadata(metadata)

    assert result["has_metrics"] is True
    assert result["has_structured_metrics"] is True
    assert result["has_benchmarks"] is True
    assert "accuracy" in result["metrics"]
    assert "f1" in result["metrics"]
    assert result["metric_count"] == 2


def test_extract_metrics_from_nested_metadata():
    """Test extraction when cardData is nested in metadata."""
    metadata = {
        "metadata": {
            "cardData": {
                "model-index": {
                    "results": [
                        {
                            "metrics": [
                                {"name": "bleu", "value": 0.45},
                            ],
                        }
                    ]
                }
            }
        }
    }

    result = _extract_performance_claims_from_metadata(metadata)

    assert result["has_metrics"] is True
    assert "bleu" in result["metrics"]


def test_extract_performance_fields():
    """Test extraction from performance-related fields."""
    metadata = {
        "cardData": {
            "performance": {
                "accuracy": 0.95,
                "f1": 0.93,
            }
        }
    }

    result = _extract_performance_claims_from_metadata(metadata)

    assert result["has_benchmarks"] is True
    assert result["has_metrics"] is True
    assert "accuracy" in result["metrics"]
    assert "f1" in result["metrics"]


def test_extract_paper_from_arxiv_field():
    """Test extraction of papers from arxiv field."""
    metadata = {"cardData": {"arxiv": "2301.12345"}}

    result = _extract_performance_claims_from_metadata(metadata)

    assert result["has_papers"] is True


def test_extract_paper_from_citation_field():
    """Test extraction of papers from citation field."""
    metadata = {"cardData": {"citation": "Smith et al., 2023"}}

    result = _extract_performance_claims_from_metadata(metadata)

    assert result["has_papers"] is True


def test_extract_paper_from_arxiv_link_in_text():
    """Test extraction of papers from arxiv.org link in description."""
    metadata = {
        "cardData": {"description": "See our paper at https://arxiv.org/abs/2301.12345 for details"}
    }

    result = _extract_performance_claims_from_metadata(metadata)

    assert result["has_papers"] is True


def test_extract_paper_from_doi_link_in_text():
    """Test extraction of papers from doi.org link in text."""
    metadata = {"cardData": {"model_card": "Published at https://doi.org/10.1234/abcd"}}

    result = _extract_performance_claims_from_metadata(metadata)

    assert result["has_papers"] is True


def test_extract_ignores_metrics_without_values():
    """Test that metrics without values are not counted."""
    metadata = {
        "cardData": {
            "model-index": {
                "results": [
                    {
                        "metrics": [
                            {"name": "accuracy"},  # Missing value
                            {"value": 0.95},  # Missing name
                            {"name": "f1", "value": 0.93},  # Valid
                        ],
                    }
                ]
            }
        }
    }

    result = _extract_performance_claims_from_metadata(metadata)

    # Only f1 should be counted
    assert result["metric_count"] == 1
    assert "f1" in result["metrics"]
    assert "accuracy" not in result["metrics"]


def test_extract_deduplicates_metrics():
    """Test that duplicate metrics are deduplicated."""
    metadata = {
        "cardData": {
            "model-index": {
                "results": [
                    {
                        "metrics": [
                            {"name": "accuracy", "value": 0.95},
                            {
                                "name": "Accuracy",
                                "value": 0.96,
                            },  # Duplicate (lowercase)
                        ],
                    }
                ]
            }
        }
    }

    result = _extract_performance_claims_from_metadata(metadata)

    # Should only count once
    assert result["metric_count"] == 1
    assert "accuracy" in result["metrics"]


# =============================================================================
# PerformanceClaimsMetric.score() Tests
# =============================================================================
def test_score_no_metadata_returns_zero(performance_claims_metric):
    """Test that model without metadata returns 0.0 score."""
    model = ModelArtifact(
        artifact_id="test-model-123",
        name="test-model",
        source_url="https://huggingface.co/model",
        s3_key="models/test-model-123",
        metadata=None,
    )

    score = performance_claims_metric.score(model)

    assert isinstance(score, dict)
    assert "performance_claims" in score
    assert score["performance_claims"] == 0.0


def test_score_empty_metadata_returns_zero(performance_claims_metric, model):
    """Test that model with empty metadata returns 0.0 score."""
    model.metadata = {}

    score = performance_claims_metric.score(model)

    assert score["performance_claims"] == 0.0


def test_score_with_structured_metrics(performance_claims_metric, model):
    """Test scoring with structured metrics."""
    model.metadata = {
        "cardData": {
            "model-index": {
                "results": [
                    {
                        "metrics": [
                            {"name": "accuracy", "value": 0.95},
                        ],
                    }
                ]
            }
        }
    }

    score = performance_claims_metric.score(model)

    # Structured metrics give 0.5 base score + 0.25 for benchmarks = 0.75
    assert score["performance_claims"] == 0.75


def test_score_with_unstructured_metrics(performance_claims_metric, model):
    """Test scoring with unstructured metrics."""
    model.metadata = {
        "cardData": {
            "performance": {
                "accuracy": 0.95,
            }
        }
    }

    score = performance_claims_metric.score(model)

    # Unstructured metrics give 0.3 base score + 0.25 for benchmarks = 0.55
    assert score["performance_claims"] == 0.55


def test_score_with_papers(performance_claims_metric, model):
    """Test scoring with paper citations."""
    model.metadata = {"cardData": {"arxiv": "2301.12345"}}

    score = performance_claims_metric.score(model)

    # Papers only give 0.15 score
    assert score["performance_claims"] == 0.15


def test_score_with_all_factors(performance_claims_metric, model):
    """Test scoring with all factors combined."""
    model.metadata = {
        "cardData": {
            "model-index": {
                "results": [
                    {
                        "metrics": [
                            {"name": "accuracy", "value": 0.95},
                            {"name": "f1", "value": 0.93},
                            {"name": "precision", "value": 0.92},
                            {"name": "recall", "value": 0.94},
                            {"name": "auc", "value": 0.96},
                        ],
                    }
                ]
            },
            "arxiv": "2301.12345",
        }
    }

    score = performance_claims_metric.score(model)

    # Structured metrics: 0.5
    # 5 metrics bonus: 0.1
    # Benchmarks: 0.25
    # Papers: 0.15
    # Total: 1.0
    assert score["performance_claims"] == 1.0


def test_score_exception_handling(performance_claims_metric, model, monkeypatch):
    """Test that exceptions during calculation return 0.0 score."""

    def raise_error(*args, **kwargs):
        raise ValueError("Test error")

    monkeypatch.setattr(
        "src.metrics.performance_claims_metric._extract_performance_claims_from_metadata",
        raise_error,
    )

    model.metadata = {"some": "data"}

    score = performance_claims_metric.score(model)

    assert score["performance_claims"] == 0.0


# =============================================================================
# _calculate_performance_claims_score Tests
# =============================================================================
def test_calculate_score_no_factors(performance_claims_metric):
    """Test calculation with no performance factors."""
    claims_info = {
        "has_metrics": False,
        "has_benchmarks": False,
        "has_papers": False,
        "metric_count": 0,
        "has_structured_metrics": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    assert score == 0.0
    assert breakdown == {
        "metrics": 0.0,
        "metric_bonus": 0.0,
        "benchmarks": 0.0,
        "papers": 0.0,
        "documentation": 0.0,
        "lenient_evidence": 0.0,
    }


def test_calculate_score_structured_metrics_only(performance_claims_metric):
    """Test calculation with only structured metrics."""
    claims_info = {
        "has_metrics": True,
        "has_structured_metrics": True,
        "metric_count": 1,
        "has_benchmarks": False,
        "has_papers": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    assert score == 0.5
    assert breakdown["metrics"] == 0.5


def test_calculate_score_unstructured_metrics_only(performance_claims_metric):
    """Test calculation with only unstructured metrics."""
    claims_info = {
        "has_metrics": True,
        "has_structured_metrics": False,
        "metric_count": 1,
        "has_benchmarks": False,
        "has_papers": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    assert score == 0.3
    assert breakdown["metrics"] == 0.3


def test_calculate_score_two_metrics_bonus(performance_claims_metric):
    """Test bonus for 2 metrics."""
    claims_info = {
        "has_metrics": True,
        "has_structured_metrics": True,
        "metric_count": 2,
        "has_benchmarks": False,
        "has_papers": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    # 0.5 (structured) + 0.04 (2 metrics bonus)
    assert score == 0.54
    assert breakdown["metric_bonus"] == 0.04


def test_calculate_score_three_metrics_bonus(performance_claims_metric):
    """Test bonus for 3 metrics."""
    claims_info = {
        "has_metrics": True,
        "has_structured_metrics": True,
        "metric_count": 3,
        "has_benchmarks": False,
        "has_papers": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    # 0.5 (structured) + 0.07 (3 metrics bonus)
    assert score == pytest.approx(0.57)
    assert breakdown["metric_bonus"] == 0.07


def test_calculate_score_five_metrics_bonus(performance_claims_metric):
    """Test bonus for 5+ metrics."""
    claims_info = {
        "has_metrics": True,
        "has_structured_metrics": True,
        "metric_count": 5,
        "has_benchmarks": False,
        "has_papers": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    # 0.5 (structured) + 0.1 (5+ metrics bonus)
    assert score == 0.6
    assert breakdown["metric_bonus"] == 0.1


def test_calculate_score_benchmarks_only(performance_claims_metric):
    """Test calculation with only benchmarks."""
    claims_info = {
        "has_metrics": False,
        "has_benchmarks": True,
        "has_papers": False,
        "metric_count": 0,
        "has_structured_metrics": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    assert score == 0.25
    assert breakdown["benchmarks"] == 0.25


def test_calculate_score_papers_only(performance_claims_metric):
    """Test calculation with only papers."""
    claims_info = {
        "has_metrics": False,
        "has_benchmarks": False,
        "has_papers": True,
        "metric_count": 0,
        "has_structured_metrics": False,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    assert score == 0.15
    assert breakdown["papers"] == 0.15


def test_calculate_score_clamped_at_one(performance_claims_metric):
    """Test that score is clamped at 1.0."""
    claims_info = {
        "has_metrics": True,
        "has_structured_metrics": True,
        "metric_count": 10,  # Large number
        "has_benchmarks": True,
        "has_papers": True,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    # Should be clamped at 1.0
    assert score <= 1.0
    assert score == 1.0  # 0.5 + 0.1 + 0.25 + 0.15 = 1.0


def test_calculate_score_all_factors_combined(performance_claims_metric):
    """Test calculation with all factors."""
    claims_info = {
        "has_metrics": True,
        "has_structured_metrics": True,
        "metric_count": 5,
        "has_benchmarks": True,
        "has_papers": True,
    }

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    # 0.5 (structured) + 0.1 (5 metrics) + 0.25 (benchmarks) + 0.15 (papers) = 1.0
    assert score == 1.0
    assert breakdown == {
        "metrics": 0.5,
        "metric_bonus": 0.1,
        "benchmarks": 0.25,
        "papers": 0.15,
        "documentation": 0.0,  # No documentation bonus when metrics present
        "lenient_evidence": 0.0,
    }


def test_calculate_score_missing_keys_use_defaults(performance_claims_metric):
    """Test that missing keys use default False/0 values."""
    claims_info = {}  # Empty dict

    score, breakdown = performance_claims_metric._calculate_performance_claims_score(claims_info)

    # Should use defaults and return 0.0
    assert score == 0.0
    assert breakdown == {
        "metrics": 0.0,
        "metric_bonus": 0.0,
        "benchmarks": 0.0,
        "papers": 0.0,
        "documentation": 0.0,
        "lenient_evidence": 0.0,
    }


# =============================================================================
# Integration Tests
# =============================================================================
def test_full_integration_with_real_model_card(performance_claims_metric, model):
    """Test full integration with realistic model card data."""
    model.metadata = {
        "metadata": {
            "cardData": {
                "model-index": {
                    "results": [
                        {
                            "task": {"type": "text-classification"},
                            "dataset": {"name": "IMDB"},
                            "metrics": [
                                {"name": "Accuracy", "value": 0.93},
                                {"name": "F1", "value": 0.92},
                                {"name": "Precision", "value": 0.91},
                            ],
                        }
                    ]
                },
                "arxiv": "2301.12345",
                "description": "Model trained on IMDB dataset",
            }
        }
    }

    score = performance_claims_metric.score(model)

    # Should have high score with structured metrics, papers, and benchmarks
    assert score["performance_claims"] > 0.8
