from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict, Optional

from .metric import Metric
from src.logger import logger
from src.artifacts.utils.api_ingestion import (
    extract_github_url_from_huggingface_metadata,
    fetch_github_contributors,
)

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class BusFactorMetric(Metric):
    """
    Bus factor metric for evaluating contributor diversity.

    Calculates the minimum number of contributors needed to account for 50% of
    the project's contributions. Higher bus factor indicates better contributor
    distribution and project resilience.

    For GitHub repositories, fetches contributor statistics and calculates based
    on commit distribution. For HuggingFace models, attempts to find linked
    GitHub repository or returns a default score.
    """

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model bus factor.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Bus factor score as a dictionary with value between 0.0 and 1.0
            (higher is better - more distributed contributions)
        """

        source_url = model.source_url
        if not source_url:
            logger.warning(f"No source_url for model {model.artifact_id}")
            return {"bus_factor": 0.0}

        # Determine GitHub URL to use for bus factor calculation
        github_url = None

        # Check if source_url is a GitHub repository
        if "github.com" in source_url:
            github_url = source_url
        # For HuggingFace models, extract GitHub URL from metadata
        elif "huggingface.co" in source_url:
            github_url = extract_github_url_from_huggingface_metadata(model.metadata)
            if not github_url:
                # No GitHub repo found, return neutral score
                logger.debug(
                    f"No GitHub repo found for HuggingFace model: {source_url}"
                )
                return {"bus_factor": 0.5}

        # Calculate bus factor if we have a GitHub URL
        if github_url:
            try:
                bus_factor = self._calculate_github_bus_factor(github_url)
                return {"bus_factor": bus_factor}
            except Exception as e:
                logger.error(
                    f"Failed to calculate bus factor for GitHub repo {github_url}: {e}",
                    exc_info=True,
                )
                return {"bus_factor": 0.0}
        # Unknown source type, return neutral score
        logger.debug(f"Unknown source URL type for bus factor: {source_url}")
        return {"bus_factor": 0.5}

    def _calculate_github_bus_factor(self, github_url: str) -> float:
        """
        Calculate bus factor for a GitHub repository.

        Args:
            github_url: GitHub repository URL

        Returns:
            Bus factor score between 0.0 and 1.0
        """
        logger.debug(f"Calculating bus factor for GitHub repo: {github_url}")

        # Fetch contributor statistics using api_ingestion
        contributors = fetch_github_contributors(github_url)
        if not contributors:
            logger.warning(f"No contributors found for {github_url}")
            return 0.0

        # Calculate total contributions
        total_contributions = sum(contrib["contributions"] for contrib in contributors)

        if total_contributions == 0:
            logger.warning(f"Zero total contributions for {github_url}")
            return 0.0

        # Sort contributors by contributions (descending)
        contributors_sorted = sorted(
            contributors, key=lambda x: x["contributions"], reverse=True
        )

        # Calculate how many contributors are needed for 50% of contributions
        cumulative_contributions = 0
        target_contributions = total_contributions * 0.5
        num_contributors_needed = 0

        for contrib in contributors_sorted:
            cumulative_contributions += contrib["contributions"]
            num_contributors_needed += 1
            if cumulative_contributions >= target_contributions:
                break

        # Normalize bus factor score
        # More contributors needed = better (higher score)
        # Scale: 1 contributor = 0.1, 5 contributors = 0.5, 10+ contributors = 1.0
        # Using a logarithmic scale for better distribution
        bus_factor = min(1.0, num_contributors_needed / 10.0)

        # Bonus for having many total contributors (indicates active project)
        total_contributors = len(contributors)
        if total_contributors > 20:
            # Add small bonus for projects with many contributors
            bus_factor = min(1.0, bus_factor + 0.1)

        logger.debug(
            f"Bus factor for {github_url}: {num_contributors_needed} contributors "
            f"needed for 50% (score: {bus_factor:.3f})"
        )

        return bus_factor
