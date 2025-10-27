#!/usr/bin/env python3
"""
Model class representing a machine learning model within the system.
Holds metadata, scores, and keys for data access in S3.
"""

from __future__ import annotations
from typing import Dict, Union, List, Optional


class Model:
    """
    Represents a machine learning model within the system.
    Holds its metadata, scores, and keys for data access in S3.
    """
    
    def __init__(
        self,
        name: str,
        model_key: str,
        code_key: str,
        dataset_key: str,
        parent_model_key: Optional[str] = None,
        size: float = 0.0,
        license: str = "unknown"
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
        self._model_key = model_key
        self._code_key = code_key
        self._dataset_key = dataset_key
        self._parent_model_key = parent_model_key
        
        # Score storage
        self.scores: Dict[str, Union[float, Dict[str, float]]] = {}
        self.scores_latency: Dict[str, float] = {}
        
        # Initialize with default scores
        self._initialize_default_scores()
    
    def _initialize_default_scores(self) -> None:
        """Initialize default scores for all metrics."""
        default_metrics = [
            "availability", "bus_factor", "code_quality", "dataset_quality",
            "license", "performance_claims", "ramp_up", "size", "reproducibility",
            "reviewedness", "treescore"
        ]
        
        for metric in default_metrics:
            self.scores[metric] = 0.0
            self.scores_latency[metric] = 0.0
    
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
    
    def get_model_key(self) -> str:
        """Retrieve the S3 key for the model."""
        return self._model_key
    
    def get_code_key(self) -> str:
        """Retrieve the S3 key for the model's code."""
        return self._code_key
    
    def get_dataset_key(self) -> str:
        """Retrieve the S3 key for the model's dataset."""
        return self._dataset_key
    
    def get_parent_model_key(self) -> Optional[str]:
        """Retrieve the S3 key for the parent model (if applicable)."""
        return self._parent_model_key
    
    def _score_metric(self, metric: 'Metric') -> None:
        """
        Internal method for scoring the model using a given metric.
        Called when Model is initialized.
        
        Args:
            metric: The metric to use for scoring
        """
        try:
            # TODO: Implement actual scoring when S3 integration is ready
            # For now, this is a stub that will be filled out later
            metric_name = metric.__class__.__name__.lower().replace("metric", "")
            self.scores[metric_name] = 0.0  # Placeholder score
            self.scores_latency[metric_name] = 0.0  # Placeholder latency
        except Exception as e:
            # Log error and set default values
            metric_name = metric.__class__.__name__.lower().replace("metric", "")
            self.scores[metric_name] = 0.0
            self.scores_latency[metric_name] = 0.0
    
    def set_score(self, metric_name: str, score: Union[float, Dict[str, float]], latency: float = 0.0) -> None:
        """
        Set a score for a specific metric.
        
        Args:
            metric_name: Name of the metric
            score: The score value
            latency: The latency in milliseconds
        """
        self.scores[metric_name] = score
        self.scores_latency[metric_name] = latency
    
    def to_dict(self) -> Dict[str, Union[str, float, Dict[str, float]]]:
        """
        Convert the model to a dictionary representation.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            "name": self.name,
            "size": self.size,
            "license": self.license,
            "model_key": self._model_key,
            "code_key": self._code_key,
            "dataset_key": self._dataset_key,
            "parent_model_key": self._parent_model_key,
            "scores": self.scores,
            "scores_latency": self.scores_latency
        }
    
    def __str__(self) -> str:
        """String representation of the model."""
        return f"Model(name='{self.name}', size={self.size}, license='{self.license}')"
    
    def __repr__(self) -> str:
        """Detailed string representation of the model."""
        return (f"Model(name='{self.name}', size={self.size}, license='{self.license}', "
                f"model_key='{self._model_key}', code_key='{self._code_key}', "
                f"dataset_key='{self._dataset_key}')")
