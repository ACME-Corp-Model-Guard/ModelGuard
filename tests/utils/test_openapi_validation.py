"""
Tests for OpenAPI validation utilities.
"""

from unittest.mock import patch

from src.utils.openapi_validation import (
    _normalize_path,
    validate_request,
    validate_response,
)


# =============================================================================
# Path Normalization Tests
# =============================================================================


def test_normalize_path_artifacts_with_type_and_id():
    """Normalize /artifacts/model/abc-123 to template path."""
    result = _normalize_path("/artifacts/model/abc-123")
    assert result == "/artifacts/{artifact_type}/{id}"


def test_normalize_path_artifacts_dataset():
    """Normalize /artifacts/dataset/xyz to template path."""
    result = _normalize_path("/artifacts/dataset/xyz-456")
    assert result == "/artifacts/{artifact_type}/{id}"


def test_normalize_path_artifacts_code():
    """Normalize /artifacts/code/abc to template path."""
    result = _normalize_path("/artifacts/code/code-789")
    assert result == "/artifacts/{artifact_type}/{id}"


def test_normalize_path_artifact_cost():
    """Normalize /artifact/model/abc/cost to template path."""
    result = _normalize_path("/artifact/model/abc-123/cost")
    assert result == "/artifact/{artifact_type}/{id}/cost"


def test_normalize_path_model_rate():
    """Normalize /artifact/model/abc/rate to template path."""
    result = _normalize_path("/artifact/model/abc-123/rate")
    assert result == "/artifact/model/{id}/rate"


def test_normalize_path_model_lineage():
    """Normalize /artifact/model/abc/lineage to template path."""
    result = _normalize_path("/artifact/model/abc-123/lineage")
    assert result == "/artifact/model/{id}/lineage"


def test_normalize_path_model_license_check():
    """Normalize /artifact/model/abc/license-check to template path."""
    result = _normalize_path("/artifact/model/abc-123/license-check")
    assert result == "/artifact/model/{id}/license-check"


def test_normalize_path_by_name():
    """Normalize /artifact/byName/MyModel to template path."""
    result = _normalize_path("/artifact/byName/MyModel")
    assert result == "/artifact/byName/{name}"


def test_normalize_path_artifact_type_only():
    """Normalize /artifact/model to template path."""
    result = _normalize_path("/artifact/model")
    assert result == "/artifact/{artifact_type}"


def test_normalize_path_strips_trailing_slash():
    """Trailing slashes should be removed."""
    result = _normalize_path("/artifact/model/")
    assert result == "/artifact/{artifact_type}"


def test_normalize_path_unknown_returns_as_is():
    """Unknown paths should be returned as-is."""
    result = _normalize_path("/health")
    assert result == "/health"


def test_normalize_path_reset():
    """Reset path should be returned as-is."""
    result = _normalize_path("/reset")
    assert result == "/reset"


# =============================================================================
# Request Validation Tests
# =============================================================================


def test_validate_request_no_spec():
    """When no spec is loaded, validation passes."""
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", {}):
        is_valid, violations = validate_request(
            endpoint="/health",
            method="GET",
            headers={},
            query_params={},
            path_params={},
            body=None,
        )
        assert is_valid is True
        assert violations == []


def test_validate_request_endpoint_not_found():
    """Unknown endpoint should fail validation."""
    fake_spec = {"paths": {"/health": {"get": {}}}}
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_request(
            endpoint="/unknown",
            method="GET",
            headers={},
            query_params={},
            path_params={},
            body=None,
        )
        assert is_valid is False
        assert "not found in OpenAPI spec" in violations[0]


def test_validate_request_method_not_found():
    """Unknown method for endpoint should fail validation."""
    fake_spec = {"paths": {"/health": {"get": {}}}}
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_request(
            endpoint="/health",
            method="POST",
            headers={},
            query_params={},
            path_params={},
            body=None,
        )
        assert is_valid is False
        assert "not defined for" in violations[0]


def test_validate_request_missing_required_header():
    """Missing required header should fail validation."""
    fake_spec = {
        "paths": {
            "/secure": {
                "get": {
                    "parameters": [{"name": "X-Authorization", "in": "header", "required": True}]
                }
            }
        }
    }
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_request(
            endpoint="/secure",
            method="GET",
            headers={},
            query_params={},
            path_params={},
            body=None,
        )
        assert is_valid is False
        assert "Missing required header: X-Authorization" in violations


