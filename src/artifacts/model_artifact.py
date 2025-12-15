"""
Model artifact class with scoring functionality.
"""

import concurrent.futures
import time
from typing import Any, Dict, List, Optional, Union

from src.artifacts.base_artifact import BaseArtifact
from src.logutil import BatchOperationLogger, clogger
from src.metrics import Metric
from src.metrics.net_score import calculate_net_score


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
        # Security fields
        suspected_package_confusion: bool = False,
        js_program_key: Optional[str] = None,
        uploader_username: Optional[str] = None,
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
            code_name: Optional name of associated code artifact
            code_artifact_id: Optional link to code artifact
            dataset_name: Optional name of associated dataset artifact
            dataset_artifact_id: Optional link to dataset artifact
            parent_model_name: Optional name of parent model artifact (for lineage)
            parent_model_source: Optional filename where parent model was discovered
            parent_model_relationship: Optional relationship type to parent model
            parent_model_id: Optional link to parent model (for lineage)
            child_model_ids: Optional list of child model IDs (for lineage)
            suspected_package_confusion: is this model suspected of package confusion
            js_program_key: Optional JS program key for security analysis
            uploader_username: Optional username of the uploader
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

        # Connection fields
        self.code_name = code_name
        self.code_artifact_id = code_artifact_id
        self.dataset_name = dataset_name
        self.dataset_artifact_id = dataset_artifact_id
        self.parent_model_name = parent_model_name
        self.parent_model_source = parent_model_source
        self.parent_model_relationship = parent_model_relationship
        self.parent_model_id = parent_model_id
        self.child_model_ids = child_model_ids

        # Security fields
        self.suspected_package_confusion = suspected_package_confusion
        self.js_program_key = js_program_key
        self.uploader_username = uploader_username

    def compute_scores(self, metrics: List[Metric]) -> None:
        """
        Populate scores and scores_latency by running each metric in parallel.

        Uses ThreadPoolExecutor since metrics may involve I/O (HTTP, S3, etc.).
        Falls back gracefully if any metric raises an exception.
        Logs progress with BatchOperationLogger for observability.
        """
        with BatchOperationLogger("compute_scores", total=len(metrics) + 1) as batch:
            clogger.info(
                "Computing scores in parallel",
                extra={
                    "artifact_id": self.artifact_id,
                    "artifact_name": self.name,
                    "num_metrics": len(metrics),
                },
            )

            def run_metric(
                metric: Metric,
            ) -> tuple[str, float | dict[str, float], float, bool]:
                metric_name = metric.__class__.__name__.replace("Metric", "")
                t0 = time.perf_counter()
                try:
                    value = metric.score(self)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    clogger.debug(
                        f"Metric computed: {metric_name}",
                        extra={
                            "metric": metric_name,
                            "value": value,
                            "duration_ms": elapsed_ms,
                            "artifact_id": self.artifact_id,
                        },
                    )
                    return metric_name, value, elapsed_ms, True
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    clogger.exception(
                        f"Metric computation failed: {metric_name}",
                        extra={
                            "metric": metric_name,
                            "artifact_id": self.artifact_id,
                            "duration_ms": elapsed_ms,
                            "error_type": type(e).__name__,
                        },
                    )
                    return metric_name, 0.0, elapsed_ms, False

            # Run all metrics concurrently
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(8, len(metrics))
            ) as executor:
                futures = {executor.submit(run_metric, m): m for m in metrics}
                for future in concurrent.futures.as_completed(futures):
                    metric_name, value, elapsed_ms, success = future.result()
                    self.scores[metric_name] = value
                    self.scores_latency[metric_name] = elapsed_ms

                    # Log to batch tracker
                    batch.log_item(
                        metric_name,
                        status="success" if success else "failure",
                        value=value,
                        duration_ms=elapsed_ms,
                    )

            # Compute NetScore (sequential, depends on other scores)
            t0 = time.perf_counter()
            net_score = calculate_net_score(self.scores)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.scores["NetScore"] = net_score
            self.scores_latency["NetScore"] = elapsed_ms

            batch.log_item(
                "NetScore",
                status="success",
                value=net_score,
                duration_ms=elapsed_ms,
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize ModelArtifact to dictionary for DynamoDB storage.
        Does not store Metric instances, only computed scores.
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
                "suspected_package_confusion": self.suspected_package_confusion,
            }
        )
        return data

    def __repr__(self) -> str:
        return (
            f"ModelArtifact(artifact_id='{self.artifact_id}', name='{self.name}', "
            f"size={self.size}, license='{self.license}')"
        )
