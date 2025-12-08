"""
POST /artifacts
Enumerate artifacts in the registry by applying one or more ArtifactQuery filters.
Supports optional pagination via the `offset` query paramete and returns a list
of ArtifactMetadata objects along with a next-page offset.

Each query may specify fields such as name or type, and the results are combined
using OR semantics.

!! OR semantics is not specifically stated in the spec, it was inferred to be the
   most practical interpretation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.utils.http import (
    LambdaResponse,
    json_response,
    error_response,
    translate_exceptions,
)
from src.artifacts.artifactory import (
    load_all_artifacts,
    load_all_artifacts_by_fields,
)
from src.artifacts.base_artifact import BaseArtifact


# =============================================================================
# Helper: Validate request body
# =============================================================================


def _parse_artifact_queries(body: Any) -> List[Dict[str, Any]]:
    """
    Validate that the request body is a JSON array of ArtifactQuery objects.
    """
    if not isinstance(body, list):
        raise ValueError("Request body must be an array of ArtifactQuery objects.")

    for i, q in enumerate(body):
        if not isinstance(q, dict):
            raise ValueError(f"ArtifactQuery at index {i} must be an object.")
        if "name" not in q and "type" not in q:
            raise ValueError(
                f"ArtifactQuery at index {i} must include at least 'name' or 'type'."
            )

    return body


# =============================================================================
# Artifact Filtering Logic
# =============================================================================


def _filter_artifacts(
    all_artifacts: List[BaseArtifact],
    queries: List[Dict[str, Any]],
) -> List[BaseArtifact]:
    """
    Apply ArtifactQuery filters using existing helpers.

    OR semantics:
        - If multiple queries are provided, results are unioned.
    """
    results: List[BaseArtifact] = []

    for q in queries:
        name = q.get("name")
        artifact_type = q.get("type")

        fields: Dict[str, Any] = {}
        if name:
            fields["name"] = name

        # load_all_artifacts_by_fields supports:
        #   - optional artifact type
        #   - searching within an existing artifact list
        matched = load_all_artifacts_by_fields(
            fields=fields,
            artifact_type=artifact_type,
            artifact_list=all_artifacts,
        )

        results.extend(matched)

    # Deduplicate by artifact_id
    seen = set()
    unique: List[BaseArtifact] = []
    for a in results:
        if a.artifact_id not in seen:
            unique.append(a)
            seen.add(a.artifact_id)

    return unique


# =============================================================================
# Pagination
# =============================================================================


def _paginate(
    items: List[Any],
    offset: int | None,
    page_size: int = 50,
) -> Tuple[List[Any], int | None]:
    """
    Simple pagination helper.

    offset:
        - None → start at 0
        - number → index to start reading from

    Returns:
        sliced_items, next_offset
    """
    start = offset or 0
    end = start + page_size

    sliced = items[start:end]
    next_offset = end if end < len(items) else None

    return sliced, next_offset


# =============================================================================
# Lambda Handler: POST /artifacts
# =============================================================================
#
# Responsibilities:
#   1. Authenticate user
#   2. Parse & validate ArtifactQuery array
#   3. Parse pagination parameters (offset)
#   4. Query DynamoDB for matching artifacts
#   5. Return ArtifactMetadata list + pagination header
#
# Error codes:
#   400 - malformed request body or invalid offset
#   403 - auth failure (handled by @auth_required)
#   500 - catchall (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
) -> LambdaResponse:
    logger.info("[post_artifacts] Handling artifact enumeration request")

    # ---------------------------------------------------------------------
    # Step 1 - Parse offset query parameter
    # ---------------------------------------------------------------------
    query_params = event.get("queryStringParameters") or {}
    raw_offset = query_params.get("offset")

    if raw_offset is not None:
        try:
            offset = int(raw_offset)
        except ValueError:
            return error_response(
                400,
                f"Invalid offset value '{raw_offset}'",
                error_code="INVALID_OFFSET",
            )
    else:
        offset = None

    logger.debug(f"[post_artifacts] offset={offset}")

    # ---------------------------------------------------------------------
    # Step 2 - Parse and validate request body
    # ---------------------------------------------------------------------
    raw_body = event.get("body")

    if isinstance(raw_body, str):
        import json

        try:
            body = json.loads(raw_body)
        except Exception:
            return error_response(
                400,
                "Request body must be valid JSON.",
                error_code="INVALID_JSON",
            )
    else:
        body = raw_body

    # ---------------------------------------------------------------------
    # Step 3 - Load all artifacts from DynamoDB
    # ---------------------------------------------------------------------
    try:
        all_artifacts = load_all_artifacts()
        if all_artifacts is None:
            all_artifacts = []
    except Exception as e:
        logger.error(f"[post_artifacts] Failed to load artifact list: {e}")
        return error_response(
            500,
            "Failed to load artifacts",
            error_code="DYNAMO_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 4 - Apply ArtifactQuery filters
    # ---------------------------------------------------------------------
    filtered = _filter_artifacts(all_artifacts, body)

    # ---------------------------------------------------------------------
    # Step 5 - Apply pagination
    # ---------------------------------------------------------------------
    page, next_offset = _paginate(filtered, offset)

    # Convert artifacts to ArtifactMetadata entries
    response_items: List[Dict[str, Any]] = [
        {
            "name": a.name,
            "id": a.artifact_id,
            "type": a.artifact_type,
        }
        for a in page
    ]

    headers = {"offset": str(next_offset) if next_offset is not None else "null"}

    # IMPORTANT: json_response only accepts dict | str | bool as body → wrap list
    response = json_response(
        200,
        response_items,
        headers=headers,
    )

    logger.info(f"Returning: {response}")
    return response
