#!/usr/bin/env python3
"""
Tests for the metric classes.
"""

import pytest
from src.model import Model
from src.metrics.abstract_metric import AbstractMetric
from src.metrics.availability_metric import AvailabilityMetric
from src.metrics.bus_factor_metric import BusFactorMetric
from src.metrics.code_quality_metric import CodeQualityMetric
from src.metrics.dataset_quality_metric import DatasetQualityMetric
from src.metrics.license_metric import LicenseMetric
from src.metrics.performance_claims_metric import PerformanceClaimsMetric
from src.metrics.ramp_up_metric import RampUpMetric
from src.metrics.size_metric import SizeMetric
from src.metrics.reproducibility_metric import ReproducibilityMetric
from src.metrics.reviewedness_metric import ReviewednessMetric
from src.metrics.treescore_metric import TreescoreMetric


class TestAbstractMetric:
    """Test cases for the AbstractMetric base class."""
    
    def test_abstract_metric_initialization(self):
        """Test AbstractMetric initialization."""
        class ConcreteMetric(AbstractMetric):
            def score(self, model: Model):
                return {"test": 0.5}
        
        metric = ConcreteMetric("test_metric")
        assert metric.get_metric_name() == "test_metric"
    
    def test_abstract_metric_abstract_method(self):
        """Test that AbstractMetric cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractMetric("test")
    
    def test_utility_methods(self):
        """Test utility methods of AbstractMetric."""
        class ConcreteMetric(AbstractMetric):
            def score(self, model: Model):
                return {"test": 0.5}
        
        metric = ConcreteMetric("test_metric")
        
        # Test _clamp01
        assert metric._clamp01(0.5) == 0.5
        assert metric._clamp01(-0.1) == 0.0
        assert metric._clamp01(1.1) == 1.0
        
        # Test _stable_unit_score
        score1 = metric._stable_unit_score("test", "salt")
        score2 = metric._stable_unit_score("test", "salt")
        assert score1 == score2  # Should be stable
        assert 0.0 <= score1 <= 1.0  # Should be in valid range


class TestAvailabilityMetric:
    """Test cases for AvailabilityMetric."""
    
    def test_initialization(self):
        """Test AvailabilityMetric initialization."""
        metric = AvailabilityMetric()
        assert metric.get_metric_name() == "availability"
    
    def test_score(self):
        """Test scoring a model."""
        metric = AvailabilityMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "availability" in result
        assert 0.0 <= result["availability"] <= 1.0


class TestBusFactorMetric:
    """Test cases for BusFactorMetric."""
    
    def test_initialization(self):
        """Test BusFactorMetric initialization."""
        metric = BusFactorMetric()
        assert metric.get_metric_name() == "bus_factor"
    
    def test_score(self):
        """Test scoring a model."""
        metric = BusFactorMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "bus_factor" in result
        assert 0.0 <= result["bus_factor"] <= 1.0


class TestCodeQualityMetric:
    """Test cases for CodeQualityMetric."""
    
    def test_initialization(self):
        """Test CodeQualityMetric initialization."""
        metric = CodeQualityMetric()
        assert metric.get_metric_name() == "code_quality"
    
    def test_score(self):
        """Test scoring a model."""
        metric = CodeQualityMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "code_quality" in result
        assert 0.0 <= result["code_quality"] <= 1.0


class TestDatasetQualityMetric:
    """Test cases for DatasetQualityMetric."""
    
    def test_initialization(self):
        """Test DatasetQualityMetric initialization."""
        metric = DatasetQualityMetric()
        assert metric.get_metric_name() == "dataset_quality"
    
    def test_score(self):
        """Test scoring a model."""
        metric = DatasetQualityMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "dataset_quality" in result
        assert 0.0 <= result["dataset_quality"] <= 1.0


class TestLicenseMetric:
    """Test cases for LicenseMetric."""
    
    def test_initialization(self):
        """Test LicenseMetric initialization."""
        metric = LicenseMetric()
        assert metric.get_metric_name() == "license"
    
    def test_score(self):
        """Test scoring a model."""
        metric = LicenseMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset",
            license="MIT"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "license" in result
        assert 0.0 <= result["license"] <= 1.0


class TestPerformanceClaimsMetric:
    """Test cases for PerformanceClaimsMetric."""
    
    def test_initialization(self):
        """Test PerformanceClaimsMetric initialization."""
        metric = PerformanceClaimsMetric()
        assert metric.get_metric_name() == "performance_claims"
    
    def test_score(self):
        """Test scoring a model."""
        metric = PerformanceClaimsMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "performance_claims" in result
        assert 0.0 <= result["performance_claims"] <= 1.0


class TestRampUpMetric:
    """Test cases for RampUpMetric."""
    
    def test_initialization(self):
        """Test RampUpMetric initialization."""
        metric = RampUpMetric()
        assert metric.get_metric_name() == "ramp_up"
    
    def test_score(self):
        """Test scoring a model."""
        metric = RampUpMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "ramp_up" in result
        assert 0.0 <= result["ramp_up"] <= 1.0


class TestSizeMetric:
    """Test cases for SizeMetric."""
    
    def test_initialization(self):
        """Test SizeMetric initialization."""
        metric = SizeMetric()
        assert metric.get_metric_name() == "size"
    
    def test_score(self):
        """Test scoring a model."""
        metric = SizeMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset",
            size=1024.0
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "size" in result
        assert 0.0 <= result["size"] <= 1.0


class TestReproducibilityMetric:
    """Test cases for ReproducibilityMetric."""
    
    def test_initialization(self):
        """Test ReproducibilityMetric initialization."""
        metric = ReproducibilityMetric()
        assert metric.get_metric_name() == "reproducibility"
    
    def test_score(self):
        """Test scoring a model."""
        metric = ReproducibilityMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "reproducibility" in result
        assert 0.0 <= result["reproducibility"] <= 1.0


class TestReviewednessMetric:
    """Test cases for ReviewednessMetric."""
    
    def test_initialization(self):
        """Test ReviewednessMetric initialization."""
        metric = ReviewednessMetric()
        assert metric.get_metric_name() == "reviewedness"
    
    def test_score(self):
        """Test scoring a model."""
        metric = ReviewednessMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "reviewedness" in result
        assert 0.0 <= result["reviewedness"] <= 1.0


class TestTreescoreMetric:
    """Test cases for TreescoreMetric."""
    
    def test_initialization(self):
        """Test TreescoreMetric initialization."""
        metric = TreescoreMetric()
        assert metric.get_metric_name() == "treescore"
    
    def test_score(self):
        """Test scoring a model."""
        metric = TreescoreMetric()
        model = Model(
            name="test_model",
            model_key="models/test_model/model",
            code_key="models/test_model/code",
            dataset_key="models/test_model/dataset"
        )
        
        result = metric.score(model)
        assert isinstance(result, dict)
        assert "treescore" in result
        assert 0.0 <= result["treescore"] <= 1.0