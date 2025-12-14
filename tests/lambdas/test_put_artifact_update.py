"""
Unit tests for lambdas/put_artifact_update.py
"""

import json
from unittest.mock import patch

import pytest

from lambdas.put_artifact_update import (
    lambda_handler,
    _parse_body,
    _validate_name_id_match,
    _get_net_score,
)
from src.artifacts.model_artifact import ModelArtifact
from src.storage.downloaders.dispatchers import FileDownloadError


class TestParseBody:
    """Tests for _parse_body helper."""

    def test_valid_body(self):
        """Valid request body should be parsed correctly."""
        event = {
            "body": json.dumps(
                {
                    "metadata": {"name": "test", "id": "123", "type": "model"},
                    "data": {"url": "https://example.com"},
                }
            )
        }
        result = _parse_body(event)

        assert result["metadata"]["name"] == "test"
        assert result["data"]["url"] == "https://example.com"

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError."""
        event = {"body": "not json"}
        with pytest.raises(ValueError, match="valid JSON"):
            _parse_body(event)

    def test_missing_metadata_raises_error(self):
        """Missing metadata should raise ValueError."""
        event = {"body": json.dumps({"data": {"url": "https://example.com"}})}
        with pytest.raises(ValueError, match="metadata"):
            _parse_body(event)

    def test_missing_data_raises_error(self):
        """Missing data should raise ValueError."""
        event = {"body": json.dumps({"metadata": {"name": "test", "id": "123", "type": "model"}})}
        with pytest.raises(ValueError, match="data"):
            _parse_body(event)

    def test_missing_name_raises_error(self):
        """Missing name in metadata should raise ValueError."""
        event = {
            "body": json.dumps(
                {
                    "metadata": {"id": "123", "type": "model"},
                    "data": {"url": "https://example.com"},
                }
            )
        }
        with pytest.raises(ValueError, match="name"):
            _parse_body(event)

    def test_missing_url_raises_error(self):
        """Missing url in data should raise ValueError."""
        event = {
            "body": json.dumps(
                {"metadata": {"name": "test", "id": "123", "type": "model"}, "data": {}}
            )
        }
        with pytest.raises(ValueError, match="url"):
            _parse_body(event)

    def test_dict_body_accepted(self):
        """Dict body should be accepted (for testing)."""
        event = {
            "body": {
                "metadata": {"name": "test", "id": "123", "type": "model"},
                "data": {"url": "https://example.com"},
            }
        }
        result = _parse_body(event)

        assert result["metadata"]["name"] == "test"


class TestValidateNameIdMatch:
    """Tests for _validate_name_id_match helper."""

    def test_valid_match(self):
        """Matching name and id should pass validation."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        request_metadata = {"name": "test", "id": artifact.artifact_id}

        # Should not raise
        _validate_name_id_match(request_metadata, artifact.artifact_id, artifact)

    def test_mismatched_id_raises_error(self):
        """Mismatched id should raise ValueError."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        request_metadata = {"name": "test", "id": "wrong-id"}

        with pytest.raises(ValueError, match="does not match path parameter"):
            _validate_name_id_match(request_metadata, artifact.artifact_id, artifact)

    def test_mismatched_name_raises_error(self):
        """Mismatched name should raise ValueError."""
        artifact = ModelArtifact(name="original", source_url="https://example.com")
        request_metadata = {"name": "different", "id": artifact.artifact_id}

        with pytest.raises(ValueError, match="does not match"):
            _validate_name_id_match(request_metadata, artifact.artifact_id, artifact)


class TestGetNetScore:
    """Tests for _get_net_score helper."""

    def test_valid_score(self):
        """Valid NetScore should be returned."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.scores = {"NetScore": 0.75}

        result = _get_net_score(artifact)

        assert result == 0.75

    def test_missing_scores(self):
        """Missing scores dict should return None."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.scores = None

        result = _get_net_score(artifact)

        assert result is None

    def test_missing_net_score(self):
        """Missing NetScore key should return None."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.scores = {"OtherMetric": 0.5}

        result = _get_net_score(artifact)

        assert result is None


