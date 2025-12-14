"""
Unit tests for lambdas/get_artifact_download.py
"""

import json
from unittest.mock import patch

from lambdas.get_artifact_download import lambda_handler
from src.artifacts.model_artifact import ModelArtifact


class TestGetArtifactDownload:
    """Tests for GET /artifacts/{type}/{id} endpoint."""

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
    def test_missing_artifact_type_returns_400(self, mock_auth):
        """Missing artifact_type should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": "test-id"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("src.auth.authorize")
    def test_missing_id_returns_400(self, mock_auth):
        """Missing id should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
        }

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

    @patch("lambdas.get_artifact_download.load_artifact_metadata")
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

    @patch("lambdas.get_artifact_download.generate_s3_download_url")
    @patch("lambdas.get_artifact_download.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_successful_download_returns_200(self, mock_auth, mock_load, mock_url):
        """Successful download request should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_url.return_value = "https://s3.example.com/presigned"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200

    @patch("lambdas.get_artifact_download.generate_s3_download_url")
    @patch("lambdas.get_artifact_download.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_response_body_format(self, mock_auth, mock_load, mock_url):
        """Response body should match Artifact schema."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test-model", source_url="https://example.com/source")
        mock_load.return_value = artifact
        mock_url.return_value = "https://s3.example.com/presigned"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert "metadata" in body
        assert "data" in body
        assert body["metadata"]["name"] == "test-model"
        assert body["metadata"]["type"] == "model"
        assert body["metadata"]["id"] == artifact.artifact_id
        assert body["data"]["url"] == "https://example.com/source"
        assert body["data"]["download_url"] == "https://s3.example.com/presigned"

    @patch("lambdas.get_artifact_download.generate_s3_download_url")
    @patch("lambdas.get_artifact_download.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_s3_url_generation_failure_returns_500(self, mock_auth, mock_load, mock_url):
        """S3 URL generation failure should return 500."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_url.side_effect = Exception("S3 error")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500

    @patch("lambdas.get_artifact_download.generate_s3_download_url")
    @patch("lambdas.get_artifact_download.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_dataset_download(self, mock_auth, mock_load, mock_url):
        """Dataset download should work correctly."""
        mock_auth.return_value = {"username": "test", "groups": []}
        from src.artifacts.dataset_artifact import DatasetArtifact

        artifact = DatasetArtifact(name="test-dataset", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_url.return_value = "https://s3.example.com/presigned"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "dataset", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["metadata"]["type"] == "dataset"

    @patch("lambdas.get_artifact_download.generate_s3_download_url")
    @patch("lambdas.get_artifact_download.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_code_download(self, mock_auth, mock_load, mock_url):
        """Code download should work correctly."""
        mock_auth.return_value = {"username": "test", "groups": []}
        from src.artifacts.code_artifact import CodeArtifact

        artifact = CodeArtifact(name="test-code", source_url="https://github.com/test/repo")
        mock_load.return_value = artifact
        mock_url.return_value = "https://s3.example.com/presigned"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "code", "id": artifact.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["metadata"]["type"] == "code"
