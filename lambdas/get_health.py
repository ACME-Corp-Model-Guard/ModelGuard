"""
Lambda handler for GET /health
Provides a lightweight heartbeat/liveness response.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from src.logger import log_lambda_handler
from src.utils.http import LambdaResponse, json_response, translate_exceptions


@translate_exceptions
@log_lambda_handler("GET /health")
def lambda_handler(event: Dict[str, Any], context: Any) -> LambdaResponse:
    """
    Returns a standardized health/liveness response.
    """
    # ---------------------------------------------------------------------
    # Step 1 — Get the current datetime
    # ---------------------------------------------------------------------
    now_utc = datetime.now(timezone.utc).isoformat()

    # ---------------------------------------------------------------------
    # Step 2 — Construct the response
    # ---------------------------------------------------------------------
    body = {
        "status": "ok",
        "checked_at": now_utc,
        "message": "Registry API is reachable",
    }

    return json_response(200, body)
