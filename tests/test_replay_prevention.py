"""
Comprehensive tests for replay attack prevention.

Test coverage:
- Fingerprint calculation (deterministic, idempotent)
- Replay detection (within/outside 5s window)
- Recording and cleanup via DynamoDB TTL
- Edge cases (empty body, same token different paths, etc.)
"""

import os
import time
from unittest.mock import patch

import boto3
from moto import mock_aws

from src.replay_prevention import (
    calculate_request_fingerprint,
    extract_resource_path,
    is_request_replayed,
    record_request_fingerprint,
)


# =============================================================================
# Fingerprint Calculation Tests
# =============================================================================


def test_fingerprint_deterministic():
    """Same inputs always produce same fingerprint."""
    token = "eyJhbGc..."
    method = "POST"
    path = "/artifact/model"
    body = '{"url":"https://example.com"}'

    fp1 = calculate_request_fingerprint(token, method, path, body)
    fp2 = calculate_request_fingerprint(token, method, path, body)

    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex is 64 chars


def test_fingerprint_changes_with_token():
    """Different tokens produce different fingerprints."""
    method = "POST"
    path = "/artifact/model"
    body = '{"url":"https://example.com"}'

    fp1 = calculate_request_fingerprint("token1", method, path, body)
    fp2 = calculate_request_fingerprint("token2", method, path, body)

    assert fp1 != fp2


def test_fingerprint_changes_with_method():
    """Different HTTP methods produce different fingerprints."""
    token = "abc"
    path = "/artifact/model"
    body = "{}"

    fp_get = calculate_request_fingerprint(token, "GET", path, body)
    fp_post = calculate_request_fingerprint(token, "POST", path, body)

    assert fp_get != fp_post


def test_fingerprint_changes_with_path():
    """Different resource paths produce different fingerprints."""
    token = "abc"
    method = "GET"
    body = ""

    fp1 = calculate_request_fingerprint(token, method, "/artifact/model/123", body)
    fp2 = calculate_request_fingerprint(token, method, "/artifact/dataset/456", body)

    assert fp1 != fp2


def test_fingerprint_changes_with_body():
    """Different request bodies produce different fingerprints."""
    token = "abc"
    method = "POST"
    path = "/artifact/model"

    fp1 = calculate_request_fingerprint(token, method, path, '{"url":"a"}')
    fp2 = calculate_request_fingerprint(token, method, path, '{"url":"b"}')

    assert fp1 != fp2


def test_fingerprint_empty_body_normalization():
    """None, empty string, and whitespace all normalize to empty."""
    token = "abc"
    method = "GET"
    path = "/health"

    fp_none = calculate_request_fingerprint(token, method, path, None)
    fp_empty = calculate_request_fingerprint(token, method, path, "")
    fp_whitespace = calculate_request_fingerprint(token, method, path, "   ")

    assert fp_none == fp_empty == fp_whitespace


# =============================================================================
# Resource Path Extraction Tests
# =============================================================================


def test_extract_resource_path_prefers_actual_path():
    """Prefer actual path over template resourcePath for unique fingerprints."""
    event = {
        "requestContext": {"resourcePath": "/artifact/{artifact_type}"},
        "path": "/artifact/model",  # Should be used (actual path with real values)
    }

    path = extract_resource_path(event)
    assert path == "/artifact/model"


def test_extract_resource_path_uses_path_when_no_template():
    """Uses path field when resourcePath is empty."""
    event = {
        "path": "/artifacts",
        "requestContext": {},
    }

    path = extract_resource_path(event)
    assert path == "/artifacts"


def test_extract_resource_path_fallback_to_template():
    """Falls back to template resourcePath when path is missing."""
    event = {
        "requestContext": {"resourcePath": "/artifacts/{artifact_type}/{id}"},
        # No "path" field
    }

    path = extract_resource_path(event)
    assert path == "/artifacts/{artifact_type}/{id}"


def test_extract_resource_path_default():
    """Default to / if nothing available."""
    event = {"requestContext": {}}

    path = extract_resource_path(event)
    assert path == "/"


# =============================================================================
# Replay Detection Tests (with DynamoDB)
# =============================================================================


