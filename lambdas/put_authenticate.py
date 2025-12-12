"""
PUT /authenticate
Create an access token for a user via Cognito authentication.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from src.logger import clogger, log_lambda_handler
from src.utils.http import (
    LambdaResponse,
    json_response,
    error_response,
    translate_exceptions,
)
from src.auth import authenticate_user


# =============================================================================
# Lambda Handler: PUT /authenticate
# =============================================================================
#
# Responsibilities:
#   1. Parse and validate AuthenticationRequest
#   2. Authenticate user via Cognito (USER_PASSWORD_AUTH)
#   3. Return spec-compliant bearer token string
#
# Error codes:
#   400 - malformed request body or missing fields
#   401 - invalid username/password
#   500 - unexpected server error (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@log_lambda_handler("PUT /authenticate", log_request_body=True)
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
) -> LambdaResponse:
    # ---------------------------------------------------------------------
    # Step 1 — Parse JSON body
    # ---------------------------------------------------------------------
    raw_body = event.get("body", "{}")
    try:
        data = json.loads(raw_body)
    except Exception:
        return error_response(
            400,
            "Malformed JSON body",
            error_code="INVALID_REQUEST",
        )

    # Request must be an object
    if not isinstance(data, dict):
        return error_response(400, "Malformed AuthenticationRequest")

    # ---------------------------------------------------------------------
    # Step 2 — Validate AuthenticationRequest fields
    # ---------------------------------------------------------------------
    user = data.get("user")
    secret = data.get("secret")

    if (
        not isinstance(user, dict)
        or not isinstance(secret, dict)
        or "name" not in user
        or "password" not in secret
    ):
        return error_response(400, "Malformed AuthenticationRequest")

    username = user.get("name")
    password = secret.get("password")

    if not username or not password:
        return error_response(400, "Missing username or password")

    # ---------------------------------------------------------------------
    # Step 3 — Authenticate via Cognito
    # ---------------------------------------------------------------------
    try:
        tokens = authenticate_user(username, password)
    except Exception as e:
        clogger.exception(
            "Authentication failed",
            extra={"username": username, "error_type": type(e).__name__},
        )
        return error_response(401, "Invalid username or password")

    access_token = tokens.get("access_token")
    if not access_token:
        clogger.error(
            "Missing access_token from Cognito response",
            extra={"username": username},
        )
        return error_response(
            500,
            "Internal Server Error",
            error_code="AUTH_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 4 — Construct spec-compliant response
    # Returned value must be a JSON *string*, not an object.
    # ---------------------------------------------------------------------
    bearer_string = f"bearer {access_token}"
    return json_response(200, bearer_string)
