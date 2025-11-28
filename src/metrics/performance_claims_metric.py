from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict, Any

from .metric import Metric
from src.logger import logger
from src.artifacts.utils.api_ingestion import extract_performance_claims_from_metadata

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


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
            logger.debug(
                f"No metadata available for model {model.artifact_id}, returning default score"
            )
            return {"performance_claims": 0.0}

        try:
            # Extract performance claims from metadata
            claims_info = extract_performance_claims_from_metadata(model.metadata)

            # Calculate score based on various factors
            score = self._calculate_performance_claims_score(claims_info)

            logger.debug(
                f"Performance claims score for {model.artifact_id}: {score:.3f} "
                f"(metrics: {claims_info['has_metrics']}, "
                f"metric_count: {claims_info.get('metric_count', 0)}, "
                f"structured: {claims_info.get('has_structured_metrics', False)}, "
                f"benchmarks: {claims_info['has_benchmarks']}, "
                f"papers: {claims_info['has_papers']})"
            )

            return {"performance_claims": score}

        except Exception as e:
            logger.error(
                f"Failed to calculate performance claims for model {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {"performance_claims": 0.0}

    def _calculate_performance_claims_score(
        self, claims_info: Dict[str, Any]
    ) -> float:
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
            claims_info: Dictionary from extract_performance_claims_from_metadata

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
