from typing import Dict, Union, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from src.model import Model

from .metric import Metric


class AvailabilityMetric(Metric):
    """
    Availability metric for evaluating model availability.
    """

    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        # Get code key from model and use it as the target to evaluate
        code_key = model.get_code_key()
        
        p = self._as_path(code_key)
        if not p:
            return {
                "availability": self._stable_unit_score(code_key, "availability")
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
