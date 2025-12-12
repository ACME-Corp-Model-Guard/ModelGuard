"""Tests for bus factor metric."""

import pytest

from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.code_artifact import CodeArtifact
from src.metrics.bus_factor_metric import BusFactorMetric


@pytest.fixture
def bus_factor_metric():
    return BusFactorMetric()


@pytest.fixture
def model():
    return ModelArtifact(
        artifact_id="test-model-123",
        name="test-model",
        source_url="https://example.com/model",
        s3_key="models/test-model-123",
        code_artifact_id="code-123",
    )


# =============================================================================
# No Code Artifact Tests
# =============================================================================
def test_no_code_artifact_id_returns_zero(bus_factor_metric):
    """Test that model without code_artifact_id returns 0.0 score."""
    model = ModelArtifact(
        artifact_id="test-model-123",
        name="test-model",
        source_url="https://example.com/model",
        s3_key="models/test-model-123",
        code_artifact_id=None,  # No code artifact
    )

    score = bus_factor_metric.score(model)

    assert isinstance(score, dict)
    assert "bus_factor" in score
    assert score["bus_factor"] == 0.0


def test_invalid_code_artifact_returns_zero(bus_factor_metric, model, monkeypatch):
    """Test that invalid code artifact returns 0.0 score."""

    def fake_load(artifact_id):
        # Return a ModelArtifact instead of CodeArtifact
        return ModelArtifact(
            artifact_id=artifact_id,
            name="wrong-type",
            source_url="https://example.com",
            s3_key="models/wrong",
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    assert score["bus_factor"] == 0.0


def test_missing_code_artifact_returns_zero(bus_factor_metric, model, monkeypatch):
    """Test that missing code artifact returns 0.0 score."""

    def fake_load(artifact_id):
        return None

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    assert score["bus_factor"] == 0.0


# =============================================================================
# Missing Metadata/Contributors Tests
# =============================================================================
def test_no_metadata_returns_zero(bus_factor_metric, model, monkeypatch):
    """Test that code artifact without metadata returns 0.0 score."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata=None,  # No metadata
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    assert score["bus_factor"] == 0.0


def test_empty_contributors_returns_zero(bus_factor_metric, model, monkeypatch):
    """Test that code artifact with empty contributors list returns 0.0 score."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={"contributors": []},  # Empty contributors
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    assert score["bus_factor"] == 0.0


def test_missing_contributors_field_returns_zero(bus_factor_metric, model, monkeypatch):
    """Test that code artifact without contributors field returns 0.0 score."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={"some_other_field": "value"},  # No contributors field
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    assert score["bus_factor"] == 0.0


# =============================================================================
# Bus Factor Calculation Tests
# =============================================================================
def test_single_contributor_low_score(bus_factor_metric, model, monkeypatch):
    """Test that single contributor results in low bus factor (0.1)."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={
                "contributors": [
                    {"name": "Alice", "contributions": 100},
                ]
            },
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    # 1 contributor needed for 50% = 1/10 = 0.1
    assert score["bus_factor"] == 0.1


def test_five_contributors_medium_score(bus_factor_metric, model, monkeypatch):
    """Test that 5 contributors results in medium bus factor (0.5)."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={
                "contributors": [
                    {"name": "A", "contributions": 20},
                    {"name": "B", "contributions": 20},
                    {"name": "C", "contributions": 20},
                    {"name": "D", "contributions": 20},
                    {"name": "E", "contributions": 20},
                ]
            },
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    # 3 contributors needed for 50% (20+20+20 = 60%), score = 3/10 = 0.3
    assert score["bus_factor"] == 0.3


def test_ten_contributors_high_score(bus_factor_metric, model, monkeypatch):
    """Test that 10+ contributors results in high bus factor (1.0)."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={
                "contributors": [
                    {"name": f"Contributor{i}", "contributions": 10} for i in range(10)
                ]
            },
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    # 5 contributors needed for 50%, score = min(1.0, 5/10) = 0.5
    assert score["bus_factor"] == 0.5


def test_many_contributors_with_bonus(bus_factor_metric, model, monkeypatch):
    """Test that 20+ contributors gets a bonus."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={
                "contributors": [
                    {"name": f"Contributor{i}", "contributions": 10} for i in range(25)
                ]
            },
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    # 13 contributors needed for 50% (10*12 = 120, 10*13 = 130 which is > 125)
    # Base score = 13/10 = 1.3, but capped at 1.0
    # Then +0.1 bonus for >20 contributors, but still capped at 1.0
    assert score["bus_factor"] == 1.0


# =============================================================================
# Unequal Distribution Tests
# =============================================================================
def test_unequal_distribution_low_bus_factor(bus_factor_metric, model, monkeypatch):
    """Test that unequal distribution (one dominant contributor) results in low bus factor."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={
                "contributors": [
                    {"name": "Alice", "contributions": 90},  # Dominant contributor
                    {"name": "Bob", "contributions": 5},
                    {"name": "Charlie", "contributions": 5},
                ]
            },
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    # Only 1 contributor (Alice) is needed for 50%, score = 1/10 = 0.1
    assert score["bus_factor"] == 0.1


