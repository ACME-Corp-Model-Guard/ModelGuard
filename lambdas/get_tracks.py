"""
GET /tracks
Return the list of extended track(s) supported by this deployment.
"""

from __future__ import annotations

from typing import Any, Dict

from src.logger import logger, with_logging
from src.utils.http import LambdaResponse, json_response, translate_exceptions

# Supported track(s) for this system.
# Must use exact enum values from OpenAPI spec v3.4.7
SUPPORTED_TRACKS = ["Access control track"]


# =============================================================================
# Lambda Handler: GET /tracks
# =============================================================================
#
# Responsibilities:
#   1. Return the list of extended tracks (Security, Performance, High-Assurance)
#   2. Comply with the OpenAPI v3.4.6 specification
#
# Error codes:
#   None defined — this endpoint always returns 200 OK
#   500 handled by @translate_exceptions
# =============================================================================


@translate_exceptions
@with_logging
def lambda_handler(event: Dict[str, Any], context: Any) -> LambdaResponse:
    logger.info("[tracks] Handling tracks listing request")

    # ---------------------------------------------------------------------
    # Step 1 - Log incoming request (useful for debugging)
    # ---------------------------------------------------------------------
    logger.debug(f"[tracks] Incoming event: {event}")

    # ---------------------------------------------------------------------
    # Step 2 - Build response body (OpenAPI spec requires "plannedTracks" key)
    # ---------------------------------------------------------------------
    response_body = {"plannedTracks": SUPPORTED_TRACKS}

    # ---------------------------------------------------------------------
    # Step 3 - Return 200 with supported tracks list
    # ---------------------------------------------------------------------
    return json_response(200, response_body)
