from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict

from .metric import Metric
from artifacts.artifactory import load_artifact_metadata
from utils.logger import logger

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class TreescoreMetric(Metric):
    """
    Treescore metric for evaluating code structure.
    """

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model treescore as the average net_score of its ancestors.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Treescore score as a dictionary
        """
        
        score : float = 0.0
        parent_count : int = 0
        temp_model = model
        if temp_model.parent_model_id is None:
            return {"treescore": 0.5} # No parent, neutral score
        else:
            while temp_model.parent_model_id is not None:
                parent = self.load_artifact_metadata(temp_model.parent_model_id)
                if parent and isinstance(parent, ModelArtifact):
                    score += parent.scores.get("net_score", 0.5)
                    parent_count += 1
                    temp_model = parent
                else:
                    break
        score = score / parent_count if parent_count > 0 else 0.5
        if score < 0.0 or score > 1.0:
            logger.warning(f"Computed treescore {score} out of bounds for model {model.artifact_id}")
            score = 0.5  # Clamp to neutral if out of bounds
        logger.info(f"Computed treescore {score} for model {model.artifact_id}")
        return {"treescore": score}
            
