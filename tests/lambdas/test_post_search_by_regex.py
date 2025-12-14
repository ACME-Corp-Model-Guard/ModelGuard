"""
Unit tests for lambdas/post_search_by_regex.py
"""

import json
import re
from unittest.mock import patch

import pytest

from lambdas.post_search_by_regex import (
    lambda_handler,
    _load_body,
    _parse_regex,
    _build_search_text,
    _search_artifacts,
)
from src.artifacts.model_artifact import ModelArtifact


class TestLoadBody:
    """Tests for _load_body helper."""

    def test_parses_json_string(self):
        """Should parse JSON string body."""
        event = {"body": '{"regex": "test"}'}
        result = _load_body(event)
        assert result["regex"] == "test"

    def test_returns_dict_as_is(self):
        """Should return dict body as-is."""
        event = {"body": {"regex": "test"}}
        result = _load_body(event)
        assert result["regex"] == "test"

    def test_empty_body_returns_empty_dict(self):
        """Empty body should return empty dict."""
        event = {"body": ""}
        result = _load_body(event)
        assert result == {}

    def test_none_body_returns_empty_dict(self):
        """None body should return empty dict."""
        event = {"body": None}
        result = _load_body(event)
        assert result == {}

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError."""
        event = {"body": "not json"}
        with pytest.raises(ValueError, match="valid JSON"):
            _load_body(event)


class TestParseRegex:
    """Tests for _parse_regex helper."""

    def test_valid_regex(self):
        """Valid regex should return compiled pattern."""
        event = {"body": json.dumps({"regex": "test.*"})}
        result = _parse_regex(event)
        assert isinstance(result, re.Pattern)

    def test_missing_regex_raises_error(self):
        """Missing regex field should raise ValueError."""
        event = {"body": json.dumps({})}
        with pytest.raises(ValueError, match="regex"):
            _parse_regex(event)

    def test_empty_regex_raises_error(self):
        """Empty regex should raise ValueError."""
        event = {"body": json.dumps({"regex": ""})}
        with pytest.raises(ValueError, match="regex"):
            _parse_regex(event)

    def test_invalid_regex_raises_error(self):
        """Invalid regex pattern should raise ValueError."""
        event = {"body": json.dumps({"regex": "[invalid"})}
        with pytest.raises(ValueError, match="Invalid regular expression"):
            _parse_regex(event)


class TestBuildSearchText:
    """Tests for _build_search_text helper."""

    def test_includes_name(self):
        """Should include artifact name."""
        artifact = ModelArtifact(name="test-model", source_url="https://example.com")
        result = _build_search_text(artifact)
        assert "test-model" in result

    def test_includes_metadata_strings(self):
        """Should include string metadata values."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.metadata = {"description": "A test artifact"}
        result = _build_search_text(artifact)
        assert "A test artifact" in result

    def test_includes_readme(self):
        """Should include README text if provided."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        result = _build_search_text(artifact, readme_text="# README\nThis is a test")
        assert "# README" in result

    def test_handles_non_string_metadata(self):
        """Should handle non-string metadata values."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        artifact.metadata = {"count": 42}
        result = _build_search_text(artifact)
        assert "42" in result


class TestSearchArtifacts:
    """Tests for _search_artifacts helper."""

    @patch("lambdas.post_search_by_regex._extract_readme_from_s3")
    @patch("lambdas.post_search_by_regex.load_all_artifacts")
    def test_returns_matching_artifacts(self, mock_load, mock_readme):
        """Should return artifacts matching pattern."""
        artifact1 = ModelArtifact(name="matching-test", source_url="https://example.com/1")
        artifact2 = ModelArtifact(name="other", source_url="https://example.com/2")
        mock_load.return_value = [artifact1, artifact2]
        mock_readme.return_value = ""

        pattern = re.compile("matching", re.IGNORECASE)
        result = _search_artifacts(pattern)

        assert len(result) == 1
        assert result[0]["name"] == "matching-test"

    @patch("lambdas.post_search_by_regex._extract_readme_from_s3")
    @patch("lambdas.post_search_by_regex.load_all_artifacts")
    def test_returns_empty_when_no_match(self, mock_load, mock_readme):
        """Should return empty list when no matches."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = [artifact]
        mock_readme.return_value = ""

        pattern = re.compile("nonexistent", re.IGNORECASE)
        result = _search_artifacts(pattern)

        assert result == []

    @patch("lambdas.post_search_by_regex._extract_readme_from_s3")
    @patch("lambdas.post_search_by_regex.load_all_artifacts")
    def test_matches_in_readme(self, mock_load, mock_readme):
        """Should match patterns in README content."""
        artifact = ModelArtifact(name="test", source_url="https://example.com")
        mock_load.return_value = [artifact]
        mock_readme.return_value = "This artifact processes images"

        pattern = re.compile("images", re.IGNORECASE)
        result = _search_artifacts(pattern)

        assert len(result) == 1


class TestLambdaHandler:
    """Tests for POST /artifact/byRegEx lambda handler."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {"headers": {}, "body": json.dumps({"regex": "test"})}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_missing_regex_returns_400(self, mock_auth):
        """Missing regex should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {"headers": {"X-Authorization": "bearer token"}, "body": json.dumps({})}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("src.auth.authorize")
    def test_invalid_regex_returns_400(self, mock_auth):
        """Invalid regex should return 400."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps({"regex": "[invalid"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    @patch("lambdas.post_search_by_regex._search_artifacts")
    @patch("src.auth.authorize")
    def test_no_matches_returns_404(self, mock_auth, mock_search):
        """No matching artifacts should return 404."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_search.return_value = []
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps({"regex": "nonexistent"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404

    @patch("lambdas.post_search_by_regex._search_artifacts")
    @patch("src.auth.authorize")
    def test_matches_returns_200(self, mock_auth, mock_search):
        """Found matches should return 200."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_search.return_value = [{"name": "test", "id": "123", "type": "model"}]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps({"regex": "test"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200

    @patch("lambdas.post_search_by_regex._search_artifacts")
    @patch("src.auth.authorize")
    def test_response_body_format(self, mock_auth, mock_search):
        """Response body should be array of ArtifactMetadata."""
        mock_auth.return_value = {"username": "test", "groups": []}
        mock_search.return_value = [{"name": "test-model", "id": "123", "type": "model"}]
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps({"regex": "test"}),
        }

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["name"] == "test-model"
        assert body[0]["id"] == "123"
        assert body[0]["type"] == "model"
