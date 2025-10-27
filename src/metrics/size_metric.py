#!/usr/bin/env python3
"""
Size Metric implementation.
"""

from typing import Dict, Union

from .metric import Metric


class SizeMetric(Metric):
    """
    Size metric for evaluating model size.
    """

    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        # Get code key from model and use it as the target to evaluate
        code_key = model.get_code_key()
        
        p = self._as_path(code_key)
        if not p:
            return {
                "files": self._stable_unit_score(code_key, "files"),
                "lines": self._stable_unit_score(code_key, "lines"),
                "commits": self._stable_unit_score(code_key, "commits"),
            }

        if not self._is_git_repo(p):
            return {
                "files": self._stable_unit_score(code_key, "files"),
                "lines": self._stable_unit_score(code_key, "lines"),
                "commits": 0.0,
            }

        # Example metrics
        files = len(list(p.glob("**/*")))
        lines = sum(self._count_lines(f) for f in p.glob("**/*.py"))
        rc, out, _ = self._git(p, "rev-list", "--count", "HEAD")
        commits = int(out.strip()) if (rc == 0 and out.strip().isdigit()) else 0

        return {
            "files": self._saturating_scale(files, max_x=1000, knee=500),
            "lines": self._saturating_scale(lines, max_x=50000, knee=10000),
            "commits": self._saturating_scale(commits, max_x=5000, knee=1000),
        }
