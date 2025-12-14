"""
Unit tests for lambdas/post_license_check.py
"""

import json
from unittest.mock import patch

import pytest

from lambdas.post_license_check import lambda_handler, fetch_github_license
from src.artifacts.model_artifact import ModelArtifact


class TestFetchGithubLicense:
    """Tests for fetch_github_license helper."""

    @patch("lambdas.post_license_check.requests.get")
    def test_returns_spdx_id(self, mock_get):
        """Should return SPDX ID from GitHub API."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"license": {"spdx_id": "MIT"}}

        result = fetch_github_license("https://github.com/owner/repo")

        assert result == "MIT"

    @patch("lambdas.post_license_check.requests.get")
    def test_returns_none_when_no_license(self, mock_get):
        """Should return None when repo has no license."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"license": None}

        result = fetch_github_license("https://github.com/owner/repo")

        assert result is None

    @patch("lambdas.post_license_check.requests.get")
    def test_raises_on_404(self, mock_get):
        """Should raise ValueError on 404."""
        mock_get.return_value.status_code = 404

        with pytest.raises(ValueError, match="Not Found"):
            fetch_github_license("https://github.com/owner/nonexistent")

    @patch("lambdas.post_license_check.requests.get")
    def test_raises_on_api_error(self, mock_get):
        """Should raise ValueError on API error."""
        mock_get.return_value.status_code = 500

        with pytest.raises(ValueError, match="GitHub API Error"):
            fetch_github_license("https://github.com/owner/repo")

    def test_raises_on_invalid_url(self):
        """Should raise ValueError on invalid URL."""
        with pytest.raises(ValueError):
            fetch_github_license("invalid")


class TestLambdaHandler:
    """Tests for POST /artifact/model/{id}/license-check lambda handler."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {
            "headers": {},
            "pathParameters": {"id": "test-id"},
            "body": json.dumps({"github_url": "https://github.com/owner/repo"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_missing_id_returns_400(self, mock_auth):
        """Missing id should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {},
            "body": json.dumps({"github_url": "https://github.com/owner/repo"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.post_license_check.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_artifact_not_found_returns_404(self, mock_auth, mock_load):
        """Non-existent artifact should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = None
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": "nonexistent"},
            "body": json.dumps({"github_url": "https://github.com/owner/repo"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.post_license_check.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_malformed_json_returns_400(self, mock_auth, mock_load):
        """Malformed JSON body should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = model
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
            "body": "not json",
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.post_license_check.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_missing_github_url_returns_400(self, mock_auth, mock_load):
        """Missing github_url should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = model
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
            "body": json.dumps({}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.post_license_check.fetch_github_license")
    @patch("lambdas.post_license_check.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_github_not_found_returns_404(self, mock_auth, mock_load, mock_fetch):
        """GitHub repo not found should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.metadata = {"license": "MIT"}
        mock_load.return_value = model
        mock_fetch.side_effect = ValueError("Not Found")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
            "body": json.dumps({"github_url": "https://github.com/owner/nonexistent"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.post_license_check.fetch_github_license")
    @patch("lambdas.post_license_check.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_github_api_error_returns_502(self, mock_auth, mock_load, mock_fetch):
        """GitHub API error should return 502."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.metadata = {"license": "MIT"}
        mock_load.return_value = model
        mock_fetch.side_effect = Exception("API Error")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
            "body": json.dumps({"github_url": "https://github.com/owner/repo"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 502

    @patch("lambdas.post_license_check.fetch_github_license")
    @patch("lambdas.post_license_check.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_compatible_licenses_returns_true(self, mock_auth, mock_load, mock_fetch):
        """Compatible licenses should return true."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.metadata = {"license": "MIT"}
        mock_load.return_value = model
        mock_fetch.return_value = "MIT"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
            "body": json.dumps({"github_url": "https://github.com/owner/repo"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body is True

    @patch("lambdas.post_license_check.fetch_github_license")
    @patch("lambdas.post_license_check.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_incompatible_licenses_returns_false(self, mock_auth, mock_load, mock_fetch):
        """Incompatible licenses should return false."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test", source_url="https://example.com")
        model.metadata = {"license": "MIT"}
        mock_load.return_value = model
        mock_fetch.return_value = "GPL-3.0"
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
            "body": json.dumps({"github_url": "https://github.com/owner/repo"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body is False
