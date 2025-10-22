from typing import Dict

from .base_metric import BaseMetric
from .metric import Metric


class PerformanceClaimsMetric(BaseMetric, Metric):
    """
    Project performance claims signals:
      - performance_claims: heuristic score for performance-related activity

    Returns a sub-score normalized to [0,1] with a saturating scale.
    """

    def score(self, path_or_url: str) -> Dict[str, float]:
        p = self._as_path(path_or_url)
        if not p or not self._is_git_repo(p):
            # Fallback: deterministic but stable dictionary
            return {
                "performance_claims": self._stable_unit_score(
                    path_or_url,
                    "perf_claims",
                )
            }

        # Example heuristic:
        # Use commit count as a proxy for project maturity, which might
        # indicate more documented performance-related work.
        rc, out, _ = self._git(p, "rev-list", "--count", "HEAD")
        commits = int(out.strip()) if (rc == 0 and out.strip().isdigit()) else 0

        return {
            "performance_claims": self._saturating_scale(
                commits,
                knee=100,
                max_x=1000,
            )
        }
