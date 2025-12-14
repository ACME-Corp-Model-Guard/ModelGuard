"""
Tests for the Performance Claims Metric (Lenient Detection).

The metric uses simple heuristics to detect ANY evidence of performance claims:
1. Section headers (## Evaluation, ## Results, etc.)
2. Paper references (arxiv, doi, BibTeX, etc.)
3. Performance keywords (at least 2 of: evaluation, results, benchmark, etc.)

If any evidence is found, score = 1.0, otherwise score = 0.0.
"""

import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.metrics.performance_claims_metric import (
    PerformanceClaimsMetric,
    _detect_performance_evidence,
    _get_text_content,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def metric():
    return PerformanceClaimsMetric()


@pytest.fixture
def model():
    return ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        size=100,
        license="MIT",
        artifact_id="test-123",
    )


# =============================================================================
# Detection Function Tests
# =============================================================================


class TestDetectPerformanceEvidence:
    """Tests for the _detect_performance_evidence function."""

    def test_empty_text_returns_no_evidence(self):
        """Empty text should return no evidence."""
        result = _detect_performance_evidence("")
        assert result["has_evidence"] is False
        assert result["evidence_types"] == []

    def test_detects_evaluation_section_header(self):
        """Should detect ## Evaluation section header."""
        text = "# Model\n\n## Evaluation\n\nThis model was evaluated on GLUE."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_section_header"] is True
        assert "section_header" in result["evidence_types"]

    def test_detects_results_section_header(self):
        """Should detect ## Results section header."""
        text = "# Model\n\n## Results\n\nHere are the results."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_section_header"] is True

    def test_detects_performance_section_header(self):
        """Should detect ## Performance section header."""
        text = "# Model\n\n## Performance\n\nPerformance details."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_section_header"] is True

    def test_detects_benchmarks_section_header(self):
        """Should detect ## Benchmarks section header."""
        text = "# Model\n\n## Benchmarks\n\nBenchmark results."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_section_header"] is True

    def test_detects_arxiv_link(self):
        """Should detect arxiv.org links."""
        text = "See our paper at https://arxiv.org/abs/1234.5678"
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_paper_reference"] is True
        assert "paper_reference" in result["evidence_types"]

    def test_detects_arxiv_id(self):
        """Should detect arxiv:1234.5678 format."""
        text = "Citation: arxiv:1910.01108"
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_paper_reference"] is True

    def test_detects_doi_link(self):
        """Should detect DOI links."""
        text = "DOI: doi:10.1234/example"
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_paper_reference"] is True

    def test_detects_bibtex_entry(self):
        """Should detect BibTeX entries."""
        text = "@article{smith2021,\n  title={A Great Model}\n}"
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_paper_reference"] is True

    def test_detects_see_paper_reference(self):
        """Should detect 'see the paper' style references."""
        text = "For more details, see the original paper."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_paper_reference"] is True

    def test_detects_openreview_link(self):
        """Should detect OpenReview links."""
        text = "Published at https://openreview.net/forum?id=abc123"
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_paper_reference"] is True

    def test_detects_two_keywords(self):
        """Should detect when 2+ performance keywords are present."""
        text = "The model achieves good accuracy on the benchmark."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_performance_keywords"] is True
        assert "keywords" in result["evidence_types"]

    def test_single_keyword_not_enough(self):
        """Single keyword should not be sufficient."""
        text = "This is a model with good accuracy."
        result = _detect_performance_evidence(text)
        # "accuracy" is only 1 keyword
        assert result["has_performance_keywords"] is False

    def test_multiple_keywords_detected(self):
        """Multiple keywords should trigger detection."""
        text = "Evaluation results show good performance on the benchmark."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is True
        assert result["has_performance_keywords"] is True

    def test_no_evidence_in_plain_text(self):
        """Plain text without performance info should return no evidence."""
        text = "This is a language model. It can generate text."
        result = _detect_performance_evidence(text)
        assert result["has_evidence"] is False


# =============================================================================
# Get Text Content Tests
# =============================================================================


class TestGetTextContent:
    """Tests for the _get_text_content function."""

    def test_empty_metadata_returns_empty_string(self):
        """Empty metadata should return empty string."""
        assert _get_text_content({}) == ""
        assert _get_text_content(None) == ""

    def test_extracts_model_card_content(self):
        """Should extract model_card_content field."""
        metadata = {"model_card_content": "This is the model card."}
        result = _get_text_content(metadata)
        assert "This is the model card." in result

    def test_extracts_readme(self):
        """Should extract readme field."""
        metadata = {"readme": "README content here."}
        result = _get_text_content(metadata)
        assert "README content here." in result

    def test_extracts_nested_metadata(self):
        """Should extract from nested metadata.metadata structure."""
        metadata = {"metadata": {"model_card_content": "Nested content."}}
        result = _get_text_content(metadata)
        assert "Nested content." in result

    def test_extracts_from_card_data(self):
        """Should extract from cardData structure."""
        metadata = {"cardData": {"model_card": "Card data content."}}
        result = _get_text_content(metadata)
        assert "Card data content." in result

    def test_combines_multiple_sources(self):
        """Should combine content from multiple sources."""
        metadata = {
            "readme": "README here.",
            "description": "Description here.",
        }
        result = _get_text_content(metadata)
        assert "README here." in result
        assert "Description here." in result


