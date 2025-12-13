"""Tests for size metric."""

import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.metrics.size_metric import SizeMetric


@pytest.fixture
def size_metric():
    return SizeMetric()


@pytest.fixture
def model():
    return ModelArtifact(
        artifact_id="test-model-123",
        name="test-model",
        source_url="https://example.com/model",
        s3_key="models/test-model-123",
        size=100 * 1024 * 1024,  # 100MB
    )


# =============================================================================
# Basic Functionality Tests
# =============================================================================
def test_small_model_fits_all_devices(size_metric, model):
    """Test that a small model (100MB) fits comfortably on all devices."""
    model.size = 100 * 1024 * 1024  # 100MB

    scores = size_metric.score(model)

    assert isinstance(scores, dict)
    assert "size_pi" in scores
    assert "size_nano" in scores
    assert "size_pc" in scores
    assert "size_server" in scores

    # 100MB fits comfortably on all devices (< 70% capacity)
    assert scores["size_pi"] == 1.0  # 100MB < 350MB (70% of 0.5GB)
    assert scores["size_nano"] == 1.0  # 100MB < 716MB (70% of 1GB)
    assert scores["size_pc"] == 1.0  # 100MB < 11.2GB (70% of 16GB)
    assert scores["size_server"] == 1.0  # 100MB < 44.8GB (70% of 64GB)


def test_medium_model_fits_some_devices(size_metric, model):
    """Test that a medium model (600MB) fits some devices but not others."""
    model.size = 600 * 1024 * 1024  # 600MB

    scores = size_metric.score(model)

    # 600MB doesn't fit on Pi (0.5GB capacity)
    assert scores["size_pi"] == 0.0

    # 600MB fits comfortably on Nano (1GB capacity, 60% utilization < 70%)
    assert scores["size_nano"] == 1.0

    # 600MB fits comfortably on PC and Server
    assert scores["size_pc"] == 1.0
    assert scores["size_server"] == 1.0


def test_large_model_fits_only_server(size_metric, model):
    """Test that a large model (20GB) only fits on server."""
    model.size = 20 * 1024 * 1024 * 1024  # 20GB

    scores = size_metric.score(model)

    # 20GB doesn't fit on Pi, Nano, or PC
    assert scores["size_pi"] == 0.0
    assert scores["size_nano"] == 0.0
    assert scores["size_pc"] == 0.0

    # 20GB fits on Server (31% utilization)
    assert scores["size_server"] == 1.0


def test_very_large_model_doesnt_fit_anywhere(size_metric, model):
    """Test that a very large model (70GB) doesn't fit even on server."""
    model.size = 70 * 1024 * 1024 * 1024  # 70GB

    scores = size_metric.score(model)

    # 70GB doesn't fit on any device
    assert scores["size_pi"] == 0.0
    assert scores["size_nano"] == 0.0
    assert scores["size_pc"] == 0.0
    assert scores["size_server"] == 0.0


# =============================================================================
# Edge Cases
# =============================================================================
def test_missing_size_returns_neutral_scores(size_metric, model):
    """Test that missing size returns neutral 0.5 scores for all devices."""
    model.size = None

    scores = size_metric.score(model)

    assert scores["size_pi"] == 0.5
    assert scores["size_nano"] == 0.5
    assert scores["size_pc"] == 0.5
    assert scores["size_server"] == 0.5


def test_zero_size_returns_neutral_scores(size_metric, model):
    """Test that zero size returns neutral 0.5 scores for all devices."""
    model.size = 0

    scores = size_metric.score(model)

    assert scores["size_pi"] == 0.5
    assert scores["size_nano"] == 0.5
    assert scores["size_pc"] == 0.5
    assert scores["size_server"] == 0.5


def test_negative_size_returns_neutral_scores(size_metric, model):
    """Test that negative size returns neutral 0.5 scores for all devices."""
    model.size = -100

    scores = size_metric.score(model)

    assert scores["size_pi"] == 0.5
    assert scores["size_nano"] == 0.5
    assert scores["size_pc"] == 0.5
    assert scores["size_server"] == 0.5


# =============================================================================
# Capacity Threshold Tests
# =============================================================================
def test_just_over_70_percent_capacity(size_metric, model):
    """Test model just over 70% of capacity."""
    # Pi capacity is 0.5GB, 70% is 0.35GB
    # Add a bit extra to ensure we're actually over 70%
    model.size = int(0.35 * 1024 * 1024 * 1024) + 1000

    scores = size_metric.score(model)

    # Just over 70% utilization, should get score of 0.7 (in 70-90% range)
    assert scores["size_pi"] == 0.7


