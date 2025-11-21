import json
import logging
from typing import Any, Dict, TypedDict

from src.auth import authenticate_user

logger = logging.getLogger()
logger.setLevel("INFO")


class LambdaResponse(TypedDict):
    statusCode: int
    headers: Dict[str, str]
    body: str


def _response(status: int, body: Any) -> LambdaResponse:
    """Utility for building JSON responses."""
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> LambdaResponse:
    """
    /authenticate  (PUT)
    Spec compliance:
      - RequestBody must contain AuthenticationRequest:
          {
            "user": { "name": "...", "is_admin": true },
            "secret": { "password": "..." }
          }
      - Return: a JSON string: "bearer <token>"
      - 400 on malformed request
      - 401 on invalid credentials
      - 501 if auth disabled (not the case here)
    """

    try:
        raw_body = event.get("body", "{}")
        data = json.loads(raw_body)

        # Validate request schema
        if (
            "user" not in data
            or "secret" not in data
            or "name" not in data["user"]
            or "password" not in data["secret"]
        ):
            return _response(400, "Malformed AuthenticationRequest")

        username = data["user"]["name"]
        password = data["secret"]["password"]

        if not username or not password:
            return _response(400, "Missing username or password")

        # Authenticate via Cognito
        try:
            tokens = authenticate_user(username, password)
        except Exception:
            # Cognito rejected user/password
            return _response(401, "Invalid username or password")

        # Extract access token for spec
        access_token = tokens["access_token"]

        # Return response
        bearer_string = f"bearer {access_token}"
        return _response(200, bearer_string)

    except Exception as e:
        logger.error(f"Unexpected error in /authenticate: {e}", exc_info=True)
        return _response(500, "Internal Server Error")
