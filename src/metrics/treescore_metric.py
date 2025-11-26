from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from src.logger import logger
from src.metrics.metric import Metric
from src.storage.dynamo_utils import load_artifact_metadata

if TYPE_CHECKING:
    from src.artifacts.model_artifact import ModelArtifact


class TreescoreMetric(Metric):
    """
    Treescore metric: average NetScore of all ancestor models in the lineage.
    """

    SCORE_FIELD = "tree_score"

    def score(self, model: "ModelArtifact") -> Dict[str, float]:
        """
        Compute the treescore as the average NetScore of all ancestors.

        Args:
            model: The ModelArtifact being scored.

        Returns:
            {"tree_score": <float>}
        """

        parent_id = model.parent_model_id
        if parent_id is None:
            return {self.SCORE_FIELD: 0.5}

        total = 0.0
        count = 0
        current_id = parent_id

        # Walk the lineage chain
        while current_id:
            parent = load_artifact_metadata(current_id)

            # Must be ModelArtifact; ignore other artifact types
            if not parent or not hasattr(parent, "scores"):
                break

            parent_net = parent.scores.get("NetScore", 0.5)
            try:
                parent_net = float(parent_net)
            except Exception:
                parent_net = 0.5

            total += parent_net
            count += 1

            current_id = parent.parent_model_id

        score = total / count if count > 0 else 0.5
        score = max(0.0, min(1.0, score))

        logger.info(f"[treescore] Computed {score:.3f} for model {model.artifact_id}")
        return {self.SCORE_FIELD: score}
