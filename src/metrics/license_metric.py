from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from src.logging import clogger
from src.metrics.metric import Metric

if TYPE_CHECKING:
    from src.artifacts.model_artifact import ModelArtifact


class LicenseMetric(Metric):
    """
    License Metric (Phase 1)

    Scores the model license based solely on the `ModelArtifact.license` field.
    No external lookup or metadata fallbacks are required because the ingestion
    pipeline guarantees:
        - If license information exists, it is stored in `model.license`
        - If it does not exist, `model.license` == "unknown"

    Scoring:
        1.0 — Permissive license (MIT, BSD, Apache-2.0)
        0.5 — Unknown or unrecognized license
        0.0 — Restrictive / copyleft / proprietary (GPL-3.0, AGPL, Proprietary)

    Output:
        {"license": <float>}
    """

    SCORE_FIELD = "license"
    DEFAULT_SCORE = 0.5

    LICENSE_COMPATIBILITY: Dict[str, float] = {
        # Permissive
        "mit": 1.0,
        "bsd": 1.0,
        "bsd-2-clause": 1.0,
        "bsd-3-clause": 1.0,
        # Ambiguous
        "apache-2.0": 0.5,
        "apache": 0.5,
        "mpl-2.0": 0.5,
        "unlicense": 0.5,
        "unknown": 0.5,
        # Restrictive
        "gpl-3.0": 0.0,
        "agpl-3.0": 0.0,
        "proprietary": 0.0,
    }

    # ============================================================================
    # SCORE METHOD
    # ============================================================================

    def score(self, model: ModelArtifact) -> Dict[str, float]:
        """
        Evaluate the license score using only model.license.

        Returns:
            {"license": float}
        """

        try:
            raw = model.license or "unknown"
            normalized = self._normalize_license(raw)

            score = self.LICENSE_COMPATIBILITY.get(
                normalized,
                self.DEFAULT_SCORE,
            )

            clogger.debug(
                f"[license] artifact_id={model.artifact_id} "
                f"raw={raw!r} normalized={normalized!r} score={score}"
            )

            return {self.SCORE_FIELD: float(score)}

        except Exception as exc:
            clogger.error(
                f"[license] Failed scoring artifact_id={model.artifact_id}: {exc}",
                exc_info=True,
            )
            return {self.SCORE_FIELD: float(self.DEFAULT_SCORE)}

    # ============================================================================
    # HELPERS
    # ============================================================================

    def _normalize_license(self, s: str) -> str:
        """
        Normalize common license string variations:
            - Remove words like "license" / "version"
            - Collapse spaces and uppercase
            - Convert "Apache License 2.0" → "apache-2.0"
            - Handle "MIT License", "BSD 3-Clause", etc.
        """

        s = s.strip().lower()

        s = s.replace("license", "").replace("version", "").strip()
        s = s.replace("(", "").replace(")", "").strip()
        s = s.replace(" ", "-")

        # Standardize Apache variants
        if s.startswith("apache") and "2" in s:
            return "apache-2.0"

        # Standardize MIT variants
        if s.startswith("mit"):
            return "mit"

        # Standardize BSD variants
        if s.startswith("bsd"):
            return s if s in self.LICENSE_COMPATIBILITY else "bsd"

        return s or "unknown"
