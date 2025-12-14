"""
Unit tests for lambdas/get_tracks.py
"""

import json

from lambdas.get_tracks import lambda_handler, SUPPORTED_TRACKS


class TestGetTracks:
    """Tests for GET /tracks endpoint."""

    def test_returns_200_status(self):
        """Tracks endpoint should return 200 OK."""
        event = {}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200

    def test_response_body_has_planned_tracks(self):
        """Response body should contain plannedTracks key."""
        event = {}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert "plannedTracks" in body

    def test_planned_tracks_is_list(self):
        """plannedTracks should be a list."""
        event = {}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert isinstance(body["plannedTracks"], list)

    def test_planned_tracks_matches_constant(self):
        """plannedTracks should match SUPPORTED_TRACKS constant."""
        event = {}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert body["plannedTracks"] == SUPPORTED_TRACKS

    def test_access_control_track_included(self):
        """Access control track should be included in supported tracks."""
        event = {}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert "Access control track" in body["plannedTracks"]

    def test_response_has_cors_headers(self):
        """Response should include CORS headers."""
        event = {}
        context = None

        response = lambda_handler(event, context)

        assert "Access-Control-Allow-Origin" in response["headers"]
