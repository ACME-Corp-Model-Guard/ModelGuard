from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from src.logutil import clogger

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


# =============================================================================
# Configuration Constants
# =============================================================================

# Recognized metric names (expanded from 8 to ~25)
_KNOWN_METRICS = {
    # Classification
    "accuracy",
    "precision",
    "recall",
    "f1",
    "f1_score",
    "auc",
    "roc_auc",
    "top_k_accuracy",
    "top1_accuracy",
    "top5_accuracy",
    # NLP
    "bleu",
    "rouge",
    "rouge1",
    "rouge2",
    "rougel",
    "meteor",
    "wer",
    "cer",
    "perplexity",
    "ppl",
    # Object Detection / Segmentation
    "map",
    "map50",
    "map75",
    "iou",
    "miou",
    "dice",
    # Regression
    "mse",
    "rmse",
    "mae",
    "r2",
    "r2_score",
    # General
    "loss",
    "score",
    "em",
    "exact_match",
    "spearmanr",
    "pearsonr",
}

# Field names to check for performance data (expanded)
_PERFORMANCE_FIELDS = [
    "performance",
    "evaluation",
    "eval",
    "eval_results",
    "metrics",
    "results",
    "benchmarks",
    "scores",
    "model-index",
]

# Paper citation fields
_PAPER_FIELDS = ["paperswithcode", "arxiv", "citation", "bibtex", "paper", "doi"]
_TEXT_FIELDS = ["model_card", "readme", "description", "summary"]
_CITATION_PATTERNS = ["arxiv.org", "doi.org", "paperswithcode.com"]

# Regex patterns for extracting metrics from text
# These match common patterns like "accuracy: 92%", "F1 score of 0.85", "BLEU: 32.5"
_TEXT_METRIC_PATTERNS = [
    # Pattern: "metric_name: value%" or "metric_name: value"
    r"\b(accuracy|precision|recall|f1|bleu|rouge|wer|cer|perplexity|em|map|iou)"
    r"\s*[=:]\s*(\d+\.?\d*)\s*%?",
    # Pattern: "metric_name score of value"
    r"\b(accuracy|precision|recall|f1|bleu|rouge)\s+(?:score\s+)?(?:of\s+)?(\d+\.?\d*)\s*%?",
    # Pattern: "achieved/reaches X% accuracy"
    r"(?:achieved?|reaches?|obtains?)\s+(\d+\.?\d*)\s*%?\s*(accuracy|precision|recall|f1)",
    # Pattern: "top-1 accuracy: X%"
    r"top[- ]?[15]\s+accuracy\s*[=:]\s*(\d+\.?\d*)\s*%?",
]

# Scoring weights
_WEIGHTS = {
    "structured_metrics": 0.5,
    "unstructured_metrics": 0.3,
    "text_metrics": 0.25,  # Metrics found in text/README
    "benchmarks": 0.25,
    "papers": 0.15,
    "has_documentation": 0.2,  # Base credit for having any documentation
}

_METRIC_COUNT_BONUS = {5: 0.1, 3: 0.07, 2: 0.04}


# =============================================================================
# Helper Functions
# =============================================================================


def _get_card_data(metadata: Dict[str, Any], artifact_id: str = "") -> Dict[str, Any]:
    """
    Extract cardData from metadata, handling nested structures.

    Args:
        metadata: Model metadata dictionary
        artifact_id: Optional artifact ID for logging context

    Returns:
        cardData dictionary, or empty dict if not found
    """
    log_prefix = f"[performance_claims] [{artifact_id}]" if artifact_id else "[performance_claims]"

    if not metadata:
        clogger.debug(f"{log_prefix} metadata is empty or None")
        return {}

    clogger.debug(f"{log_prefix} metadata keys: {list(metadata.keys())}")

    # Get cardData from various possible locations
    card_data = (
        metadata.get("metadata", {}).get("cardData", {}) or metadata.get("cardData", {}) or {}
    )

    if not card_data:
        clogger.debug(f"{log_prefix} cardData is empty or missing")
    elif isinstance(card_data, dict):
        clogger.debug(f"{log_prefix} cardData keys: {list(card_data.keys())}")

    return card_data


