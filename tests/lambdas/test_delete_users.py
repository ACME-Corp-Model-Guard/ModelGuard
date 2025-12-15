"""
Unit tests for lambdas/delete_users.py (DELETE /users/{username} endpoint).

Tests cover:
- Authentication requirements
- Self-deletion authorization
- Admin deletion authorization
- User not found handling
- Error handling
"""

import json
from unittest.mock import patch

from botocore.exceptions import ClientError

from lambdas.delete_users import lambda_handler


class TestDeleteUsersAuth:
    """Tests for DELETE /users authentication."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {
            "headers": {},
            "pathParameters": {"username": "testuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403


class TestDeleteUsersAuthorization:
    """Tests for DELETE /users authorization logic."""

    @patch("lambdas.delete_users.delete_user")
    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_user_can_delete_self(self, mock_auth, mock_exists, mock_delete):
        """User can delete their own account."""
        mock_auth.return_value = {"username": "testuser", "groups": ["User"]}
        mock_exists.return_value = True

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "testuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        mock_delete.assert_called_once_with("testuser")

    @patch("src.auth.authorize")
    def test_user_cannot_delete_other(self, mock_auth):
        """Non-admin user cannot delete another user's account."""
        mock_auth.return_value = {"username": "alice", "groups": ["User"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "bob"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert body["error_code"] == "PERMISSION_DENIED"

    @patch("lambdas.delete_users.delete_user")
    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_admin_can_delete_any_user(self, mock_auth, mock_exists, mock_delete):
        """Admin can delete any user's account."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = True

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "someuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        mock_delete.assert_called_once_with("someuser")

    @patch("lambdas.delete_users.delete_user")
    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_admin_can_delete_self(self, mock_auth, mock_exists, mock_delete):
        """Admin can delete their own account."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = True

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "admin"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        mock_delete.assert_called_once_with("admin")


class TestDeleteUsersValidation:
    """Tests for DELETE /users request validation."""

    @patch("src.auth.authorize")
    def test_missing_username_param_returns_400(self, mock_auth):
        """Missing username path parameter should return 400."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "MISSING_PARAM"

    @patch("src.auth.authorize")
    def test_null_path_params_returns_400(self, mock_auth):
        """Null pathParameters should return 400."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": None,
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400


class TestDeleteUsersNotFound:
    """Tests for DELETE /users when user doesn't exist."""

    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_nonexistent_user_returns_404(self, mock_auth, mock_exists):
        """Deleting non-existent user should return 404."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = False

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "nonexistent"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error_code"] == "USER_NOT_FOUND"

    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_self_delete_nonexistent_returns_404(self, mock_auth, mock_exists):
        """Self-deleting non-existent user should return 404."""
        mock_auth.return_value = {"username": "ghost", "groups": ["User"]}
        mock_exists.return_value = False

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "ghost"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404


class TestDeleteUsersErrors:
    """Tests for DELETE /users error handling."""

    @patch("lambdas.delete_users.delete_user")
    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_cognito_user_not_found_returns_404(self, mock_auth, mock_exists, mock_delete):
        """Cognito UserNotFoundException should return 404."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = True
        mock_delete.side_effect = ClientError(
            {
                "Error": {
                    "Code": "UserNotFoundException",
                    "Message": "User not found",
                }
            },
            "AdminDeleteUser",
        )

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "deleteduser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error_code"] == "USER_NOT_FOUND"

    @patch("lambdas.delete_users.delete_user")
    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_other_cognito_error_returns_500(self, mock_auth, mock_exists, mock_delete):
        """Other Cognito errors should return 500."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = True
        mock_delete.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InternalError",
                    "Message": "Something went wrong",
                }
            },
            "AdminDeleteUser",
        )

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "testuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error_code"] == "USER_DELETION_FAILED"


class TestDeleteUsersSuccess:
    """Tests for DELETE /users successful responses."""

    @patch("lambdas.delete_users.delete_user")
    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_success_response_format(self, mock_auth, mock_exists, mock_delete):
        """Successful deletion should return proper response format."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = True

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "deleteduser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "message" in body
        assert "deleteduser" in body["message"]
        assert "deleted" in body["message"].lower()

    @patch("lambdas.delete_users.delete_user")
    @patch("lambdas.delete_users.user_exists")
    @patch("src.auth.authorize")
    def test_delete_user_service_called(self, mock_auth, mock_exists, mock_delete):
        """delete_user service should be called with correct username."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = True

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "targetuser"},
        }

        lambda_handler(event, None)

        mock_delete.assert_called_once_with("targetuser")
