"""
Tests for the permissions module (src/permissions.py).

Tests cover:
- Loading and saving permissions from/to DynamoDB
- Permission checking with admin bypass
- The @permissions_required decorator
"""

import os

import boto3
import pytest
from moto import mock_aws

from src.permissions import (
    UserPermissions,
    check_permission,
    delete_user_permissions,
    get_user_permission_flags,
    load_user_permissions,
    permissions_required,
    save_user_permissions,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_permissions() -> UserPermissions:
    """Sample user permissions for testing."""
    return {
        "username": "testuser",
        "can_upload": True,
        "can_search": True,
        "can_download": False,
        "created_at": "2024-01-01T00:00:00Z",
        "created_by": "admin",
        "updated_at": None,
    }


@pytest.fixture
def mock_ddb_table(mocker):
    """
    Create a moto-mocked DynamoDB table and patch get_ddb_table to return it.
    This ensures tests use the mocked table instead of the cached client.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
        table = dynamodb.create_table(
            TableName=os.environ["USER_PERMISSIONS_TABLE"],
            KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # Patch get_ddb_table to return our moto-mocked table
        mocker.patch("src.permissions.get_ddb_table", return_value=table)
        yield table


# =============================================================================
# Test: load_user_permissions
# =============================================================================


def test_load_user_permissions_found(mock_ddb_table):
    """Test loading permissions for an existing user."""
    # Insert test data
    mock_ddb_table.put_item(
        Item={
            "username": "testuser",
            "can_upload": True,
            "can_search": False,
            "can_download": True,
            "created_at": "2024-01-01T00:00:00Z",
            "created_by": "admin",
        }
    )

    # Test
    result = load_user_permissions("testuser")

    assert result is not None
    assert result["username"] == "testuser"
    assert result["can_upload"] is True
    assert result["can_search"] is False
    assert result["can_download"] is True


def test_load_user_permissions_not_found(mock_ddb_table):
    """Test loading permissions for a non-existent user returns None."""
    result = load_user_permissions("nonexistent")
    assert result is None


# =============================================================================
# Test: save_user_permissions
# =============================================================================


def test_save_user_permissions(mock_ddb_table, sample_permissions):
    """Test saving user permissions to DynamoDB."""
    # Save
    save_user_permissions(sample_permissions)

    # Verify
    response = mock_ddb_table.get_item(Key={"username": "testuser"})
    item = response.get("Item")

    assert item is not None
    assert item["username"] == "testuser"
    assert item["can_upload"] is True
    assert item["can_search"] is True
    assert item["can_download"] is False


# =============================================================================
# Test: delete_user_permissions
# =============================================================================


def test_delete_user_permissions(mock_ddb_table, sample_permissions):
    """Test deleting user permissions from DynamoDB."""
    # Insert and then delete
    mock_ddb_table.put_item(Item=sample_permissions)
    result = delete_user_permissions("testuser")

    assert result is True

    # Verify deletion
    response = mock_ddb_table.get_item(Key={"username": "testuser"})
    assert "Item" not in response


# =============================================================================
# Test: check_permission
# =============================================================================


def test_check_permission_admin_bypass(mock_ddb_table):
    """Test that admins bypass permission checks."""
    # Admin auth context
    auth_context = {
        "username": "adminuser",
        "groups": ["Admin"],
        "claims": {},
        "token": "xxx",
    }

    # Admin should have all permissions regardless of DB state
    assert check_permission(auth_context, "can_upload") is True
    assert check_permission(auth_context, "can_search") is True
    assert check_permission(auth_context, "can_download") is True


def test_check_permission_user_has_permission(mock_ddb_table, sample_permissions):
    """Test checking a permission that the user has."""
    mock_ddb_table.put_item(Item=sample_permissions)

    auth_context = {
        "username": "testuser",
        "groups": ["User"],
        "claims": {},
        "token": "xxx",
    }

    # testuser has can_upload = True
    assert check_permission(auth_context, "can_upload") is True


def test_check_permission_user_lacks_permission(mock_ddb_table, sample_permissions):
    """Test checking a permission that the user lacks."""
    mock_ddb_table.put_item(Item=sample_permissions)

    auth_context = {
        "username": "testuser",
        "groups": ["User"],
        "claims": {},
        "token": "xxx",
    }

    # testuser has can_download = False
    assert check_permission(auth_context, "can_download") is False


def test_check_permission_no_permissions_record(mock_ddb_table):
    """Test checking permission when user has no permissions record."""
    auth_context = {
        "username": "unknownuser",
        "groups": ["User"],
        "claims": {},
        "token": "xxx",
    }

    assert check_permission(auth_context, "can_upload") is False


# =============================================================================
# Test: get_user_permission_flags
# =============================================================================


def test_get_user_permission_flags_found(mock_ddb_table, sample_permissions):
    """Test getting all permission flags for an existing user."""
    mock_ddb_table.put_item(Item=sample_permissions)

    flags = get_user_permission_flags("testuser")

    assert flags["can_upload"] is True
    assert flags["can_search"] is True
    assert flags["can_download"] is False


def test_get_user_permission_flags_not_found(mock_ddb_table):
    """Test getting permission flags for non-existent user returns all False."""
    flags = get_user_permission_flags("nonexistent")

    assert flags["can_upload"] is False
    assert flags["can_search"] is False
    assert flags["can_download"] is False


# =============================================================================
# Test: @permissions_required decorator
# =============================================================================


def test_permissions_required_admin_bypass(mock_ddb_table):
    """Test that @permissions_required allows admins regardless of permissions."""

    @permissions_required(["can_upload"])
    def handler(event, context, auth):
        return {"statusCode": 200, "body": "success"}

    auth = {"username": "admin", "groups": ["Admin"], "claims": {}, "token": "xxx"}
    result = handler({}, None, auth)

    assert result["statusCode"] == 200


def test_permissions_required_user_allowed(mock_ddb_table, sample_permissions):
    """Test that @permissions_required allows users with the required permission."""
    mock_ddb_table.put_item(Item=sample_permissions)

    @permissions_required(["can_upload"])
    def handler(event, context, auth):
        return {"statusCode": 200, "body": "success"}

    auth = {"username": "testuser", "groups": ["User"], "claims": {}, "token": "xxx"}
    result = handler({}, None, auth)

    assert result["statusCode"] == 200


def test_permissions_required_user_denied(mock_ddb_table, sample_permissions):
    """Test that @permissions_required denies users lacking the required permission."""
    mock_ddb_table.put_item(Item=sample_permissions)

    @permissions_required(["can_download"])  # testuser has can_download = False
    def handler(event, context, auth):
        return {"statusCode": 200, "body": "success"}

    auth = {"username": "testuser", "groups": ["User"], "claims": {}, "token": "xxx"}
    result = handler({}, None, auth)

    assert result["statusCode"] == 403
    assert "PERMISSION_DENIED" in result["body"]


def test_permissions_required_multiple_permissions(mock_ddb_table, sample_permissions):
    """Test @permissions_required with multiple required permissions."""
    mock_ddb_table.put_item(Item=sample_permissions)

    # testuser has can_upload=True, can_search=True, but can_download=False
    @permissions_required(["can_upload", "can_download"])
    def handler(event, context, auth):
        return {"statusCode": 200, "body": "success"}

    auth = {"username": "testuser", "groups": ["User"], "claims": {}, "token": "xxx"}
    result = handler({}, None, auth)

    # Should be denied because can_download is False
    assert result["statusCode"] == 403
