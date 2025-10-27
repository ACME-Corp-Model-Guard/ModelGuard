#!/usr/bin/env python3
"""
Dataset Quality Metric implementation.
"""

import csv
from pathlib import Path
from typing import Dict

from .metric import Metric


class DatasetQualityMetric(Metric):
    """
    Dataset quality metric for evaluating dataset quality.
    """

    DATA_GLOBS = ["**/*.csv", "**/*.tsv", "**/*.jsonl"]

    def score(self, path_or_url: str) -> Dict[str, float]:
        p = self._as_path(path_or_url)
        if not p:
            return {
                "dataset_quality": self._stable_unit_score(
                    path_or_url,
                    "dataset_quality",
                )
            }

        data_files = self._glob(p, self.DATA_GLOBS)
        if not data_files:
            return {"dataset_quality": 0.5}

        # Evaluate at most first 5 files for speed
        score_acc = 0.0
        counted = 0
        for f in data_files[:5]:
            if f.suffix.lower() in {".csv", ".tsv"}:
                delim = "\t" if f.suffix.lower() == ".tsv" else ","
                score_acc += self._score_csv(f, delimiter=delim)
                counted += 1
            elif f.suffix.lower() == ".jsonl":
                score_acc += self._score_jsonl(f)
                counted += 1

        if counted == 0:
            return {"dataset_quality": 0.5}

        return {"dataset_quality": self._clamp01(score_acc / counted)}

    def _score_csv(self, path: Path, delimiter: str) -> float:
        rows = self._read_csv_rows(path, delimiter)
        if not rows:
            return 0.3

        header_score = self._score_csv_header(rows[0])
        consistency_score, blank_ratio = self._score_csv_rows(rows)

        s = header_score + consistency_score
        if blank_ratio >= 0.1:
            s -= 0.1

        return self._clamp01(s)

    def _read_csv_rows(self, path: Path, delimiter: str) -> list[list[str]]:
        """Read up to 200 rows from a CSV/TSV file."""
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                reader = csv.reader(fh, delimiter=delimiter)
                return [row for i, row in enumerate(reader) if i < 200]
        except Exception:
            return []

    def _score_csv_header(self, header: list[str]) -> float:
        """Score the header row based on uniqueness and presence of alpha names."""
        if not header:
            return 0.0
        unique_names = len(set(header)) == len(header)
        alpha_count = sum(1 for x in header if x and not x.isdigit())
        header_is_alpha = alpha_count >= max(1, int(0.6 * len(header)))
        return 0.2 if (unique_names and header_is_alpha) else 0.0

    def _score_csv_rows(self, rows: list[list[str]]) -> tuple[float, float]:
        """Score row consistency and return blank row ratio."""
        counts = [len(r) for r in rows if any(cell.strip() for cell in r)]
        if not counts:
            return 0.0, 1.0

        mode = max(set(counts), key=counts.count)
        consistency = counts.count(mode) / len(counts)

        if consistency >= 0.98:
            consistency_score = 0.5
        elif consistency >= 0.9:
            consistency_score = 0.35
        elif consistency >= 0.75:
            consistency_score = 0.2
        else:
            consistency_score = 0.0

        blank_rows = sum(1 for r in rows if not any(cell.strip() for cell in r))
        blank_ratio = blank_rows / len(rows)

        return consistency_score, blank_ratio

    def _score_jsonl(self, path: Path) -> float:
        total = 0
        valid = 0
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh):
                    if i >= 200:
                        break
                    line = line.strip()
                    total += 1
                    if line.startswith("{") and line.endswith("}"):
                        valid += 1
        except Exception:
            return 0.4

        if total == 0:
            return 0.3

        ratio = valid / total
        if ratio >= 0.98:
            return 0.8
        if ratio >= 0.9:
            return 0.7
        if ratio >= 0.75:
            return 0.6
        return 0.4
