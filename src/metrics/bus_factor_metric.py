from collections import Counter
from typing import Dict

from src.metrics.metric import Metric

from .base_metric import BaseMetric


class BusFactorMetric(BaseMetric, Metric):
    """
    Estimate bus factor via commit author distribution.

    Higher diversity (less dominance by a single author) -> higher score.

    Heuristic:
      - Get top N commits (default all) and count authors.
      - Score = 1 - max_author_share.
      - Scale by total number of contributors (more is better).

    Fallback: stable placeholder if not a local path.
    """

    def score(self, path_or_url: str) -> Dict[str, float]:
        p = self._as_path(path_or_url)
        if not p or not self._is_git_repo(p):
            return {"bus_factor": self._stable_unit_score(path_or_url, "bus_factor")}

        rc, out, _ = self._git(p, "log", "--pretty=%ae")
        if rc != 0 or not out.strip():
            return {"bus_factor": 0.0}

        authors = [a.strip().lower() for a in out.splitlines() if a.strip()]
        if not authors:
            return {"bus_factor": 0.0}

        total = len(authors)
        counts = Counter(authors)
        max_share = max(counts.values()) / max(1, total)
        diversity = 1.0 - max_share
        contrib_scale = self._saturating_scale(len(counts), knee=5, max_x=20)
        return {"bus_factor": self._clamp01(0.7 * diversity + 0.3 * contrib_scale)}
