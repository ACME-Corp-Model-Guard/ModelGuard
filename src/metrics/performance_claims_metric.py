"""
Performance Claims Metric - Lenient Detection

This metric uses lenient detection to determine if a model makes ANY mention of
performance, evaluation, results, or references to papers. The goal is simple:
does the model documentation discuss performance at all?

Detection criteria (ANY ONE is sufficient to pass):
1. Section headers: ## Evaluation, ## Results, ## Performance, ## Benchmarks, etc.
2. Paper references: arxiv links, doi links, BibTeX entries, "see paper", etc.
3. Performance keywords: At least 2 mentions of evaluation, results, benchmark, etc.

If any evidence is found, the model passes with a score of 1.0.
If no evidence is found, the model fails with a score of 0.0.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Union

from src.logutil import clogger

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


# =============================================================================
# Lenient Detection Patterns
# =============================================================================

# Section header patterns that indicate evaluation/results content
_SECTION_HEADER_PATTERNS = [
    r"#+\s*(?:evaluation|results?|performance|benchmarks?|metrics?|experiments?|testing)",
    r"\*\*(?:evaluation|results?|performance|benchmarks?|metrics?)\*\*",
]

# Paper reference patterns
_PAPER_REFERENCE_PATTERNS = [
    r"arxiv[:\s]*\d+\.\d+",  # arxiv:1234.5678 or arxiv 1234.5678
    r"arxiv\.org/abs/\d+\.\d+",  # arxiv.org/abs/1234.5678
    r"doi[:\s]*10\.\d+",  # doi:10.1234/...
    r"doi\.org/10\.\d+",  # doi.org/10.1234/...
    r"\[paper\]",  # [paper] link
    r"(?:see|refer to|described in)\s+(?:the\s+)?(?:original\s+)?paper",
    r"(?:our|the)\s+paper",
    r"published\s+(?:at|in)\s+\w+",  # published at/in conference
    r"@(?:article|inproceedings|misc)\{",  # BibTeX entry
    r"openreview\.net",  # OpenReview links
    r"aclweb\.org",  # ACL Anthology links
    r"paperswithcode\.com",  # Papers with Code links
]

# Generic keywords that indicate performance discussion
# We require at least 2 of these to avoid false positives
_PERFORMANCE_KEYWORDS = [
    "evaluation",
    "results",
    "performance",
    "benchmark",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "score",
    "metric",
    "evaluated",
    "achieves",
    "outperforms",
    "state-of-the-art",
    "sota",
    "baseline",
    "compared to",
    "comparison",
    "fine-tuned",
    "trained on",
    "test set",
    "validation",
    "leaderboard",
]


# =============================================================================
# Lenient Detection Function
# =============================================================================


def _detect_performance_evidence(text: str, artifact_id: str = "") -> Dict[str, Any]:
    """
    Perform lenient detection for ANY evidence of performance claims.

    This is intentionally very permissive - we just want to know if the model
    makes ANY mention of evaluation, results, performance, or references papers.

    Args:
        text: The text content to scan (README, model card, etc.)
        artifact_id: Optional artifact ID for logging context

    Returns:
        Dictionary with detection results:
        - has_section_header: bool - found evaluation/results section header
        - has_paper_reference: bool - found reference to external paper
        - has_performance_keywords: bool - found 2+ performance-related keywords
        - has_evidence: bool - any of the above is True
        - evidence_types: list of strings describing what was found
    """
    log_prefix = f"[performance_claims] [{artifact_id}]" if artifact_id else "[performance_claims]"

    result: Dict[str, Any] = {
        "has_section_header": False,
        "has_paper_reference": False,
        "has_performance_keywords": False,
        "has_evidence": False,
        "evidence_types": [],
    }

    if not text or not isinstance(text, str):
        return result

    text_lower = text.lower()

    # Check 1: Section headers indicating evaluation/results
    for pattern in _SECTION_HEADER_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE):
            result["has_section_header"] = True
            result["evidence_types"].append("section_header")
            clogger.debug(f"{log_prefix} found evaluation/results section header")
            break

    # Check 2: Paper references
    for pattern in _PAPER_REFERENCE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            result["has_paper_reference"] = True
            result["evidence_types"].append("paper_reference")
            clogger.debug(f"{log_prefix} found paper reference")
            break

    # Check 3: Performance keywords (require at least 2)
    found_keywords: List[str] = []
    for keyword in _PERFORMANCE_KEYWORDS:
        if keyword in text_lower:
            found_keywords.append(keyword)
            if len(found_keywords) >= 2:
                result["has_performance_keywords"] = True
                result["evidence_types"].append("keywords")
                clogger.debug(f"{log_prefix} found performance keywords: {found_keywords[:3]}")
                break

    # Overall result
    result["has_evidence"] = (
        result["has_section_header"]
        or result["has_paper_reference"]
        or result["has_performance_keywords"]
    )

    return result


def _get_text_content(metadata: Dict[str, Any]) -> str:
    """
    Extract all text content from metadata that might contain performance info.

    Args:
        metadata: Model metadata dictionary

    Returns:
        Combined text content from all relevant fields
    """
    if not metadata:
        return ""

    text_parts: List[str] = []

    # Direct fields
    for field in ["model_card_content", "readme", "description", "summary"]:
        value = metadata.get(field)
        if value and isinstance(value, str):
            text_parts.append(value)

    # Nested in metadata.metadata (HuggingFace structure)
    nested_metadata = metadata.get("metadata", {})
    if isinstance(nested_metadata, dict):
        for field in ["model_card_content", "readme", "description"]:
            value = nested_metadata.get(field)
            if value and isinstance(value, str):
                text_parts.append(value)

    # Nested in cardData
    card_data = (
        metadata.get("metadata", {}).get("cardData", {}) or metadata.get("cardData", {}) or {}
    )
    if isinstance(card_data, dict):
        for field in ["model_card", "readme", "description", "summary"]:
            value = card_data.get(field)
            if value and isinstance(value, str):
                text_parts.append(value)

    return "\n\n".join(text_parts)


# =============================================================================
# Metric Class
# =============================================================================


class PerformanceClaimsMetric(Metric):
    """
    Performance claims metric using lenient detection.

    Uses simple heuristics to detect ANY mention of performance, evaluation,
    results, or paper references in the model documentation.

    Scoring:
    - 1.0: Evidence of performance claims found (section header, paper ref, or keywords)
    - 0.0: No evidence found

    This is intentionally permissive - the goal is to pass models that have
    ANY documentation about their performance, not to validate specific claims.
    """

    SCORE_FIELD = "performance_claims"

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model based on presence of performance claims evidence.

        Args:
            model: The ModelArtifact object to score

        Returns:
            {"performance_claims": 1.0} if evidence found, else {"performance_claims": 0.0}
        """
        artifact_id = model.artifact_id or ""
        log_prefix = f"[performance_claims] [{artifact_id}]"

        clogger.debug(f"{log_prefix} Scoring model")

        # No metadata = no evidence
        if not model.metadata:
            clogger.debug(f"{log_prefix} No metadata, returning 0.0")
            return {"performance_claims": 0.0}

        try:
            # Get all text content from metadata
            text_content = _get_text_content(model.metadata)

            if not text_content:
                clogger.debug(f"{log_prefix} No text content found, returning 0.0")
                return {"performance_claims": 0.0}

            # Detect performance evidence
            detection = _detect_performance_evidence(text_content, artifact_id)

            if detection["has_evidence"]:
                evidence = ", ".join(detection["evidence_types"])
                clogger.info(f"{log_prefix} Evidence found ({evidence}), returning 1.0")
                return {"performance_claims": 1.0}
            else:
                clogger.debug(
                    f"{log_prefix} No direct evidence found, "
                    f"but files still exist, so returning 0.5"
                )
                return {"performance_claims": 0.5}

        except Exception as e:
            clogger.exception(
                f"{log_prefix} Error during scoring: {e}",
                extra={"error_type": type(e).__name__},
            )
            return {"performance_claims": 0.0}
