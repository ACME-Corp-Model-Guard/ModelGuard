"""
Unit tests for lambdas/get_model_rate.py
"""

import json
from unittest.mock import patch

from lambdas.get_model_rate import (
    lambda_handler,
    _extract_score_value,
    _format_rate_response,
)
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.dataset_artifact import DatasetArtifact


class TestExtractScoreValue:
    """Tests for _extract_score_value helper."""

    def test_none_returns_zero(self):
        """None should return 0.0."""
        assert _extract_score_value(None) == 0.0

    def test_float_returned_as_is(self):
        """Float value should be returned as-is."""
        assert _extract_score_value(0.75) == 0.75

    def test_int_converted_to_float(self):
        """Int value should be converted to float."""
        assert _extract_score_value(1) == 1.0

    def test_single_key_dict_extracts_value(self):
        """Single-key dict should extract the value."""
        assert _extract_score_value({"availability": 0.8}) == 0.8

    def test_multi_key_dict_averages(self):
        """Multi-key dict should average the values."""
        result = _extract_score_value({"a": 0.5, "b": 1.0})
        assert result == 0.75

    def test_empty_dict_returns_zero(self):
        """Empty dict should return 0.0."""
        assert _extract_score_value({}) == 0.0

    def test_invalid_type_returns_zero(self):
        """Invalid types should return 0.0."""
        assert _extract_score_value("string") == 0.0


class TestFormatRateResponse:
    """Tests for _format_rate_response helper."""

    def test_includes_name(self):
        """Response should include name."""
        artifact_dict = {"name": "test-model", "scores": {}, "scores_latency": {}}
        result = _format_rate_response(artifact_dict)
        assert result["name"] == "test-model"

    def test_includes_category(self):
        """Response should include category from metadata."""
        artifact_dict = {
            "name": "test",
            "scores": {},
            "scores_latency": {},
            "metadata": {"category": "nlp"},
        }
        result = _format_rate_response(artifact_dict)
        assert result["category"] == "nlp"

    def test_default_category(self):
        """Category should default to 'unknown'."""
        artifact_dict = {"name": "test", "scores": {}, "scores_latency": {}}
        result = _format_rate_response(artifact_dict)
        assert result["category"] == "unknown"

    def test_includes_net_score(self):
        """Response should include net_score."""
        artifact_dict = {
            "name": "test",
            "scores": {"NetScore": 0.85},
            "scores_latency": {"NetScore": 100},
        }
        result = _format_rate_response(artifact_dict)
        assert result["net_score"] == 0.85

    def test_includes_all_required_fields(self):
        """Response should include all required API fields."""
        artifact_dict = {"name": "test", "scores": {}, "scores_latency": {}}
        result = _format_rate_response(artifact_dict)

        required_fields = [
            "name",
            "category",
            "net_score",
            "net_score_latency",
            "ramp_up_time",
            "ramp_up_time_latency",
            "bus_factor",
            "bus_factor_latency",
            "performance_claims",
            "performance_claims_latency",
            "license",
            "license_latency",
            "dataset_and_code_score",
            "dataset_and_code_score_latency",
            "dataset_quality",
            "dataset_quality_latency",
            "code_quality",
            "code_quality_latency",
            "tree_score",
            "tree_score_latency",
            "size_score",
            "size_score_latency",
            "reproducibility",
            "reproducibility_latency",
            "reviewedness",
            "reviewedness_latency",
        ]

        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_size_score_has_all_platforms(self):
        """size_score should have all platform keys."""
        artifact_dict = {"name": "test", "scores": {}, "scores_latency": {}}
        result = _format_rate_response(artifact_dict)

        assert "raspberry_pi" in result["size_score"]
        assert "jetson_nano" in result["size_score"]
        assert "desktop_pc" in result["size_score"]
        assert "aws_server" in result["size_score"]

    def test_maps_size_keys_correctly(self):
        """Size keys should be mapped from internal to API format."""
        artifact_dict = {
            "name": "test",
            "scores": {
                "Size": {
                    "size_pi": 0.9,
                    "size_nano": 0.8,
                    "size_pc": 0.7,
                    "size_server": 0.6,
                }
            },
            "scores_latency": {},
        }
        result = _format_rate_response(artifact_dict)

        assert result["size_score"]["raspberry_pi"] == 0.9
        assert result["size_score"]["jetson_nano"] == 0.8
        assert result["size_score"]["desktop_pc"] == 0.7
        assert result["size_score"]["aws_server"] == 0.6


class TestLambdaHandler:
    """Tests for GET /artifact/model/{id}/rate lambda handler."""

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

    @patch("lambdas.get_model_rate.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_model_not_found_returns_404(self, mock_auth, mock_load):
        """Non-existent model should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = None
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": "nonexistent"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.get_model_rate.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_non_model_artifact_returns_400(self, mock_auth, mock_load):
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

    @patch("lambdas.get_model_rate.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_successful_rate_returns_200(self, mock_auth, mock_load):
        """Successful rate request should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test-model", source_url="https://example.com")
        model.scores = {"NetScore": 0.75}
        model.scores_latency = {"NetScore": 50}
        mock_load.return_value = model
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200

    @patch("lambdas.get_model_rate.load_artifact_metadata")
    @patch("src.auth.authorize")
    def test_response_body_format(self, mock_auth, mock_load):
        """Response body should contain rate data."""
        mock_auth.return_value = {"username": "test", "groups": []}
        model = ModelArtifact(name="test-model", source_url="https://example.com")
        model.scores = {"NetScore": 0.75}
        model.scores_latency = {}
        mock_load.return_value = model
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"id": model.artifact_id},
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert body["name"] == "test-model"
        assert body["net_score"] == 0.75
        assert "size_score" in body
