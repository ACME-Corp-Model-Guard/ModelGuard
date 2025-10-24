#!/usr/bin/env python3
"""
Abstract base class for all metrics in the ModelGuard system.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Union, Dict, Any, Optional
from pathlib import Path


class AbstractMetric(ABC):
    """
    Abstract base class for all metrics.
    Defines the interface that all concrete metric classes must implement.
    """
    
    def __init__(self, name: str):
        """
        Initialize the metric.
        
        Args:
            name: The name of this metric
        """
        self.name = name
    
    @abstractmethod
    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        """
        Score a model and return the result.
        
        Args:
            model: The Model object to score
            
        Returns:
            Either a float score or a dictionary of scores
        """
        pass
    
    def get_metric_name(self) -> str:
        """Get the name of this metric."""
        return self.name
    
    def _is_git_repo(self, path: Path) -> bool:
        """
        Check if a path is a git repository.
        
        Args:
            path: Path to check
            
        Returns:
            True if the path is a git repository
        """
        return (path / ".git").exists()
    
    def _count_lines(self, path: Path) -> int:
        """
        Count lines in a file or directory.
        
        Args:
            path: Path to count lines in
            
        Returns:
            Number of lines
        """
        if path.is_file():
            try:
                with path.open('r', encoding='utf-8', errors='ignore') as f:
                    return sum(1 for _ in f)
            except Exception:
                return 0
        elif path.is_dir():
            total_lines = 0
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    total_lines += self._count_lines(file_path)
            return total_lines
        return 0
    
    def _saturating_scale(
        self,
        x: float,
        *,
        knee: float,
        max_x: float
    ) -> float:
        """
        Scale value to [0,1] with a knee point and max_x saturation.
        
        Args:
            x: Value to scale
            knee: Knee point for scaling
            max_x: Maximum value for saturation
            
        Returns:
            Scaled value between 0 and 1
        """
        if x <= 0:
            return 0.0
        if x >= max_x:
            return 1.0
        
        # Linear scaling with knee point
        if x <= knee:
            return x / knee * 0.5
        else:
            return 0.5 + (x - knee) / (max_x - knee) * 0.5
    
    def _clamp01(self, x: float) -> float:
        """
        Clamp a value to the range [0, 1].
        
        Args:
            x: Value to clamp
            
        Returns:
            Clamped value between 0 and 1
        """
        return max(0.0, min(1.0, x))
    
    def _read_text(self, path: Path) -> str:
        """
        Read text from a file.
        
        Args:
            path: Path to the file
            
        Returns:
            File contents as string
        """
        try:
            with path.open('r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""
    
    def _glob(self, base: Path, patterns: list[str]) -> list[Path]:
        """
        Find files matching patterns.
        
        Args:
            base: Base directory to search
            patterns: List of glob patterns
            
        Returns:
            List of matching file paths
        """
        files: list[Path] = []
        for pattern in patterns:
            files.extend(base.glob(pattern))
        return list(files)
    
    def _as_path(self, path_or_url: str) -> Optional[Path]:
        """
        Convert a string to a Path if it's a local path.
        
        Args:
            path_or_url: String that might be a path or URL
            
        Returns:
            Path object if it's a local path, None otherwise
        """
        if (path_or_url.startswith("http://") or 
            path_or_url.startswith("https://")):
            return None
        p = Path(path_or_url)
        if p.exists():
            return p
        return None
    
    def _stable_unit_score(self, key: str, salt: str) -> float:
        """
        Generate a stable unit score based on a key and salt.
        
        Args:
            key: Key to generate score from
            salt: Salt for the hash
            
        Returns:
            Stable score between 0 and 1
        """
        import hashlib
        h = hashlib.md5((key + "::" + salt).encode("utf-8")).hexdigest()
        v = int(h[:8], 16) / 0xFFFFFFFF
        return self._clamp01(v)
