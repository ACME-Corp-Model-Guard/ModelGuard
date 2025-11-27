from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Dict

from src.artifacts.dataset_artifact import DatasetArtifact
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


class DatasetQualityMetric(Metric):
    """
    Dataset Quality Metric

    Evaluates the clarity, structure, documentation, and general utility of
    a model's associated dataset artifact by:

      1. Looking up the dataset artifact from DynamoDB
      2. Fetching its dataset bundle (.tar.gz) from S3
      3. Extracting representative dataset/documentation files
      4. Submitting them to a Bedrock LLM for evaluation
      5. Returning the LLM-generated numeric score

    Output Format:
        { "dataset_quality": <float in [0.0, 1.0]> }
    """

    SCORE_FIELD = "dataset_quality"
    INCLUDE_EXT = [".csv", ".tsv", ".json", ".jsonl", ".md", ".txt"]
    MAX_FILES = 6
    MAX_CHARS_PER_FILE = 4000

    METRIC_DESCRIPTION = """
This metric evaluates the overall quality of a dataset, including:
- Documentation clarity (README, dataset card, metadata files)
- Structure and consistency of dataset samples
- Proper formatting of CSV/TSV/JSON/JSONL files
- Evidence of coherent labeling or metadata
- Data suitability for machine learning applications

A score of 1.0 indicates excellent dataset documentation and sample quality.
A score near 0.0 indicates a poor, inconsistent, or unusable dataset.
"""

    # ====================================================================================
    # SCORE METHOD (mirror pattern of CodeQualityMetric)
    # ====================================================================================

    def score(self, model: ModelArtifact) -> Dict[str, float]:
        """Compute dataset_quality score for the provided ModelArtifact."""

        # ------------------------------------------------------------------
        # Step 0 — Identify dataset artifact
        # ------------------------------------------------------------------
        dataset_id = model.dataset_artifact_id
        if dataset_id is None:
            logger.warning(
                f"[dataset_quality] No dataset artifact_id for model {model.artifact_id}"
            )
            return {self.SCORE_FIELD: 0.0}

        dataset_artifact = load_artifact_metadata(dataset_id)

        if not isinstance(dataset_artifact, DatasetArtifact):
            logger.warning(
                f"[dataset_quality] Missing or invalid dataset artifact for model "
                f"{model.artifact_id}"
            )
            return {self.SCORE_FIELD: 0.0}

        # ------------------------------------------------------------------
        # Step 1 — Download dataset tarball from S3
        # ------------------------------------------------------------------
        tmp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        try:
            logger.debug(
                f"[dataset_quality] Downloading dataset bundle for {dataset_artifact.artifact_id}"
            )

            download_artifact_from_s3(
                artifact_id=dataset_artifact.artifact_id,
                s3_key=dataset_artifact.s3_key,
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
                    f"[dataset_quality] No relevant dataset files extracted for "
                    f"{dataset_artifact.artifact_id}"
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
            # Step 5 — Extract score
            # ------------------------------------------------------------------
            score = extract_llm_score_field(response, self.SCORE_FIELD)

            if score is None:
                logger.error(
                    f"[dataset_quality] Invalid score returned for {dataset_artifact.artifact_id}: "
                    f"{response}"
                )
                return {self.SCORE_FIELD: 0.0}

            # Clamp to [0.0, 1.0]
            score = max(0.0, min(float(score), 1.0))
            return {self.SCORE_FIELD: score}

        except Exception as e:
            logger.error(
                f"[dataset_quality] Evaluation failed for {dataset_artifact.artifact_id}: {e}",
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