def _extract_model_index_metrics(
    card_data: Dict[str, Any], artifact_id: str = ""
) -> Tuple[List[str], bool, bool]:
    """
    Extract metrics from HuggingFace model-index structure.

    Args:
        card_data: The cardData dictionary
        artifact_id: Optional artifact ID for logging context

    Returns:
        Tuple of (metrics_list, has_structured_metrics, has_benchmarks)
    """
    log_prefix = f"[performance_claims] [{artifact_id}]" if artifact_id else "[performance_claims]"
    metrics_list: List[str] = []
    has_structured = False
    has_benchmarks = False

    if not isinstance(card_data, dict):
        return metrics_list, has_structured, has_benchmarks

    model_index = card_data.get("model-index", {})
    if not model_index or not isinstance(model_index, dict):
        clogger.debug(f"{log_prefix} no model-index structure found")
        return metrics_list, has_structured, has_benchmarks

    results = model_index.get("results", [])
    if not results or not isinstance(results, list):
        clogger.debug(f"{log_prefix} model-index exists but has no results")
        return metrics_list, has_structured, has_benchmarks

    clogger.debug(f"{log_prefix} model-index found with {len(results)} result(s)")
    has_benchmarks = True
    has_structured = True

    for result_item in results:
        if not isinstance(result_item, dict):
            continue

        # Check for task type (indicates proper benchmark structure)
        if result_item.get("task"):
            has_benchmarks = True

        # Extract metrics from results
        metrics = result_item.get("metrics", [])
        if metrics and isinstance(metrics, list):
            for metric in metrics:
                if isinstance(metric, dict):
                    metric_name = metric.get("name", "")
                    metric_value = metric.get("value")
                    # Only count if it has both name and value
                    if metric_name and metric_value is not None:
                        metrics_list.append(metric_name.lower())

    return metrics_list, has_structured, has_benchmarks


def _extract_performance_field_metrics(
    card_data: Dict[str, Any], artifact_id: str = ""
) -> Tuple[List[str], bool]:
    """
    Extract metrics from performance-related fields in cardData.

    Args:
        card_data: The cardData dictionary
        artifact_id: Optional artifact ID for logging context

    Returns:
        Tuple of (metrics_list, has_benchmarks)
    """
    log_prefix = f"[performance_claims] [{artifact_id}]" if artifact_id else "[performance_claims]"
    metrics_list: List[str] = []
    has_benchmarks = False

    if not isinstance(card_data, dict):
        return metrics_list, has_benchmarks

    found_perf_fields: List[str] = []
    for field in _PERFORMANCE_FIELDS:
        if field not in card_data:
            continue

        field_value = card_data[field]
        if not isinstance(field_value, (dict, list)) or not field_value:
            continue

        found_perf_fields.append(field)
        has_benchmarks = True

        # Try to extract metrics from dict fields
        if isinstance(field_value, dict):
            for key, value in field_value.items():
                if isinstance(value, (int, float)) and key.lower() in _KNOWN_METRICS:
                    metrics_list.append(key.lower())

    if found_perf_fields:
        clogger.debug(f"{log_prefix} found performance fields: {found_perf_fields}")
    else:
        clogger.debug(f"{log_prefix} no performance fields found (checked: {_PERFORMANCE_FIELDS})")

    return metrics_list, has_benchmarks


def _extract_paper_citations(
    card_data: Dict[str, Any], artifact_id: str = ""
) -> Tuple[bool, Optional[str]]:
    """
    Check for paper citations in cardData.

    Args:
        card_data: The cardData dictionary
        artifact_id: Optional artifact ID for logging context

    Returns:
        Tuple of (has_papers, source_field) where source_field indicates where citation was found
    """
    log_prefix = f"[performance_claims] [{artifact_id}]" if artifact_id else "[performance_claims]"

    if not isinstance(card_data, dict):
        return False, None

    # Check for paper-related fields
    for field in _PAPER_FIELDS:
        if field not in card_data:
            continue

        field_value = card_data[field]
        if field_value and (
            isinstance(field_value, str)
            or (isinstance(field_value, list) and len(field_value) > 0)
            or (isinstance(field_value, dict) and len(field_value) > 0)
        ):
            clogger.debug(f"{log_prefix} found paper citation in field: {field}")
            return True, field

    # Check for citations in text fields
    for field in _TEXT_FIELDS:
        if field not in card_data:
            continue

        field_value = str(card_data[field]).lower()
        for pattern in _CITATION_PATTERNS:
            if pattern in field_value:
                clogger.debug(
                    f"{log_prefix} found paper citation ({pattern}) in text field: {field}"
                )
                return True, field

    clogger.debug(
        f"{log_prefix} no paper citations found "
        f"(checked fields: {_PAPER_FIELDS}, text: {_TEXT_FIELDS})"
    )
    return False, None


def _get_metric_count_bonus(count: int) -> float:
    """
    Get bonus score for number of metrics reported.

    Args:
        count: Number of distinct metrics

    Returns:
        Bonus score (0.0 to 0.1)
    """
    for threshold in sorted(_METRIC_COUNT_BONUS.keys(), reverse=True):
        if count >= threshold:
            return _METRIC_COUNT_BONUS[threshold]
    return 0.0


