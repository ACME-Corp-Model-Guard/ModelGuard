from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict

from .metric import Metric

if TYPE_CHECKING:
    from ..model import Model


class RampUpMetric(Metric):
    """
    Ramp up metric for evaluating ease of getting started.

    This is a stub implementation that will be filled out when
    S3 and SageMaker/Bedrock integration is available.
    """

    def score(self, model: Model) -> Union[float, Dict[str, float]]:
        """
        Score model ramp up time.

        Args:
            model: The Model object to score

        Returns:
            Ramp up score as a dictionary
        """
        # TODO: Implement actual ramp up scoring when S3 integration is ready
        # For now, return a placeholder score
        return {"ramp_up": 0.5}
