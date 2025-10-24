from collections import Counter
from typing import Dict, Union

from .abstract_metric import AbstractMetric


class BusFactorMetric(AbstractMetric):
    """
    Estimate bus factor via commit author distribution.

    Higher diversity (less dominance by a single author) -> higher score.

    Heuristic:
      - Get top N commits (default all) and count authors.
      - Score = 1 - max_author_share.
      - Scale by total number of contributors (more is better).

    Fallback: stable placeholder if not a local path.
    """

    def __init__(self):
        super().__init__("bus_factor")

    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        # TODO: Implement actual bus factor scoring when S3 integration is ready
        # For now, return a placeholder score based on model name
        bus_factor_score = self._stable_unit_score(model.name, "bus_factor")
        return {"bus_factor": bus_factor_score}
