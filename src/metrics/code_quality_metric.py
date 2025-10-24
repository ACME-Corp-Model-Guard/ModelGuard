import re
from typing import Dict, Union

from .abstract_metric import AbstractMetric


class CodeQualityMetric(AbstractMetric):
    """
    Heuristics (language-agnostic):
      + Presence of lint/format configs: .flake8, pyproject, .pylintrc,
        .editorconfig, .eslintrc.*, .prettierrc.*
      + CI present: .github/workflows/*
      + Tests present: tests/ or *_test.* files
      + Average line length <= 120 over code files
      - Penalize excessive TODO/FIXME
    Fallback: stable placeholder if not a local path.
    """

    LINTER_GLOBS = [
        ".flake8",
        "pyproject.toml",
        ".pylintrc",
        ".editorconfig",
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.json",
        ".prettierrc",
        ".prettierrc.js",
        ".prettierrc.json",
    ]

    CI_GLOB = [".github/workflows/*.yml", ".github/workflows/*.yaml"]

    TEST_HINTS = ["tests", "test", "spec"]

    CODE_EXTS = {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".cs",
        ".go",
        ".rb",
        ".cpp",
        ".c",
        ".hpp",
        ".h",
        ".rs",
        ".php",
    }

    def __init__(self):
        super().__init__("code_quality")

    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        # TODO: Implement actual code quality scoring when S3 integration is ready
        # For now, return a placeholder score based on model name
        code_quality_score = self._stable_unit_score(model.name, "code_quality")
        return {"code_quality": code_quality_score}

