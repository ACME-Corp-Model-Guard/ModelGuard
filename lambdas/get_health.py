"""
Lambda handler for GET /health
Provides a lightweight heartbeat/liveness response.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from src.logger import with_logging
from src.utils.http import LambdaResponse, json_response, translate_exceptions


@with_logging
@translate_exceptions
def lambda_handler(event: Dict[str, Any], context: Any) -> LambdaResponse:
    """
    Returns a standardized health/liveness response.
    """
    now_utc = datetime.now(timezone.utc).isoformat()

    body = {
        "status": "ok",
        "checked_at": now_utc,
        "message": "Registry API is reachable",
    }

    return json_response(200, body)
