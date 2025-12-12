from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Union

from src.logutil import clogger
from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts.model_artifact import ModelArtifact


class AvailabilityMetric(Metric):
    """
    Availability Metric

    Measures whether a model has both:
      1. An available dataset (dataset_artifact_id not None)
      2. An available code artifact (code_artifact_id not None)

    Scoring:
        +0.5 if dataset is available
        +0.5 if code is available

    Output Format:
        { "availability": <float in {0.0, 0.5, 1.0}> }
    """

    SCORE_FIELD = "availability"

    # ====================================================================================
    # SCORE METHOD
    # ====================================================================================
    # Computes a simple availability score based on linked artifact presence.
    # ====================================================================================

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Evaluate availability for a ModelArtifact.

        Steps:
            1. Check whether dataset_artifact_id is present
            2. Check whether code_artifact_id is present
            3. Compute score:
                - 0.0 : neither available
                - 0.5 : exactly one available
                - 1.0 : both available

        Returns:
            {"availability": float} on success
        """

        clogger.debug(
            f"[availability] Scoring model {model.artifact_id} "
            f"(dataset_id={model.dataset_artifact_id}, code_id={model.code_artifact_id})"
        )

        try:
            # ------------------------------------------------------------------
            # Step 1 — Check dataset availability
            # ------------------------------------------------------------------
            dataset_available = model.dataset_artifact_id is not None

            # ------------------------------------------------------------------
            # Step 2 — Check code availability
            # ------------------------------------------------------------------
            code_available = model.code_artifact_id is not None

            # ------------------------------------------------------------------
            # Step 3 — Compute score
            # ------------------------------------------------------------------
            score = 0.0
            if dataset_available:
                score += 0.5
            if code_available:
                score += 0.5

            clogger.debug(
                f"[availability] Model {model.artifact_id} → availability={score}"
            )

            return {self.SCORE_FIELD: score}

        except Exception as e:
            clogger.exception(
                f"[availability] Unexpected error scoring availability for "
                f"model {model.artifact_id}",
                extra={"error_type": type(e).__name__},
            )
            return {self.SCORE_FIELD: 0.0}
