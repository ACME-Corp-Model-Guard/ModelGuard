#!/usr/bin/env python3
"""
ModelManager class for managing a collection of Model objects and Metric objects.
Handles the lifecycle of models, including uploading, loading, searching, and downloading.
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from pathlib import Path
import json

from .model import Model, Metric
from .metrics.availability_metric import AvailabilityMetric
from .metrics.bus_factor_metric import BusFactorMetric
from .metrics.code_quality_metric import CodeQualityMetric
from .metrics.dataset_quality_metric import DatasetQualityMetric
from .metrics.license_metric import LicenseMetric
from .metrics.performance_claims_metric import PerformanceClaimsMetric
from .metrics.ramp_up_metric import RampUpMetric
from .metrics.size_metric import SizeMetric
from .metrics.reproducibility_metric import ReproducibilityMetric
from .metrics.reviewedness_metric import ReviewednessMetric
from .metrics.treescore_metric import TreescoreMetric


class ModelManager:
    """
    Manages a collection of Model objects and Metric objects.
    Handles the lifecycle of models, including uploading, loading, searching, and downloading.
    """
    
    def __init__(self):
        """Initialize the ModelManager with empty collections."""
        self.models: List[Model] = []
        self.metrics: List[Metric] = []
        
        # Initialize default metrics
        self._initialize_default_metrics()
    
    def _initialize_default_metrics(self) -> None:
        """Initialize the default set of metrics."""
        self.metrics = [
            AvailabilityMetric(),
            BusFactorMetric(),
            CodeQualityMetric(),
            DatasetQualityMetric(),
            LicenseMetric(),
            PerformanceClaimsMetric(),
            RampUpMetric(),
            SizeMetric(),
            ReproducibilityMetric(),
            ReviewednessMetric(),
            TreescoreMetric()
        ]
    
    def upload(self, zip_path: str) -> bool:
        """
        Upload a model from a zip file.
        Scores the model and uploads it to S3 if the scores are high enough.
        
        Args:
            zip_path: Path to the zip file containing the model
            
        Returns:
            True if upload was successful, False otherwise
        """
        try:
            # Check if file exists first
            zip_file_path = Path(zip_path)
            if not zip_file_path.exists():
                return False
            
            # TODO: Implement actual zip file processing and S3 upload
            # For now, this is a stub that will be filled out later
            
            # Extract model information from zip path (placeholder)
            model_name = zip_file_path.stem
            model_key = f"models/{model_name}/model"
            code_key = f"models/{model_name}/code"
            dataset_key = f"models/{model_name}/dataset"
            
            # Create a new model instance
            model = Model(
                name=model_name,
                model_key=model_key,
                code_key=code_key,
                dataset_key=dataset_key,
                size=0.0,  # TODO: Calculate actual size
                license="unknown"  # TODO: Extract from zip contents
            )
            
            # Score the model using all available metrics
            self._score_model(model)
            
            # Check if scores are high enough for upload
            # TODO: Implement actual threshold checking
            if self._should_upload_model(model):
                # TODO: Implement actual S3 upload
                self.models.append(model)
                return True
            else:
                return False
                
        except Exception as e:
            # Log error and return False
            print(f"Error uploading model {zip_path}: {e}")
            return False
    
    def load(self) -> List[Model]:
        """
        Load all models from S3 and instantiate them as Model objects.
        
        Returns:
            List of loaded Model objects
        """
        try:
            # TODO: Implement actual S3 loading
            # For now, return the current models list
            return self.models.copy()
        except Exception as e:
            print(f"Error loading models: {e}")
            return []
    
    def search(self, name: str) -> Optional[Model]:
        """
        Search for a model by its name.
        
        Args:
            name: Name of the model to search for
            
        Returns:
            Model object if found, None otherwise
        """
        try:
            for model in self.models:
                if model.name.lower() == name.lower():
                    return model
            return None
        except Exception as e:
            print(f"Error searching for model {name}: {e}")
            return None
    
    def download(self, model: Model) -> bool:
        """
        Download a specific model.
        
        Args:
            model: Model object to download
            
        Returns:
            True if download was successful, False otherwise
        """
        try:
            # TODO: Implement actual S3 download
            # For now, this is a stub that will be filled out later
            print(f"Downloading model: {model.name}")
            return True
        except Exception as e:
            print(f"Error downloading model {model.name}: {e}")
            return False
    
    def _score_model(self, model: Model) -> None:
        """
        Score a model using all available metrics.
        
        Args:
            model: Model object to score
        """
        for metric in self.metrics:
            try:
                score_result = metric.score(model)
                if isinstance(score_result, dict):
                    for metric_name, score_value in score_result.items():
                        model.set_score(metric_name, score_value)
                else:
                    # Single score value
                    metric_name = metric.get_metric_name()
                    model.set_score(metric_name, score_result)
            except Exception as e:
                print(f"Error scoring model {model.name} with metric {metric.get_metric_name()}: {e}")
    
    def _should_upload_model(self, model: Model) -> bool:
        """
        Determine if a model should be uploaded based on its scores.
        
        Args:
            model: Model object to evaluate
            
        Returns:
            True if model should be uploaded, False otherwise
        """
        # TODO: Implement actual threshold logic
        # For now, always return True as a placeholder
        return True
    
    def get_model_by_name(self, name: str) -> Optional[Model]:
        """
        Get a model by name (case-insensitive).
        
        Args:
            name: Name of the model
            
        Returns:
            Model object if found, None otherwise
        """
        return self.search(name)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Get a list of all models with their basic information.
        
        Returns:
            List of dictionaries containing model information
        """
        return [model.to_dict() for model in self.models]
    
    def add_model(self, model: Model) -> None:
        """
        Add a model to the manager.
        
        Args:
            model: Model object to add
        """
        self.models.append(model)
    
    def remove_model(self, model: Model) -> bool:
        """
        Remove a model from the manager.
        
        Args:
            model: Model object to remove
            
        Returns:
            True if model was removed, False if not found
        """
        try:
            self.models.remove(model)
            return True
        except ValueError:
            return False
    
    def get_metrics(self) -> List[Metric]:
        """
        Get all available metrics.
        
        Returns:
            List of Metric objects
        """
        return self.metrics.copy()
    
    def add_metric(self, metric: Metric) -> None:
        """
        Add a custom metric to the manager.
        
        Args:
            metric: Metric object to add
        """
        self.metrics.append(metric)
    
    def to_json(self) -> str:
        """
        Convert the model manager state to JSON.
        
        Returns:
            JSON string representation
        """
        return json.dumps({
            "models": [model.to_dict() for model in self.models],
            "metrics_count": len(self.metrics)
        }, indent=2)
    
    def __str__(self) -> str:
        """String representation of the model manager."""
        return f"ModelManager(models={len(self.models)}, metrics={len(self.metrics)})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the model manager."""
        return f"ModelManager(models={self.models}, metrics={self.metrics})"
