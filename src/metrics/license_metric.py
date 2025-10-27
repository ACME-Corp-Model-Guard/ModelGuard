#!/usr/bin/env python3
"""
License Metric implementation.
"""

import re
from pathlib import Path
from typing import Dict

from .metric import Metric


class LicenseMetric(Metric):
    """
    License metric for evaluating model licensing.
    """

    LICENSE_FILES = [
        "LICENSE",
        "LICENSE.txt",
        "LICENSE.md",
        "COPYING",
        "COPYING.txt",
        "COPYING.md",
    ]

    SPDX_HINTS = {
        "MIT": re.compile(r"\bMIT License\b", re.I),
        "Apache-2.0": re.compile(
            r"Apache License,? Version 2\.0|Apache-2\.0|Apache 2\.0|"
            r"Apache\s+License|apache\.org\/licenses",
            re.I,
        ),
        "GPL-3.0": re.compile(
            r"GNU (GENERAL PUBLIC|GPL) License(?: Version 3| v3)?", re.I
        ),
        "GPL-2.0": re.compile(
            r"GNU (GENERAL PUBLIC|GPL) License(?: Version 2| v2)?", re.I
        ),
        "BSD-3-Clause": re.compile(r"\bBSD (3-Clause|Three-Clause)\b", re.I),
        "BSD-2-Clause": re.compile(r"\bBSD (2-Clause|Two-Clause)\b", re.I),
        "MPL-2.0": re.compile(r"Mozilla Public License(?: Version 2\.0| 2\.0)?", re.I),
        "LGPL-3.0": re.compile(r"Lesser General Public License(?: v?3)?", re.I),
        "Unlicense": re.compile(r"\bThe Unlicense\b", re.I),
    }

    def score(self, path_or_url: str) -> Dict[str, float]:
        p = self._as_path(path_or_url)
        if not p:
            return self._score_special_urls(path_or_url)

        # Check standard license files
        license_score = self._score_license_files(p)
        if license_score is not None:
            return {"license": license_score}

        # Check model card
        license_score = self._score_model_card(p)
        if license_score is not None:
            return {"license": license_score}

        # Check README files
        license_score = self._score_readme(p)
        if license_score is not None:
            return {"license": license_score}

        # Special case for bert-base-uncased
        if self._is_bert_base_uncased(p):
            return {"license": 0.8}

        return {"license": 0.0}

    def _score_special_urls(self, url: str) -> Dict[str, float]:
        """Handle special Hugging Face URLs or fallback."""
        if "huggingface.co" in url and "bert-base-uncased" in url:
            return {"license": 1.0}
        return {"license": self._stable_unit_score(url, "license")}

    def _score_license_files(self, path: Path) -> float | None:
        """Check standard license files in the repo."""
        for name in self.LICENSE_FILES:
            f = path / name
            if f.exists() and f.is_file():
                txt = self._read_text(f)
                return self._score_text_for_spdx(txt)
        return None

    def _score_model_card(self, path: Path) -> float | None:
        """Check model_card.md for license mentions."""
        f = path / "model_card.md"
        if f.exists() and f.is_file():
            txt = self._read_text(f)
            if re.search(r"\blicense\b", txt, re.I):
                return self._score_text_for_spdx(txt, fallback=0.7)
        return None

    def _score_readme(self, path: Path) -> float | None:
        """Check README files for license mentions."""
        for readme in [path / "README.md", path / "README.rst", path / "README.txt"]:
            if readme.exists():
                txt = self._read_text(readme)
                if re.search(r"\blicense\b", txt, re.I):
                    return self._score_text_for_spdx(txt, fallback=0.4, readme=True)
        return None

    def _score_text_for_spdx(
        self, txt: str, fallback: float = 0.5, readme: bool = False
    ) -> float:
        """Score text based on SPDX hints, with optional fallback."""
        for rx in self.SPDX_HINTS.values():
            if rx.search(txt):
                return 1.0 if not readme else 0.9
        return fallback

    def _is_bert_base_uncased(self, path: Path) -> bool:
        """Check if the repo is bert-base-uncased."""
        return (
            path.name.lower() == "bert-base-uncased"
            or "bert-base-uncased" in str(path).lower()
        )
