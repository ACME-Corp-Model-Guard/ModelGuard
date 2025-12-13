"""
Tests for artifact rejection and promotion functions.
"""

import pytest
from unittest.mock import patch

from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.artifactory.rejection import scores_below_threshold, promote


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def model_artifact():
    """Create a basic model artifact for testing."""
    return ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        size=1000,
        license="MIT",
        artifact_id="m-12345",
    )


# =============================================================================
# scores_below_threshold Tests
# =============================================================================


def test_scores_below_threshold_empty_scores(model_artifact):
    """Artifact with no scores should return empty list."""
    model_artifact.scores = {}
    result = scores_below_threshold(model_artifact)
    assert result == []


def test_scores_below_threshold_all_passing(model_artifact):
    """All scores >= 0.5 should return empty list."""
    model_artifact.scores = {
        "Availability": 0.5,
        "License": 0.8,
        "BusFactor": 0.6,
    }
    result = scores_below_threshold(model_artifact)
    assert result == []


def test_scores_below_threshold_one_failing(model_artifact):
    """One score < 0.5 should be returned."""
    model_artifact.scores = {
        "Availability": 0.5,
        "License": 0.3,  # Below threshold
        "BusFactor": 0.6,
    }
    result = scores_below_threshold(model_artifact)
    assert result == ["License"]


def test_scores_below_threshold_multiple_failing(model_artifact):
    """Multiple scores < 0.5 should all be returned."""
    model_artifact.scores = {
        "Availability": 0.4,  # Below threshold
        "License": 0.3,  # Below threshold
        "BusFactor": 0.6,
    }
    result = scores_below_threshold(model_artifact)
    assert "Availability" in result
    assert "License" in result
    assert len(result) == 2


def test_scores_below_threshold_skips_netscore(model_artifact):
    """NetScore should be skipped even if below threshold."""
    model_artifact.scores = {
        "Availability": 0.5,
        "License": 0.5,
        "NetScore": 0.3,  # Should be skipped
    }
    result = scores_below_threshold(model_artifact)
    assert result == []


def test_scores_below_threshold_exactly_at_threshold(model_artifact):
    """Score exactly at 0.5 should pass."""
    model_artifact.scores = {
        "Availability": 0.5,
        "License": 0.5,
    }
    result = scores_below_threshold(model_artifact)
    assert result == []


def test_scores_below_threshold_just_below_threshold(model_artifact):
    """Score just below 0.5 should fail."""
    model_artifact.scores = {
        "Availability": 0.49,
    }
    result = scores_below_threshold(model_artifact)
    assert result == ["Availability"]


def test_scores_below_threshold_dict_scores_all_passing(model_artifact):
    """Dict scores (like Size) with all platforms passing."""
    model_artifact.scores = {
        "Size": {
            "raspberry_pi": 0.6,
            "jetson_nano": 0.7,
            "desktop_pc": 0.8,
            "aws_server": 0.9,
        }
    }
    result = scores_below_threshold(model_artifact)
    assert result == []


def test_scores_below_threshold_dict_scores_one_failing(model_artifact):
    """Dict scores with one platform failing."""
    model_artifact.scores = {
        "Size": {
            "raspberry_pi": 0.3,  # Below threshold
            "jetson_nano": 0.7,
            "desktop_pc": 0.8,
            "aws_server": 0.9,
        }
    }
    result = scores_below_threshold(model_artifact)
    assert result == ["Size.raspberry_pi"]


def test_scores_below_threshold_dict_scores_multiple_failing(model_artifact):
    """Dict scores with multiple platforms failing."""
    model_artifact.scores = {
        "Size": {
            "raspberry_pi": 0.2,  # Below threshold
            "jetson_nano": 0.3,  # Below threshold
            "desktop_pc": 0.8,
            "aws_server": 0.9,
        }
    }
    result = scores_below_threshold(model_artifact)
    assert "Size.raspberry_pi" in result
    assert "Size.jetson_nano" in result
    assert len(result) == 2


def test_scores_below_threshold_mixed_scores(model_artifact):
    """Mix of regular scores and dict scores."""
    model_artifact.scores = {
        "Availability": 0.4,  # Below threshold
        "License": 0.8,
        "Size": {
            "raspberry_pi": 0.3,  # Below threshold
            "desktop_pc": 0.9,
        },
    }
    result = scores_below_threshold(model_artifact)
    assert "Availability" in result
    assert "Size.raspberry_pi" in result
    assert len(result) == 2


def test_scores_below_threshold_zero_score(model_artifact):
    """Score of 0 should fail."""
    model_artifact.scores = {
        "Availability": 0.0,
    }
    result = scores_below_threshold(model_artifact)
    assert result == ["Availability"]


def test_scores_below_threshold_perfect_score(model_artifact):
    """Score of 1.0 should pass."""
    model_artifact.scores = {
        "Availability": 1.0,
    }
    result = scores_below_threshold(model_artifact)
    assert result == []


def test_scores_below_threshold_no_scores_attr(model_artifact):
    """Artifact without scores attribute should return empty list."""
    # Remove scores attribute
    if hasattr(model_artifact, "scores"):
        delattr(model_artifact, "scores")
    result = scores_below_threshold(model_artifact)
    assert result == []


def test_scores_below_threshold_integer_scores(model_artifact):
    """Integer scores should work correctly."""
    model_artifact.scores = {
        "Availability": 1,  # Integer 1
        "License": 0,  # Integer 0 - should fail
    }
    result = scores_below_threshold(model_artifact)
    assert result == ["License"]


def test_scores_below_threshold_dict_with_non_numeric(model_artifact):
    """Dict scores with non-numeric values should be skipped."""
    model_artifact.scores = {
        "Size": {
            "raspberry_pi": 0.3,  # Below threshold
            "metadata": "some string",  # Should be skipped
        }
    }
    result = scores_below_threshold(model_artifact)
    assert result == ["Size.raspberry_pi"]


# =============================================================================
# promote Tests
# =============================================================================


@patch("src.artifacts.artifactory.rejection.batch_delete")
@patch("src.artifacts.artifactory.rejection.save_artifact_metadata")
def test_promote_saves_to_main_table(mock_save, mock_delete, model_artifact):
    """Promote should save artifact to main table."""
    promote(model_artifact)
    mock_save.assert_called_once_with(model_artifact, rejected=False)


@patch("src.artifacts.artifactory.rejection.batch_delete")
@patch("src.artifacts.artifactory.rejection.save_artifact_metadata")
def test_promote_deletes_from_rejected_table(mock_save, mock_delete, model_artifact):
    """Promote should delete artifact from rejected table."""
    promote(model_artifact)
    mock_delete.assert_called_once()
    # Check that the artifact_id was passed correctly
    call_args = mock_delete.call_args
    assert call_args[1]["items"] == [{"artifact_id": model_artifact.artifact_id}]
    assert call_args[1]["key_name"] == "artifact_id"


@patch("src.artifacts.artifactory.rejection.batch_delete")
@patch("src.artifacts.artifactory.rejection.save_artifact_metadata")
def test_promote_order_of_operations(mock_save, mock_delete, model_artifact):
    """Promote should save before deleting."""
    call_order = []

    def save_side_effect(*args, **kwargs):
        call_order.append("save")

    def delete_side_effect(*args, **kwargs):
        call_order.append("delete")

    mock_save.side_effect = save_side_effect
    mock_delete.side_effect = delete_side_effect

    promote(model_artifact)

    assert call_order == ["save", "delete"]
