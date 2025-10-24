from datetime import datetime, timezone
from typing import Dict, Union

from .abstract_metric import AbstractMetric


class AvailabilityMetric(AbstractMetric):
    """
    Availability heuristic:
      - Repo directory exists -> base availability.
      - Git repo with reachable HEAD -> more.
      - Recent commits in last 365 days -> best.
    Fallback: stable placeholder if not a local path.
    """

    def __init__(self):
        super().__init__("availability")

    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        # TODO: Implement actual availability scoring when S3 integration is ready
        # For now, return a placeholder score based on model name
        availability_score = self._stable_unit_score(model.name, "availability")
        return {"availability": availability_score}
