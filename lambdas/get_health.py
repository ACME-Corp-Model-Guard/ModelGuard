import json
from datetime import datetime, timezone
from typing import Any, Dict

<<<<<<< HEAD
=======
from src.logger import with_logging
from src.utils.http import LambdaResponse, json_response, translate_exceptions
>>>>>>> main

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for the /health endpoint.

    Returns a lightweight heartbeat/liveness response.
    """
<<<<<<< HEAD
    # Generate Current UTC Timestamp
    now_utc = datetime.now(timezone.utc).isoformat()

    # Response Payload
=======
    # ---------------------------------------------------------------------
    # Step 1 — Get the current datetime
    # ---------------------------------------------------------------------
    now_utc = datetime.now(timezone.utc).isoformat()

    # ---------------------------------------------------------------------
    # Step 2 — Construct the response
    # ---------------------------------------------------------------------
>>>>>>> main
    body = {
        "status": "ok",
        "checked_at": now_utc,
        "message": "Registry API is reachable",
    }

    # Construct Response
    response = {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

    return response
