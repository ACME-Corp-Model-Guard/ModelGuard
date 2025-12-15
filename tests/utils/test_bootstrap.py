import pytest
from unittest.mock import MagicMock

import src.utils.bootstrap as bootstrap


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """
    Ensure required environment variables exist.
    """
    monkeypatch.setenv("ADMIN_SECRET_NAME", "dummy_secret")
    monkeypatch.setenv("DEFAULT_ADMIN_GROUP", "Admin")
    monkeypatch.setenv("USER_POOL_ID", "pool-123")

    bootstrap.ADMIN_SECRET_NAME = "dummy_secret"
    bootstrap.DEFAULT_ADMIN_GROUP = "Admin"
    bootstrap.USER_POOL_ID = "pool-123"


@pytest.fixture(autouse=True)
def mock_secrets(monkeypatch):
    """
    Patch get_secret_value to return fixed admin credentials.
    """

    def fake_get_secret_value(secret_name: str, value: str) -> str:
        secrets = {
            "dummy_secret": {
                "DEFAULT_ADMIN_USERNAME": "admin",
                "DEFAULT_ADMIN_PASSWORD": "Pass123!",
            }
        }
        return secrets.get(secret_name, {}).get(value, "")

    monkeypatch.setattr(bootstrap, "get_secret_value", fake_get_secret_value)


@pytest.fixture
def mock_cognito(monkeypatch):
    """
    Patch boto3.client("cognito-idp") to return a MagicMock client.
    """
    client = MagicMock()
    monkeypatch.setattr(bootstrap.boto3, "client", lambda svc: client)
    return client


# ================================================================
# _ensure_cognito_group_exists()
# ================================================================


def test_ensure_group_exists_already_present(mock_cognito):
    mock_cognito.get_group.return_value = {"Group": {"GroupName": "Admin"}}

    bootstrap._ensure_cognito_group_exists(mock_cognito, "Admin")

    mock_cognito.get_group.assert_called_once()
    mock_cognito.create_group.assert_not_called()


def test_ensure_group_exists_creates_when_missing(mock_cognito):
    from botocore.exceptions import ClientError

    mock_cognito.get_group.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetGroup"
    )

    bootstrap._ensure_cognito_group_exists(mock_cognito, "Admin")

    mock_cognito.create_group.assert_called_once_with(
        GroupName="Admin",
        UserPoolId="pool-123",
        Description="Autocreated group: Admin",
    )


# ================================================================
# _ensure_user_exists()
# ================================================================


def test_ensure_user_exists_already_present(mock_cognito):
    """
    User already exists → should not call admin_create_user.
    """
    mock_cognito.admin_get_user.return_value = {"Username": "admin"}

    bootstrap._ensure_user_exists(
        mock_cognito, username="admin", password="Pass123!", admin_group="Admin"
    )

    mock_cognito.admin_create_user.assert_not_called()
    mock_cognito.admin_set_user_password.assert_not_called()
    mock_cognito.admin_confirm_sign_up.assert_called_once()
    mock_cognito.admin_add_user_to_group.assert_called_once()


def test_ensure_user_exists_creates_when_missing(mock_cognito):
    from botocore.exceptions import ClientError

    # Simulate "user not found"
    mock_cognito.admin_get_user.side_effect = ClientError(
        {"Error": {"Code": "UserNotFoundException"}}, "AdminGetUser"
    )

    bootstrap._ensure_user_exists(
        mock_cognito, username="admin", password="Pass123!", admin_group="Admin"
    )

    # Should create
    mock_cognito.admin_create_user.assert_called_once()
    mock_cognito.admin_set_user_password.assert_called_once_with(
        UserPoolId="pool-123",
        Username="admin",
        Password="Pass123!",
        Permanent=True,
    )
    mock_cognito.admin_confirm_sign_up.assert_called_once()
    mock_cognito.admin_add_user_to_group.assert_called_once()


def test_ensure_user_exists_already_confirmed(mock_cognito):
    from botocore.exceptions import ClientError

    # User exists
    mock_cognito.admin_get_user.return_value = {"Username": "admin"}

    # Confirmation fails because already confirmed
    mock_cognito.admin_confirm_sign_up.side_effect = ClientError(
        {"Error": {"Code": "NotAuthorizedException"}}, "Confirm"
    )

    bootstrap._ensure_user_exists(
        mock_cognito, username="admin", password="Pass123!", admin_group="Admin"
    )

    # Should swallow "NotAuthorizedException"
    mock_cognito.admin_add_user_to_group.assert_called_once()


def test_ensure_user_exists_group_already_added(mock_cognito):
    from botocore.exceptions import ClientError

    mock_cognito.admin_get_user.return_value = {"Username": "admin"}
    mock_cognito.admin_confirm_sign_up.return_value = {}

    # Adding to group → "already in group"
    mock_cognito.admin_add_user_to_group.side_effect = ClientError(
        {"Error": {"Code": "UserAlreadyInGroupException"}}, "AddUser"
    )

    bootstrap._ensure_user_exists(
        mock_cognito, username="admin", password="Pass123!", admin_group="Admin"
    )

    # Should NOT raise
    mock_cognito.admin_add_user_to_group.assert_called_once()


# ================================================================
# bootstrap_system()
# ================================================================


def test_bootstrap_system_calls_both_steps(mock_cognito, monkeypatch):
    """
    bootstrap_system() writes group and user setup in the correct order.
    """

    # Patch helpers to track calls
    called = []

    def fake_group(cognito, name):
        called.append(("group", name))

    def fake_user(cognito, username, password, admin_group):
        called.append(("user", username, admin_group))

    def fake_permissions(username):
        called.append(("permissions", username))

    monkeypatch.setattr(bootstrap, "_ensure_cognito_group_exists", fake_group)
    monkeypatch.setattr(bootstrap, "_ensure_user_exists", fake_user)
    monkeypatch.setattr(bootstrap, "_ensure_admin_permissions", fake_permissions)

    bootstrap.bootstrap_system()

    assert called == [
        ("group", "Admin"),
        ("user", "admin", "Admin"),
        ("permissions", "admin"),
    ]
