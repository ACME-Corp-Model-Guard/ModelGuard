"""
Unit tests for lambdas/post_artifacts.py
"""

import json
from unittest.mock import patch

import pytest

from lambdas.post_artifacts import (
    lambda_handler,
    _parse_artifact_queries,
    _filter_artifacts,
    _paginate,
)
from src.artifacts.model_artifact import ModelArtifact
from src.artifacts.dataset_artifact import DatasetArtifact
from src.artifacts.code_artifact import CodeArtifact


class TestParseArtifactQueries:
    """Tests for _parse_artifact_queries helper."""

    def test_valid_query_array(self):
        """Valid query array should be returned as-is."""
        body = [{"name": "test"}]
        result = _parse_artifact_queries(body)
        assert result == body

    def test_non_array_raises_error(self):
        """Non-array body should raise ValueError."""
        with pytest.raises(ValueError, match="must be an array"):
            _parse_artifact_queries({"name": "test"})

    def test_non_object_in_array_raises_error(self):
        """Non-object in array should raise ValueError."""
        with pytest.raises(ValueError, match="must be an object"):
            _parse_artifact_queries(["string"])

    def test_missing_name_raises_error(self):
        """Query without name field should raise ValueError."""
        with pytest.raises(ValueError, match="must include 'name' field"):
            _parse_artifact_queries([{"types": ["model"]}])

    def test_invalid_type_in_types_raises_error(self):
        """Invalid type in types array should raise ValueError."""
        with pytest.raises(ValueError, match="invalid type"):
            _parse_artifact_queries([{"name": "test", "types": ["invalid"]}])

    def test_types_not_array_raises_error(self):
        """types as non-array should raise ValueError."""
        with pytest.raises(ValueError, match="'types' must be an array"):
            _parse_artifact_queries([{"name": "test", "types": "model"}])

    def test_valid_types_array(self):
        """Valid types array should pass validation."""
        body = [{"name": "test", "types": ["model", "dataset", "code"]}]
        result = _parse_artifact_queries(body)
        assert result == body


class TestFilterArtifacts:
    """Tests for _filter_artifacts helper."""

    def test_wildcard_name_returns_all(self):
        """name='*' should return all artifacts."""
        artifacts = [
            ModelArtifact(name="model-1", source_url="https://example.com/1"),
            DatasetArtifact(name="dataset-1", source_url="https://example.com/2"),
        ]
        queries = [{"name": "*"}]

        result = _filter_artifacts(artifacts, queries)

        assert len(result) == 2

    def test_wildcard_with_type_filter(self):
        """name='*' with types filter should return only matching types."""
        artifacts = [
            ModelArtifact(name="model-1", source_url="https://example.com/1"),
            DatasetArtifact(name="dataset-1", source_url="https://example.com/2"),
            CodeArtifact(name="code-1", source_url="https://github.com/test/repo"),
        ]
        queries = [{"name": "*", "types": ["model"]}]

        result = _filter_artifacts(artifacts, queries)

        assert len(result) == 1
        assert result[0].artifact_type == "model"

    def test_name_filter(self):
        """Name filter should return matching artifacts."""
        artifacts = [
            ModelArtifact(name="target", source_url="https://example.com/1"),
            ModelArtifact(name="other", source_url="https://example.com/2"),
        ]
        queries = [{"name": "target"}]

        with patch("lambdas.post_artifacts.load_all_artifacts_by_fields") as mock_load:
            mock_load.return_value = [artifacts[0]]
            result = _filter_artifacts(artifacts, queries)

            assert len(result) == 1

    def test_deduplication(self):
        """Duplicate artifacts should be deduplicated."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifacts = [artifact]
        queries = [{"name": "*"}, {"name": "*"}]

        result = _filter_artifacts(artifacts, queries)

        assert len(result) == 1


class TestPaginate:
    """Tests for _paginate helper."""

    def test_first_page(self):
        """First page should return items from start."""
        items = list(range(10))
        page, next_offset = _paginate(items, offset=None, page_size=5)

        assert page == [0, 1, 2, 3, 4]
        assert next_offset == 5

    def test_second_page(self):
        """Second page should return items from offset."""
        items = list(range(10))
        page, next_offset = _paginate(items, offset=5, page_size=5)

        assert page == [5, 6, 7, 8, 9]
        assert next_offset is None

    def test_last_page_partial(self):
        """Last page may be partial."""
        items = list(range(7))
        page, next_offset = _paginate(items, offset=5, page_size=5)

        assert page == [5, 6]
        assert next_offset is None

    def test_empty_list(self):
        """Empty list should return empty page."""
        page, next_offset = _paginate([], offset=None, page_size=5)

        assert page == []
        assert next_offset is None


class TestLambdaHandler:
    """Tests for POST /artifacts lambda handler."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {"headers": {}, "body": json.dumps([{"name": "*"}])}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_invalid_json_returns_400(self, mock_auth):
        """Invalid JSON body should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {"headers": {"X-Authorization": "bearer token"}, "body": "not json"}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("src.auth.authorize")
    def test_invalid_query_format_returns_400(self, mock_auth):
        """Invalid query format should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps({"not": "array"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("src.auth.authorize")
    def test_invalid_offset_returns_400(self, mock_auth):
        """Invalid offset header should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token", "offset": "not_a_number"},
            "body": json.dumps([{"name": "*"}]),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.post_artifacts.load_all_artifacts")
    @patch("src.auth.authorize")
    def test_successful_query_returns_200(self, mock_auth, mock_load):
        """Successful query should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_load.return_value = [ModelArtifact(name="test", source_url="https://example.com")]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps([{"name": "*"}]),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200

    @patch("lambdas.post_artifacts.load_all_artifacts")
    @patch("src.auth.authorize")
    def test_response_includes_offset_header(self, mock_auth, mock_load):
        """Response should include offset header."""
        mock_auth.return_value = {"username": "test", "groups": []}
        # Create more than 5 artifacts to trigger pagination
        artifacts = [
            ModelArtifact(name=f"test-{i}", source_url=f"https://example.com/{i}")
            for i in range(10)
        ]
        mock_load.return_value = artifacts
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps([{"name": "*"}]),
        }

        response = lambda_handler(event, None)

        assert "offset" in response["headers"]

    @patch("lambdas.post_artifacts.load_all_artifacts")
    @patch("src.auth.authorize")
    def test_response_body_format(self, mock_auth, mock_load):
        """Response body should be array of ArtifactMetadata."""
        mock_auth.return_value = {"username": "test", "groups": []}
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = [artifact]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps([{"name": "*"}]),
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert isinstance(body, list)
        assert len(body) == 1
        assert "name" in body[0]
        assert "id" in body[0]
        assert "type" in body[0]

    @patch("lambdas.post_artifacts.load_all_artifacts")
    @patch("src.auth.authorize")
    def test_too_many_results_returns_413(self, mock_auth, mock_load):
        """Too many results should return 413."""
        mock_auth.return_value = {"username": "test", "groups": []}
        # Create 501 artifacts (exceeds MAX_QUERY_RESULTS of 500)
        artifacts = [
            ModelArtifact(name="test", source_url=f"https://example.com/{i}") for i in range(501)
        ]
        mock_load.return_value = artifacts
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps([{"name": "*"}]),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 413
