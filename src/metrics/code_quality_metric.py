from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Dict

from src.artifacts.code_artifact import CodeArtifact
from src.logger import logger
from src.metrics.metric import Metric
from src.storage.dynamo_utils import load_artifact_metadata
from src.storage.file_extraction import extract_relevant_files
from src.storage.s3_utils import download_artifact_from_s3
from src.utils.llm_analysis import (
    ask_llm,
    build_file_analysis_prompt,
    extract_llm_score_field,
)

if TYPE_CHECKING:
    from src.artifacts.model_artifact import ModelArtifact


class CodeQualityMetric(Metric):
    """
    Code Quality Metric

    Evaluates the readability, maintainability, structure, and general
    engineering quality of a code artifact by:

      1. Fetching its code bundle (.tar.gz) from S3
      2. Extracting a representative subset of source files
      3. Submitting files to a Bedrock LLM for evaluation
      4. Returning the LLM-generated numeric score

    Output Format:
        { "code_quality": <float in [0.0, 1.0]> }
    """

    SCORE_FIELD = "code_quality"
    INCLUDE_EXT = [".py", ".txt", ".md"]
    MAX_FILES = 5
    MAX_CHARS_PER_FILE = 4000

    METRIC_DESCRIPTION = """
This metric evaluates the overall quality of a code repository, including:
- Organization and modularity
- Readability and clarity of logic
- Documentation, comments, and coding conventions
- Maintainability and extensibility
- General adherence to good software engineering practices
"""

    # ====================================================================================
    # SCORE METHOD
    # ====================================================================================

    def score(self, model: ModelArtifact) -> Dict[str, float]:
        """
        Execute the complete code-quality evaluation pipeline.

        Returns:
            {"code_quality": float} on success
            {"code_quality": 0.0} on any failure
        """

        # ------------------------------------------------------------------
        # Step 0 — Identify code artifact
        # ------------------------------------------------------------------
        if not model.code_artifact_id:
            logger.warning(
                f"[code_quality] No code artifact_id for {model.artifact_id}"
            )
            return {self.SCORE_FIELD: 0.0}

        code_artifact = load_artifact_metadata(model.code_artifact_id)
        if not isinstance(code_artifact, CodeArtifact):
            logger.warning(
                f"[code_quality] Missing or invalid code artifact for {model.artifact_id}"
            )
            return {self.SCORE_FIELD: 0.0}

        # ------------------------------------------------------------------
        # Step 1 — Download tarball from S3
        # ------------------------------------------------------------------
        tmp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        try:
            logger.debug(
                f"[code_quality] Downloading code bundle for {code_artifact.artifact_id}"
            )

            download_artifact_from_s3(
                artifact_id=code_artifact.artifact_id,
                s3_key=code_artifact.s3_key,
                local_path=tmp_tar,
            )

            # ------------------------------------------------------------------
            # Step 2 — Extract relevant source files
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
                    f"[code_quality] No relevant files extracted for {code_artifact.artifact_id}"
                )
                return {self.SCORE_FIELD: 0.0}

            # ------------------------------------------------------------------
            # Step 3 — Build LLM prompt
            # ------------------------------------------------------------------
            prompt = build_file_analysis_prompt(
                metric_name="Code Quality",
                score_name=self.SCORE_FIELD,
                files=files,
                metric_description=self.METRIC_DESCRIPTION,
            )

            # ------------------------------------------------------------------
            # Step 4 — Ask LLM
            # ------------------------------------------------------------------
            response = ask_llm(prompt, return_json=True)

            # ------------------------------------------------------------------
            # Step 5 — Extract score using shared helper
            # ------------------------------------------------------------------
            score = extract_llm_score_field(response, self.SCORE_FIELD)

            if score is None:
                logger.error(
                    f"[code_quality] Invalid score returned for {code_artifact.artifact_id}: "
                    f"{response}"
                )
                return {self.SCORE_FIELD: 0.0}

            return {self.SCORE_FIELD: score}

        except Exception as e:
            logger.error(
                f"[code_quality] Evaluation failed for {code_artifact.artifact_id}: {e}",
                exc_info=True,
            )
            return {self.SCORE_FIELD: 0.0}

        finally:
            # Cleanup temporary tarball
            try:
                if os.path.exists(tmp_tar):
                    os.unlink(tmp_tar)
            except Exception:
                logger.warning(f"[code_quality] Failed to remove temp file {tmp_tar}")
