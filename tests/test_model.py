#!/usr/bin/env python3
"""
Tests for the Model class.
"""

import pytest
from src.model import Model, Metric


class MockMetric(Metric):
    """Mock metric for testing."""
    
    def score(self, model: Model):
        return {"test_metric": 0.5}


class TestModel:
    """Test cases for the Model class."""
    
    def test_model_initialization(self):
        """Test model initialization with all parameters."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset",
            parent_model_key="models/parent_model/model",
            size=1024.0,
            license="MIT"
        )
        
        assert model.name == "test_model"
        assert model.size == 1024.0
        assert model.license == "MIT"
        assert model.get_model_key() == "models/test_model/model"
        assert model.get_code_key() == "models/test_model/code"
        assert model.get_dataset_key() == "models/test_model/dataset"
        assert model.get_parent_model_key() == "models/parent_model/model"
    
    def test_model_initialization_minimal(self):
        """Test model initialization with minimal parameters."""
        model = Model(
            name="minimal_model",
            model_key="models/minimal_model/model",
            code_key="models/minimal_model/code",
            dataset_key="models/minimal_model/dataset"
        )
        
        assert model.name == "minimal_model"
        assert model.size == 0.0
        assert model.license == "unknown"
        assert model.get_parent_model_key() is None
    
    def test_default_scores_initialization(self):
        """Test that default scores are initialized."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        expected_metrics = [
            "availability", "bus_factor", "code_quality", "dataset_quality",
            "license", "performance_claims", "ramp_up", "size", "reproducibility",
            "reviewedness", "treescore"
        ]
        
        for metric in expected_metrics:
            assert metric in model.scores
            assert model.scores[metric] == 0.0
            assert metric in model.scores_latency
            assert model.scores_latency[metric] == 0.0
    
    def test_get_score(self):
        """Test getting scores."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        # Test getting existing score
        assert model.get_score("availability") == 0.0
        
        # Test getting non-existing score
        assert model.get_score("non_existing") == 0.0
    
    def test_get_latency(self):
        """Test getting latency scores."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        # Test getting existing latency
        assert model.get_latency("availability") == 0.0
        
        # Test getting non-existing latency
        assert model.get_latency("non_existing") == 0.0
    
    def test_set_score(self):
        """Test setting scores."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        # Set a score
        model.set_score("test_metric", 0.8, 100.0)
        
        assert model.get_score("test_metric") == 0.8
        assert model.get_latency("test_metric") == 100.0
    
    def test_to_dict(self):
        """Test converting model to dictionary."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset",
            size=512.0,
            license="Apache-2.0"
        )
        
        model_dict = model.to_dict()
        
        assert model_dict["name"] == "test_model"
        assert model_dict["size"] == 512.0
        assert model_dict["license"] == "Apache-2.0"
        assert model_dict["model_key"] == "models/test_model/model"
        assert model_dict["code_key"] == "models/test_model/code"
        assert model_dict["dataset_key"] == "models/test_model/dataset"
        assert "scores" in model_dict
        assert "scores_latency" in model_dict
    
    def test_str_representation(self):
        """Test string representation."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        str_repr = str(model)
        assert "test_model" in str_repr
        assert "0" in str_repr  # size
        assert "unknown" in str_repr  # license
    
    def test_repr_representation(self):
        """Test detailed string representation."""
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        repr_str = repr(model)
        assert "test_model" in repr_str
        assert "models/test_model/model" in repr_str
        assert "models/test_model/code" in repr_str
        assert "models/test_model/dataset" in repr_str
