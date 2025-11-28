from __future__ import annotations

import requests
from typing import TYPE_CHECKING, Union, Dict, List, Optional

from .metric import Metric
from src.logger import logger

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

        # Check if source_url is a GitHub repository
        if "github.com" in source_url:
            try:
                bus_factor = self._calculate_github_bus_factor(source_url)
                return {"bus_factor": bus_factor}
            except Exception as e:
                logger.error(
                    f"Failed to calculate bus factor for GitHub repo {source_url}: {e}"
                )
                return {"bus_factor": 0.0}

        # For HuggingFace models, check if there's a linked GitHub repo in metadata
        if "huggingface.co" in source_url:
            try:
                github_url = self._get_github_url_from_huggingface(
                    source_url, model.metadata
                )
                if github_url:
                    bus_factor = self._calculate_github_bus_factor(github_url)
                    return {"bus_factor": bus_factor}
                else:
                    # No GitHub repo found, return neutral score
                    logger.debug(
                        f"No GitHub repo found for HuggingFace model: {source_url}"
                    )
                    return {"bus_factor": 0.5}
            except Exception as e:
                logger.error(
                    f"Failed to get GitHub URL for HuggingFace model {source_url}: {e}"
                )
                return {"bus_factor": 0.5}

        # Unknown source type, return neutral score
        logger.debug(f"Unknown source URL type for bus factor: {source_url}")
        return {"bus_factor": 0.5}

    def _get_github_url_from_huggingface(
        self, huggingface_url: str, metadata: Dict
    ) -> Optional[str]:
        """
        Extract GitHub repository URL from HuggingFace model metadata.

        Args:
            huggingface_url: HuggingFace model URL
            metadata: Model metadata dictionary

        Returns:
            GitHub repository URL if found, None otherwise
        """
        # Check metadata for GitHub URL
        if metadata:
            # Common fields where GitHub URL might be stored
            github_url = (
                metadata.get("github_url")
                or metadata.get("github")
                or metadata.get("code_repository")
                or metadata.get("repository")
            )
            if github_url and "github.com" in str(github_url):
                return str(github_url)

        # Try to fetch from HuggingFace API
        try:
            parts = huggingface_url.rstrip("/").split("huggingface.co/")
            if len(parts) < 2:
                return None

            model_id = parts[1]
            api_url = f"https://huggingface.co/api/models/{model_id}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check various fields where GitHub URL might be stored
            github_url = (
                data.get("cardData", {}).get("github")
                or data.get("cardData", {}).get("code_repository")
                or data.get("siblings", [{}])[0].get("rfilename", "").split("/")[0]
                if data.get("siblings")
                else None
            )

            if github_url and "github.com" in str(github_url):
                return str(github_url)

        except Exception as e:
            logger.debug(f"Could not fetch GitHub URL from HuggingFace API: {e}")

        return None

    def _calculate_github_bus_factor(self, github_url: str) -> float:
        """
        Calculate bus factor for a GitHub repository.

        Args:
            github_url: GitHub repository URL

        Returns:
            Bus factor score between 0.0 and 1.0
        """
        # Parse owner/repo from URL
        parts = github_url.rstrip("/").split("github.com/")
        if len(parts) < 2:
            logger.warning(f"Invalid GitHub URL format: {github_url}")
            return 0.0

        repo_path = parts[1].split("/")[:2]
        if len(repo_path) < 2:
            logger.warning(f"Invalid GitHub repository URL: {github_url}")
            return 0.0

        owner, repo = repo_path
        logger.debug(f"Calculating bus factor for GitHub repo: {owner}/{repo}")

        # Fetch contributor statistics
        contributors = self._fetch_github_contributors(owner, repo)
        if not contributors:
            logger.warning(f"No contributors found for {owner}/{repo}")
            return 0.0

        # Calculate total contributions
        total_contributions = sum(contrib["contributions"] for contrib in contributors)

        if total_contributions == 0:
            logger.warning(f"Zero total contributions for {owner}/{repo}")
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
            f"Bus factor for {owner}/{repo}: {num_contributors_needed} contributors "
            f"needed for 50% (score: {bus_factor:.3f})"
        )

        return bus_factor

    def _fetch_github_contributors(self, owner: str, repo: str) -> List[Dict[str, int]]:
        """
        Fetch contributor statistics from GitHub API.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of contributor dictionaries with 'contributions' field
        """
        try:
            # GitHub API endpoint for contributors
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
            response = requests.get(api_url, timeout=10, params={"per_page": 100})

            # Handle rate limiting
            if response.status_code == 403:
                logger.warning("GitHub API rate limit exceeded")
                return []

            response.raise_for_status()
            contributors = response.json()

            # Extract contribution counts
            result = []
            for contrib in contributors:
                if isinstance(contrib, dict) and "contributions" in contrib:
                    result.append({"contributions": contrib["contributions"]})

            return result

        except requests.RequestException as e:
            logger.error(
                f"Failed to fetch contributors from GitHub API for {owner}/{repo}: {e}"
            )
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching GitHub contributors: {e}")
            return []
