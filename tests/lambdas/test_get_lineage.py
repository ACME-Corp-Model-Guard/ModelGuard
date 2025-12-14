"""
Unit tests for lambdas/get_lineage.py
"""

import json
from unittest.mock import patch

from lambdas.get_lineage import lambda_handler, add_ancestors, add_descendants
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.dataset_artifact import DatasetArtifact


class TestAddAncestors:
    """Tests for add_ancestors helper."""

    @patch("lambdas.get_lineage.load_artifact_metadata")
    def test_no_parent(self, mock_load):
        """Model with no parent should not add nodes."""
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.parent_model_id = None
        nodes = []
        edges = []

        add_ancestors(model, nodes, edges)

        assert len(nodes) == 0
        assert len(edges) == 0

    @patch("lambdas.get_lineage.load_artifact_metadata")
    def test_with_parent(self, mock_load):
        """Model with parent should add parent node and edge."""
        parent = ModelArtifact(name="parent", source_url="https://example.com/parent")
        parent.parent_model_id = None

        child = ModelArtifact(name="child", source_url="https://example.com/child")
        child.parent_model_id = parent.artifact_id
        child.parent_model_source = "config_json"
        child.parent_model_relationship = "derived"

        mock_load.return_value = parent
        nodes = []
        edges = []

        add_ancestors(child, nodes, edges)

        assert len(nodes) == 1
        assert nodes[0]["artifact_id"] == parent.artifact_id
        assert len(edges) == 1
        assert edges[0]["from_node_artifact_id"] == parent.artifact_id
        assert edges[0]["to_node_artifact_id"] == child.artifact_id

    @patch("lambdas.get_lineage.load_artifact_metadata")
    def test_parent_not_found(self, mock_load):
        """Non-existent parent should not add nodes."""
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.parent_model_id = "nonexistent"
        mock_load.return_value = None
        nodes = []
        edges = []

        add_ancestors(model, nodes, edges)

        assert len(nodes) == 0
        assert len(edges) == 0


class TestAddDescendants:
    """Tests for add_descendants helper."""

    @patch("lambdas.get_lineage.load_artifact_metadata")
    def test_no_children(self, mock_load):
        """Model with no children should not add nodes."""
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.child_model_ids = []
        nodes = []
        edges = []

        add_descendants(model, nodes, edges)

        assert len(nodes) == 0
        assert len(edges) == 0

    @patch("lambdas.get_lineage.load_artifact_metadata")
    def test_with_children(self, mock_load):
        """Model with children should add child nodes and edges."""
        parent = ModelArtifact(name="parent", source_url="https://example.com/parent")

        child = ModelArtifact(name="child", source_url="https://example.com/child")
        child.child_model_ids = []
        child.parent_model_source = "config_json"
        child.parent_model_relationship = "derived"

        parent.child_model_ids = [child.artifact_id]

        mock_load.return_value = child
        nodes = []
        edges = []

        add_descendants(parent, nodes, edges)

        assert len(nodes) == 1
        assert nodes[0]["artifact_id"] == child.artifact_id
        assert len(edges) == 1
        assert edges[0]["from_node_artifact_id"] == parent.artifact_id
        assert edges[0]["to_node_artifact_id"] == child.artifact_id


class TestLambdaHandler:
    """Tests for GET /artifact/model/{id}/lineage lambda handler."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {"headers": {}, "pathParameters": {"id": "test-id"}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_missing_id_returns_400(self, mock_auth):
        """Missing id should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {"headers": {"X-Authorization": "bearer token"}, "pathParameters": {}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.get_lineage.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_artifact_not_found_returns_404(self, mock_auth, mock_load):
        """Non-existent artifact should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = None
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": "nonexistent"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.get_lineage.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_non_model_returns_400(self, mock_auth, mock_load):
        """Non-model artifact should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        dataset = DatasetArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = dataset
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": dataset.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.get_lineage.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_successful_lineage_returns_200(self, mock_auth, mock_load):
        """Successful lineage request should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.parent_model_id = None
        model.child_model_ids = []
        mock_load.return_value = model
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200

    @patch("lambdas.get_lineage.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_response_includes_nodes_and_edges(self, mock_auth, mock_load):
        """Response should include nodes and edges arrays."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.parent_model_id = None
        model.child_model_ids = []
        mock_load.return_value = model
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert "nodes" in body
        assert "edges" in body
        assert isinstance(body["nodes"], list)
        assert isinstance(body["edges"], list)

    @patch("lambdas.get_lineage.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_root_node_included(self, mock_auth, mock_load):
        """Root node should be included in response."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="root-model", source_url="https://example.com")
        model.parent_model_id = None
        model.child_model_ids = []
        mock_load.return_value = model
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert len(body["nodes"]) == 1
        assert body["nodes"][0]["artifact_id"] == model.artifact_id
        assert body["nodes"][0]["name"] == "root-model"
