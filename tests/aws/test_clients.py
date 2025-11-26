import pytest
from unittest.mock import MagicMock

import src.aws.clients as clients


# -------------------------------------------------------------------
# Helpers to reset module-level caches
# -------------------------------------------------------------------
def reset_caches():
    clients._dynamodb_resource = None
    clients._s3_client = None
    clients._cognito_client = None
    clients._bedrock_runtime = None


@pytest.fixture(autouse=True)
def reset_before_each_test(monkeypatch):
    reset_caches()
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    clients.AWS_REGION = "us-east-1"


# ===============================================================
# get_dynamodb()
# ===============================================================

def test_get_dynamodb_initializes_once(monkeypatch):
    mock_resource = MagicMock()
    monkeypatch.setattr(clients.boto3, "resource", lambda svc, region_name=None: mock_resource)

    r1 = clients.get_dynamodb()
    r2 = clients.get_dynamodb()

    assert r1 is mock_resource
    assert r2 is mock_resource  # cached
    assert clients._dynamodb_resource is mock_resource


def test_get_dynamodb_runtime_error(monkeypatch):
    monkeypatch.setattr(clients, "boto3", None)

    with pytest.raises(RuntimeError):
        clients.get_dynamodb()


def test_get_ddb_table_returns_table(monkeypatch):
    mock_dynamo = MagicMock()
    mock_table = MagicMock()
    mock_dynamo.Table.return_value = mock_table

    monkeypatch.setattr(clients, "get_dynamodb", lambda: mock_dynamo)

    table = clients.get_ddb_table("MyTable")

    assert table is mock_table
    mock_dynamo.Table.assert_called_once_with("MyTable")


# ===============================================================
# get_s3()
# ===============================================================

def test_get_s3_initializes_once(monkeypatch):
    mock_s3 = MagicMock()
    monkeypatch.setattr(clients.boto3, "client",
                        lambda svc, region_name=None: mock_s3)

    s1 = clients.get_s3()
    s2 = clients.get_s3()

    assert s1 is mock_s3
    assert s2 is mock_s3
    assert clients._s3_client is mock_s3


def test_get_s3_runtime_error(monkeypatch):
    monkeypatch.setattr(clients, "boto3", None)

    with pytest.raises(RuntimeError):
        clients.get_s3()


# ===============================================================
# get_cognito()
# ===============================================================

def test_get_cognito_initializes_once(monkeypatch):
    mock_cognito = MagicMock()
    monkeypatch.setattr(
        clients.boto3,
        "client",
        lambda svc, region_name=None: mock_cognito,
    )

    c1 = clients.get_cognito()
    c2 = clients.get_cognito()

    assert c1 is mock_cognito
    assert c2 is mock_cognito
    assert clients._cognito_client is mock_cognito


def test_get_cognito_runtime_error(monkeypatch):
    monkeypatch.setattr(clients, "boto3", None)

    with pytest.raises(RuntimeError):
        clients.get_cognito()


# ===============================================================
# get_bedrock_runtime()
# ===============================================================

def test_get_bedrock_runtime_initializes_once(monkeypatch):
    mock_bedrock = MagicMock()
    monkeypatch.setattr(
        clients.boto3,
        "client",
        lambda svc, region_name=None: mock_bedrock,
    )

    b1 = clients.get_bedrock_runtime("us-west-2")
    b2 = clients.get_bedrock_runtime("us-west-2")

    assert b1 is mock_bedrock
    assert b2 is mock_bedrock
    assert clients._bedrock_runtime is mock_bedrock


def test_get_bedrock_runtime_default_region(monkeypatch):
    """
    If no region passed, it should use AWS_REGION.
    """
    mock_bedrock = MagicMock()

    def fake_client(name, region_name=None):
        assert region_name == "us-east-1"
        return mock_bedrock

    monkeypatch.setattr(clients.boto3, "client", fake_client)

    result = clients.get_bedrock_runtime()
    assert result is mock_bedrock


def test_get_bedrock_runtime_runtime_error(monkeypatch):
    monkeypatch.setattr(clients, "boto3", None)

    with pytest.raises(RuntimeError):
        clients.get_bedrock_runtime()
