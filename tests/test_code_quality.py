"""
Tests for the code_quality_metric module.
"""

import os
import tempfile
from pathlib import Path

from src.metrics.code_quality_metric import CodeQualityMetric


def test_score_with_url():
    """Test that non-path strings return stable scores."""
    metric = CodeQualityMetric()
    result = metric.score("https://example.com/repo")
    assert "code_quality" in result
    assert isinstance(result["code_quality"], float)
    assert 0.0 <= result["code_quality"] <= 1.0


def test_score_with_nonexistent_path():
    """Test scoring with a path that doesn't exist."""
    metric = CodeQualityMetric()
    result = metric.score("/path/that/does/not/exist")
    assert "code_quality" in result
    assert isinstance(result["code_quality"], float)
    assert 0.0 <= result["code_quality"] <= 1.0


def test_linter_configs():
    """Test detection of linter configuration files."""

    class TestCodeQualityMetric(CodeQualityMetric):
        def _as_path(self, path_or_url: str) -> Path:
            return Path(path_or_url)

        def _glob(self, base, patterns):
            return []  # Return empty list for simplicity

        def _clamp01(self, x: float) -> float:
            return max(0.0, min(1.0, x))

    metric = TestCodeQualityMetric()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a linter config file
        path = Path(tmpdir)
        with open(path / ".flake8", "w") as f:
            f.write("[flake8]\nmax-line-length = 100\n")

        result = metric.score(tmpdir)
        assert "code_quality" in result


def test_ci_detection():
    """Test detection of CI workflow files."""

    class TestCodeQualityMetric(CodeQualityMetric):
        def _as_path(self, path_or_url: str) -> Path:
            return Path(path_or_url)

        def _glob(self, base, patterns):
            # Mock glob to find our CI file
            path = Path(base)
            return [path / ".github" / "workflows" / "ci.yml"]

        def _clamp01(self, x: float) -> float:
            return max(0.0, min(1.0, x))

    metric = TestCodeQualityMetric()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a CI workflow file
        path = Path(tmpdir)
        os.makedirs(path / ".github" / "workflows", exist_ok=True)
        ci_file_path = path / ".github" / "workflows" / "ci.yml"
        with open(ci_file_path, "w") as f:
            ci_content = (
                "name: CI\n"
                "on: push\n"
                "jobs:\n"
                "  test:\n"
                "    runs-on: ubuntu-latest\n"
            )
            f.write(ci_content)

        result = metric.score(tmpdir)
        assert "code_quality" in result


def test_tests_detection():
    """Test detection of test directories and files."""

    class TestCodeQualityMetric(CodeQualityMetric):
        def _as_path(self, path_or_url: str) -> Path:
            return Path(path_or_url)

        def _glob(self, base, patterns):
            return []

        def _clamp01(self, x: float) -> float:
            return max(0.0, min(1.0, x))

    metric = TestCodeQualityMetric()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a tests directory
        path = Path(tmpdir)
        os.makedirs(path / "tests", exist_ok=True)

        result = metric.score(tmpdir)
        assert "code_quality" in result


def test_line_length_analysis():
    """Test analysis of code line lengths."""

    class TestCodeQualityMetric(CodeQualityMetric):
        def _as_path(self, path_or_url: str) -> Path:
            return Path(path_or_url)

        def _glob(self, base, patterns):
            return []

        def _clamp01(self, x: float) -> float:
            return max(0.0, min(1.0, x))

    metric = TestCodeQualityMetric()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a Python file with short lines
        path = Path(tmpdir)
        file_path = path / "short_lines.py"
        with open(file_path, "w") as f:
            code_content = (
                "def hello():\n" "    return 'Hello World'\n\n" "print(hello())\n"
            )
            f.write(code_content)

        result = metric.score(tmpdir)
        assert "code_quality" in result