class TestLambdaHandler:
    """Tests for PUT /artifacts/{type}/{id} lambda handler."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {
            "headers": {},
            "pathParameters": {"artifact_type": "model", "id": "test-id"},
            "body": json.dumps(
                {
                    "metadata": {"name": "test", "id": "test-id", "type": "model"},
                    "data": {"url": "https://example.com"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_missing_path_params_returns_400(self, mock_auth):
        """Missing path parameters should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {},
            "body": json.dumps(
                {
                    "metadata": {"name": "test", "id": "test-id", "type": "model"},
                    "data": {"url": "https://example.com"},
                }
            ),
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
            "body": json.dumps(
                {
                    "metadata": {"name": "test", "id": "test-id", "type": "invalid"},
                    "data": {"url": "https://example.com"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("src.auth.authorize")
    def test_invalid_body_returns_400(self, mock_auth):
        """Invalid request body should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": "test-id"},
            "body": "not json",
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.put_artifact_update.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_artifact_not_found_returns_404(self, mock_auth, mock_load):
        """Non-existent artifact should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = None
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": "nonexistent"},
            "body": json.dumps(
                {
                    "metadata": {"name": "test", "id": "nonexistent", "type": "model"},
                    "data": {"url": "https://example.com"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.put_artifact_update.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_name_mismatch_returns_400(self, mock_auth, mock_load):
        """Name mismatch should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="original", source_url="https://example.com")
        mock_load.return_value = artifact
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
            "body": json.dumps(
                {
                    "metadata": {
                        "name": "different",
                        "id": artifact.artifact_id,
                        "type": "model",
                    },
                    "data": {"url": "https://example.com/new"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.put_artifact_update.create_artifact")
    @patch("lambdas.put_artifact_update.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_source_not_found_returns_404(self, mock_auth, mock_load, mock_create):
        """Source URL not found should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_create.side_effect = FileDownloadError("Not found")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
            "body": json.dumps(
                {
                    "metadata": {
                        "name": "test",
                        "id": artifact.artifact_id,
                        "type": "model",
                    },
                    "data": {"url": "https://example.com/new"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.put_artifact_update.delete_objects")
    @patch("lambdas.put_artifact_update.create_artifact")
    @patch("lambdas.put_artifact_update.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_lower_net_score_returns_400(self, mock_auth, mock_load, mock_create, mock_delete):
        """Model with lower NetScore should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        old_artifact = ModelArtifact(name="test", source_url="https://example.com/old")
        old_artifact.scores = {"NetScore": 0.8}
        mock_load.return_value = old_artifact

        new_artifact = ModelArtifact(name="test", source_url="https://example.com/new")
        new_artifact.scores = {"NetScore": 0.5}  # Lower score
        mock_create.return_value = new_artifact

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": old_artifact.artifact_id},
            "body": json.dumps(
                {
                    "metadata": {
                        "name": "test",
                        "id": old_artifact.artifact_id,
                        "type": "model",
                    },
                    "data": {"url": "https://example.com/new"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "NetScore" in body.get("message", body.get("error", ""))

    @patch("lambdas.put_artifact_update.save_artifact_metadata")
    @patch("lambdas.put_artifact_update.delete_objects")
    @patch("lambdas.put_artifact_update.create_artifact")
    @patch("lambdas.put_artifact_update.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_successful_update_returns_200(
        self, mock_auth, mock_load, mock_create, mock_delete, mock_save
    ):
        """Successful update should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        old_artifact = ModelArtifact(name="test", source_url="https://example.com/old")
        old_artifact.scores = {"NetScore": 0.5}
        mock_load.return_value = old_artifact

        new_artifact = ModelArtifact(name="test", source_url="https://example.com/new")
        new_artifact.scores = {"NetScore": 0.8}  # Higher score
        mock_create.return_value = new_artifact

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": old_artifact.artifact_id},
            "body": json.dumps(
                {
                    "metadata": {
                        "name": "test",
                        "id": old_artifact.artifact_id,
                        "type": "model",
                    },
                    "data": {"url": "https://example.com/new"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body.get("message", body.get("error", "")) == "Artifact is updated"
