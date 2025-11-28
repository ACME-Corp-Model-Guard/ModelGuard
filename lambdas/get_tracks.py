from __future__ import annotations

from typing import Any, Dict

from src.logger import logger, with_logging
from src.utils.http import LambdaResponse, json_response, translate_exceptions

# ============================================================================
# /tracks  —  Return supported extended track(s)
#
# OpenAPI spec requires this endpoint and expects:
#   200 OK
#   { "tracks": [ "security" ] }
#
# Your team selected the Security Track, so we return exactly that.
# ============================================================================

SUPPORTED_TRACKS = ["security"]


@with_logging
@translate_exceptions
def handler(event: Dict[str, Any], context: Any) -> LambdaResponse:
    """
    Lambda handler for GET /tracks

    Returns the list of extended tracks supported by this deployment.
    This endpoint is required by the OpenAPI v3.4.6 specification.

    Response:
        200 OK
        {
            "tracks": ["security"]
        }
    """
    logger.debug(f"[tracks] Incoming event: {event}")

    return json_response(status_code=200, body={"tracks": SUPPORTED_TRACKS})
