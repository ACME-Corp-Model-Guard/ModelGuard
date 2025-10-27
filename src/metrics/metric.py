from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
import hashlib
import subprocess
from collections import Counter
from datetime import datetime, timezone
import csv
import re


class Metric(ABC):
    """
    Abstract base class for all metrics in the ModelGuard system.
    All concrete metrics must implement the score() method.
    Also provides helper methods for common metric operations.
    """
    
    def _is_git_repo(self, path: Path) -> bool:
        """Check if a path is a git repository."""
        return (path / ".git").exists()
    
    def _git(self, path: Path, *args: str) -> tuple[int, str, str]:
        """Run a git command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode, result.stdout, result.stderr
        except Exception:
            return 1, "", ""
    
    def _as_path(self, path_or_url: str) -> Optional[Path]:
        """Convert a string to a Path if it's a local path."""
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return None
        p = Path(path_or_url)
        if p.exists():
            return p
        return None
    
    def _glob(self, base: Path, patterns: List[str]) -> List[Path]:
        """Find files matching patterns."""
        files: List[Path] = []
        for pattern in patterns:
            files.extend(base.glob(pattern))
        return files
    
    def _stable_unit_score(self, key: str, salt: str) -> float:
        """Generate a stable deterministic score between 0 and 1."""
        combined = f"{key}:{salt}"
        hash_obj = hashlib.md5(combined.encode())
        # Convert first 8 bytes to int for determinism
        hash_int = int.from_bytes(hash_obj.digest()[:8], 'big')
        return (hash_int % 10000) / 10000.0
    
    def _clamp01(self, x: float) -> float:
        """Clamp a value to the range [0, 1]."""
        return max(0.0, min(1.0, x))
    
    def _saturating_scale(self, x: float, *, knee: float, max_x: float) -> float:
        """Scale value to [0,1] with a knee point and max_x saturation."""
        if x <= 0:
            return 0.0
        if x >= max_x:
            return 1.0
        if x <= knee:
            return x / knee * 0.5
        return 0.5 + (x - knee) / (max_x - knee) * 0.5
    
    def _count_lines(self, path: Path) -> int:
        """Count lines in a file."""
        try:
            with path.open('r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def _read_text(self, path: Path) -> str:
        """Read text from a file."""
        try:
            with path.open('r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""
    
    @abstractmethod
    def score(self, model: 'Model') -> Dict[str, float]:
        """
        Score a model and return the result.
        
        Args:
            model: The Model object to score
            
        Returns:
            A dictionary of scores
        """
        pass
