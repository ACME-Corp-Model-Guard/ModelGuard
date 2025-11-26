from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from src.logger import logger
from src.metrics.metric import Metric
from src.storage.dynamo_utils import load_artifact_metadata

if TYPE_CHECKING:
    # Type hints only, no runtime dependency
    from src.artifacts.base_artifact import BaseArtifact


class TreescoreMetric(Metric):
    """
    Treescore metric: average NetScore of all ancestor models in the lineage.
    """

    SCORE_FIELD = "tree_score"

    def score(self, model: BaseArtifact) -> Dict[str, float]:
        """
        Compute the treescore as the average NetScore of all ancestors.

        Args:
            model: The ModelArtifact being scored (BaseArtifact for type safety)

        Returns:
            {"tree_score": <float>}
        """

        parent_id = getattr(model, "parent_model_id", None)
        if parent_id is None:
            # No parent → neutral treescore
            return {self.SCORE_FIELD: 0.5}

        total = 0.0
        count = 0
        current_id = parent_id

        # Walk the lineage chain
        while current_id:
            parent = load_artifact_metadata(current_id)

            # Ensure valid parent
            if not parent or not hasattr(parent, "scores"):
                break

            # Get parent's NetScore, default to neutral 0.5
            parent_net = parent.scores.get("NetScore", 0.5)
            try:
                parent_net = float(parent_net)
            except Exception:
                parent_net = 0.5

            total += parent_net
            count += 1

            # Move up the chain
            current_id = getattr(parent, "parent_model_id", None)

        # Compute final value
        if count == 0:
            score = 0.5
        else:
            score = total / count

        # Clamp to [0.0, 1.0]
        if not (0.0 <= score <= 1.0):
            logger.warning(
                f"[treescore] Computed out-of-bounds score {score} for model {model.artifact_id}"
            )
            score = 0.5

        logger.info(f"[treescore] Computed {score:.3f} for model {model.artifact_id}")
        return {self.SCORE_FIELD: score}
