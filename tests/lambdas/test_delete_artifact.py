"""
Unit tests for lambdas/delete_artifact.py
"""

import json
from unittest.mock import patch

from lambdas.delete_artifact import lambda_handler
from src.artifacts.model_artifact import ModelArtifact


class TestDeleteArtifact:
    """Tests for DELETE /artifacts/{type}/{id} endpoint."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {
            "headers": {},
            "pathParameters": {"artifact_type": "model", "id": "test-id"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_missing_path_params_returns_400(self, mock_auth):
        """Missing path parameters should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {"headers": {"X-Authorization": "bearer token"}, "pathParameters": {}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("src.auth.authorize")
    def test_invalid_artifact_type_returns_400(self, mock_auth):
        """Invalid artifact_type should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "invalid", "id": "test-id"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.delete_artifact.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_artifact_not_found_returns_404(self, mock_auth, mock_load):
        """Non-existent artifact should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = None
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": "nonexistent"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.delete_artifact.delete_objects")
    @patch("lambdas.delete_artifact.delete_item")
    @patch("lambdas.delete_artifact.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_successful_delete_returns_200(
        self, mock_auth, mock_load, mock_delete_item, mock_delete_s3
    ):
        """Successful delete should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Artifact is deleted"

    @patch("lambdas.delete_artifact.delete_objects")
    @patch("lambdas.delete_artifact.delete_item")
    @patch("lambdas.delete_artifact.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_delete_calls_dynamo_delete(
        self, mock_auth, mock_load, mock_delete_item, mock_delete_s3
    ):
        """Delete should call DynamoDB delete."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        lambda_handler(event, None)

        mock_delete_item.assert_called_once()

    @patch("lambdas.delete_artifact.delete_objects")
    @patch("lambdas.delete_artifact.delete_item")
    @patch("lambdas.delete_artifact.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_delete_calls_s3_delete(self, mock_auth, mock_load, mock_delete_item, mock_delete_s3):
        """Delete should call S3 delete."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        lambda_handler(event, None)

        mock_delete_s3.assert_called_once()

    @patch("lambdas.delete_artifact.delete_objects")
    @patch("lambdas.delete_artifact.delete_item")
    @patch("lambdas.delete_artifact.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_dynamo_delete_failure_returns_500(
        self, mock_auth, mock_load, mock_delete_item, mock_delete_s3
    ):
        """DynamoDB delete failure should return 500."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_delete_item.side_effect = Exception("DynamoDB error")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500

    @patch("lambdas.delete_artifact.delete_objects")
    @patch("lambdas.delete_artifact.delete_item")
    @patch("lambdas.delete_artifact.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_s3_delete_failure_still_returns_200(
        self, mock_auth, mock_load, mock_delete_item, mock_delete_s3
    ):
        """S3 delete failure should still return 200 (best effort)."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_delete_s3.side_effect = Exception("S3 error")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)

        # Should still return 200 since metadata was deleted
        assert response["statusCode"] == 200
