from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Dict

from src.logger import logger
from src.metrics.metric import Metric
from src.storage.s3_utils import download_artifact_from_s3
from src.storage.file_extraction import extract_relevant_files
from src.utils.llm_analysis import (
    ask_llm,
    build_file_analysis_prompt,
    extract_llm_score_field,
)

if TYPE_CHECKING:
    from src.artifacts.model_artifact import ModelArtifact


class RampUpMetric(Metric):
    """
    Ramp-Up Time Metric

    Uses LLM analysis of README, documentation, examples, and config files
    to assess how easy it is for an engineer to begin using a model.
    """

    SCORE_FIELD = "ramp_up"
    INCLUDE_EXT = [".md", ".txt", ".json", ".py"]
    MAX_FILES = 5
    MAX_CHARS_PER_FILE = 4000

    METRIC_DESCRIPTION = """
This metric evaluates how easy it is for an engineer to onboard and begin using a model:
- Presence and clarity of README or documentation
- Installation and setup instructions
- Usage examples or quickstart guides
- Configuration details or dependency information
- Overall ease of understanding the model's structure and usage
"""

    # ============================================================================
    # SCORE METHOD
    # ============================================================================

    def score(self, model: ModelArtifact) -> Dict[str, float]:
        """
        Compute a ramp-up score based on LLM evaluation of documentation.

        Returns:
            {"ramp_up": float}
        """

        # ------------------------------------------------------------------
        # Step 0 — Validate S3 key
        # ------------------------------------------------------------------
        if not model.s3_key:
            logger.warning(f"[ramp_up] Model {model.artifact_id} missing s3_key")
            return {self.SCORE_FIELD: 0.0}

        # Use the CodeQualityMetric temp-file pattern
        tmp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        try:
            # ------------------------------------------------------------------
            # Step 1 — Download model tarball from S3
            # ------------------------------------------------------------------
            logger.debug(f"[ramp_up] Downloading bundle for model {model.artifact_id}")

            download_artifact_from_s3(
                artifact_id=model.artifact_id,
                s3_key=model.s3_key,
                local_path=tmp_tar,
            )

            # ------------------------------------------------------------------
            # Step 2 — Extract relevant documentation files
            # ------------------------------------------------------------------
            files = extract_relevant_files(
                tar_path=tmp_tar,
                include_ext=self.INCLUDE_EXT,
                max_files=self.MAX_FILES,
                max_chars=self.MAX_CHARS_PER_FILE,
                prioritize_readme=True,
            )

            if not files:
                logger.warning(
                    f"[ramp_up] No relevant files extracted for model {model.artifact_id}"
                )
                return {self.SCORE_FIELD: 0.0}

            # ------------------------------------------------------------------
            # Step 3 — Build LLM prompt
            # ------------------------------------------------------------------
            prompt = build_file_analysis_prompt(
                metric_name="Ramp-Up Time",
                score_name=self.SCORE_FIELD,
                files=files,
                metric_description=self.METRIC_DESCRIPTION,
            )

            # ------------------------------------------------------------------
            # Step 4 — Query LLM (JSON mode)
            # ------------------------------------------------------------------
            response = ask_llm(prompt, return_json=True)

            # ------------------------------------------------------------------
            # Step 5 — Extract score
            # ------------------------------------------------------------------
            score = extract_llm_score_field(response, self.SCORE_FIELD)

            if score is None:
                logger.error(
                    f"[ramp_up] Invalid score for model {model.artifact_id}: {response}"
                )
                return {self.SCORE_FIELD: 0.0}

            return {self.SCORE_FIELD: score}

        except Exception as e:
            logger.error(
                f"[ramp_up] Evaluation failed for model {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {self.SCORE_FIELD: 0.0}

        finally:
            # Cleanup
            try:
                if os.path.exists(tmp_tar):
                    os.unlink(tmp_tar)
            except Exception:
                logger.warning(f"[ramp_up] Failed to remove temp file {tmp_tar}")
