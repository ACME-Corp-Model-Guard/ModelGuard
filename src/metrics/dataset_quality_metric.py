from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Dict

from src.logger import logger
from src.metrics.metric import Metric
from src.storage.file_extraction import extract_relevant_files
from src.storage.s3_utils import download_artifact_from_s3
from src.utils.llm_analysis import (
    ask_llm,
    build_file_analysis_prompt,
    extract_llm_score_field,
)

if TYPE_CHECKING:
    from src.artifacts.dataset_artifact import DatasetArtifact


class DatasetQualityMetric(Metric):
    """
    Dataset Quality Metric

    Evaluates the clarity, structure, documentation, and general
    usefulness of a dataset artifact by:

      1. Fetching its dataset bundle (.tar.gz) from S3
      2. Extracting representative dataset + documentation files
      3. Submitting those files to a Bedrock LLM for evaluation
      4. Returning the LLM-generated numeric score

    Output Format:
        { "dataset_quality": <float in [0.0, 1.0]> }
    """

    SCORE_FIELD = "dataset_quality"

    # Include dataset-relevant formats + documentation
    INCLUDE_EXT = [".csv", ".tsv", ".json", ".jsonl", ".md", ".txt"]

    MAX_FILES = 6
    MAX_CHARS_PER_FILE = 4000

    METRIC_DESCRIPTION = """
This metric evaluates the overall quality of a dataset, including:
- Clarity and completeness of dataset documentation
- Readability and consistency of dataset samples
- Presence of meaningful README or dataset card files
- Quality and structure of CSV/TSV/JSON/JSONL samples
- Evidence of clear labeling and metadata
- General suitability of the dataset for ML training

A score of 1.0 means excellent dataset clarity and structure.
A score of 0.0 means poorly documented, inconsistent, or unusable data.
"""

    # ====================================================================================
    # SCORE METHOD
    # ====================================================================================

    def score(self, model: DatasetArtifact) -> Dict[str, float]:
        """
        Execute the complete dataset-quality evaluation pipeline.

        Returns:
            {"dataset_quality": float} on success
            {"dataset_quality": 0.0} on any failure
        """

        # ------------------------------------------------------------------
        # Step 1 — Download dataset tarball from S3
        # ------------------------------------------------------------------
        tmp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        try:
            logger.debug(
                f"[dataset_quality] Downloading dataset bundle for {model.artifact_id}"
            )

            download_artifact_from_s3(
                artifact_id=model.artifact_id,
                s3_key=model.s3_key,
                local_path=tmp_tar,
            )

            # ------------------------------------------------------------------
            # Step 2 — Extract relevant dataset files
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
                    f"[dataset_quality] No relevant dataset files extracted for {model.artifact_id}"
                )
                return {self.SCORE_FIELD: 0.0}

            # ------------------------------------------------------------------
            # Step 3 — Build LLM prompt
            # ------------------------------------------------------------------
            prompt = build_file_analysis_prompt(
                metric_name="Dataset Quality",
                score_name=self.SCORE_FIELD,
                files=files,
                metric_description=self.METRIC_DESCRIPTION,
            )

            # ------------------------------------------------------------------
            # Step 4 — Ask LLM
            # ------------------------------------------------------------------
            response = ask_llm(prompt, return_json=True)

            # ------------------------------------------------------------------
            # Step 5 — Extract score from LLM JSON
            # ------------------------------------------------------------------
            score = extract_llm_score_field(response, self.SCORE_FIELD)

            if score is None:
                logger.error(
                    f"[dataset_quality] Invalid score returned for {model.artifact_id}: {response}"
                )
                return {self.SCORE_FIELD: 0.0}

            # Ensure score in [0, 1]
            score = max(0.0, min(float(score), 1.0))

            return {self.SCORE_FIELD: score}

        except Exception as e:
            logger.error(
                f"[dataset_quality] Evaluation failed for {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {self.SCORE_FIELD: 0.0}

        finally:
            # ------------------------------------------------------------------
            # Cleanup temporary tarball
            # ------------------------------------------------------------------
            try:
                if os.path.exists(tmp_tar):
                    os.unlink(tmp_tar)
            except Exception:
                logger.warning(
                    f"[dataset_quality] Failed to remove temp file {tmp_tar}"
                )
