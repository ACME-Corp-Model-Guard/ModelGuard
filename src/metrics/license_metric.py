from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class LicenseMetric(Metric):
    """
    License metric for evaluating model licensing.

    This is a stub implementation that will be filled out when
    S3 and SageMaker/Bedrock integration is available.

    Scoring (0.0 - 1.0)
    -------------------
    - 1.0: Known license and fully compatible (ex: MIT, Apache-2.0)
    - 0.5: Unknown, ambiguous, or undetermined license.
    - 0.0: Known but incompatible license (ex: GPL-3.0, AGPL-3.0, Proprietary)

    Output
    ------
    Returns a dictionary in the standard metric format:
    {"license": <float score>}
    So that it can be consumed by the calculate_net_score method, and persisted 
    in ModelArtifact.scores.

    """
    
    SCORE_FIELD = "license"

    #Mapping
    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model license.

        Args:
            model: The ModelArtifact object to score

        Returns:
            License score as a dictionary
        """
        # TODO: Implement actual license scoring when S3 integration is ready
        # For now, return a placeholder score
        return {"license": 0.5}
