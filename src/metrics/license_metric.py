from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from src.logger import logger
from .metric import Metric

if TYPE_CHECKING:
    # Import only for type checking to avoid circular imports at runtime
    from src.artifacts.model_artifact import ModelArtifact


class LicenseMetric(Metric):
    """
    LicenseMetric

    Computes a license compatibility score for a model based on the license information
    captured during artifact ingestion.

    The ingestion pipeline is responsible for populating license metadata (ex: from HuggingFace
    model cards or GitHub repository metadata) into the ModelArtifact. This metric only reads
    the metadata and does not perform any further operations.

    Scoring (0.0 - 1.0)
    -------------------
    - 1.0: Known license and fully compatible (ex: MIT, Apache-2.0)
    - 0.5: Unknown, ambiguous, or undetermined license.
    - 0.0: Known but incompatible license (ex: GPL-3.0, AGPL-3.0, Proprietary)

    Output
    ------
        {"license": <float score>}
    """

    SCORE_FIELD = "license"
    DEFAULT_SCORE = 0.5

    # Map normalized license identifier scores, anything not listed will default to 0.5.
    LICENSE_COMPATIBILITY: Dict[str, float] = {
        # Compatible (1.0)
        "mit": 1.0,
        "bsd-2-clause": 1.0,
        "bsd-3-clause": 1.0,
        "lgpl-2.1": 1.0,
        "lgpl-2.1-or-later": 1.0,
        "gpl-2.0-or-later": 1.0,
        "apache-2.0": 1.0,
        # Ambiguous / Limited (0.5)
        "gpl-2.0": 0.5,
        "mpl-2.0": 0.5,
        "unlicense": 0.5,
        # Incompatible (0.0)
        "gpl-3.0": 0.0,
        "lgpl-3.0": 0.0,
        "agpl-3.0": 0.0,
        "proprietary": 0.0,
    }

    def score(self, model: ModelArtifact) -> Dict[str, float]:
        """
        Compute a license compatibilty score for a ModelArtifact

        Resolution order for the license string identifier:
        1. model.license
        2. model.metadata["license"]
        3. model.metadata["metadata"]["license"]

        The resolved string is normalized to lowercase and mapped via LICENSE_COMPATIBILITY.
        Any unmapped value defaults to DEFAULT_SCORE = 0.5.

        Returns:
            dict: {"license": <float score> }

        """

        logger.debug(
            "Calculating license metric for artifact_id=%r license=%r",
            getattr(model, "artifact_id", None),
            getattr(model, "license", None),
        )

        try:
            """
            Step 1 - Start with the dedicated model.license field
            """
            license_id = (getattr(model, "license", "") or "").strip()

            """
            Step 3 - Normalize and map to score
            """
            normalized = license_id.lower()
            score = self.LICENSE_COMPATIBILITY.get(normalized, self.DEFAULT_SCORE)

            logger.debug(
                "License metric result for artifact_id=%r: "
                "license_id=%r normalized=%r score=%.3f",
                getattr(model, "artifact_id", None),
                license_id,
                normalized,
                score,
            )

            return {self.SCORE_FIELD: float(score)}
        except Exception as exc:
            # If anything goes wrong during scoring, treat the license as
            # ambiguous/unknown/unrecognized, and apply a score of 0.5
            logger.error(
                "Failed to calculate license metric for artifact_id=%r: %s",
                exc,
                exc_info=True,
            )
        return {self.SCORE_FIELD: float(self.DEFAULT_SCORE)}
