"""
Tests for the user service module (src/users/user_service.py).

Tests cover:
- User creation with permissions
- User deletion including token cleanup
- User existence checks
- User info retrieval
"""

import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.users.user_service import (
    create_user,
    delete_user,
    get_user_info,
    user_exists,
    _invalidate_user_tokens,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_cognito_client():
    """Create a mock Cognito client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "username": "testuser",
        "password": "SecurePassword123!",
        "is_admin": False,
        "permissions": {
            "can_upload": True,
            "can_search": True,
            "can_download": False,
        },
        "created_by": "admin",
    }


@pytest.fixture
def mock_tables(mocker):
    """
    Create moto-mocked DynamoDB tables and patch get_ddb_table to return them.
    This ensures tests use the mocked tables instead of cached clients.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-2")

        permissions_table = dynamodb.create_table(
            TableName=os.environ["USER_PERMISSIONS_TABLE"],
            KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        tokens_table = dynamodb.create_table(
            TableName=os.environ["TOKENS_TABLE"],
            KeySchema=[{"AttributeName": "token", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "token", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        def get_table_mock(table_name):
            if table_name == os.environ["USER_PERMISSIONS_TABLE"]:
                return permissions_table
            elif table_name == os.environ["TOKENS_TABLE"]:
                return tokens_table
            raise ValueError(f"Unexpected table: {table_name}")

        # Patch get_ddb_table in both modules that use it
        mocker.patch("src.permissions.get_ddb_table", side_effect=get_table_mock)
        mocker.patch("src.users.user_service.get_ddb_table", side_effect=get_table_mock)

        yield {
            "permissions": permissions_table,
            "tokens": tokens_table,
        }


# =============================================================================
# Test: user_exists
# =============================================================================


def test_user_exists_true(mock_cognito_client):
    """Test user_exists returns True for existing user."""
    mock_cognito_client.admin_get_user.return_value = {"Username": "testuser"}

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = user_exists("testuser")

    assert result is True
    mock_cognito_client.admin_get_user.assert_called_once()


def test_user_exists_false(mock_cognito_client):
    """Test user_exists returns False for non-existent user."""
    error_response = {"Error": {"Code": "UserNotFoundException", "Message": "User not found"}}
    mock_cognito_client.admin_get_user.side_effect = ClientError(error_response, "AdminGetUser")

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = user_exists("nonexistent")

    assert result is False


def test_user_exists_other_error(mock_cognito_client):
    """Test user_exists raises for other Cognito errors."""
    error_response = {"Error": {"Code": "InternalError", "Message": "Internal error"}}
    mock_cognito_client.admin_get_user.side_effect = ClientError(error_response, "AdminGetUser")

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        with pytest.raises(ClientError):
            user_exists("testuser")


# =============================================================================
# Test: create_user
# =============================================================================


def test_create_user_success(mock_cognito_client, mock_tables, sample_user_data):
    """Test successful user creation."""
    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = create_user(
            username=sample_user_data["username"],
            password=sample_user_data["password"],
            is_admin=sample_user_data["is_admin"],
            permissions=sample_user_data["permissions"],
            created_by=sample_user_data["created_by"],
        )

    # Verify result structure
    assert result["user"]["name"] == "testuser"
    assert result["user"]["is_admin"] is False
    assert result["permissions"]["can_upload"] is True
    assert result["permissions"]["can_search"] is True
    assert result["permissions"]["can_download"] is False

    # Verify Cognito calls
    mock_cognito_client.admin_create_user.assert_called_once()
    mock_cognito_client.admin_set_user_password.assert_called_once()
    mock_cognito_client.admin_add_user_to_group.assert_called_once()


def test_create_user_admin(mock_cognito_client, mock_tables):
    """Test creating an admin user."""
    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = create_user(
            username="adminuser",
            password="AdminPassword123!",
            is_admin=True,
            permissions={"can_upload": True, "can_search": True, "can_download": True},
            created_by="system",
        )

    assert result["user"]["is_admin"] is True

    # Verify user was added to Admin group
    mock_cognito_client.admin_add_user_to_group.assert_called_with(
        UserPoolId=os.environ["USER_POOL_ID"],
        Username="adminuser",
        GroupName="Admin",
    )


# =============================================================================
# Test: delete_user
# =============================================================================


def test_delete_user_success(mock_cognito_client, mock_tables):
    """Test successful user deletion."""
    # Insert test data
    mock_tables["permissions"].put_item(
        Item={
            "username": "testuser",
            "can_upload": True,
            "can_search": True,
            "can_download": True,
        }
    )
    mock_tables["tokens"].put_item(Item={"token": "token1", "username": "testuser"})
    mock_tables["tokens"].put_item(Item={"token": "token2", "username": "testuser"})
    mock_tables["tokens"].put_item(Item={"token": "token3", "username": "otheruser"})

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        delete_user("testuser")

    # Verify Cognito deletion
    mock_cognito_client.admin_delete_user.assert_called_once_with(
        UserPoolId=os.environ["USER_POOL_ID"],
        Username="testuser",
    )

    # Verify permissions deleted
    response = mock_tables["permissions"].get_item(Key={"username": "testuser"})
    assert "Item" not in response

    # Verify tokens deleted (only testuser's tokens)
    response = mock_tables["tokens"].scan()
    items = response.get("Items", [])
    assert len(items) == 1
    assert items[0]["username"] == "otheruser"


# =============================================================================
# Test: _invalidate_user_tokens
# =============================================================================


def test_invalidate_user_tokens(mock_tables):
    """Test token invalidation for a user."""
    # Insert tokens for multiple users
    mock_tables["tokens"].put_item(Item={"token": "t1", "username": "alice"})
    mock_tables["tokens"].put_item(Item={"token": "t2", "username": "alice"})
    mock_tables["tokens"].put_item(Item={"token": "t3", "username": "bob"})

    # Invalidate alice's tokens
    count = _invalidate_user_tokens("alice")

    assert count == 2

    # Verify only bob's token remains
    response = mock_tables["tokens"].scan()
    items = response.get("Items", [])
    assert len(items) == 1
    assert items[0]["username"] == "bob"


def test_invalidate_user_tokens_none(mock_tables):
    """Test token invalidation when user has no tokens."""
    count = _invalidate_user_tokens("nonexistent")
    assert count == 0


# =============================================================================
# Test: get_user_info
# =============================================================================


def test_get_user_info_found(mock_cognito_client, mock_tables):
    """Test getting user info for an existing user."""
    mock_tables["permissions"].put_item(
        Item={
            "username": "testuser",
            "can_upload": True,
            "can_search": False,
            "can_download": True,
        }
    )

    # Mock Cognito responses
    mock_cognito_client.admin_get_user.return_value = {"Username": "testuser"}
    mock_cognito_client.admin_list_groups_for_user.return_value = {
        "Groups": [{"GroupName": "User"}]
    }

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = get_user_info("testuser")

    assert result is not None
    assert result["user"]["name"] == "testuser"
    assert result["user"]["is_admin"] is False
    assert result["permissions"]["can_upload"] is True
    assert result["permissions"]["can_search"] is False
    assert result["permissions"]["can_download"] is True


def test_get_user_info_admin(mock_cognito_client, mock_tables):
    """Test getting user info for an admin user."""
    mock_tables["permissions"].put_item(
        Item={
            "username": "adminuser",
            "can_upload": True,
            "can_search": True,
            "can_download": True,
        }
    )

    # Mock Cognito responses
    mock_cognito_client.admin_get_user.return_value = {"Username": "adminuser"}
    mock_cognito_client.admin_list_groups_for_user.return_value = {
        "Groups": [{"GroupName": "Admin"}, {"GroupName": "User"}]
    }

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = get_user_info("adminuser")

    assert result is not None
    assert result["user"]["is_admin"] is True


def test_get_user_info_not_found(mock_cognito_client):
    """Test getting user info for a non-existent user returns None."""
    error_response = {"Error": {"Code": "UserNotFoundException", "Message": "User not found"}}
    mock_cognito_client.admin_get_user.side_effect = ClientError(error_response, "AdminGetUser")

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = get_user_info("nonexistent")

    assert result is None


def test_get_user_info_no_permissions(mock_cognito_client, mock_tables):
    """Test getting user info when user has no permissions record."""
    # Mock Cognito responses
    mock_cognito_client.admin_get_user.return_value = {"Username": "testuser"}
    mock_cognito_client.admin_list_groups_for_user.return_value = {
        "Groups": [{"GroupName": "User"}]
    }

    with patch("src.users.user_service.get_cognito", return_value=mock_cognito_client):
        result = get_user_info("testuser")

    assert result is not None
    # Should default to all False permissions
    assert result["permissions"]["can_upload"] is False
    assert result["permissions"]["can_search"] is False
    assert result["permissions"]["can_download"] is False
