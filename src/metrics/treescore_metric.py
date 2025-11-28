from __future__ import annotations

from typing import Dict, Union

from src.artifacts.artifactory import load_artifact_metadata
from src.artifacts.model_artifact import ModelArtifact
from src.logger import logger

from src.metrics.metric import Metric


class TreescoreMetric(Metric):
    """
    Treescore metric: average NetScore of all ancestor models in the lineage.
    """

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Compute the treescore as the average NetScore of all ancestors.

        Args:
            model: The ModelArtifact object to score

        Returns:
            {"treescore": <float>}
        """

        score: float = 0.0
        parent_count: int = 0
        temp_model = model
        if temp_model.parent_model_id is None:
            return {"treescore": 0.5}  # No parent, neutral score
        else:
            while temp_model.parent_model_id is not None:
                parent = load_artifact_metadata(temp_model.parent_model_id)
                if parent and isinstance(parent, ModelArtifact):
                    net_score = parent.scores.get("net_score")
                    if isinstance(net_score, float):  # Check if net_score is a float
                        score += net_score
                        parent_count += 1
                        temp_model = parent
                else:
                    break
        score = score / parent_count if parent_count > 0 else 0.5
        if score < 0.0 or score > 1.0:
            logger.warning(
                f"Computed treescore {score} out of bounds for model {model.artifact_id}"
            )
            score = 0.5  # Clamp to neutral if out of bounds
        logger.info(f"Computed treescore {score} for model {model.artifact_id}")
        return {"treescore": score}