@mock_aws
def test_replay_detection_first_request():
    """First request should not be detected as replayed."""
    # Create test table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.create_table(
        TableName=os.environ["FINGERPRINTS_TABLE"],
        KeySchema=[{"AttributeName": "fingerprint", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "fingerprint", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Reset cached DDB resource inside clients.py
    from src.aws import clients

    clients._dynamodb_resource = None

    # Patch get_ddb_table where it's used (in replay_prevention module)
    with (
        patch("src.replay_prevention.get_ddb_table", return_value=table),
        patch("src.aws.clients.get_dynamodb", return_value=dynamodb),
    ):
        is_replay = is_request_replayed(
            token="token1",
            http_method="POST",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

    assert is_replay is False


@mock_aws
def test_replay_detection_immediate_retry():
    """Immediate retry should be detected as replayed."""

    # Create the moto DynamoDB resource + table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.create_table(
        TableName=os.environ["FINGERPRINTS_TABLE"],
        KeySchema=[{"AttributeName": "fingerprint", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "fingerprint", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Reset cached DDB resource inside clients.py
    from src.aws import clients

    clients._dynamodb_resource = None

    with (
        patch("src.replay_prevention.get_ddb_table", return_value=table),
        patch("src.aws.clients.get_dynamodb", return_value=dynamodb),
    ):
        record_request_fingerprint(
            token="token1",
            http_method="POST",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

        is_replay = is_request_replayed(
            token="token1",
            http_method="POST",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

    assert is_replay is True


@mock_aws
def test_replay_detection_different_token():
    """Different tokens should not be detected as replayed."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.create_table(
        TableName=os.environ["FINGERPRINTS_TABLE"],
        KeySchema=[{"AttributeName": "fingerprint", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "fingerprint", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Reset cached DynamoDB so replay_prevention binds to Moto
    from src.aws import clients

    clients._dynamodb_resource = None

    with (
        patch("src.replay_prevention.get_ddb_table", return_value=table),
        patch("src.aws.clients.get_dynamodb", return_value=dynamodb),
    ):
        # First request with token1
        record_request_fingerprint(
            token="token1",
            http_method="POST",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

        # Different token should *not* be replay
        is_replay = is_request_replayed(
            token="token2",
            http_method="POST",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

    assert is_replay is False


@mock_aws
def test_replay_detection_different_path():
    """Same token but different path should not be replayed."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.create_table(
        TableName=os.environ["FINGERPRINTS_TABLE"],
        KeySchema=[{"AttributeName": "fingerprint", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "fingerprint", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    from src.aws import clients

    clients._dynamodb_resource = None

    with (
        patch("src.replay_prevention.get_ddb_table", return_value=table),
        patch("src.aws.clients.get_dynamodb", return_value=dynamodb),
    ):
        # Request A
        record_request_fingerprint(
            token="token1",
            http_method="GET",
            resource_path="/artifact/model/123",
            request_body="",
        )

        # Different path should not be replay
        is_replay = is_request_replayed(
            token="token1",
            http_method="GET",
            resource_path="/artifact/dataset/456",
            request_body="",
        )

    assert is_replay is False


@mock_aws
def test_replay_detection_different_method():
    """Same token and path but different HTTP method should not be replayed."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.create_table(
        TableName=os.environ["FINGERPRINTS_TABLE"],
        KeySchema=[{"AttributeName": "fingerprint", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "fingerprint", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    from src.aws import clients

    clients._dynamodb_resource = None

    with (
        patch("src.replay_prevention.get_ddb_table", return_value=table),
        patch("src.aws.clients.get_dynamodb", return_value=dynamodb),
    ):
        # POST request
        record_request_fingerprint(
            token="token1",
            http_method="POST",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

        # GET should *not* be replay
        is_replay = is_request_replayed(
            token="token1",
            http_method="GET",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

    assert is_replay is False


# =============================================================================
# Recording and TTL Tests
# =============================================================================


@mock_aws
def test_fingerprint_recording_sets_ttl():
    """Recording should set TTL for automatic cleanup."""

    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.create_table(
        TableName=os.environ["FINGERPRINTS_TABLE"],
        KeySchema=[{"AttributeName": "fingerprint", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "fingerprint", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Reset cached resource
    from src.aws import clients

    clients._dynamodb_resource = None

    with (
        patch("src.replay_prevention.get_ddb_table", return_value=table),
        patch("src.aws.clients.get_dynamodb", return_value=dynamodb),
    ):
        record_request_fingerprint(
            token="token1",
            http_method="POST",
            resource_path="/artifact/model",
            request_body='{"url":"example.com"}',
        )

    items = table.scan()["Items"]
    assert len(items) == 1

    ttl = items[0]["ttl_expiry"]
    now = int(time.time())
    assert now + 4 <= ttl <= now + 6


@mock_aws
def test_fingerprint_recording_preserves_metadata():
    """Recording should preserve token, method, path for audit."""

    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.create_table(
        TableName=os.environ["FINGERPRINTS_TABLE"],
        KeySchema=[{"AttributeName": "fingerprint", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "fingerprint", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Reset cached resource
    from src.aws import clients

    clients._dynamodb_resource = None

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

    with (
        patch("src.replay_prevention.get_ddb_table", return_value=table),
        patch("src.aws.clients.get_dynamodb", return_value=dynamodb),
    ):
        record_request_fingerprint(
            token=token,
            http_method="PUT",
            resource_path="/artifacts/model/abc123",
            request_body='{"version":2}',
        )

    items = table.scan()["Items"]
    assert len(items) == 1

    item = items[0]
    assert item["token_partial"] == token[:16]
    assert item["method"] == "PUT"
    assert item["path"] == "/artifacts/model/abc123"
