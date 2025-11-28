from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict

from src.logger import logger

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact

class LicenseMetric(Metric):
    """
    License metric for evaluating model licensing.

    This is a stub implementation that will be filled out when
    S3 and SageMaker/Bedrock integration is available.

    Scoring (0.0 - 1.0)
    -------------------
    - 1.0: Known license and fully compatible (ex: MIT, Apache-2.0)
    - 0.5: Unknown, ambiguous, or undetermined license.
    - 0.0: Known but incompatible license (ex: GPL-3.0, AGPL-3.0, Proprietary)

    Output
    ------
    Returns a dictionary in the standard metric format:
    {"license": <float score>}
    So that it can be consumed by the calculate_net_score method, and persisted 
    in ModelArtifact.scores.

    """
    
    SCORE_FIELD = "license"

    #Mapping
    LICENSE_COMPATIBILITY: Dict[str, float] = {
        # Compatible License (1.0)
        "mit": 1.0,
        "bsd-2-clause": 1.0,
        "bsd-3-clause": 1.0,
        "lgpl-2.1": 1.0,
        "lgpl-2.1-or-later": 1.0,
        "gpl-2.0-or-later": 1.0,
         "apache-2.0": 1.0,

        #Ambiguous License (0.5)
        "gpl-2.0": 0.5,
        "mpl-2.0": 0.5,
        "unlicense": 0.5,

        # Incompatible License (0.0)
        "gpl-3.0": 0.0,
        "lgpl": 0.0,
        "agpl-3.0": 0.0,
        "proprietary": 0.0
    }

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model license.

        Compute a license compatibilty score for a ModelArtifact

        Resolution order for the license identifier:
        1. model.license (top-level field populated during ingestion, 
        ex: from HuggingFace model card "license")
        2. model.metadata["license"]
        3. model.metadata["metadata"]["license"] --> Fallback for nested shapes

        The resolved license string (SPDX-style where possible) is normalized to 
        lowercase and mapped using LICENSE_COMPATIBILITY. Any unkonw or unmapped license falls back 
        to the value 0.5 as an "unambiguous license"

        Returns:
            dict: {"license": <float score> }
            
        """

        logger.debug(
            "[license] Scoring model %s (license=%r, metadata=%r)",
            getattr(model, "artifact_id", None),
            getattr(model, "license", None),
            getattr(model, "metadata", None)
        )

        try:
            """
            Step 1 - Start with the dedicated model.license field
            """
            license_id = (getattr(model, "license", "") or "").strip() or "unknown"

            # Treat common "unknown-ish" values as unknown
            if license_id.lower() in ("", "unknown", "none", "no-license", "nolicense"):
                license_id = "unknown"

            """
            Step 2 - Fallback to metadata if needed
            """
            if license_id == "unknown":
                meta = getattr(model, "metadata", {}) or {}

                # Some ingestion paths may stash license alongside other metadata
                meta_license = (
                    meta.get("license")
                    or meta.get("metadata", {}).get("license")
                )

                if isinstance(meta_license, str) and meta_license.strip():
                    license_id = meta_license.strip()

            """
            Step 3 - Normalize and map to a score
            """
            license_key = (license_id or "unknown").lower()
            license_score = self.LICENSE_COMPATIBILITY.get(license_key, 0.5)

            logger.debug(
                "[License] Model %s -> license_id=%r -> score=%.3f",
                getattr(model, "artifact_id", None),
                license_key,
                license_score
            )

            return {self.SCORE_FIELD: float(license_score)}
        
        except Exception as exc:
            """ 
            Edge case/Error handling: if anything goes wrong, treat 
            the license as ambiguous/unknown
            """
            logger.error(
                "[license] Failed to score license for model %s: %s",
                getattr(model, "artifact_id", None),
                exc,
                exc_info=True
            )
            return {self.SCORE_FIELD: 0.5}




        # TODO: Implement actual license scoring when S3 integration is ready
        # For now, return a placeholder score
        return {"license": 0.5}
