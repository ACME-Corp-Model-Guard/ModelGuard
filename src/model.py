#!/usr/bin/env python3
"""
Model class representing a machine learning model in the system.
Stores metadata, scores, and S3 keys for data access.
Ready for Lambda integration with DynamoDB and S3.
"""

from __future__ import annotations
from typing import Dict, Union, Optional

# Add a local import to the metrics module (avoids circular import issues)
from . import metrics as _metrics
from src.metrics.net_score import calculate_net_score

import time  # high-resolution timing



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


class Model:
    """
    Represents a machine learning model in the system.
    Holds metadata, scores, and keys for accessing data in S3.

    Attributes:
        name: Model name
        size: Model size in bytes
        license: Model license
        scores: Dictionary of metric scores
        scores_latency: Dictionary of metric latencies
        model_key: S3 key for the model file
        code_key: S3 key for the model's code
        dataset_key: S3 key for the model's dataset
        parent_model_key: S3 key for parent model (optional)
    """

    def __init__(
        self,
        name: str,
        model_key: str,
        code_key: str,
        dataset_key: str,
        parent_model_key: Optional[str] = None,
        size: float = 0.0,
        license: str = "unknown",
    ):
        """
        Initialize a Model instance.

        Args:
            name: The name of the model
            model_key: S3 key for the model data
            code_key: S3 key for the model's code
            dataset_key: S3 key for the model's dataset
            parent_model_key: S3 key for the parent model (if applicable)
            size: The size of the model in bytes
            license: The license associated with the model
        """
        self.name = name
        self.size = size
        self.license = license

        # S3 keys for data access
        self.model_key = model_key
        self.code_key = code_key
        self.dataset_key = dataset_key
        self.parent_model_key = parent_model_key

        # Score storage - initially empty, will be populated by metrics
        self.scores: Dict[str, Union[float, Dict[str, float]]] = {}
        self.scores_latency: Dict[str, float] = {}

        # Compute initial scores once for new models
        self._compute_scores()

    def get_score(self, metric_name: str) -> Union[float, Dict[str, float]]:
        """
        Retrieve a specific score.

        Args:
            metric_name: Name of the metric to retrieve

        Returns:
            The score value (float or dict)
        """
        return self.scores.get(metric_name, 0.0)

    def get_latency(self, metric_name: str) -> float:
        """
        Retrieve a specific latency score.

        Args:
            metric_name: Name of the metric to retrieve latency for

        Returns:
            The latency value in milliseconds
        """
        return self.scores_latency.get(metric_name, 0.0)

    def to_dict(self) -> Dict:
        """
        Convert the model to a dictionary for DynamoDB storage or API responses.

        Returns:
            Dictionary representation of the model
        """
        return {
            "name": self.name,
            "size": self.size,
            "license": self.license,
            "model_key": self.model_key,
            "code_key": self.code_key,
            "dataset_key": self.dataset_key,
            "parent_model_key": self.parent_model_key,
            "scores": self.scores,
            "scores_latency": self.scores_latency,
        }

    @classmethod
    def create_with_scores(cls, data: Dict) -> "Model":
        """
        Create a Model instance from a dictionary (e.g., from DynamoDB).
        Scores and latencies are populated from the data - no need to recompute.

        Args:
            data: Dictionary containing model data

        Returns:
            Model instance
        """
        model = cls(
            name=data["name"],
            model_key=data.get("model_key", ""),
            code_key=data.get("code_key", ""),
            dataset_key=data.get("dataset_key", ""),
            parent_model_key=data.get("parent_model_key"),
            size=data.get("size", 0.0),
            license=data.get("license", "unknown"),
        )
        model.scores = data.get("scores", {})
        model.scores_latency = data.get("scores_latency", {})
        return model

    def _compute_scores(self) -> None:
        """
        Populate scores and scores_latency by running each metric once.
        Iterates the static METRICS list and times each metric.score() call.
        """
        scores: Dict[str, Union[float, Dict[str, float]]] = {}
        latencies: Dict[str, float] = {}

        for metric in METRICS:
            t0 = time.perf_counter()
            value = metric.score(self)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # Use the metric class name as the key
            metric_name = metric.__class__.__name__.replace("Metric", "")
            scores[metric_name] = value
            latencies[metric_name] = elapsed_ms

        self.scores = scores
        self.scores_latency = latencies

        # Calculate NetScore separately
        t0 = time.perf_counter()
        self.scores["NetScore"] = calculate_net_score(self.scores)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.scores_latency["NetScore"] = elapsed_ms

    def __str__(self) -> str:
        """String representation of the model."""
        return f"Model(name='{self.name}', size={self.size}, license='{self.license}')"

    def __repr__(self) -> str:
        """Detailed string representation of the model."""
        return (
            f"Model(name='{self.name}', size={self.size}, license='{self.license}', "
            f"model_key='{self.model_key}')"
        )
