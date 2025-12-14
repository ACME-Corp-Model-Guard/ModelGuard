"""
Unit tests for lambdas/get_search_by_name.py
"""

import json
from unittest.mock import patch

from lambdas.get_search_by_name import lambda_handler
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.dataset_artifact import DatasetArtifact


class TestGetSearchByName:
    """Tests for GET /artifact/byName/{name} endpoint."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {"headers": {}, "pathParameters": {"name": "test"}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_missing_name_returns_400(self, mock_auth):
        """Missing name should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {"headers": {"X-Authorization": "bearer token"}, "pathParameters": {}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.get_search_by_name.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_no_artifacts_found_returns_404(self, mock_auth, mock_load):
        """No matching artifacts should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"name": "nonexistent"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.get_search_by_name.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_found_artifacts_returns_200(self, mock_auth, mock_load):
        """Found artifacts should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test-model", source_url="https://example.com")
        mock_load.return_value = [artifact]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"name": "test-model"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200

    @patch("lambdas.get_search_by_name.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_response_body_format(self, mock_auth, mock_load):
        """Response body should be array of ArtifactMetadata."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test-model", source_url="https://example.com")
        mock_load.return_value = [artifact]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"name": "test-model"},
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["name"] == "test-model"
        assert body[0]["id"] == artifact.artifact_id
        assert body[0]["type"] == "model"

    @patch("lambdas.get_search_by_name.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_multiple_artifacts_same_name(self, mock_auth, mock_load):
        """Multiple artifacts with same name should all be returned."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact1 = ModelArtifact(name="shared-name", source_url="https://example.com/1")
        artifact2 = DatasetArtifact(name="shared-name", source_url="https://example.com/2")
        mock_load.return_value = [artifact1, artifact2]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"name": "shared-name"},
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert len(body) == 2
        types = [item["type"] for item in body]
        assert "model" in types
        assert "dataset" in types

    @patch("lambdas.get_search_by_name.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_passes_name_to_loader(self, mock_auth, mock_load):
        """Should pass correct name to artifact loader."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"name": "specific-name"},
        }

        lambda_handler(event, None)

        mock_load.assert_called_once_with(fields={"name": "specific-name"})