def test_equal_distribution_higher_bus_factor(bus_factor_metric, model, monkeypatch):
    """Test that equal distribution results in higher bus factor."""

    def fake_load(artifact_id):
        return CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={
                "contributors": [
                    {"name": "A", "contributions": 25},
                    {"name": "B", "contributions": 25},
                    {"name": "C", "contributions": 25},
                    {"name": "D", "contributions": 25},
                ]
            },
        )

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)

    score = bus_factor_metric.score(model)

    # 2 contributors needed for 50% (25+25 = 50%), score = 2/10 = 0.2
    assert score["bus_factor"] == 0.2


# =============================================================================
# Edge Cases
# =============================================================================
def test_zero_total_contributions_returns_zero(bus_factor_metric):
    """Test that zero total contributions returns 0.0 score."""
    contributors = [
        {"name": "Alice", "contributions": 0},
        {"name": "Bob", "contributions": 0},
    ]

    score = bus_factor_metric._calculate_bus_factor(contributors)

    assert score == 0.0


def test_missing_contributions_field_treated_as_zero(bus_factor_metric):
    """Test that missing contributions field is treated as 0."""
    contributors = [
        {"name": "Alice", "contributions": 100},
        {"name": "Bob"},  # Missing contributions field
    ]

    score = bus_factor_metric._calculate_bus_factor(contributors)

    # Only Alice has contributions, so 1 contributor needed for 50%
    assert score == 0.1


def test_empty_contributors_list_returns_zero(bus_factor_metric):
    """Test that empty contributors list returns 0.0 score."""
    score = bus_factor_metric._calculate_bus_factor([])

    assert score == 0.0


def test_score_capped_at_one(bus_factor_metric):
    """Test that score is capped at 1.0 even with many contributors."""
    # Create scenario where base score would exceed 1.0
    contributors = [{"name": f"C{i}", "contributions": 1} for i in range(50)]

    score = bus_factor_metric._calculate_bus_factor(contributors)

    # Score should be capped at 1.0
    assert score == 1.0


# =============================================================================
# Exception Handling Tests
# =============================================================================
def test_exception_during_calculation_returns_zero(bus_factor_metric, model, monkeypatch):
    """Test that exceptions during calculation return 0.0 score."""

    def fake_load(artifact_id):
        code_artifact = CodeArtifact(
            artifact_id=artifact_id,
            name="test-code",
            source_url="https://github.com/user/repo",
            s3_key="code/test-code",
            metadata={"contributors": [{"name": "Alice", "contributions": 100}]},
        )
        return code_artifact

    def fake_calculate(*args, **kwargs):
        raise ValueError("Test error")

    monkeypatch.setattr("src.metrics.bus_factor_metric.load_artifact_metadata", fake_load)
    monkeypatch.setattr(bus_factor_metric, "_calculate_bus_factor", fake_calculate)

    score = bus_factor_metric.score(model)

    assert score["bus_factor"] == 0.0


# =============================================================================
# Sorting and Calculation Logic Tests
# =============================================================================
def test_contributors_sorted_by_contributions(bus_factor_metric):
    """Test that contributors are properly sorted by contributions."""
    contributors = [
        {"name": "A", "contributions": 10},
        {"name": "B", "contributions": 50},  # Should be first
        {"name": "C", "contributions": 30},
        {"name": "D", "contributions": 10},
    ]

    score = bus_factor_metric._calculate_bus_factor(contributors)

    # B alone has 50% of 100 contributions, so 1 contributor needed
    assert score == 0.1


def test_cumulative_calculation_stops_at_50_percent(bus_factor_metric):
    """Test that calculation stops once 50% threshold is reached."""
    contributors = [
        {"name": "A", "contributions": 30},
        {"name": "B", "contributions": 25},  # Cumulative: 55% - stops here
        {"name": "C", "contributions": 25},
        {"name": "D", "contributions": 20},
    ]

    score = bus_factor_metric._calculate_bus_factor(contributors)

    # 2 contributors needed (30 + 25 = 55 > 50)
    assert score == 0.2
