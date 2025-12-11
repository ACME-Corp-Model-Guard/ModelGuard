from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Union

from src.logging import clogger

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


def _extract_performance_claims_from_metadata(
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract performance claims and metrics from model metadata.

    Helper function for PerformanceClaimsMetric. Checks various fields where
    performance information might be stored, including HuggingFace model card data.
    Uses structured field checking to avoid false positives from keyword matching.

    Args:
        metadata: Model metadata dictionary (from artifact.metadata)

    Returns:
        Dictionary with performance claims information:
        - has_metrics: bool - whether any performance metrics were found
        - metrics: list - list of found metric names
        - has_benchmarks: bool - whether benchmark results were found
        - has_papers: bool - whether papers are cited
        - metric_count: int - number of distinct metrics found
        - has_structured_metrics: bool - whether metrics are in structured format
        - card_data: dict - raw cardData if available
    """
    metrics_list: List[str] = []
    result: Dict[str, Any] = {
        "has_metrics": False,
        "metrics": metrics_list,
        "has_benchmarks": False,
        "has_papers": False,
        "metric_count": 0,
        "has_structured_metrics": False,
        "card_data": {},
    }

    if not metadata:
        return result

    # Get cardData from various possible locations
    card_data = (
        metadata.get("metadata", {}).get("cardData", {})
        or metadata.get("cardData", {})
        or {}
    )

    result["card_data"] = card_data

    if not card_data:
        return result

    # Primary: Check HuggingFace model-index structure (most reliable)
    if isinstance(card_data, dict):
        model_index = card_data.get("model-index", {})
        if model_index and isinstance(model_index, dict):
            results = model_index.get("results", [])
            if results and isinstance(results, list):
                result["has_benchmarks"] = True
                result["has_structured_metrics"] = True

                # Extract metrics from structured results
                for result_item in results:
                    if isinstance(result_item, dict):
                        # Check for task type (indicates proper benchmark structure)
                        task_type = result_item.get("task", {})
                        if task_type:
                            result["has_benchmarks"] = True

                        # Extract metrics from results
                        metrics = result_item.get("metrics", [])
                        if metrics and isinstance(metrics, list):
                            result["has_metrics"] = True
                            for metric in metrics:
                                if isinstance(metric, dict):
                                    metric_name = metric.get("name", "")
                                    metric_value = metric.get("value")
                                    # Only count if it has both name and value (actual metric)
                                    if metric_name and metric_value is not None:
                                        metrics_list.append(metric_name.lower())

    # Secondary: Check for performance-related fields in cardData
    if isinstance(card_data, dict):
        # Check for explicit performance/evaluation sections
        performance_fields = [
            "performance",
            "evaluation",
            "metrics",
            "results",
            "benchmarks",
            "scores",
        ]

        for field in performance_fields:
            if field in card_data:
                field_value = card_data[field]
                if isinstance(field_value, (dict, list)) and field_value:
                    result["has_benchmarks"] = True
                    # Try to extract metrics from these fields
                    if isinstance(field_value, dict):
                        for key, value in field_value.items():
                            if isinstance(value, (int, float)) and key.lower() in [
                                "accuracy",
                                "f1",
                                "precision",
                                "recall",
                                "bleu",
                                "rouge",
                                "perplexity",
                                "auc",
                            ]:
                                result["has_metrics"] = True
                                metrics_list.append(key.lower())

    # Tertiary: Check for paper citations (more reliable than keyword matching)
    if isinstance(card_data, dict):
        # Check for paper-related fields
        paper_fields = ["paperswithcode", "arxiv", "citation", "bibtex", "paper"]
        for field in paper_fields:
            if field in card_data:
                field_value = card_data[field]
                if field_value and (
                    isinstance(field_value, str)
                    or (isinstance(field_value, list) and len(field_value) > 0)
                    or (isinstance(field_value, dict) and len(field_value) > 0)
                ):
                    result["has_papers"] = True
                    break

        # Check for model card text fields that might contain citations
        text_fields = ["model_card", "readme", "description", "summary"]
        for field in text_fields:
            if field in card_data:
                field_value = str(card_data[field]).lower()
                # Look for arxiv links or DOI patterns (more reliable than keywords)
                if "arxiv.org" in field_value or "doi.org" in field_value:
                    result["has_papers"] = True
                    break

    # Remove duplicates and set count
    result["metrics"] = list(set(metrics_list))
    result["metric_count"] = len(result["metrics"])

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

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model performance claims.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Performance claims score as a dictionary with value between 0.0 and 1.0
            (higher is better - more comprehensive and verifiable performance documentation)
        """
        if not model.metadata:
            clogger.debug(
                f"No metadata available for model {model.artifact_id}, returning default score"
            )
            return {"performance_claims": 0.0}

        try:
            # Extract performance claims from metadata
            claims_info = _extract_performance_claims_from_metadata(model.metadata)

            # Calculate score based on various factors
            score = self._calculate_performance_claims_score(claims_info)

            clogger.debug(
                f"Performance claims score for {model.artifact_id}: {score:.3f} "
                f"(metrics: {claims_info['has_metrics']}, "
                f"metric_count: {claims_info.get('metric_count', 0)}, "
                f"structured: {claims_info.get('has_structured_metrics', False)}, "
                f"benchmarks: {claims_info['has_benchmarks']}, "
                f"papers: {claims_info['has_papers']})"
            )

            return {"performance_claims": score}

        except Exception as e:
            clogger.error(
                f"Failed to calculate performance claims for model {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {"performance_claims": 0.0}

    def _calculate_performance_claims_score(self, claims_info: Dict[str, Any]) -> float:
        """
        Calculate performance claims score from extracted information.

        Improved scoring that considers quality and structure:
        - Structured metrics (model-index format): Higher weight
        - Multiple metrics: Indicates comprehensive evaluation
        - Benchmarks: Shows verifiable evaluation
        - Papers: Indicates peer-reviewed claims

        Scoring breakdown:
        - Has structured metrics (model-index): 0.5 points
        - Has unstructured metrics: 0.3 points
        - Has benchmarks/evaluation datasets: 0.25 points
        - Has paper citations: 0.15 points
        - Multiple metrics bonus: Up to 0.1 points

        Args:
            claims_info: Dictionary from _extract_performance_claims_from_metadata

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0

        has_metrics = claims_info.get("has_metrics", False)
        has_structured = claims_info.get("has_structured_metrics", False)
        metric_count = claims_info.get("metric_count", 0)

        # Score for having performance metrics
        if has_metrics:
            if has_structured:
                # Structured metrics (model-index) are more reliable
                score += 0.5
            else:
                # Unstructured metrics are less reliable but still valuable
                score += 0.3

            # Bonus for having multiple metrics (indicates comprehensive evaluation)
            if metric_count >= 5:
                score += 0.1
            elif metric_count >= 3:
                score += 0.07
            elif metric_count >= 2:
                score += 0.04

        # Score for having benchmarks/evaluation datasets
        if claims_info.get("has_benchmarks", False):
            score += 0.25

        # Score for having paper citations (indicates peer review)
        if claims_info.get("has_papers", False):
            score += 0.15

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))
