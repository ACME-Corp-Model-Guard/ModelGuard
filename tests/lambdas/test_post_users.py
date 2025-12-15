"""
Unit tests for lambdas/post_users.py (POST /users endpoint).

Tests cover:
- Admin-only access control
- Request validation (missing fields, invalid username)
- User creation success
- Duplicate user handling
- Password validation errors
"""

import json
from unittest.mock import patch

from botocore.exceptions import ClientError

from lambdas.post_users import lambda_handler


class TestPostUsersAuth:
    """Tests for POST /users authentication and authorization."""

    @patch("src.auth.authorize")
    def test_missing_auth_returns_403(self, mock_auth):
        """Missing authorization should return 403."""
        mock_auth.side_effect = Exception("Unauthorized")
        event = {"headers": {}, "body": "{}"}

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_non_admin_returns_403(self, mock_auth):
        """Non-admin user should return 403 (insufficient role)."""
        # @roles_required calls authorize with allowed_roles, which triggers require_roles
        # When roles don't match, it raises an exception caught by the decorator
        mock_auth.side_effect = Exception("User not in allowed roles")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "newuser"},
                    "secret": {"password": "Password123!"},
                    "permissions": {},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403

    @patch("src.auth.authorize")
    def test_empty_groups_returns_403(self, mock_auth):
        """User with no groups should return 403."""
        mock_auth.side_effect = Exception("User not in allowed roles")
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "newuser"},
                    "secret": {"password": "Password123!"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 403


class TestPostUsersValidation:
    """Tests for POST /users request validation."""

    @patch("src.auth.authorize")
    def test_invalid_json_returns_400(self, mock_auth):
        """Invalid JSON body should return 400."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": "not valid json",
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "INVALID_JSON"

    @patch("src.auth.authorize")
    def test_missing_username_returns_400(self, mock_auth):
        """Missing username should return 400."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {},
                    "secret": {"password": "Password123!"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "MISSING_FIELD"
        assert "user.name" in body["error"]

    @patch("src.auth.authorize")
    def test_missing_password_returns_400(self, mock_auth):
        """Missing password should return 400."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "newuser"},
                    "secret": {},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "MISSING_FIELD"
        assert "secret.password" in body["error"]

    @patch("src.auth.authorize")
    def test_short_username_returns_400(self, mock_auth):
        """Username less than 3 characters should return 400."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "ab"},
                    "secret": {"password": "Password123!"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "INVALID_USERNAME"

    @patch("src.auth.authorize")
    def test_empty_body_returns_400(self, mock_auth):
        """Empty body should return 400 for missing fields."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": "{}",
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400


class TestPostUsersSuccess:
    """Tests for POST /users successful user creation."""

    @patch("lambdas.post_users.create_user")
    @patch("lambdas.post_users.user_exists")
    @patch("src.auth.authorize")
    def test_create_user_success(self, mock_auth, mock_exists, mock_create):
        """Admin can successfully create a new user."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = False
        mock_create.return_value = {
            "user": {"name": "newuser", "is_admin": False},
            "permissions": {"can_upload": True, "can_search": True, "can_download": False},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "newuser", "is_admin": False},
                    "secret": {"password": "SecurePass123!"},
                    "permissions": {
                        "can_upload": True,
                        "can_search": True,
                        "can_download": False,
                    },
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["user"]["name"] == "newuser"
        assert body["permissions"]["can_upload"] is True

    @patch("lambdas.post_users.create_user")
    @patch("lambdas.post_users.user_exists")
    @patch("src.auth.authorize")
    def test_create_admin_user(self, mock_auth, mock_exists, mock_create):
        """Admin can create another admin user."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = False
        mock_create.return_value = {
            "user": {"name": "newadmin", "is_admin": True},
            "permissions": {"can_upload": True, "can_search": True, "can_download": True},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "newadmin", "is_admin": True},
                    "secret": {"password": "SecurePass123!"},
                    "permissions": {
                        "can_upload": True,
                        "can_search": True,
                        "can_download": True,
                    },
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["user"]["is_admin"] is True

    @patch("lambdas.post_users.create_user")
    @patch("lambdas.post_users.user_exists")
    @patch("src.auth.authorize")
    def test_create_user_calls_service(self, mock_auth, mock_exists, mock_create):
        """create_user should be called with correct parameters."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = False
        mock_create.return_value = {
            "user": {"name": "testuser", "is_admin": False},
            "permissions": {},
        }

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "testuser", "is_admin": False},
                    "secret": {"password": "MyPass123!"},
                    "permissions": {"can_upload": True},
                }
            ),
        }

        lambda_handler(event, None)

        mock_create.assert_called_once_with(
            username="testuser",
            password="MyPass123!",
            is_admin=False,
            permissions={"can_upload": True},
            created_by="admin",
        )


class TestPostUsersErrors:
    """Tests for POST /users error handling."""

    @patch("lambdas.post_users.user_exists")
    @patch("src.auth.authorize")
    def test_duplicate_user_returns_409(self, mock_auth, mock_exists):
        """Creating duplicate user should return 409."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = True

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "existinguser"},
                    "secret": {"password": "Password123!"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert body["error_code"] == "USER_EXISTS"

    @patch("lambdas.post_users.create_user")
    @patch("lambdas.post_users.user_exists")
    @patch("src.auth.authorize")
    def test_weak_password_returns_400(self, mock_auth, mock_exists, mock_create):
        """Weak password should return 400."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = False
        mock_create.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InvalidPasswordException",
                    "Message": "Password must have uppercase letters",
                }
            },
            "AdminCreateUser",
        )

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "newuser"},
                    "secret": {"password": "weak"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "WEAK_PASSWORD"

    @patch("lambdas.post_users.create_user")
    @patch("lambdas.post_users.user_exists")
    @patch("src.auth.authorize")
    def test_cognito_username_exists_returns_409(self, mock_auth, mock_exists, mock_create):
        """Cognito UsernameExistsException should return 409."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = False  # Race condition - check passed but creation failed
        mock_create.side_effect = ClientError(
            {
                "Error": {
                    "Code": "UsernameExistsException",
                    "Message": "Username already exists",
                }
            },
            "AdminCreateUser",
        )

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "existinguser"},
                    "secret": {"password": "Password123!"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert body["error_code"] == "USER_EXISTS"

    @patch("lambdas.post_users.create_user")
    @patch("lambdas.post_users.user_exists")
    @patch("src.auth.authorize")
    def test_other_cognito_error_returns_500(self, mock_auth, mock_exists, mock_create):
        """Other Cognito errors should return 500."""
        mock_auth.return_value = {"username": "admin", "groups": ["Admin"]}
        mock_exists.return_value = False
        mock_create.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InternalError",
                    "Message": "Something went wrong",
                }
            },
            "AdminCreateUser",
        )

        event = {
            "headers": {"X-Authorization": "bearer token"},
            "body": json.dumps(
                {
                    "user": {"name": "newuser"},
                    "secret": {"password": "Password123!"},
                }
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error_code"] == "USER_CREATION_FAILED"
