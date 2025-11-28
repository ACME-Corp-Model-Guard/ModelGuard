import json
from unittest.mock import MagicMock

import src.utils.http as http


# ================================================================
# json_response()
# ================================================================
def test_json_response_basic():
    resp = http.json_response(200, {"hello": "world"})

    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"hello": "world"}

    # Default CORS headers must be present
    for key, value in http.DEFAULT_HEADERS.items():
        assert resp["headers"][key] == value


def test_json_response_merges_custom_headers():
    resp = http.json_response(
        201,
        {"ok": True},
        headers={"X-Test": "123"},
    )

    assert resp["statusCode"] == 201
    assert resp["headers"]["X-Test"] == "123"

    # Should still include built-ins
    assert resp["headers"]["Content-Type"] == "application/json"


def test_json_response_accepts_raw_string():
    resp = http.json_response(200, "raw text")

    assert json.loads(resp["body"]) == "raw text"


def test_json_response_accepts_boolean():
    resp = http.json_response(200, True)
    assert json.loads(resp["body"]) is True


# ================================================================
# error_response()
# ================================================================
def test_error_response_basic():
    resp = http.error_response(400, "Bad request")

    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"] == "Bad request"
    assert "error_code" not in body  # optional


def test_error_response_with_error_code():
    resp = http.error_response(403, "Forbidden", error_code="NO_ACCESS")

    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert body == {"error": "Forbidden", "error_code": "NO_ACCESS"}


def test_error_response_passes_headers():
    resp = http.error_response(
        404,
        "Not found",
        error_code="NOT_FOUND",
        headers={"X-Test": "1"},
    )

    assert resp["headers"]["X-Test"] == "1"
    # ensure default headers remain
    assert resp["headers"]["Content-Type"] == "application/json"


# ================================================================
# translate_exceptions()
# ================================================================
def test_translate_exceptions_success(monkeypatch):
    """
    If handler returns normally, wrapper should pass its response through unchanged.
    """

    @http.translate_exceptions
    def handler(event, context):
        return http.json_response(200, {"ok": True})

    resp = handler({}, {})

    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"ok": True}


def test_translate_exceptions_turns_exception_into_500(monkeypatch):
    """
    If handler raises, translate_exceptions should catch it and return
    a standardized 500 error response.
    """

    @http.translate_exceptions
    def handler(event, context):
        raise RuntimeError("boom")

    resp = handler({}, {})
    assert resp["statusCode"] == 500

    body = json.loads(resp["body"])
    assert body["error"].startswith("Internal Server Error:")
    assert body["error_code"] == "INTERNAL_ERROR"


def test_translate_exceptions_logs(monkeypatch):
    """
    Ensure that translate_exceptions logs errors.
    """
    mock_log = MagicMock()
    monkeypatch.setattr(http, "logger", mock_log)

    @http.translate_exceptions
    def handler(event, context):
        raise ValueError("fail")

    handler({}, {})

    # Should log error with stacktrace
    assert mock_log.error.called
    msg = mock_log.error.call_args[0][0]
    assert "handler" in msg or "fail" in msg
