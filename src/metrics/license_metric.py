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

    # Mapping
    LICENSE_COMPATIBILITY: Dict[str, float] = {
        # Compatible (1.0)
        "mit": 1.0,
        "bsd-2-clause": 1.0,
        "bsd-3-clause": 1.0,
        "lgpl-2.1": 1.0,
        "lgpl-2.1-or-later": 1.0,
        "gpl-2.0-or-later": 1.0,
        "apache-2.0": 1.0,

        #Ambiguous / Limited (0.5)
        "gpl-2.0": 0.5,
        "mpl-2.0": 0.5,
        "unlicense": 0.5,

        # Incompatible (0.0)
        "gpl-3.0": 0.0,
        "lgpl-3.0": 0.0,
        "agpl-3.0": 0.0,
        "proprietary": 0.0        
    }

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Compute a license compatibilty score for a ModelArtifact

        Resolution order for the license string identifier:
        1. model.license (top-level field populated during ingestion, 
        ex: from HuggingFace model card "license")
        2. model.metadata["license"]
        3. model.metadata["metadata"]["license"] --> Fallback for nested shapes

        The resolved license string is normalized to lowercase and mapped 
        using LICENSE_COMPATIBILITY. Any unmapped value defaults to 0.5 
        to indicate an unknown/ambiguous license.

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
            license_id = (getattr(model, "license", "") or "").strip()

            if not license_id:
                license_id = "unknown"
            
            # Treat common "unknown-ish" values as unknown
            if license_id.lower() in (
                "",
                "unknown",
                "none",
                "no-license",
                "nolicense"
                ):
                """
                Step 2 - Fallback to metadata if needed
                """
                meta = getattr(model, "metadata", {}) or {}

                meta_license = (
                    meta.get("license") or meta.get("metadata", {}).get("license")
                )

                if isinstance(meta_license, str) and meta_license.strip():
                    license_id = meta_license.strip()
                else:
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
                else:
                    license_id = "unknown"
            
            """
            Step 3 - Normalize and map to a score
            """
            key = license_id.lower()
            score = self.LICENSE_COMPATIBILITY.get(key, 0.5)

            logger.debug(
                "[license] Model %s -> license_id=%r (key=%r) -> score=%.3f",
                getattr(model, "artifact_if", None),
                license_id,
                key,
                score
            )
            return {self.SCORE_FIELD: float(score)}
    
        except Exception as exc:
            """
            As final resort, give a score of 0.5 to any 
            license that has not been given a score up to this point. 
            (Treating it as ambiguous)
            """
            logger.error(
                "[license] Failed to score license for model %s: %s",
                getattr(model, "artifact_id", None),
                exc,
                exc_info=True
            )
            return {self.SCORE_FIELD: 0.5}
