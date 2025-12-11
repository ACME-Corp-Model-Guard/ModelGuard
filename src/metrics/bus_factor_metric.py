from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Union

from src.artifacts.artifactory import load_artifact_metadata
from src.artifacts.code_artifact import CodeArtifact
from src.logging import clogger

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class BusFactorMetric(Metric):
    """
    Bus factor metric for evaluating contributor diversity.

    Calculates the minimum number of contributors needed to account for 50% of
    the project's contributions. Higher bus factor indicates better contributor
    distribution and project resilience.

    Works with ModelArtifact by loading the connected CodeArtifact and using
    contributor data stored in the CodeArtifact's metadata.
    """

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model bus factor using connected CodeArtifact.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Bus factor score as a dictionary with value between 0.0 and 1.0
            (higher is better - more distributed contributions)
        """
        # Load the connected CodeArtifact
        if not model.code_artifact_id:
            clogger.debug(
                f"No code artifact_id for model {model.artifact_id}, "
                f"returning default score"
            )
            return {"bus_factor": 0.0}

        code_artifact = load_artifact_metadata(model.code_artifact_id)
        if not isinstance(code_artifact, CodeArtifact):
            clogger.debug(
                f"Missing or invalid code artifact for model {model.artifact_id}"
            )
            return {"bus_factor": 0.0}

        if not code_artifact.metadata:
            clogger.debug(
                f"No metadata available for code artifact {code_artifact.artifact_id}, "
                f"returning default score"
            )
            return {"bus_factor": 0.0}

        # Get contributors from metadata (stored during artifact creation)
        contributors = code_artifact.metadata.get("contributors", [])
        if not contributors:
            clogger.debug(
                f"No contributors data in metadata for code artifact {code_artifact.artifact_id}"
            )
            return {"bus_factor": 0.0}

        try:
            bus_factor = self._calculate_bus_factor(contributors)
            clogger.debug(
                f"Bus factor score for model {model.artifact_id} "
                f"(code: {code_artifact.artifact_id}): {bus_factor:.3f}"
            )
            return {"bus_factor": bus_factor}
        except Exception as e:
            clogger.error(
                f"Failed to calculate bus factor for model {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {"bus_factor": 0.0}

    def _calculate_bus_factor(self, contributors: List[Dict[str, Any]]) -> float:
        """
        Calculate bus factor from contributor data.

        Args:
            contributors: List of contributor dictionaries with 'contributions' field

        Returns:
            Bus factor score between 0.0 and 1.0
        """
        if not contributors:
            return 0.0

        # Calculate total contributions
        total_contributions = sum(
            contrib.get("contributions", 0) for contrib in contributors
        )

        if total_contributions == 0:
            clogger.warning("Zero total contributions")
            return 0.0

        # Sort contributors by contributions (descending)
        contributors_sorted = sorted(
            contributors,
            key=lambda x: x.get("contributions", 0),
            reverse=True,
        )

        # Calculate how many contributors are needed for 50% of contributions
        cumulative_contributions = 0
        target_contributions = total_contributions * 0.5
        num_contributors_needed = 0

        for contrib in contributors_sorted:
            cumulative_contributions += contrib.get("contributions", 0)
            num_contributors_needed += 1
            if cumulative_contributions >= target_contributions:
                break

        # Normalize bus factor score
        # More contributors needed = better (higher score)
        # Scale: 1 contributor = 0.1, 5 contributors = 0.5, 10+ contributors = 1.0
        bus_factor = min(1.0, num_contributors_needed / 10.0)

        # Bonus for having many total contributors (indicates active project)
        total_contributors = len(contributors)
        if total_contributors > 20:
            # Add small bonus for projects with many contributors
            bus_factor = min(1.0, bus_factor + 0.1)

        clogger.debug(
            f"Bus factor: {num_contributors_needed} contributors needed for 50% "
            f"(score: {bus_factor:.3f})"
        )

        return bus_factor
