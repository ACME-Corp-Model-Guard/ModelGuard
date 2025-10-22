from typing import Dict

from .base_metric import BaseMetric


class SizeMetric(BaseMetric):
    def score(self, path_or_url: str) -> Dict[str, float]:
        p = self._as_path(path_or_url)
        if not p or not self._is_git_repo(p):
            # Fallback: deterministic but stable dictionary
            return {
                "files": self._stable_unit_score(
                    path_or_url,
                    "size_files",
                ),
                "lines": self._stable_unit_score(
                    path_or_url,
                    "size_lines",
                ),
                "commits": self._stable_unit_score(
                    path_or_url,
                    "size_commits",
                ),
            }

        # Example metrics
        files = len(list(p.glob("**/*")))
        lines = sum(self._count_lines(f) for f in p.glob("**/*.py"))
        commits = int(self._git("rev-list", "--count", "HEAD"))

        return {
            "files": self._saturating_scale(files, max_x=1000, knee=500),
            "lines": self._saturating_scale(lines, max_x=50000, knee=10000),
            "commits": self._saturating_scale(commits, max_x=5000, knee=1000),
        }
