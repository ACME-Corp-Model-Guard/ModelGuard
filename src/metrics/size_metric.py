from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict

from .metric import Metric

if TYPE_CHECKING:
    from ..model import Model


class SizeMetric(Metric):
    """
    Size metric for evaluating model size.

    This is a stub implementation that will be filled out when
    S3 and SageMaker/Bedrock integration is available.
    """

    def score(self, model: Model) -> Union[float, Dict[str, float]]:
        """
        Score model size.

        Args:
            model: The Model object to score

        Returns:
            Size score as a dictionary
        """
        # TODO: Implement actual size scoring when S3 integration is ready
        # For now, return a placeholder score
        return {"size": 0.5}
