from pathlib import Path
from typing import Any, List, Optional


class BaseMetric:
    def _is_git_repo(self, path: Path) -> bool:
        return False

    def _git(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def _count_lines(self, path: Path) -> int:
        return 0

    def _saturating_scale(self, x: float, *, knee: float, max_x: float) -> float:
        """Scale value to [0,1] with a knee point and max_x saturation."""
        return 0.0

    def _clamp01(self, x: float) -> float:
        return 0.0

    def _read_text(self, path: Path) -> str:
        return ""

    def _glob(self, base: Path, patterns: List[str]) -> List[Path]:
        files: list[Path] = []
        for pattern in patterns:
            files.extend(base.glob(pattern))
        return list(files)

    def _as_path(self, path_or_url: str) -> Optional[Path]:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return None
        p = Path(path_or_url)
        if p.exists():
            return p
        return None

    def _stable_unit_score(self, key: str, salt: str) -> float:
        return 0.0
