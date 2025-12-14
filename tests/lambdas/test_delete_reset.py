"""
Unit tests for lambdas/delete_reset.py
"""

import json
from unittest.mock import patch

from lambdas.delete_reset import lambda_handler


class TestDeleteReset:
    """Tests for DELETE /reset endpoint."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {"headers": {}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_non_admin_returns_401(self, mock_auth):
        """Non-admin user should return 401."""
        mock_auth.return_value = {"username": "test", "groups": ["User"]}
        event = {"headers": {"X-Authorization": "bearer token"}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 401

    @patch("lambdas.delete_reset.bootstrap_system")
    @patch("lambdas.delete_reset.clear_bucket")
    @patch("lambdas.delete_reset.clear_table")
    @patch("src.auth.authorize")
    def test_admin_can_reset(self, mock_auth, mock_clear_table, mock_clear_bucket, mock_bootstrap):
        """Admin user should be able to reset."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {"headers": {"X-Authorization": "bearer token"}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200

    @patch("lambdas.delete_reset.bootstrap_system")
    @patch("lambdas.delete_reset.clear_bucket")
    @patch("lambdas.delete_reset.clear_table")
    @patch("src.auth.authorize")
    def test_clears_artifacts_table(
        self, mock_auth, mock_clear_table, mock_clear_bucket, mock_bootstrap
    ):
        """Reset should clear artifacts table."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {"headers": {"X-Authorization": "bearer token"}}

        lambda_handler(event, None)

        # Should be called twice - once for artifacts, once for rejected artifacts
        assert mock_clear_table.call_count == 2

    @patch("lambdas.delete_reset.bootstrap_system")
    @patch("lambdas.delete_reset.clear_bucket")
    @patch("lambdas.delete_reset.clear_table")
    @patch("src.auth.authorize")
    def test_clears_s3_bucket(self, mock_auth, mock_clear_table, mock_clear_bucket, mock_bootstrap):
        """Reset should clear S3 bucket."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {"headers": {"X-Authorization": "bearer token"}}

        lambda_handler(event, None)

        mock_clear_bucket.assert_called_once()

    @patch("lambdas.delete_reset.bootstrap_system")
    @patch("lambdas.delete_reset.clear_bucket")
    @patch("lambdas.delete_reset.clear_table")
    @patch("src.auth.authorize")
    def test_runs_bootstrap(self, mock_auth, mock_clear_table, mock_clear_bucket, mock_bootstrap):
        """Reset should run bootstrap_system."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {"headers": {"X-Authorization": "bearer token"}}

        lambda_handler(event, None)

        mock_bootstrap.assert_called_once()

    @patch("lambdas.delete_reset.bootstrap_system")
    @patch("lambdas.delete_reset.clear_bucket")
    @patch("lambdas.delete_reset.clear_table")
    @patch("src.auth.authorize")
    def test_response_body_format(
        self, mock_auth, mock_clear_table, mock_clear_bucket, mock_bootstrap
    ):
        """Response body should contain success message."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {"headers": {"X-Authorization": "bearer token"}}

        response = lambda_handler(event, None)
        body = json.loads(response["body"])

        assert body["status"] == "ok"
        assert "reset" in body["message"].lower() or "bootstrap" in body["message"].lower()

    @patch("src.auth.authorize")
    def test_empty_groups_returns_401(self, mock_auth):
        """User with no groups should return 401."""
        mock_auth.return_value = {"username": "test", "groups": []}
        event = {"headers": {"X-Authorization": "bearer token"}}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 401

    @patch("src.auth.authorize")
    def test_admin_case_sensitive(self, mock_auth):
        """Admin check should be case-sensitive."""
        mock_auth.return_value = {"username": "test", "groups": ["admin"]}  # lowercase
        event = {"headers": {"X-Authorization": "bearer token"}}

        response = lambda_handler(event, None)

        # "admin" (lowercase) is not "Admin", so should fail
        assert response["statusCode"] == 401