def test_just_over_90_percent_capacity(size_metric, model):
    """Test model just over 90% of capacity."""
    # Pi capacity is 0.5GB, 90% is 0.45GB
    # Add a bit extra to ensure we're actually over 90%
    model.size = int(0.45 * 1024 * 1024 * 1024) + 1000

    scores = size_metric.score(model)

    # Just over 90% utilization, should get score of 0.4 (in 90-100% range)
    assert scores["size_pi"] == 0.4


def test_exactly_100_percent_capacity(size_metric, model):
    """Test model at exactly 100% of capacity."""
    # Pi capacity is 0.5GB
    model.size = int(0.5 * 1024 * 1024 * 1024)

    scores = size_metric.score(model)

    # At 100% utilization, should get score of 0.4 (still fits, in 90-100% range)
    assert scores["size_pi"] == 0.4


def test_over_capacity(size_metric, model):
    """Test model over 100% of capacity."""
    # Pi capacity is 0.5GB, use 0.51GB to ensure we're over
    model.size = int(0.51 * 1024 * 1024 * 1024)

    scores = size_metric.score(model)

    # Over capacity, model doesn't fit
    assert scores["size_pi"] == 0.0


def test_just_over_capacity(size_metric, model):
    """Test model just slightly over capacity."""
    # Pi capacity is 0.5GB, add 1 byte
    model.size = int(0.5 * 1024 * 1024 * 1024) + 1

    scores = size_metric.score(model)

    # Over capacity, doesn't fit
    assert scores["size_pi"] == 0.0


# =============================================================================
# Device Capacity Constants Tests
# =============================================================================
def test_device_capacity_constants():
    """Test that device capacity constants are correctly defined."""
    metric = SizeMetric()

    assert metric.PI_CAPACITY == 0.5 * 1024 * 1024 * 1024  # 0.5GB
    assert metric.NANO_CAPACITY == 1 * 1024 * 1024 * 1024  # 1GB
    assert metric.PC_CAPACITY == 16 * 1024 * 1024 * 1024  # 16GB
    assert metric.SERVER_CAPACITY == 64 * 1024 * 1024 * 1024  # 64GB


# =============================================================================
# Exception Handling Tests
# =============================================================================
def test_exception_during_calculation_returns_neutral_scores(size_metric, monkeypatch):
    """Test that exceptions during calculation return neutral scores."""

    def raise_error(*args, **kwargs):
        raise ValueError("Test error")

    monkeypatch.setattr(size_metric, "_calculate_device_score", raise_error)

    model = ModelArtifact(
        artifact_id="test-model-123",
        name="test-model",
        source_url="https://example.com/model",
        s3_key="models/test-model-123",
        size=100 * 1024 * 1024,
    )

    scores = size_metric.score(model)

    # Should return neutral scores on exception
    assert scores["size_pi"] == 0.5
    assert scores["size_nano"] == 0.5
    assert scores["size_pc"] == 0.5
    assert scores["size_server"] == 0.5


# =============================================================================
# Utilization Range Tests
# =============================================================================
def test_comfortable_fit_under_70_percent(size_metric):
    """Test _calculate_device_score with utilization < 70%."""
    capacity = 1024 * 1024 * 1024  # 1GB
    size = 600 * 1024 * 1024  # 600MB (60% utilization)

    score = size_metric._calculate_device_score(size, capacity)

    assert score == 1.0


def test_tight_fit_70_to_90_percent(size_metric):
    """Test _calculate_device_score with 70-90% utilization."""
    capacity = 1024 * 1024 * 1024  # 1GB
    size = 800 * 1024 * 1024  # 800MB (80% utilization)

    score = size_metric._calculate_device_score(size, capacity)

    assert score == 0.7


def test_barely_fits_90_to_100_percent(size_metric):
    """Test _calculate_device_score with 90-100% utilization."""
    capacity = 1024 * 1024 * 1024  # 1GB
    size = 950 * 1024 * 1024  # 950MB (95% utilization)

    score = size_metric._calculate_device_score(size, capacity)

    assert score == 0.4


def test_doesnt_fit_over_100_percent(size_metric):
    """Test _calculate_device_score when size exceeds capacity."""
    capacity = 1024 * 1024 * 1024  # 1GB
    size = 2 * 1024 * 1024 * 1024  # 2GB (200% utilization)

    score = size_metric._calculate_device_score(size, capacity)

    assert score == 0.0
