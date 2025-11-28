from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict

from .metric import Metric
from src.logger import logger

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class SizeMetric(Metric):
    """
    Size metric for evaluating model size.

    Scores models based on their size in bytes. Generally, smaller models
    receive higher scores as they are easier to deploy, use less resources,
    and are more accessible. However, very small models (<1MB) may indicate
    incomplete or minimal models and receive lower scores.

    Scoring ranges:
    - <1MB: 0.3 (very small, may be incomplete)
    - 1MB-100MB: 1.0 (optimal for most use cases)
    - 100MB-500MB: 0.9 (good, still manageable)
    - 500MB-1GB: 0.7 (acceptable, larger but usable)
    - 1GB-5GB: 0.5 (large, harder to deploy)
    - 5GB-10GB: 0.3 (very large, deployment challenges)
    - >10GB: 0.1 (extremely large, significant deployment barriers)
    """

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model size.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Size score as a dictionary with value between 0.0 and 1.0
            (higher is better - smaller, more deployable models)
        """
        size_bytes = model.size

        # Handle missing or invalid size
        if not size_bytes or size_bytes <= 0:
            logger.debug(
                f"No valid size information for model {model.artifact_id}, "
                f"returning neutral score"
            )
            return {"size": 0.5}

        try:
            score = self._calculate_size_score(size_bytes)

            # Convert to human-readable format for logging
            size_mb = size_bytes / (1024 * 1024)
            logger.debug(
                f"Size score for {model.artifact_id}: {score:.3f} "
                f"(size: {size_mb:.2f} MB)"
            )

            return {"size": score}

        except Exception as e:
            logger.error(
                f"Failed to calculate size score for model {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {"size": 0.5}

    def _calculate_size_score(self, size_bytes: float) -> float:
        """
        Calculate size score based on model size in bytes.

        Args:
            size_bytes: Model size in bytes

        Returns:
            Score between 0.0 and 1.0
        """
        # Convert to MB for easier comparison
        size_mb = size_bytes / (1024 * 1024)

        # Score based on size ranges
        if size_mb < 1:
            # Very small (<1MB) - may be incomplete or minimal
            return 0.3
        elif size_mb < 100:
            # Optimal range (1MB-100MB) - excellent for deployment
            return 1.0
        elif size_mb < 500:
            # Good range (100MB-500MB) - still very manageable
            return 0.9
        elif size_mb < 1024:  # 1GB
            # Acceptable (500MB-1GB) - larger but still usable
            return 0.7
        elif size_mb < 5 * 1024:  # 5GB
            # Large (1GB-5GB) - harder to deploy but manageable
            return 0.5
        elif size_mb < 10 * 1024:  # 10GB
            # Very large (5GB-10GB) - significant deployment challenges
            return 0.3
        else:
            # Extremely large (>10GB) - major deployment barriers
            return 0.1
