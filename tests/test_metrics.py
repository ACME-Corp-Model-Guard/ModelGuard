#!/usr/bin/env python3
"""
Tests for the metric classes.
"""

from pathlib import Path

import pytest
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
from src.metrics.metric import Metric


class TestMetricUtilities:
    """Test cases for Metric utility methods."""
    
    def test_clamp01(self):
        """Test clamping values to [0, 1]."""
        # Create a minimal metric instance
        class TestMetric(Metric):
            def score(self, path_or_url: str) -> dict:
                return {}
        
        metric = TestMetric()
        
        assert metric._clamp01(0.5) == 0.5
        assert metric._clamp01(-0.1) == 0.0
        assert metric._clamp01(1.1) == 1.0
    
    def test_saturating_scale(self):
        """Test saturating scale function."""
        class TestMetric(Metric):
            def score(self, path_or_url: str) -> dict:
                return {}
        
        metric = TestMetric()
        
        assert metric._saturating_scale(0.5, knee=1.0, max_x=2.0) == 0.25
        assert metric._saturating_scale(1.5, knee=1.0, max_x=2.0) == 0.75
        assert metric._saturating_scale(0.0, knee=1.0, max_x=2.0) == 0.0
        assert metric._saturating_scale(3.0, knee=1.0, max_x=2.0) == 1.0


class TestAvailabilityMetric:
    """Test cases for AvailabilityMetric."""
    
    def test_initialization(self):
        """Test AvailabilityMetric initialization."""
        metric = AvailabilityMetric()
        assert isinstance(metric, AvailabilityMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = AvailabilityMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "availability" in result
        assert 0.0 <= result["availability"] <= 1.0


class TestBusFactorMetric:
    """Test cases for BusFactorMetric."""
    
    def test_initialization(self):
        """Test BusFactorMetric initialization."""
        metric = BusFactorMetric()
        assert isinstance(metric, BusFactorMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = BusFactorMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "bus_factor" in result
        assert 0.0 <= result["bus_factor"] <= 1.0


class TestCodeQualityMetric:
    """Test cases for CodeQualityMetric."""
    
    def test_initialization(self):
        """Test CodeQualityMetric initialization."""
        metric = CodeQualityMetric()
        assert isinstance(metric, CodeQualityMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = CodeQualityMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "code_quality" in result
        assert 0.0 <= result["code_quality"] <= 1.0


class TestDatasetQualityMetric:
    """Test cases for DatasetQualityMetric."""
    
    def test_initialization(self):
        """Test DatasetQualityMetric initialization."""
        metric = DatasetQualityMetric()
        assert isinstance(metric, DatasetQualityMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = DatasetQualityMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "dataset_quality" in result
        assert 0.0 <= result["dataset_quality"] <= 1.0


class TestLicenseMetric:
    """Test cases for LicenseMetric."""
    
    def test_initialization(self):
        """Test LicenseMetric initialization."""
        metric = LicenseMetric()
        assert isinstance(metric, LicenseMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = LicenseMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "license" in result
        assert 0.0 <= result["license"] <= 1.0


class TestPerformanceClaimsMetric:
    """Test cases for PerformanceClaimsMetric."""
    
    def test_initialization(self):
        """Test PerformanceClaimsMetric initialization."""
        metric = PerformanceClaimsMetric()
        assert isinstance(metric, PerformanceClaimsMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = PerformanceClaimsMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "performance_claims" in result
        assert 0.0 <= result["performance_claims"] <= 1.0


class TestRampUpMetric:
    """Test cases for RampUpMetric."""
    
    def test_initialization(self):
        """Test RampUpMetric initialization."""
        metric = RampUpMetric()
        assert isinstance(metric, RampUpMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = RampUpMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "ramp_up" in result
        assert 0.0 <= result["ramp_up"] <= 1.0


class TestSizeMetric:
    """Test cases for SizeMetric."""
    
    def test_initialization(self):
        """Test SizeMetric initialization."""
        metric = SizeMetric()
        assert isinstance(metric, SizeMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = SizeMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "files" in result
        assert "lines" in result
        assert "commits" in result


class TestReproducibilityMetric:
    """Test cases for ReproducibilityMetric."""
    
    def test_initialization(self):
        """Test ReproducibilityMetric initialization."""
        metric = ReproducibilityMetric()
        assert isinstance(metric, ReproducibilityMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = ReproducibilityMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "reproducibility" in result
        assert 0.0 <= result["reproducibility"] <= 1.0


class TestReviewednessMetric:
    """Test cases for ReviewednessMetric."""
    
    def test_initialization(self):
        """Test ReviewednessMetric initialization."""
        metric = ReviewednessMetric()
        assert isinstance(metric, ReviewednessMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = ReviewednessMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "reviewedness" in result
        assert 0.0 <= result["reviewedness"] <= 1.0


class TestTreescoreMetric:
    """Test cases for TreescoreMetric."""
    
    def test_initialization(self):
        """Test TreescoreMetric initialization."""
        metric = TreescoreMetric()
        assert isinstance(metric, TreescoreMetric)
    
    def test_score_with_url(self):
        """Test scoring a URL."""
        metric = TreescoreMetric()
        result = metric.score("https://example.com/repo")
        
        assert isinstance(result, dict)
        assert "treescore" in result
        assert 0.0 <= result["treescore"] <= 1.0
