"""
Unit tests for lambdas/get_health.py
"""

import json
from datetime import datetime, timezone

from lambdas.get_health import lambda_handler


class TestGetHealth:
    """Tests for GET /health endpoint."""

    def test_returns_200_status(self):
        """Health check should return 200 OK."""
        event = {}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200

    def test_response_body_has_status_ok(self):
        """Response body should contain status 'ok'."""
        event = {}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert body["status"] == "ok"

    def test_response_body_has_checked_at(self):
        """Response body should contain checked_at timestamp."""
        event = {}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert "checked_at" in body
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(body["checked_at"].replace("Z", "+00:00"))

    def test_response_body_has_message(self):
        """Response body should contain a message."""
        event = {}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert body["message"] == "Registry API is reachable"

    def test_response_has_cors_headers(self):
        """Response should include CORS headers."""
        event = {}
        context = None

        response = lambda_handler(event, context)

        assert "Access-Control-Allow-Origin" in response["headers"]

    def test_checked_at_is_recent(self):
        """checked_at timestamp should be recent (within last minute)."""
        event = {}
        context = None

        before = datetime.now(timezone.utc)
        response = lambda_handler(event, context)
        after = datetime.now(timezone.utc)

        body = json.loads(response["body"])
        checked_at = datetime.fromisoformat(body["checked_at"].replace("Z", "+00:00"))

        assert before <= checked_at <= after
