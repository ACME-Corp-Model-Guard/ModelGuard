"""
Lambda function for POST /artifact/byRegEx endpoint
Search artifacts using regular expressions over artifact names and README-like metadata.

OpenAPI spec:
- Request body: ArtifactRegEx {"regex": "<pattern>"}
- Response 200: array of ArtifactMetadata objects
- 400: missing/invalid regex
- 403: auth failure (handled by auth_required)
- 404: no artifacts found
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Pattern

from src.artifacts,artifactory import load_all_artifacts
from src.artifacts.base_artifact import BaseArtifact
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions
)

# =============================================================================
# Request Parsing
# =============================================================================


def _load_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse the request body into a dictionary.

    Accepts both a JSON string (normal API Gateway) and a dict (for unit testing).
    Raises ValueError if the body cannot be parsed as JSON.
    """

    raw_body = event.get("body", {})

    # Already a dict (e.g. in tests)
    if isinstance(raw_body, dict):
        return raw_body

    if raw_body is None or raw_body == "":
        return {}

    if not isinstance(raw_body, str):
        raise ValueError("Request body must be a JSON object or JSON string.")

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Request body must be valid JSON: {exc}") from exc
    


def _parse_regex(event: Dict[str, Any]) -> Pattern[str]:
    """
    Extract and validate the 'regex' field from the request body.

    - Must be present.
    - Must be a non-empty string.
    - Must compile as avalid regular expression.
    """

    body = _load_body(event)

    pattern = body.get("regex")
    if not isinstance(pattern, str) or not pattern.strip():
        raise ValueError("Missing required field: 'regex'")
    
    try:
        compiled = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}") from exc
    return compiled


# =============================================================================
# Search logic
# =============================================================================


def _build_search_text(artifact: BaseArtifact) -> str:
    """
    Build a text blob to run the regex against.

    Always include:
    - artifact.name
    - any string-valued metadata fields (this is where README-like content or descriptions
    are likely to reside).
    """

    parts: List[str] = []

    if getattr(artifact, "name", None):
        parts.append(str(artifact.name))

    metadata = getattr(artifact, "metadata", None)
    if isinstance(metadata, dict):
        for value in metadata.values():
            parts.append(value)

    return "\n".join(parts)


def _search_artifacts(pattern: Pattern[str]) -> List[Dict[str, str]]:
    """
    Apply the regex to all artifacts and return a list of ArtifactMetadata-like 
    dicts: {"name": ..., "id": ..., "type": ...}.
    """
    artifacts = load_all_artifacts()
    logger.info (
        f"[post_search_by_regex] Loaded {len(artifacts)} artifacts for regex search"
    )

    matches: List[Dict[str, str]d] = []

    for artifact in artifacts:
        haystack = _build_search_text(artifact)
        if not haystack:
            continue

        if pattern.search(haystack):
            matches.append(
                {
                    "name": artifact.name,
                    "id": artifact.artifact.id,
                    "type": artifact.artifact_type
                }
            )
    logger.info(f"[post_search_by_regex] Found {len(matches)} matching artifacts")
    return matches


# =============================================================================
# Lambda handler: POST /artifact/byRegEx
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext
    ) -> LambdaResponse:
    """
    Stub handler for POST /artifact/byRegEx - Search by regex
    Search for artifacts using regular expression over names and READMEs

    Handle POST /artifact/byRegEx.

    On success:
    - 200 with a JSON array of ArtifactMetadata objects.

    On error:
    - 400 for bad or mission regex.
    - 404 if no artifacts match.
    - 403 / 500 handled by decorators and error_response.
    """
    logger.info("[post_search_by_regex] Handling regex search request")
    # ------------------------------------------------------------------
    # Step 1 - Parse and validate regex from body
    # ------------------------------------------------------------------
    try:
        pattern = _parse_regex(event)
    except ValueError as exc:
        logger.warning(f"[post_search_by_regex] Invalid request: {exc}")
        return error_response(
            400,
            str(exc),
            error_code="INVALID_ARTIFACT_REGEX"
        )
    
    
    # ------------------------------------------------------------------
    # Step 2 - Execute search
    # ------------------------------------------------------------------
    results = _search_artifacts(pattern)

    if not results:
        return error_response(
            404,
            "No artifact found under this regex",
            error_code="NOT_FOUND"
        )
    
    # ------------------------------------------------------------------
    # Step 3 - Build response
    # ------------------------------------------------------------------
    """
    json_response can take any JSON-serializable object, passing the list
    preserves the top-level array required by OpenAPI.
    """
    return json_response(200, results)
