"""
Unit tests for lambdas/get_artifact_cost.py
"""

import json
from unittest.mock import patch, MagicMock

from lambdas.get_artifact_cost import (
    lambda_handler,
    _get_artifact_size_mb,
    _calculate_costs_with_dependencies,
)
from src.artifacts.model_artifact import ModelArtifact


class TestGetArtifactSizeMb:
    """Tests for _get_artifact_size_mb helper."""

    @patch("lambdas.get_artifact_cost.get_s3")
    def test_returns_size_in_mb(self, mock_get_s3):
        """Should return size in MB."""
        mock_s3 = MagicMock()
        mock_get_s3.return_value = mock_s3
        mock_s3.head_object.return_value = {"ContentLength": 10 * 1024 * 1024}  # 10 MB

        result = _get_artifact_size_mb("test-id", "models/test-id.tar.gz")

        assert result == 10.0

    @patch("lambdas.get_artifact_cost.get_s3")
    def test_returns_zero_on_error(self, mock_get_s3):
        """Should return 0.0 on S3 error."""
        mock_s3 = MagicMock()
        mock_get_s3.return_value = mock_s3
        mock_s3.head_object.side_effect = Exception("S3 error")

        result = _get_artifact_size_mb("test-id", "models/test-id.tar.gz")

        assert result == 0.0

    @patch("lambdas.get_artifact_cost.get_s3")
    def test_rounds_to_two_decimals(self, mock_get_s3):
        """Should round to 2 decimal places."""
        mock_s3 = MagicMock()
        mock_get_s3.return_value = mock_s3
        # 1.5 MB = 1572864 bytes
        mock_s3.head_object.return_value = {"ContentLength": 1572864}

        result = _get_artifact_size_mb("test-id", "models/test-id.tar.gz")

        assert result == 1.5


class TestCalculateCostsWithDependencies:
    """Tests for _calculate_costs_with_dependencies helper."""

    @patch("lambdas.get_artifact_cost._get_artifact_size_mb")
    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    def test_single_artifact_no_deps(self, mock_load, mock_size):
        """Single artifact with no dependencies."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.connected_artifacts = []
        mock_load.return_value = artifact
        mock_size.return_value = 5.0

        result = _calculate_costs_with_dependencies(artifact.artifact_id)

        assert artifact.artifact_id in result
        assert result[artifact.artifact_id]["standalone_cost"] == 5.0
        assert result[artifact.artifact_id]["total_cost"] == 5.0

    @patch("lambdas.get_artifact_cost._get_artifact_size_mb")
    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    def test_artifact_not_found_returns_empty(self, mock_load, mock_size):
        """Non-existent artifact returns empty dict."""
        mock_load.return_value = None

        result = _calculate_costs_with_dependencies("nonexistent")

        assert result == {}

    @patch("lambdas.get_artifact_cost._get_artifact_size_mb")
    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    def test_with_dependencies(self, mock_load, mock_size):
        """Artifact with dependencies includes their costs."""
        parent = ModelArtifact(name="parent", source_url="https://example.com/parent")
        child = ModelArtifact(name="child", source_url="https://example.com/child")
        parent.connected_artifacts = [child.artifact_id]
        child.connected_artifacts = []

        mock_load.side_effect = lambda id: parent if id == parent.artifact_id else child
        mock_size.return_value = 5.0

        result = _calculate_costs_with_dependencies(parent.artifact_id)

        assert parent.artifact_id in result
        assert child.artifact_id in result
        # Parent total should include child
        assert result[parent.artifact_id]["total_cost"] == 10.0

    @patch("lambdas.get_artifact_cost._get_artifact_size_mb")
    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    def test_handles_circular_deps(self, mock_load, mock_size):
        """Should handle circular dependencies without infinite loop."""
        artifact1 = ModelArtifact(name="a1", source_url="https://example.com/1")
        artifact2 = ModelArtifact(name="a2", source_url="https://example.com/2")
        artifact1.connected_artifacts = [artifact2.artifact_id]
        artifact2.connected_artifacts = [artifact1.artifact_id]  # Circular

        mock_load.side_effect = lambda id: artifact1 if id == artifact1.artifact_id else artifact2
        mock_size.return_value = 5.0

        # Should not hang
        result = _calculate_costs_with_dependencies(artifact1.artifact_id)

        assert artifact1.artifact_id in result


class TestLambdaHandler:
    """Tests for GET /artifact/{type}/{id}/cost lambda handler."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {
            "headers": {},
            "pathParameters": {"artifact_type": "model", "id": "test-id"},
            "queryStringParameters": {},
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
            "queryStringParameters": {},
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
            "queryStringParameters": {},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_artifact_not_found_returns_404(self, mock_auth, mock_load):
        """Non-existent artifact should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = None
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": "nonexistent"},
            "queryStringParameters": {},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_type_mismatch_returns_400(self, mock_auth, mock_load):
        """Type mismatch should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "dataset", "id": artifact.artifact_id},
            "queryStringParameters": {},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.get_artifact_cost._get_artifact_size_mb")
    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_returns_cost_without_dependencies(self, mock_auth, mock_load, mock_size):
        """Should return cost without dependencies by default."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_size.return_value = 5.0
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
            "queryStringParameters": {},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert artifact.artifact_id in body
        assert body[artifact.artifact_id]["total_cost"] == 5.0

    @patch("lambdas.get_artifact_cost._calculate_costs_with_dependencies")
    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_returns_cost_with_dependencies(self, mock_auth, mock_load, mock_calc):
        """Should return costs with dependencies when requested."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = artifact
        mock_calc.return_value = {
            artifact.artifact_id: {"standalone_cost": 5.0, "total_cost": 10.0}
        }
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
            "queryStringParameters": {"dependency": "true"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "standalone_cost" in body[artifact.artifact_id]

    @patch("lambdas.get_artifact_cost._get_artifact_size_mb")
    @patch("lambdas.get_artifact_cost.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_dependency_param_variations(self, mock_auth, mock_load, mock_size):
        """Should accept various dependency parameter values."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.connected_artifacts = []
        mock_load.return_value = artifact
        mock_size.return_value = 5.0

        for value in ["true", "1", "yes"]:
            event = {
                "headers": {"X-Authorization": "bearer token"},
                "pathParameters": {"artifact_type": "model", "id": artifact.artifact_id},
                "queryStringParameters": {"dependency": value},
            }

            response = lambda_handler(event, None)

            body = json.loads(response["body"])
            # With dependencies, should have standalone_cost key
            assert "standalone_cost" in body[artifact.artifact_id]
