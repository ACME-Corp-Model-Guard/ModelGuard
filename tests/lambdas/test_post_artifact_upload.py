"""
Unit tests for lambdas/post_artifact_upload.py
"""

import json
from unittest.mock import patch

from lambdas.post_artifact_upload import lambda_handler
from src.artifacts.model_artifact import ModelArtifact
from src.storage.downloaders.dispatchers import FileDownloadError


class TestPostArtifactUpload:
    """Tests for POST /artifact/{type} endpoint."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {
            "headers": {},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_missing_artifact_type_returns_400(self, mock_auth):
        """Missing artifact_type path parameter should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "artifact_type" in body.get("message", body.get("error", ""))

    @patch("src.auth.authorize")
    def test_invalid_artifact_type_returns_400(self, mock_auth):
        """Invalid artifact_type should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "invalid"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid artifact_type" in body.get("message", body.get("error", ""))

    @patch("src.auth.authorize")
    def test_invalid_json_body_returns_400(self, mock_auth):
        """Invalid JSON body should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": "not json",
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("src.auth.authorize")
    def test_missing_url_returns_400(self, mock_auth):
        """Missing url field should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"name": "test"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "url" in body.get("message", body.get("error", "")).lower()

    @patch("lambdas.post_artifact_upload.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_duplicate_url_returns_409(self, mock_auth, mock_load):
        """Duplicate source URL should return 409 Conflict."""
        mock_auth.return_value = {"username": "test", "groups": []}
        existing = ModelArtifact(name="existing", source_url="https://example.com")
        mock_load.return_value = [existing]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 409

    @patch("lambdas.post_artifact_upload.create_artifact")
    @patch("lambdas.post_artifact_upload.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_upstream_not_found_returns_404(self, mock_auth, mock_load, mock_create):
        """Upstream artifact not found should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        mock_create.side_effect = FileDownloadError("Not found")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"url": "https://example.com/nonexistent"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.post_artifact_upload.generate_s3_download_url")
    @patch("lambdas.post_artifact_upload.save_artifact_metadata")
    @patch("lambdas.post_artifact_upload.create_artifact")
    @patch("lambdas.post_artifact_upload.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_successful_upload_returns_201(
        self, mock_auth, mock_load, mock_create, mock_save, mock_url
    ):
        """Successful upload should return 201 Created."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.scores = {"NetScore": 0.8}  # Above threshold
        mock_create.return_value = artifact
        mock_url.return_value = "https://s3.example.com/presigned"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 201
        mock_save.assert_called_once()

    @patch("lambdas.post_artifact_upload.generate_s3_download_url")
    @patch("lambdas.post_artifact_upload.save_artifact_metadata")
    @patch("lambdas.post_artifact_upload.create_artifact")
    @patch("lambdas.post_artifact_upload.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_response_body_format(self, mock_auth, mock_load, mock_create, mock_save, mock_url):
        """Response body should match ArtifactResponse schema."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        artifact = ModelArtifact(name="test-model", source_url="https://example.com")
        artifact.scores = {"NetScore": 0.8}
        mock_create.return_value = artifact
        mock_url.return_value = "https://s3.example.com/presigned"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert "metadata" in body
        assert "data" in body
        assert body["metadata"]["name"] == "test-model"
        assert body["metadata"]["type"] == "model"
        assert "id" in body["metadata"]
        assert body["data"]["url"] == "https://example.com"
        assert "download_url" in body["data"]

    @patch("lambdas.post_artifact_upload.save_artifact_metadata")
    @patch("lambdas.post_artifact_upload.scores_below_threshold")
    @patch("lambdas.post_artifact_upload.create_artifact")
    @patch("lambdas.post_artifact_upload.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_model_below_threshold_returns_424(
        self, mock_auth, mock_load, mock_create, mock_threshold, mock_save
    ):
        """Model with scores below threshold should return 424."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_create.return_value = artifact
        mock_threshold.return_value = ["NetScore", "License"]  # Failing metrics
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 424

    @patch("lambdas.post_artifact_upload.generate_s3_download_url")
    @patch("lambdas.post_artifact_upload.save_artifact_metadata")
    @patch("lambdas.post_artifact_upload.create_artifact")
    @patch("lambdas.post_artifact_upload.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_dataset_upload_no_threshold_check(
        self, mock_auth, mock_load, mock_create, mock_save, mock_url
    ):
        """Dataset uploads should not have threshold checks."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        from src.artifacts.dataset_artifact import DatasetArtifact

        artifact = DatasetArtifact(name="test", source_url="https://example.com")
        mock_create.return_value = artifact
        mock_url.return_value = "https://s3.example.com/presigned"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "dataset"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 201

    @patch("lambdas.post_artifact_upload.create_artifact")
    @patch("lambdas.post_artifact_upload.load_all_artifacts_by_fields")
    @patch("src.auth.authorize")
    def test_ingestion_failure_returns_500(self, mock_auth, mock_load, mock_create):
        """Unexpected ingestion error should return 500."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = []
        mock_create.side_effect = Exception("Unexpected error")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model"},
            "body": json.dumps({"url": "https://example.com"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500
