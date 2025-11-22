from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Any, Dict, Union, cast

from src.logger import logger
from src.metrics.metric import Metric
from src.storage.file_extraction import extract_relevant_files
from src.storage.s3_utils import download_artifact_from_s3
from src.utils.llm_analysis import ask_llm, build_file_analysis_prompt

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class CodeQualityMetric(Metric):
    """
    Code Quality Metric

    Evaluates the quality, readability, structure, and maintainability of
    a code artifact by:
      1. Downloading its .tar.gz bundle from S3
      2. Extracting a representative subset of source files
      3. Submitting them to a Bedrock LLM for evaluation
      4. Returning the LLM-generated numeric score

    Output Format:
        { "code_quality": <float in [0.0, 1.0]> }
    """

    SCORE_FIELD = "code_quality"
    INCLUDE_EXT = [".py", ".txt", ".md"]
    MAX_FILES = 5
    MAX_CHARS_PER_FILE = 4000

    # ====================================================================================
    # SCORE METHOD
    # ====================================================================================
    # Executes the complete code-quality evaluation pipeline.
    # ====================================================================================

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Evaluate code quality for a ModelArtifact.

        Steps:
            1. Download S3 artifact bundle
            2. Extract representative source files
            3. Build an LLM evaluation prompt
            4. Ask Bedrock to score the code
            5. Parse and return formatted results

        Returns:
            {"code_quality": float} on success
            {"code_quality": 0.0} on failure
        """

        # ------------------------------------------------------------------
        # Step 1 — Download tarball from S3
        # ------------------------------------------------------------------
        tmp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        try:
            logger.debug(
                f"[code_quality] Downloading artifact {model.artifact_id} from S3"
            )
            download_artifact_from_s3(
                artifact_id=model.artifact_id,
                s3_key=model.s3_key,
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
                    f"[code_quality] No relevant files extracted for {model.artifact_id}"
                )
                return {self.SCORE_FIELD: 0.0}

            # ------------------------------------------------------------------
            # Step 3 — Build prompt
            # ------------------------------------------------------------------
            prompt = build_file_analysis_prompt(
                metric_name="Code Quality",
                score_name=self.SCORE_FIELD,
                files=files,
            )

            # ------------------------------------------------------------------
            # Step 4 — Ask LLM
            # ------------------------------------------------------------------
            response = ask_llm(prompt, return_json=True)

            # Ensure JSON dictionary result
            if not isinstance(response, dict) or self.SCORE_FIELD not in response:
                logger.error(
                    f"[code_quality] Invalid/empty response for {model.artifact_id}: {response}"
                )
                return {self.SCORE_FIELD: 0.0}

            typed_response = cast(Dict[str, Any], response)

            # ------------------------------------------------------------------
            # Step 5 — Return score
            # ------------------------------------------------------------------
            try:
                return {self.SCORE_FIELD: float(typed_response[self.SCORE_FIELD])}
            except (TypeError, ValueError):
                logger.error(
                    f"[code_quality] Score field returned in wrong format: {typed_response}"
                )
                return {self.SCORE_FIELD: 0.0}

        except Exception as e:
            logger.error(
                f"[code_quality] Evaluation failed for {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {self.SCORE_FIELD: 0.0}

        finally:
            # Cleanup temp tarball
            try:
                if os.path.exists(tmp_tar):
                    os.unlink(tmp_tar)
            except Exception:
                logger.warning(f"[code_quality] Failed to remove temp file {tmp_tar}")
