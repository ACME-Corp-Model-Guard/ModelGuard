"""Tests for the Model class."""

import pytest
from src.model import Model


def test_model_initialization():
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
    assert model.model_key == "models/test_model/model"
    assert model.code_key == "models/test_model/code"
    assert model.dataset_key == "models/test_model/dataset"
    assert model.parent_model_key == "models/parent_model/model"


def test_model_initialization_minimal():
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
    assert model.parent_model_key is None


def test_get_score():
    """Test getting scores."""
    model = Model(
        name="test_model",
        model_key="models/test_model/model",
        code_key="models/test_model/code",
        dataset_key="models/test_model/dataset"
    )
    
    # Test getting non-existing score
    assert model.get_score("availability") == 0.0


def test_set_score():
    """Test setting scores."""
    model = Model(
        name="test_model",
        model_key="models/test_model/model",
        code_key="models/test_model/code",
        dataset_key="models/test_model/dataset"
    )
    
    # Set a score
    model.set_score("availability", 0.8, 100.0)
    
    assert model.get_score("availability") == 0.8
    assert model.get_latency("availability") == 100.0


def test_to_dict():
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
    assert "scores" in model_dict
    assert "scores_latency" in model_dict


def test_from_dict():
    """Test creating model from dictionary."""
    data = {
        "name": "test_model",
        "size": 1024.0,
        "license": "MIT",
        "model_key": "models/test_model/model",
        "code_key": "models/test_model/code",
        "dataset_key": "models/test_model/dataset",
        "scores": {"availability": 0.8},
        "scores_latency": {"availability": 100.0}
    }
    
    model = Model.from_dict(data)
    
    assert model.name == "test_model"
    assert model.size == 1024.0
    assert model.license == "MIT"
    assert model.scores == {"availability": 0.8}
    assert model.scores_latency == {"availability": 100.0}