def _extract_metrics_from_text(text: str, artifact_id: str = "") -> Tuple[List[str], bool]:
    """
    Extract performance metrics from free-form text (README, description, etc.).

    Uses regex patterns to find common metric reporting patterns like:
    - "accuracy: 92%"
    - "F1 score of 0.85"
    - "achieves 95% accuracy"

    Args:
        text: The text content to scan
        artifact_id: Optional artifact ID for logging context

    Returns:
        Tuple of (metrics_found, has_documentation) where:
        - metrics_found: list of metric names found
        - has_documentation: whether any substantial text was present
    """
    log_prefix = f"[performance_claims] [{artifact_id}]" if artifact_id else "[performance_claims]"
    metrics_found: List[str] = []
    has_documentation = False

    if not text or not isinstance(text, str):
        return metrics_found, has_documentation

    # Consider it documentation if text is reasonably long
    if len(text.strip()) > 100:
        has_documentation = True
        clogger.debug(f"{log_prefix} found documentation text ({len(text)} chars)")

    text_lower = text.lower()

    for pattern in _TEXT_METRIC_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            # Extract metric name from match groups
            if isinstance(match, tuple):
                for group in match:
                    if group and group.lower() in _KNOWN_METRICS:
                        metrics_found.append(group.lower())

    # Deduplicate
    metrics_found = list(set(metrics_found))

    if metrics_found:
        clogger.debug(f"{log_prefix} found metrics in text: {metrics_found}")

    return metrics_found, has_documentation


# =============================================================================
# Main Extraction Function
# =============================================================================


def _extract_performance_claims_from_metadata(
    metadata: Dict[str, Any],
    artifact_id: str = "",
) -> Dict[str, Any]:
    """
    Extract performance claims and metrics from model metadata.

    Orchestrates helper functions to check various fields where performance
    information might be stored, including HuggingFace model card data and
    free-form text in README/model_card fields.

    Args:
        metadata: Model metadata dictionary (from artifact.metadata)
        artifact_id: Optional artifact ID for logging context

    Returns:
        Dictionary with performance claims information:
        - has_metrics: bool - whether any performance metrics were found
        - metrics: list - list of found metric names
        - has_benchmarks: bool - whether benchmark results were found
        - has_papers: bool - whether papers are cited
        - metric_count: int - number of distinct metrics found
        - has_structured_metrics: bool - whether metrics are in structured format
        - has_text_metrics: bool - whether metrics were found in free-form text
        - has_documentation: bool - whether model has documentation
        - card_data: dict - raw cardData if available
    """
    log_prefix = f"[performance_claims] [{artifact_id}]" if artifact_id else "[performance_claims]"

    # Initialize result with defaults
    result: Dict[str, Any] = {
        "has_metrics": False,
        "metrics": [],
        "has_benchmarks": False,
        "has_papers": False,
        "metric_count": 0,
        "has_structured_metrics": False,
        "has_text_metrics": False,
        "has_documentation": False,
        "card_data": {},
    }

    if not metadata:
        return result

    # Step 1: Get cardData from metadata
    card_data = _get_card_data(metadata, artifact_id)
    result["card_data"] = card_data

    # Step 2: Extract metrics from model-index (primary source)
    model_index_metrics, has_structured, has_benchmarks = _extract_model_index_metrics(
        card_data, artifact_id
    )

    # Step 3: Extract metrics from performance fields (secondary source)
    perf_field_metrics, perf_has_benchmarks = _extract_performance_field_metrics(
        card_data, artifact_id
    )

    # Step 4: Check for paper citations
    has_papers, _ = _extract_paper_citations(card_data, artifact_id)

    # Step 5: Extract metrics from text fields (README, model_card, description)
    text_metrics: List[str] = []
    has_documentation = False

    # Check various text fields in metadata
    text_sources = [
        metadata.get("model_card_content"),
        metadata.get("readme"),
        metadata.get("description"),
        card_data.get("model_card"),
        card_data.get("readme"),
        card_data.get("description"),
        card_data.get("summary"),
    ]

    for text_source in text_sources:
        if text_source and isinstance(text_source, str):
            found_metrics, found_docs = _extract_metrics_from_text(text_source, artifact_id)
            text_metrics.extend(found_metrics)
            if found_docs:
                has_documentation = True

    text_metrics = list(set(text_metrics))
    has_text_metrics = len(text_metrics) > 0

    # Combine all metrics
    all_metrics = model_index_metrics + perf_field_metrics + text_metrics
    unique_metrics = list(set(all_metrics))

    result["metrics"] = unique_metrics
    result["metric_count"] = len(unique_metrics)
    result["has_metrics"] = len(unique_metrics) > 0
    result["has_structured_metrics"] = has_structured
    result["has_text_metrics"] = has_text_metrics
    result["has_benchmarks"] = has_benchmarks or perf_has_benchmarks
    result["has_papers"] = has_papers
    result["has_documentation"] = has_documentation

    if unique_metrics:
        clogger.debug(f"{log_prefix} extracted metrics: {unique_metrics}")

    return result


