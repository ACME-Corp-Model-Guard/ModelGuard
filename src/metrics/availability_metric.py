from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class AvailabilityMetric(Metric):
    """
    Availability metric for evaluating model availability.

    This is a stub implementation that will be filled out when
    S3 and SageMaker/Bedrock integration is available.
    """

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model availability.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Availability score as a dictionary
        """
        # TODO: Implement actual availability scoring when S3 integration is ready
        # For now, return a placeholder score
        return {"availability": 0.5}