def test_validate_request_has_required_header():
    """When required header is present, validation passes."""
    fake_spec = {
        "paths": {
            "/secure": {
                "get": {
                    "parameters": [{"name": "X-Authorization", "in": "header", "required": True}]
                }
            }
        }
    }
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_request(
            endpoint="/secure",
            method="GET",
            headers={"x-authorization": "bearer token"},  # lowercase should work
            query_params={},
            path_params={},
            body=None,
        )
        assert is_valid is True
        assert violations == []


def test_validate_request_missing_required_query_param():
    """Missing required query param should fail validation."""
    fake_spec = {
        "paths": {
            "/search": {"get": {"parameters": [{"name": "q", "in": "query", "required": True}]}}
        }
    }
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_request(
            endpoint="/search",
            method="GET",
            headers={},
            query_params={},
            path_params={},
            body=None,
        )
        assert is_valid is False
        assert "Missing required query param: q" in violations


def test_validate_request_missing_required_body():
    """Missing required request body should fail validation."""
    fake_spec = {
        "paths": {
            "/create": {
                "post": {"requestBody": {"required": True, "content": {"application/json": {}}}}
            }
        }
    }
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_request(
            endpoint="/create",
            method="POST",
            headers={},
            query_params={},
            path_params={},
            body=None,
        )
        assert is_valid is False
        assert "Missing required request body" in violations


def test_validate_request_with_body_present():
    """When required body is present, validation passes."""
    fake_spec = {
        "paths": {
            "/create": {
                "post": {"requestBody": {"required": True, "content": {"application/json": {}}}}
            }
        }
    }
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_request(
            endpoint="/create",
            method="POST",
            headers={},
            query_params={},
            path_params={},
            body={"name": "test"},
        )
        assert is_valid is True


# =============================================================================
# Response Validation Tests
# =============================================================================


def test_validate_response_no_spec():
    """When no spec is loaded, validation passes."""
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", {}):
        is_valid, violations = validate_response(
            endpoint="/health",
            method="GET",
            status_code=200,
            body={"status": "ok"},
        )
        assert is_valid is True
        assert violations == []


def test_validate_response_endpoint_not_in_spec():
    """Unknown endpoint in response validation passes (can't validate)."""
    fake_spec = {"paths": {"/health": {"get": {}}}}
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_response(
            endpoint="/unknown",
            method="GET",
            status_code=200,
            body={},
        )
        assert is_valid is True  # Can't validate, so passes


def test_validate_response_method_not_in_spec():
    """Unknown method in response validation passes (can't validate)."""
    fake_spec = {"paths": {"/health": {"get": {}}}}
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_response(
            endpoint="/health",
            method="POST",
            status_code=200,
            body={},
        )
        assert is_valid is True  # Can't validate, so passes


def test_validate_response_status_code_defined():
    """When status code is defined, validation passes."""
    fake_spec = {"paths": {"/health": {"get": {"responses": {"200": {"description": "OK"}}}}}}
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_response(
            endpoint="/health",
            method="GET",
            status_code=200,
            body={"status": "ok"},
        )
        assert is_valid is True
        assert violations == []


def test_validate_response_status_code_not_defined():
    """When status code is not defined and no default, validation fails."""
    fake_spec = {"paths": {"/health": {"get": {"responses": {"200": {"description": "OK"}}}}}}
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_response(
            endpoint="/health",
            method="GET",
            status_code=500,
            body={"error": "fail"},
        )
        assert is_valid is False
        assert "Status code 500 not defined" in violations[0]


def test_validate_response_uses_default_response():
    """When status code not defined but default exists, validation passes."""
    fake_spec = {
        "paths": {
            "/health": {
                "get": {
                    "responses": {
                        "200": {"description": "OK"},
                        "default": {"description": "Error"},
                    }
                }
            }
        }
    }
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_response(
            endpoint="/health",
            method="GET",
            status_code=500,
            body={"error": "fail"},
        )
        assert is_valid is True


def test_validate_response_normalized_path():
    """Response validation should normalize paths."""
    fake_spec = {
        "paths": {
            "/artifacts/{artifact_type}/{id}": {
                "get": {"responses": {"200": {"description": "OK"}}}
            }
        }
    }
    with patch("src.utils.openapi_validation.OPENAPI_SPEC", fake_spec):
        is_valid, violations = validate_response(
            endpoint="/artifacts/model/abc-123",
            method="GET",
            status_code=200,
            body={},
        )
        assert is_valid is True
