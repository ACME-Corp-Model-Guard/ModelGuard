from typing import Dict
from collections import Counter

from .metric import Metric


class BusFactorMetric(Metric):
    """
    Bus factor metric for evaluating contributor diversity.
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
