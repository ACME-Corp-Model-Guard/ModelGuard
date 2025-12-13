from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Union

from src.logutil import clogger
from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts.model_artifact import ModelArtifact


class AvailabilityMetric(Metric):
    """
    Availability Metric

    Measures whether a model has linked artifacts and linkable metadata:
      1. Dataset availability (linked or linkable)
      2. Code availability (linked or linkable)

    Scoring:
        +0.25 if dataset_name exists (linkable when dataset uploaded)
        +0.25 if dataset_artifact_id exists (actual link)
        +0.25 if code_name exists (linkable when code uploaded)
        +0.25 if code_artifact_id exists (actual link)

    This allows models to score 0.5 just by having metadata that enables future linking.

    Output Format:
        { "availability": <float in [0.0, 1.0]> }
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
            1. Check for linkable metadata (dataset_name, code_name)
            2. Check for actual linked artifacts (dataset_artifact_id, code_artifact_id)
            3. Compute score:
                - +0.25 for each linkable metadata field
                - +0.25 for each actual linked artifact

        Returns:
            {"availability": float} on success
        """

        clogger.debug(
            f"[availability] Scoring model {model.artifact_id} "
            f"(dataset_name={model.dataset_name}, dataset_id={model.dataset_artifact_id}, "
            f"code_name={model.code_name}, code_id={model.code_artifact_id})"
        )

        try:
            score = 0.0

            # ------------------------------------------------------------------
            # Step 1 — Check dataset linkability and availability
            # ------------------------------------------------------------------
            if model.dataset_name:
                score += 0.25  # Linkable when dataset is uploaded
            if model.dataset_artifact_id:
                score += 0.25  # Actually linked

            # ------------------------------------------------------------------
            # Step 2 — Check code linkability and availability
            # ------------------------------------------------------------------
            if model.code_name:
                score += 0.25  # Linkable when code is uploaded
            if model.code_artifact_id:
                score += 0.25  # Actually linked

            clogger.debug(f"[availability] Model {model.artifact_id} → availability={score}")

            return {self.SCORE_FIELD: score}

        except Exception as e:
            clogger.exception(
                f"[availability] Unexpected error scoring availability for "
                f"model {model.artifact_id}",
                extra={"error_type": type(e).__name__},
            )
            return {self.SCORE_FIELD: 0.0}
