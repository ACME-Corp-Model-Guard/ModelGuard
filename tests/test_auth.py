import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws


# ====================================================================================
# FIXTURE: Patch JWKS loading BEFORE import
# ====================================================================================
@pytest.fixture(autouse=True)
def mock_jwks(mocker):
    # Patch urllib3.PoolManager.request before auth.py import occurs
    mock_req = mocker.patch(
        "urllib3.PoolManager.request",
        return_value=SimpleNamespace(json=lambda: {"keys": [{"kid": "testkid"}]}),
    )
    return mock_req


# ====================================================================================
# FIXTURE: Patch boto3 clients before import
# ====================================================================================
@pytest.fixture(autouse=True)
def mock_boto_clients(mocker):
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
# IMPORT MODULE UNDER TEST *after* mocks
# ====================================================================================
@pytest.fixture
def auth_module(mock_jwks, mock_boto_clients):
    # Reload both modules to ensure clean state
    if "src.replay_prevention" in sys.modules:
        del sys.modules["src.replay_prevention"]
    if "src.auth" in sys.modules:
        del sys.modules["src.auth"]
    import src.auth as auth

    return auth


# ====================================================================================
# authenticate_user
# ====================================================================================
def test_authenticate_user_success(auth_module, mock_boto_clients):
    fake_auth_result = {
        "AuthenticationResult": {
            "AccessToken": "foo",
            "IdToken": "id",
            "RefreshToken": "ref",
            "ExpiresIn": 3600,
        }
    }

    mock_boto_clients["cognito"].return_value.initiate_auth.return_value = (
        fake_auth_result
    )

    result = auth_module.authenticate_user("alice", "pw")

    assert result["access_token"] == "foo"
    mock_boto_clients["table"].put_item.assert_called_once()


def test_authenticate_user_cognito_failure(auth_module, mock_boto_clients):
    mock_boto_clients["cognito"].return_value.initiate_auth.side_effect = Exception(
        "boom"
    )

    with pytest.raises(Exception):
        auth_module.authenticate_user("bob", "badpw")


# ====================================================================================
# verify_token tests
# ====================================================================================
def test_verify_token_invalid_kid(auth_module, mocker):
    # Patch jwt.get_unverified_header so kid mismatch occurs
    mocker.patch("src.auth.jwt.get_unverified_header", return_value={"kid": "wrong"})
    with pytest.raises(Exception):
        auth_module.verify_token("abc.def.ghi")


def test_verify_token_signature_fail(auth_module, mocker):
    mocker.patch("src.auth.jwt.get_unverified_header", return_value={"kid": "testkid"})
    mocker.patch(
        "src.auth.jwt.get_unverified_claims", return_value={"exp": time.time() + 1000}
    )
    mocker.patch("src.auth.jwk.construct").return_value.verify.return_value = False

    with pytest.raises(Exception):
        auth_module.verify_token("abc.def.ghi")


@mock_aws
def test_verify_token_expired_jwt(auth_module, mocker):
    # Setup minimal table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=os.environ["TOKENS_TABLE"],
        KeySchema=[{"AttributeName": "token", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "token", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.put_item(
        Item={"token": "abc", "username": "x", "issued_at": int(time.time()), "uses": 0}
    )

    mocker.patch("src.auth.jwt.get_unverified_header", return_value={"kid": "testkid"})
    mocker.patch(
        "src.auth.jwt.get_unverified_claims", return_value={"exp": time.time() - 5}
    )
    mocker.patch("src.auth.jwk.construct").return_value.verify.return_value = True

    with pytest.raises(Exception):
        auth_module.verify_token("abc")


@mock_aws
def test_verify_token_usage_limit_exceeded(auth_module, mocker):
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=os.environ["TOKENS_TABLE"],
        KeySchema=[{"AttributeName": "token", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "token", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Max uses reached
    table.put_item(
        Item={
            "token": "abc",
            "username": "x",
            "issued_at": int(time.time()),
            "uses": auth_module.API_TOKEN_CALL_LIMIT,
        }
    )

    mocker.patch("src.auth.jwt.get_unverified_header", return_value={"kid": "testkid"})
    mocker.patch(
        "src.auth.jwt.get_unverified_claims", return_value={"exp": time.time() + 1000}
    )
    mocker.patch("src.auth.jwk.construct").return_value.verify.return_value = True

    with pytest.raises(Exception):
        auth_module.verify_token("abc")


# ====================================================================================
# authorize
# ====================================================================================
def test_authorize_missing_header(auth_module):
    event = {"headers": {}}
    with pytest.raises(Exception):
        auth_module.authorize(event)


def test_authorize_malformed_header(auth_module):
    event = {"headers": {"X-Authorization": "badtoken"}}
    with pytest.raises(Exception):
        auth_module.authorize(event)


def test_authorize_success(auth_module, mocker):
    mocker.patch(
        "src.auth.verify_token",
        return_value={"username": "alice", "cognito:groups": ["Admin"]},
    )

    event = {"headers": {"X-Authorization": "bearer abc"}}
    out = auth_module.authorize(event)

    assert out["username"] == "alice"
    assert out["groups"] == ["Admin"]
    assert out["token"] == "abc"


# ====================================================================================
# auth_required decorator
# ====================================================================================
def test_auth_required_success(auth_module, mocker):
    mocker.patch("src.auth.authorize", return_value={"username": "bob"})

    @auth_module.auth_required
    def handler(event, context, auth):
        return {"success": True, "auth": auth}

    res = handler({"headers": {"X-Authorization": "bearer x"}}, None)
    assert res["auth"]["username"] == "bob"


def test_auth_required_unauthorized(auth_module, mocker):
    mocker.patch("src.auth.authorize", side_effect=Exception("bad token"))

    @auth_module.auth_required
    def handler(event, context, auth):
        return {"ok": True}

    res = handler({"headers": {}}, None)
    assert res["statusCode"] == 401
    assert "Unauthorized" in res["body"]


# ====================================================================================
# roles_required decorator
# ====================================================================================
def test_roles_required_forbidden(auth_module, mocker):
    mocker.patch("src.auth.authorize", side_effect=Exception("forbidden"))

    @auth_module.roles_required(["Admin"])
    def handler(event, context, auth):
        return {"ok": True}

    res = handler({"headers": {}}, None)
    assert res["statusCode"] == 403


def test_roles_required_success(auth_module, mocker):
    mocker.patch(
        "src.auth.authorize",
        return_value={"username": "bob", "cognito:groups": ["Admin"]},
    )

    @auth_module.roles_required(["Admin"])
    def handler(event, context, auth):
        return {"ok": True, "auth": auth}

    res = handler({"headers": {"X-Authorization": "bearer x"}}, None)
    assert res["auth"]["username"] == "bob"
