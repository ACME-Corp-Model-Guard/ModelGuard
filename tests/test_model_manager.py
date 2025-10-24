#!/usr/bin/env python3
"""
Tests for the ModelManager class.
"""

import pytest
from src.model_manager import ModelManager
from src.model import Model


class TestModelManager:
    """Test cases for the ModelManager class."""
    
    def test_initialization(self):
        """Test ModelManager initialization."""
        manager = ModelManager()
        
        assert isinstance(manager.models, list)
        assert isinstance(manager.metrics, list)
        assert len(manager.models) == 0
        assert len(manager.metrics) > 0  # Should have default metrics
    
    def test_default_metrics_initialization(self):
        """Test that default metrics are initialized."""
        manager = ModelManager()
        
        # Check that we have the expected metrics
        metric_names = [metric.get_metric_name() for metric in manager.metrics]
        
        expected_metrics = [
            "availability", "bus_factor", "code_quality", "dataset_quality",
            "license", "performance_claims", "ramp_up", "size", "reproducibility",
            "reviewedness", "treescore"
        ]
        
        for expected_metric in expected_metrics:
            assert expected_metric in metric_names
    
    def test_upload_stub(self):
        """Test upload method (stub implementation)."""
        manager = ModelManager()
        
        # Test with a non-existent zip file
        result = manager.upload("non_existent.zip")
        
        # Should return False for non-existent file
        assert result is False
    
    def test_load(self):
        """Test load method."""
        manager = ModelManager()
        
        # Initially should return empty list
        models = manager.load()
        assert isinstance(models, list)
        assert len(models) == 0
    
    def test_search(self):
        """Test search method."""
        manager = ModelManager()
        
        # Search for non-existent model
        result = manager.search("non_existent")
        assert result is None
    
    def test_download_stub(self):
        """Test download method (stub implementation)."""
        manager = ModelManager()
        
        # Create a test model
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        # Test download (should return True for stub)
        result = manager.download(model)
        assert result is True
    
    def test_add_model(self):
        """Test adding a model to the manager."""
        manager = ModelManager()
        
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        manager.add_model(model)
        
        assert len(manager.models) == 1
        assert manager.models[0] == model
    
    def test_remove_model(self):
        """Test removing a model from the manager."""
        manager = ModelManager()
        
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        # Add model
        manager.add_model(model)
        assert len(manager.models) == 1
        
        # Remove model
        result = manager.remove_model(model)
        assert result is True
        assert len(manager.models) == 0
        
        # Try to remove non-existent model
        result = manager.remove_model(model)
        assert result is False
    
    def test_get_model_by_name(self):
        """Test getting model by name."""
        manager = ModelManager()
        
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        manager.add_model(model)
        
        # Test case-insensitive search
        found_model = manager.get_model_by_name("TEST_MODEL")
        assert found_model == model
        
        # Test non-existent model
        found_model = manager.get_model_by_name("non_existent")
        assert found_model is None
    
    def test_list_models(self):
        """Test listing models."""
        manager = ModelManager()
        
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        manager.add_model(model)
        
        models_list = manager.list_models()
        assert isinstance(models_list, list)
        assert len(models_list) == 1
        assert models_list[0]["name"] == "test_model"
    
    def test_get_metrics(self):
        """Test getting metrics."""
        manager = ModelManager()
        
        metrics = manager.get_metrics()
        assert isinstance(metrics, list)
        assert len(metrics) > 0
    
    def test_add_metric(self):
        """Test adding a custom metric."""
        manager = ModelManager()
        
        # Create a mock metric
        class MockMetric:
            def get_metric_name(self):
                return "mock_metric"
            
            def score(self, model):
                return {"mock_metric": 0.5}
        
        mock_metric = MockMetric()
        initial_count = len(manager.metrics)
        
        manager.add_metric(mock_metric)
        
        assert len(manager.metrics) == initial_count + 1
        assert mock_metric in manager.metrics
    
    def test_to_json(self):
        """Test converting to JSON."""
        manager = ModelManager()
        
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        manager.add_model(model)
        
        json_str = manager.to_json()
        assert isinstance(json_str, str)
        
        # Parse JSON to verify structure
        import json
        data = json.loads(json_str)
        assert "models" in data
        assert "metrics_count" in data
        assert len(data["models"]) == 1
        assert data["models"][0]["name"] == "test_model"
    
    def test_str_representation(self):
        """Test string representation."""
        manager = ModelManager()
        
        str_repr = str(manager)
        assert "ModelManager" in str_repr
        assert "models=0" in str_repr
        assert "metrics=" in str_repr
    
    def test_repr_representation(self):
        """Test detailed string representation."""
        manager = ModelManager()
        
        repr_str = repr(manager)
        assert "ModelManager" in repr_str
        assert "models=" in repr_str
        assert "metrics=" in repr_str
