"""
Model artifact class with scoring functionality.
"""

import concurrent.futures
import time
import traceback
from typing import Any, Dict, List, Optional, Union

from src.artifacts.base_artifact import BaseArtifact
from src.logger import logger
from src.metrics import Metric
from src.metrics.net_score import calculate_net_score
from src.metrics.registry import METRICS


class ModelArtifact(BaseArtifact):
    """
    Model artifact with scoring functionality.

    Extends BaseArtifact with:
    - Model-specific fields (size, license)
    - Scoring system (scores, scores_latency)
    - Connection fields for lineage (dataset_artifact_id, code_artifact_id, parent_model_id)
    """

    def __init__(
        # Basic info
        self,
        name: str,
        source_url: str,
        artifact_id: Optional[str] = None,
        s3_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # Model-specific fields
        size: float = 0.0,
        license: str = "unknown",
        # Scoring fields
        scores: Optional[Dict[str, Union[float, Dict[str, float]]]] = None,
        scores_latency: Optional[Dict[str, float]] = None,
        auto_score: bool = True,
        # Connection fields
        code_name: Optional[str] = None,
        code_artifact_id: Optional[str] = None,
        dataset_name: Optional[str] = None,
        dataset_artifact_id: Optional[str] = None,
        parent_model_name: Optional[str] = None,
        parent_model_source: Optional[str] = None,
        parent_model_relationship: Optional[str] = None,
        parent_model_id: Optional[str] = None,
        child_model_ids: Optional[List[str]] = None,
    ):
        """
        Initialize ModelArtifact.

        Args:
            artifact_id: Optional UUID (generated if not provided)
            name: Model name
            source_url: URL where model was sourced from
            s3_key: Optional S3 storage key
            metadata: Optional dict for additional model-specific data
            size: Model size in bytes (default: 0.0)
            license: Model license (default: "unknown")
            scores: Optional pre-computed scores dict
            scores_latency: Optional pre-computed latencies dict
            auto_score: Whether to automatically compute scores on creation (default: True)
            code_name: Optional name of associated code artifact
            code_artifact_id: Optional link to code artifact
            dataset_name: Optional name of associated dataset artifact
            dataset_artifact_id: Optional link to dataset artifact
            parent_model_name: Optional name of parent model artifact (for lineage)
            parent_model_source: Optional filename where parent model was discovered
            parent_model_relationship: Optional relationship type to parent model
            parent_model_id: Optional link to parent model (for lineage)
            child_model_ids: Optional list of child model IDs (for lineage)
        """
        super().__init__(
            artifact_id=artifact_id,
            artifact_type="model",
            name=name,
            source_url=source_url,
            s3_key=s3_key,
            metadata=metadata,
        )

        # Model-specific fields
        self.size = size
        self.license = license

        # Scoring fields
        self.scores = scores or {}
        self.scores_latency = scores_latency or {}

        # Automatically compute scores on creation unless explicitly disabled
        if auto_score and not scores:
            logger.info(f"Auto-scoring model artifact: {self.artifact_id}")
            self._compute_scores()
        else:
            logger.debug(f"Skipping auto-score for model artifact: {self.artifact_id}")

    def _compute_scores(self) -> None:
        """
        Populate scores and scores_latency by running each metric in parallel.

        Uses ThreadPoolExecutor since metrics may involve I/O (HTTP, S3, etc.).
        Falls back gracefully if any metric raises an exception.
        """
        logger.info(
            f"Computing scores (parallel) for model artifact: {self.artifact_id}"
        )
        scores: Dict[str, Union[float, Dict[str, float]]] = {}
        latencies: Dict[str, float] = {}

        def run_metric(
            metric: Metric,
        ) -> tuple[str, float | dict[str, float], float]:
            metric_name = metric.__class__.__name__.replace("Metric", "")
            t0 = time.perf_counter()
            try:
                value = metric.score(self)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                logger.debug(f"[{metric_name}] scored {value} in {elapsed_ms:.2f}ms")
                return metric_name, value, elapsed_ms
            except Exception as e:
                logger.error(
                    f"Metric {metric_name} failed for artifact {self.artifact_id}: {e}\n"
                    f"{traceback.format_exc()}"
                )
                return metric_name, 0.0, 0.0

        # Run all metrics concurrently
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(8, len(METRICS))
        ) as executor:
            futures = {executor.submit(run_metric, m): m for m in METRICS}
            for future in concurrent.futures.as_completed(futures):
                metric_name, value, elapsed_ms = future.result()
                scores[metric_name] = value
                latencies[metric_name] = elapsed_ms

        # Compute NetScore (sequential, depends on other scores)
        t0 = time.perf_counter()
        scores["NetScore"] = calculate_net_score(scores)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies["NetScore"] = elapsed_ms

        self.scores = scores
        self.scores_latency = latencies

        logger.info(
            f"Computed NetScore {self.scores['NetScore']:.3f} for artifact {self.artifact_id} "
            f"({len(METRICS)} metrics in parallel)"
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
                "code_name": self.code_name,
                "code_artifact_id": self.code_artifact_id,
                "dataset_name": self.dataset_name,
                "dataset_artifact_id": self.dataset_artifact_id,
                "parent_model_name": self.parent_model_name,
                "parent_model_source": self.parent_model_source,
                "parent_model_relationship": self.parent_model_relationship,
                "parent_model_id": self.parent_model_id,
                "child_model_ids": self.child_model_ids,
            }
        )
        return data

    def __repr__(self) -> str:
        return (
            f"ModelArtifact(artifact_id='{self.artifact_id}', name='{self.name}', "
            f"size={self.size}, license='{self.license}')"
        )
