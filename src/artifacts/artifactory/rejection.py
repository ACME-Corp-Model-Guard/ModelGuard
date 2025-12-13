"""
Functions for rejecting (and later promoting) artifacts based on their metrics.
"""

from src.artifacts.model_artifact import ModelArtifact
from src.settings import MINIMUM_METRIC_THRESHOLD, REJECTED_ARTIFACTS_TABLE
from src.logutil import clogger
from src.storage.dynamo_utils import batch_delete
from src.artifacts.artifactory.persistence import save_artifact_metadata

from typing import List


def scores_below_threshold(artifact: ModelArtifact) -> List[str]:
    """
    Check if any of the model's scores are below the minimum threshold.
    """
    scores = getattr(artifact, "scores", {})
    failing_metrics = []
    # Check each non-latency metric against threshold
    for metric_name, score_value in scores.items():
        # Skip special cases and handle Size dict
        if isinstance(score_value, dict):
            # Size metric has per-platform scores - check each one
            for platform, platform_score in score_value.items():
                if isinstance(platform_score, (int, float)):
                    if platform_score < MINIMUM_METRIC_THRESHOLD:
                        failing_metrics.append(f"{metric_name}.{platform}")
        elif isinstance(score_value, (int, float)):
            if score_value < MINIMUM_METRIC_THRESHOLD:
                failing_metrics.append(metric_name)
    return failing_metrics


def promote(artifact: ModelArtifact) -> None:
    """
    Promote a rejected artifact to the main artifacts table.

    Args:
        artifact: The rejected ModelArtifact to promote
    """

    # Save to main artifacts table
    save_artifact_metadata(artifact, rejected=False)

    # Delete from rejected artifacts table
    batch_delete(
        table_name=REJECTED_ARTIFACTS_TABLE,
        items=[{"artifact_id": artifact.artifact_id}],
        key_name="artifact_id",
    )
    clogger.info(f"Promoted artifact {artifact.artifact_id} to main artifacts table")