# =============================================================================
# Metric Scoring Tests
# =============================================================================


class TestPerformanceClaimsMetric:
    """Tests for the PerformanceClaimsMetric class."""

    def test_no_metadata_returns_zero(self, metric, model):
        """Model without metadata should score 0.0."""
        model.metadata = None
        result = metric.score(model)
        assert result == {"performance_claims": 0.0}

    def test_empty_metadata_returns_zero(self, metric, model):
        """Model with empty metadata should score 0.0."""
        model.metadata = {}
        result = metric.score(model)
        assert result == {"performance_claims": 0.0}

    def test_metadata_without_text_returns_zero(self, metric, model):
        """Model with metadata but no text content should score 0.0."""
        model.metadata = {"size": 100, "license": "MIT"}
        result = metric.score(model)
        assert result == {"performance_claims": 0.0}

    def test_section_header_scores_one(self, metric, model):
        """Model with evaluation section header should score 1.0."""
        model.metadata = {"model_card_content": "# Model\n\n## Evaluation Results\n\nGood results."}
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_paper_reference_scores_one(self, metric, model):
        """Model with paper reference should score 1.0."""
        model.metadata = {"model_card_content": "See https://arxiv.org/abs/1234.5678 for details."}
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_keywords_score_one(self, metric, model):
        """Model with performance keywords should score 1.0."""
        model.metadata = {
            "model_card_content": "The model achieves state-of-the-art results on benchmark."
        }
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_nested_metadata_detected(self, metric, model):
        """Should detect evidence in nested metadata structure."""
        model.metadata = {"metadata": {"model_card_content": "## Evaluation\n\nResults are good."}}
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_card_data_detected(self, metric, model):
        """Should detect evidence in cardData structure."""
        model.metadata = {
            "cardData": {"model_card": "Paper: arxiv:1234.5678\n\nGreat performance."}
        }
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_no_evidence_scores_zero(self, metric, model):
        """Model without any performance evidence should score 0.0."""
        model.metadata = {"model_card_content": "This is a model. It does things. Nothing special."}
        result = metric.score(model)
        assert result == {"performance_claims": 0.0}


# =============================================================================
# Integration Tests with Realistic Content
# =============================================================================


class TestRealWorldExamples:
    """Tests with realistic model card content."""

    def test_bert_style_readme(self, metric, model):
        """BERT-style README with evaluation results should pass."""
        model.metadata = {
            "model_card_content": """
# BERT Base

## Model description
BERT is a transformer model.

## Evaluation results
When fine-tuned on downstream tasks, this model achieves the following results:

| Task | MNLI | QQP | QNLI | SST-2 |
|------|------|-----|------|-------|
| Score | 84.6 | 71.2 | 90.5 | 93.5 |

## Citation
@article{devlin2018bert,
  title={BERT: Pre-training of Deep Bidirectional Transformers},
  author={Devlin, Jacob and others},
  journal={arXiv preprint arXiv:1810.04805},
  year={2018}
}
"""
        }
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_gpt2_style_readme(self, metric, model):
        """GPT-2 style README with benchmarks should pass."""
        model.metadata = {
            "model_card_content": """
# GPT-2

Language Models are Unsupervised Multitask Learners.

## Evaluation results

| Benchmark | Score |
|-----------|-------|
| LAMBADA (PPL) | 35.13 |
| WikiText2 (PPL) | 29.41 |

"""
        }
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_minimal_but_valid_readme(self, metric, model):
        """Minimal README with just paper reference should pass."""
        model.metadata = {
            "model_card_content": """
# My Model

A fine-tuned model for text classification.

For more details, see the paper at arxiv:2301.12345
"""
        }
        result = metric.score(model)
        assert result == {"performance_claims": 1.0}

    def test_model_with_only_description(self, metric, model):
        """Model with generic description but no performance info should score 0.5."""
        model.metadata = {
            "model_card_content": """
# My Model

This is a language model that can generate text.
It was created using transformers library.
You can use it for various NLP tasks.
"""
        }
        result = metric.score(model)
        assert result == {"performance_claims": 0.5}
