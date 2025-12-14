"""
Unit tests for lambdas/put_authenticate.py
"""

import json
from unittest.mock import patch

from lambdas.put_authenticate import lambda_handler


class TestPutAuthenticate:
    """Tests for PUT /authenticate endpoint."""

    def test_malformed_json_body_returns_400(self):
        """Malformed JSON body should return 400."""
        event = {"body": "not valid json"}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Malformed JSON" in body.get("message", body.get("error", ""))

    def test_non_object_body_returns_400(self):
        """Non-object JSON body should return 400."""
        event = {"body": json.dumps(["array", "not", "object"])}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Malformed AuthenticationRequest" in body.get("message", body.get("error", ""))

    def test_missing_user_returns_400(self):
        """Missing user field should return 400."""
        event = {"body": json.dumps({"secret": {"password": "test"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Malformed AuthenticationRequest" in body.get("message", body.get("error", ""))

    def test_missing_secret_returns_400(self):
        """Missing secret field should return 400."""
        event = {"body": json.dumps({"user": {"name": "test"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Malformed AuthenticationRequest" in body.get("message", body.get("error", ""))

    def test_missing_name_in_user_returns_400(self):
        """Missing name in user object should return 400."""
        event = {"body": json.dumps({"user": {"invalid": "field"}, "secret": {"password": "test"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Malformed AuthenticationRequest" in body.get("message", body.get("error", ""))

    def test_missing_password_in_secret_returns_400(self):
        """Missing password in secret object should return 400."""
        event = {"body": json.dumps({"user": {"name": "test"}, "secret": {"invalid": "field"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Malformed AuthenticationRequest" in body.get("message", body.get("error", ""))

    def test_empty_username_returns_400(self):
        """Empty username should return 400."""
        event = {"body": json.dumps({"user": {"name": ""}, "secret": {"password": "test"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Missing username or password" in body.get("message", body.get("error", ""))

    def test_empty_password_returns_400(self):
        """Empty password should return 400."""
        event = {"body": json.dumps({"user": {"name": "test"}, "secret": {"password": ""}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Missing username or password" in body.get("message", body.get("error", ""))

    @patch("lambdas.put_authenticate.authenticate_user")
    def test_authentication_failure_returns_401(self, mock_auth):
        """Authentication failure should return 401."""
        mock_auth.side_effect = Exception("Invalid credentials")
        event = {"body": json.dumps({"user": {"name": "test"}, "secret": {"password": "wrong"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "Invalid username or password" in body.get("message", body.get("error", ""))

    @patch("lambdas.put_authenticate.authenticate_user")
    def test_missing_access_token_returns_500(self, mock_auth):
        """Missing access_token in Cognito response should return 500."""
        mock_auth.return_value = {}  # No access_token
        event = {"body": json.dumps({"user": {"name": "test"}, "secret": {"password": "test"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 500

    @patch("lambdas.put_authenticate.authenticate_user")
    def test_successful_authentication_returns_200(self, mock_auth):
        """Successful authentication should return 200 with bearer token."""
        mock_auth.return_value = {"access_token": "test_token_12345"}
        event = {"body": json.dumps({"user": {"name": "test"}, "secret": {"password": "test"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200

    @patch("lambdas.put_authenticate.authenticate_user")
    def test_successful_authentication_returns_bearer_string(self, mock_auth):
        """Successful authentication should return bearer token string."""
        mock_auth.return_value = {"access_token": "test_token_12345"}
        event = {"body": json.dumps({"user": {"name": "test"}, "secret": {"password": "test"}})}
        context = None

        response = lambda_handler(event, context)
        body = json.loads(response["body"])

        assert body == "bearer test_token_12345"

    def test_empty_body_returns_400(self):
        """Empty body should return 400."""
        event = {"body": "{}"}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400

    def test_user_as_string_returns_400(self):
        """User field as string instead of object should return 400."""
        event = {"body": json.dumps({"user": "string", "secret": {"password": "test"}})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400

    def test_secret_as_string_returns_400(self):
        """Secret field as string instead of object should return 400."""
        event = {"body": json.dumps({"user": {"name": "test"}, "secret": "string"})}
        context = None

        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
