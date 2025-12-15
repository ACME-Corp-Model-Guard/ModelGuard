"""
Unit tests for lambdas/get_users.py (GET /users/{username} endpoint).

Tests cover:
- Authentication requirements
- Self-view authorization
- Admin view authorization
- User not found handling
- Response format
"""

import json
from unittest.mock import patch

from lambdas.get_users import lambda_handler


class TestGetUsersAuth:
    """Tests for GET /users authentication."""

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


class TestGetUsersAuthorization:
    """Tests for GET /users authorization logic."""

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_user_can_view_self(self, mock_auth, mock_get_info):
        """User can view their own info."""
        mock_auth.return_value = {"username": "testuser", "groups": ["User"]}
        mock_get_info.return_value = {
            "user": {"name": "testuser", "is_admin": False},
            "permissions": {"can_upload": True, "can_search": True, "can_download": False},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "testuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        mock_get_info.assert_called_once_with("testuser")

    @patch("src.auth.authorize")
    def test_user_cannot_view_other(self, mock_auth):
        """Non-admin user cannot view another user's info."""
        mock_auth.return_value = {"username": "alice", "groups": ["User"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "bob"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert body["error_code"] == "PERMISSION_DENIED"

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_admin_can_view_any_user(self, mock_auth, mock_get_info):
        """Admin can view any user's info."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_get_info.return_value = {
            "user": {"name": "someuser", "is_admin": False},
            "permissions": {"can_upload": False, "can_search": True, "can_download": True},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "someuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        mock_get_info.assert_called_once_with("someuser")

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_admin_can_view_self(self, mock_auth, mock_get_info):
        """Admin can view their own info."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_get_info.return_value = {
            "user": {"name": "admin", "is_admin": True},
            "permissions": {"can_upload": True, "can_search": True, "can_download": True},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "admin"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200


class TestGetUsersValidation:
    """Tests for GET /users request validation."""

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


class TestGetUsersNotFound:
    """Tests for GET /users when user doesn't exist."""

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_nonexistent_user_returns_404(self, mock_auth, mock_get_info):
        """Requesting non-existent user should return 404."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_get_info.return_value = None

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "nonexistent"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error_code"] == "USER_NOT_FOUND"

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_self_view_nonexistent_returns_404(self, mock_auth, mock_get_info):
        """Viewing own non-existent user record should return 404."""
        mock_auth.return_value = {"username": "ghost", "groups": ["User"]}
        mock_get_info.return_value = None

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "ghost"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404


class TestGetUsersSuccess:
    """Tests for GET /users successful responses."""

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_success_response_format(self, mock_auth, mock_get_info):
        """Successful request should return user info in proper format."""
        mock_auth.return_value = {"username": "testuser", "groups": ["User"]}
        mock_get_info.return_value = {
            "user": {"name": "testuser", "is_admin": False},
            "permissions": {"can_upload": True, "can_search": True, "can_download": False},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "testuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "user" in body
        assert "permissions" in body
        assert body["user"]["name"] == "testuser"
        assert body["user"]["is_admin"] is False
        assert body["permissions"]["can_upload"] is True
        assert body["permissions"]["can_download"] is False

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_admin_user_info_format(self, mock_auth, mock_get_info):
        """Admin user info should show is_admin as True."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_get_info.return_value = {
            "user": {"name": "admin", "is_admin": True},
            "permissions": {"can_upload": True, "can_search": True, "can_download": True},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "admin"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"]["is_admin"] is True
        assert body["permissions"]["can_upload"] is True
        assert body["permissions"]["can_search"] is True
        assert body["permissions"]["can_download"] is True

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_get_user_info_service_called(self, mock_auth, mock_get_info):
        """get_user_info service should be called with correct username."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_get_info.return_value = {
            "user": {"name": "targetuser", "is_admin": False},
            "permissions": {},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "targetuser"},
        }

        lambda_handler(event, None)

        mock_get_info.assert_called_once_with("targetuser")


class TestGetUsersEdgeCases:
    """Tests for GET /users edge cases."""

    @patch("src.auth.authorize")
    def test_user_with_admin_in_name_cannot_view_others(self, mock_auth):
        """User with 'admin' in username still can't view others."""
        mock_auth.return_value = {"username": "adminlike", "groups": ["User"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "otheruser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("lambdas.get_users.get_user_info")
    @patch("src.auth.authorize")
    def test_user_in_multiple_groups_including_admin(self, mock_auth, mock_get_info):
        """User in Admin group (among others) can view any user."""
        mock_auth.return_value = {
            "username": "superuser",
            "groups": ["Admin", "User", "Special"],
        }
        mock_get_info.return_value = {
            "user": {"name": "anyuser", "is_admin": False},
            "permissions": {},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "pathParameters": {"username": "anyuser"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
