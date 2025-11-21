"""
HTTP response utilities for Lambda functions behind API Gateway.
Provides consistent JSON responses, error formatting, and CORS headers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, TypedDict


# -----------------------------------------------------------------------------
# Typed response object for API Gateway
# -----------------------------------------------------------------------------
class LambdaResponse(TypedDict):
    statusCode: int
    headers: Dict[str, str]
    body: str


# -----------------------------------------------------------------------------
# Default CORS headers (shared by all responses)
# -----------------------------------------------------------------------------
DEFAULT_HEADERS: Dict[str, str] = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": (
        "Content-Type, X-Authorization, Authorization, X-Amz-Date, "
        "X-Api-Key, X-Amz-Security-Token"
    ),
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


# -----------------------------------------------------------------------------
# Success Response
# -----------------------------------------------------------------------------
def json_response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> LambdaResponse:
    """
    Build a standardized JSON response object for API Gateway.
    """
    combined_headers = DEFAULT_HEADERS.copy()
    if headers:
        combined_headers.update(headers)

    return LambdaResponse(
        statusCode=status_code,
        headers=combined_headers,
        body=json.dumps(body),
    )


# -----------------------------------------------------------------------------
# Error Response
# -----------------------------------------------------------------------------
def error_response(
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> LambdaResponse:
    """
    Build a standardized error JSON response.

    Example body:
    {
        "error": "Authentication failed",
        "error_code": "INVALID_TOKEN"
    }
    """
    payload: Dict[str, Any] = {"error": message}

    if error_code is not None:
        payload["error_code"] = error_code

    return json_response(
        status_code=status_code,
        body=payload,
        headers=headers,
    )
