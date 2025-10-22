"""
This module contains a proper implementation of BaseMetric for testing.
"""

from pathlib import Path
from typing import Any, List, Optional


class TestBaseMetric:
    """An implementation of BaseMetric for testing."""

    def _is_git_repo(self, path: Path) -> bool:
        return True

    def _git(self, *args: Any, **kwargs: Any) -> Any:
        return "mock git output"

    def _count_lines(self, path: Path) -> int:
        return 100

    def _saturating_scale(self, x: float, *, knee: float, max_x: float) -> float:
        """Scale value to [0,1] with a knee point and max_x saturation."""
        if x <= 0:
            return 0.0
        if x >= max_x:
            return 1.0
        if x <= knee:
            return x / knee * 0.5
        return 0.5 + 0.5 * (x - knee) / (max_x - knee)

    def _clamp01(self, x: float) -> float:
        return max(0.0, min(1.0, x))

    def _read_text(self, path: Path) -> str:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return "mock content"

    def _glob(self, base: Path, patterns: List[str]) -> List[Path]:
        """Mock glob implementation that returns paths based on patterns."""
        result = []
        for pattern in patterns:
            if "test" in pattern:
                result.append(base / "tests" / "test_mock.py")
            elif "workflow" in pattern or "yml" in pattern:
                result.append(base / ".github" / "workflows" / "ci.yml")
        return result

    def _as_path(self, path_or_url: str) -> Optional[Path]:
        if "://" in path_or_url:  # Looks like a URL
            return None
        return Path(path_or_url)

    def _stable_unit_score(self, key: str, salt: str) -> float:
        # Simple hash-based stable scoring between 0 and 1
        combined = f"{key}:{salt}"
        hash_value = sum(ord(c) for c in combined)
        return (hash_value % 1000) / 1000.0
