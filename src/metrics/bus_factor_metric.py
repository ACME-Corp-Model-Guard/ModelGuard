from typing import Dict, Union
from collections import Counter

from .metric import Metric


class BusFactorMetric(Metric):
    """
    Bus factor metric for evaluating contributor diversity.
    """

    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        # Get code key from model and use it as the target to evaluate
        code_key = model.get_code_key()
        
        p = self._as_path(code_key)
        if not p or not self._is_git_repo(p):
            return {"bus_factor": self._stable_unit_score(code_key, "bus_factor")}

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