class PerformanceClaimsMetric(Metric):
    """
    Performance claims metric for evaluating performance claims.

    Evaluates the presence and quality of performance documentation for a model:
    - Checks for documented performance metrics (accuracy, F1, BLEU, etc.)
    - Checks for benchmark results and evaluation datasets
    - Checks for paper citations and verifiable claims
    - Scores based on comprehensiveness and verifiability of performance claims

    Higher scores indicate better documented and more verifiable performance claims.
    """

    SCORE_FIELD = "performance_claims"

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model performance claims.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Performance claims score as a dictionary with value between 0.0 and 1.0
            (higher is better - more comprehensive and verifiable performance documentation)
        """
        clogger.debug(f"[performance_claims] Scoring model {model.artifact_id}")

        if not model.metadata:
            clogger.debug(
                f"[performance_claims] [{model.artifact_id}] metadata is None, returning 0.0"
            )
            return {"performance_claims": 0.0}

        try:
            # Extract performance claims from metadata
            claims_info = _extract_performance_claims_from_metadata(
                model.metadata, artifact_id=model.artifact_id
            )

            # Calculate score based on various factors
            score, score_breakdown = self._calculate_performance_claims_score(
                claims_info, artifact_id=model.artifact_id
            )

            clogger.debug(
                f"[performance_claims] [{model.artifact_id}] final score: {score:.3f} "
                f"(breakdown: {score_breakdown})"
            )

            return {"performance_claims": score}

        except Exception as e:
            clogger.exception(
                f"Failed to calculate performance claims for model {model.artifact_id}",
                extra={"error_type": type(e).__name__},
            )
            return {"performance_claims": 0.0}

    def _calculate_performance_claims_score(
        self, claims_info: Dict[str, Any], artifact_id: str = ""
    ) -> tuple[float, Dict[str, float]]:
        """
        Calculate performance claims score from extracted information.

        Uses module-level _WEIGHTS and _METRIC_COUNT_BONUS constants for scoring.

        Args:
            claims_info: Dictionary from _extract_performance_claims_from_metadata
            artifact_id: Optional artifact ID for logging context

        Returns:
            Tuple of (score, breakdown) where:
            - score: float between 0.0 and 1.0
            - breakdown: dict showing contribution from each component
        """
        breakdown: Dict[str, float] = {
            "metrics": 0.0,
            "metric_bonus": 0.0,
            "benchmarks": 0.0,
            "papers": 0.0,
            "documentation": 0.0,
        }

        has_metrics = claims_info.get("has_metrics", False)
        has_structured = claims_info.get("has_structured_metrics", False)
        has_text_metrics = claims_info.get("has_text_metrics", False)
        has_documentation = claims_info.get("has_documentation", False)
        metric_count = claims_info.get("metric_count", 0)

        # Score for having performance metrics
        if has_metrics:
            if has_structured:
                breakdown["metrics"] = _WEIGHTS["structured_metrics"]
            elif has_text_metrics:
                # Text metrics are worth less than structured but more than nothing
                breakdown["metrics"] = _WEIGHTS["text_metrics"]
            else:
                breakdown["metrics"] = _WEIGHTS["unstructured_metrics"]

            # Bonus for having multiple metrics
            breakdown["metric_bonus"] = _get_metric_count_bonus(metric_count)

        # Score for having benchmarks/evaluation datasets
        if claims_info.get("has_benchmarks", False):
            breakdown["benchmarks"] = _WEIGHTS["benchmarks"]

        # Score for having paper citations (indicates peer review)
        if claims_info.get("has_papers", False):
            breakdown["papers"] = _WEIGHTS["papers"]

        # Base score for having documentation (even without metrics)
        # This ensures models with READMEs aren't scored 0.0
        if has_documentation and not has_metrics:
            breakdown["documentation"] = _WEIGHTS["has_documentation"]

        # Sum up the breakdown and clamp to [0.0, 1.0]
        score = max(0.0, min(1.0, sum(breakdown.values())))

        return score, breakdown
