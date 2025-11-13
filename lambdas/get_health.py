import json
from datetime import datetime, timezone


def lambda_handler(event, context):
    """
    Lambda handler for the /health endpoint.

    Returns a lightweight heartbeat/liveness response.
    """
    # Generate Current UTC Timestamp
    now_utc = datetime.now(timezone.utc).isoformat()

    # Response Payload
    body = {
        "status": "ok",
        "checked_at": now_utc,
        "message": "Registry API is reachable"
    }

    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }

    return response
