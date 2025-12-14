"""
Conftest for lambda tests - provides fixtures for mocking AWS clients and auth.
"""

from unittest.mock import MagicMock

import pytest


# ====================================================================================
# FIXTURE: Patch boto3 clients for each test
# ====================================================================================
@pytest.fixture(autouse=True)
def mock_boto_clients(mocker):
    """Patch boto3 resource and client to prevent AWS calls during tests."""
    mock_ddb = mocker.patch("boto3.resource")
    mock_cognito = mocker.patch("boto3.client")

    # Fake DynamoDB table
    fake_table = MagicMock()
    mock_ddb.return_value.Table.return_value = fake_table

    return {
        "ddb": mock_ddb,
        "table": fake_table,
        "cognito": mock_cognito,
    }


# ====================================================================================
# FIXTURE: Mock authorize function for authenticated endpoints
# ====================================================================================
@pytest.fixture
def mock_authorize(mocker):
    """
    Convenience fixture to mock the authorize function.
    Usage:
        def test_something(mock_authorize):
            mock_authorize.return_value = {"username": "test", "groups": ["User"]}
    """
    return mocker.patch("src.auth.authorize")
