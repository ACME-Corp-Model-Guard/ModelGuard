"""
Replay attack prevention using request fingerprinting.

This module provides transparent replay detection by generating SHA-256 hashes
of request components (token, method, path, body) and tracking them in DynamoDB
with a 5-second TTL. Replayed requests within the time window are rejected.

Completely transparent to clients - no new headers or API changes required.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from src.aws.clients import get_ddb_table
from src.logutil import clogger
from src.settings import FINGERPRINTS_TABLE

# ==============================================================================
# Configuration
# ==============================================================================

REPLAY_WINDOW_SECONDS = 5


# ==============================================================================
# Fingerprint Calculation
# ==============================================================================


def calculate_request_fingerprint(
    token: str,
    http_method: str,
    resource_path: str,
    request_body: Optional[str],
) -> str:
    """
    Generate deterministic SHA-256 hash of request components.

    Components (in order):
      1. Bearer token (full JWT)
      2. HTTP method (GET, POST, PUT, DELETE)
      3. Resource path (e.g., /artifact/model/123)
      4. Request body (empty string if None/empty)

    Args:
        token: JWT bearer token
        http_method: HTTP method (GET, POST, PUT, DELETE)
        resource_path: API resource path
        request_body: JSON request body (or None for GET requests)

    Returns:
        64-character hexadecimal SHA-256 digest

    Example:
        >>> calculate_request_fingerprint(
        ...     "eyJ0eXAi...",
        ...     "POST",
        ...     "/artifact/model",
        ...     '{"url":"https://example.com"}'
        ... )
        'a1b2c3d4e5f6789...'
    """
    # Normalize body (handle None, empty string, whitespace)
    normalized_body = (request_body or "").strip()

    # Concatenate components in fixed order
    combined = f"{token}|{http_method}|{resource_path}|{normalized_body}"

    # SHA-256 hash
    fingerprint = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    clogger.debug(f"[replay] Calculated fingerprint: {fingerprint[:16]}...")
    return fingerprint


# ==============================================================================
# Resource Path Extraction
# ==============================================================================


def extract_resource_path(event: Dict[str, Any]) -> str:
    """
    Extract the resource path from API Gateway Lambda event.

    Tries in order:
      1. event["path"] (actual path with real IDs, e.g., /artifacts/model/abc-123)
      2. event["requestContext"]["resourcePath"] (template path, e.g., /artifacts/{type}/{id})
      3. Default to "/"

    We prioritize the actual path over the template path because fingerprints
    must be unique per-request. Using the template path would cause all requests
    to the same endpoint (e.g., different artifact IDs) to have identical
    fingerprints, resulting in false "replay attack" detections.

    Args:
        event: Lambda event from API Gateway

    Returns:
        Resource path string

    Example paths:
        /artifact/model (actual)
        /artifacts/model/abc-123 (actual)
        /artifact/model/abc-123/rate (actual)
    """
    # Method 1: Actual path with real IDs (preferred for unique fingerprints)
    if "path" in event and event["path"]:
        return event["path"]

    # Method 2: Template path from requestContext (fallback)
    request_context = event.get("requestContext") or {}
    resource_path = request_context.get("resourcePath")
    if resource_path:
        return resource_path

    # Method 3: Fallback to "/" if nothing found
    clogger.debug("[replay] Could not extract resource path from event")
    return "/"


# ==============================================================================
# Replay Detection Check
# ==============================================================================


def is_request_replayed(
    token: str,
    http_method: str,
    resource_path: str,
    request_body: Optional[str],
) -> bool:
    """
    Check if this request fingerprint has been seen within the replay window.

    Queries DynamoDB FingerprintsTable for the calculated fingerprint.
    If found, the request is a replay within the time window.

    Args:
        token: JWT bearer token
        http_method: HTTP method (GET, POST, PUT, DELETE)
        resource_path: API resource path
        request_body: JSON request body (or None)

    Returns:
        True if replayed (fingerprint exists in DynamoDB)
        False if new request

    Raises:
        Exception on DynamoDB errors (logged and re-raised)
    """
    fingerprint = calculate_request_fingerprint(token, http_method, resource_path, request_body)

    try:
        table = get_ddb_table(FINGERPRINTS_TABLE)
        response = table.get_item(Key={"fingerprint": fingerprint})

        if "Item" in response:
            clogger.warning(
                f"[replay] REPLAY DETECTED: fingerprint={fingerprint[:16]}... "
                f"token={token[:20]}... method={http_method} path={resource_path}"
            )
            return True

        return False

    except ClientError as e:
        clogger.error(f"[replay] DynamoDB check failed: {e}")
        raise


# ==============================================================================
# Fingerprint Recording
# ==============================================================================


def record_request_fingerprint(
    token: str,
    http_method: str,
    resource_path: str,
    request_body: Optional[str],
) -> None:
    """
    Record fingerprint in DynamoDB with TTL for replay window.

    Stores the following fields:
      - fingerprint: SHA-256 hash (Primary Key)
      - timestamp: Current Unix epoch
      - ttl_expiry: Current time + REPLAY_WINDOW_SECONDS (DynamoDB auto-deletes)
      - token_partial: First 16 chars of token (for audit logs)
      - method: HTTP method (for audit logs)
      - path: Resource path (for audit logs)

    Failure is non-blocking: If recording fails, request still succeeds.
    Recording is defensive, not protective.

    Args:
        token: JWT bearer token
        http_method: HTTP method (GET, POST, PUT, DELETE)
        resource_path: API resource path
        request_body: JSON request body (or None)
    """
    fingerprint = calculate_request_fingerprint(token, http_method, resource_path, request_body)

    current_time = int(time.time())
    ttl_expiry = current_time + REPLAY_WINDOW_SECONDS

    try:
        table = get_ddb_table(FINGERPRINTS_TABLE)
        table.put_item(
            Item={
                "fingerprint": fingerprint,
                "timestamp": current_time,
                "ttl_expiry": ttl_expiry,
                "token_partial": token[:16],
                "method": http_method,
                "path": resource_path,
            }
        )
        clogger.debug(
            f"[replay] Recorded fingerprint: {fingerprint[:16]}... " f"expires_at={ttl_expiry}"
        )
    except Exception as e:
        clogger.error(f"[replay] Failed to record fingerprint: {e}")
        # Do NOT raise: recording is defensive, not required for request success
