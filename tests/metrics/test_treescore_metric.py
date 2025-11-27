import pytest
from unittest.mock import patch

from src.metrics.treescore_metric import TreescoreMetric
from src.artifacts.model_artifact import ModelArtifact


class DummyModelArtifact(ModelArtifact):
    def __init__(self, artifact_id, parent_model_id=None, scores=None):
        self.artifact_id = artifact_id
        self.parent_model_id = parent_model_id
        self.scores = scores or {}


@pytest.fixture
def metric():
    return TreescoreMetric()


# =====================================================================================
# NO PARENT CASE
# =====================================================================================
def test_treescore_no_parent(metric):
    model = DummyModelArtifact(artifact_id="m1", parent_model_id=None)
    result = metric.score(model)
    assert "treescore" in result
    assert result["treescore"] == 0.5


# =====================================================================================
# SINGLE PARENT CASE
# =====================================================================================
def test_treescore_single_parent(metric):
    parent = DummyModelArtifact(
        artifact_id="p1", parent_model_id=None, scores={"net_score": 0.8}
    )
    model = DummyModelArtifact(artifact_id="m1", parent_model_id="p1")
    with patch(
        "src.metrics.treescore_metric.load_artifact_metadata", return_value=parent
    ):
        result = metric.score(model)
    assert result["treescore"] == 0.8


# =====================================================================================
# ANCESTOR CHAIN CASE
# =====================================================================================
def test_treescore_ancestor_chain(metric):
    grandparent = DummyModelArtifact(
        artifact_id="g1", parent_model_id=None, scores={"net_score": 0.6}
    )
    parent = DummyModelArtifact(
        artifact_id="p1", parent_model_id="g1", scores={"net_score": 0.9}
    )
    model = DummyModelArtifact(artifact_id="m1", parent_model_id="p1")

    def load_artifact_metadata_side_effect(artifact_id):
        if artifact_id == "p1":
            return parent
        elif artifact_id == "g1":
            return grandparent
        return None

    from src.artifacts.artifactory import load_artifact_metadata

    with patch(
        "src.metrics.treescore_metric.load_artifact_metadata",
        side_effect=load_artifact_metadata_side_effect,
    ):
        result = metric.score(model)
    # Average of parent and grandparent net_scores
    assert result["treescore"] == pytest.approx((0.9 + 0.6) / 2)
