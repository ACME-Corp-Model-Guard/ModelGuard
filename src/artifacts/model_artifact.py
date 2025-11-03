"""
Model artifact class with scoring functionality.
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime
import time

from .base_artifact import BaseArtifact
from src.metrics.net_score import calculate_net_score
from src.logger import logger

# Import metrics module to access METRICS list
from src import metrics as _metrics


# Static list of all metrics to run on model artifacts
METRICS: list[_metrics.Metric] = [
    _metrics.AvailabilityMetric(),
    _metrics.BusFactorMetric(),
    _metrics.CodeQualityMetric(),
    _metrics.DatasetQualityMetric(),
    _metrics.LicenseMetric(),
    _metrics.PerformanceClaimsMetric(),
    _metrics.RampUpMetric(),
    _metrics.ReproducibilityMetric(),
    _metrics.ReviewednessMetric(),
    _metrics.SizeMetric(),
    _metrics.TreescoreMetric(),
]


class ModelArtifact(BaseArtifact):
    """
    Model artifact with scoring functionality.

    Extends BaseArtifact with:
    - Model-specific fields (size, license)
    - Scoring system (scores, scores_latency)
    - Connection fields for lineage (dataset_artifact_id, code_artifact_id, parent_model_key)
    """

    def __init__(
        self,
        artifact_id: Optional[str] = None,
        name: str = None,
        source_url: str = None,
        size: float = 0.0,
        license: str = "unknown",
        s3_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        scores: Optional[Dict[str, Union[float, Dict[str, float]]]] = None,
        scores_latency: Optional[Dict[str, float]] = None,
        dataset_artifact_id: Optional[str] = None,
        code_artifact_id: Optional[str] = None,
        parent_model_key: Optional[str] = None,
        auto_score: bool = True,
    ):
        """
        Initialize ModelArtifact.

        Args:
            artifact_id: Optional UUID (generated if not provided)
            name: Model name
            source_url: URL where model was sourced from
            size: Model size in bytes (default: 0.0)
            license: Model license (default: "unknown")
            s3_key: Optional S3 storage key
            metadata: Optional dict for additional model-specific data
            scores: Optional pre-computed scores dict
            scores_latency: Optional pre-computed latencies dict
            dataset_artifact_id: Optional link to dataset artifact (for lineage)
            code_artifact_id: Optional link to code artifact (for lineage)
            parent_model_key: Optional link to parent model (for lineage)
            auto_score: Whether to automatically compute scores on creation (default: True)
        """
        super().__init__(
            artifact_id=artifact_id,
            artifact_type="model",
            name=name,
            source_url=source_url,
            s3_key=s3_key,
            metadata=metadata,
        )

        self.size = size
        self.license = license

        # Scoring fields
        self.scores = scores or {}
        self.scores_latency = scores_latency or {}

        # Connection fields for lineage (stored but not used in MVP)
        self.dataset_artifact_id = dataset_artifact_id
        self.code_artifact_id = code_artifact_id
        self.parent_model_key = parent_model_key

        # Automatically compute scores on creation unless explicitly disabled
        if auto_score and not scores:
            logger.info(f"Auto-scoring model artifact: {self.artifact_id}")
            self._compute_scores()
        else:
            logger.debug(f"Skipping auto-score for model artifact: {self.artifact_id}")

    def _compute_scores(self) -> None:
        """
        Populate scores and scores_latency by running each metric once.
        Iterates the static METRICS list and times each metric.score() call.

        Note: Metrics expect a Model object, but we're transitioning to ModelArtifact.
        For now, we'll pass self and assume metrics will be updated to handle ModelArtifact.
        """
        logger.info(f"Computing scores for model artifact: {self.artifact_id}")
        scores: Dict[str, Union[float, Dict[str, float]]] = {}
        latencies: Dict[str, float] = {}

        for metric in METRICS:
            metric_name = metric.__class__.__name__.replace("Metric", "")
            t0 = time.perf_counter()
            try:
                # Pass self (ModelArtifact) to metric.score()
                # Metrics will need to be updated to handle ModelArtifact instead of Model
                value = metric.score(self)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0

                scores[metric_name] = value
                latencies[metric_name] = elapsed_ms
                logger.debug(
                    f"Metric {metric_name} scored {value} in {elapsed_ms:.2f}ms"
                )
            except Exception as e:
                # If metric fails, store error and continue
                scores[metric_name] = 0.0
                latencies[metric_name] = 0.0
                logger.error(
                    f"Metric {metric_name} failed for artifact {self.artifact_id}: {e}",
                    exc_info=True,
                )

        self.scores = scores
        self.scores_latency = latencies

        # Calculate NetScore separately
        t0 = time.perf_counter()
        self.scores["NetScore"] = calculate_net_score(self.scores)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.scores_latency["NetScore"] = elapsed_ms
        logger.info(
            f"Computed NetScore {self.scores['NetScore']:.3f} for artifact {self.artifact_id}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize ModelArtifact to dictionary for DynamoDB storage.
        """
        data = self._base_to_dict()
        data.update(
            {
                "size": self.size,
                "license": self.license,
                "scores": self.scores,
                "scores_latency": self.scores_latency,
                "dataset_artifact_id": self.dataset_artifact_id,
                "code_artifact_id": self.code_artifact_id,
                "parent_model_key": self.parent_model_key,
            }
        )
        return data

    def __repr__(self) -> str:
        return (
            f"ModelArtifact(artifact_id='{self.artifact_id}', name='{self.name}', "
            f"size={self.size}, license='{self.license}')"
        )
