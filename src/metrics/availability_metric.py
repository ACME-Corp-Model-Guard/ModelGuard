from typing import Dict
from datetime import datetime, timezone

from .metric import Metric


class AvailabilityMetric(Metric):
    """
    Availability metric for evaluating model availability.
    """

    def score(self, path_or_url: str) -> Dict[str, float]:
        p = self._as_path(path_or_url)
        if not p:
            return {
                "availability": self._stable_unit_score(path_or_url, "availability")
            }

        score = 0.0

        if p.exists():
            score += 0.3

        if self._is_git_repo(p):
            rc, out, _ = self._git(p, "rev-parse", "HEAD")
            if rc == 0 and out.strip():
                score += 0.3

            rc, out, _ = self._git(p, "log", "-1", "--format=%ct")
            if rc == 0 and out.strip().isdigit():
                ts = int(out.strip())
                last_commit = datetime.fromtimestamp(ts, tz=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_commit).days
                # full points if commit within 90 days; fades to 0 by 365 days
                if days_since <= 90:
                    score += 0.4
                elif days_since <= 365:
                    score += 0.4 * (1 - (days_since - 90) / 275)

        return {"availability": self._clamp01(score)}
