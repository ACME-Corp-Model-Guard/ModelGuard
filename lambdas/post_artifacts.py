"""
POST /artifacts
Enumerate artifacts in the registry by applying one or more ArtifactQuery filters.
Supports optional pagination via the `offset` query parameter and returns a list
of ArtifactMetadata objects along with a next-page offset.

Each query may specify fields such as name or type, and the results are combined
using OR semantics.

!! OR semantics is not specifically stated in the spec, it was inferred to be the
   most practical interpretation.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from src.auth import AuthContext, auth_required
from src.logutil import clogger, log_lambda_handler
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

# Maximum number of artifacts allowed in a single query response
MAX_QUERY_RESULTS = 500


# =============================================================================
# Helper: Validate request body
# =============================================================================


def _parse_artifact_queries(body: Any) -> List[Dict[str, Any]]:
    """
    Validate that the request body is a JSON array of ArtifactQuery objects.

    Per OpenAPI spec:
    - Each query must have a "name" field (required)
    - Each query may optionally have a "types" array field
    """
    if not isinstance(body, list):
        raise ValueError("Request body must be an array of ArtifactQuery objects.")

    for i, q in enumerate(body):
        if not isinstance(q, dict):
            raise ValueError(f"ArtifactQuery at index {i} must be an object.")

        # Per spec, "name" is required (line 884)
        if "name" not in q:
            raise ValueError(f"ArtifactQuery at index {i} must include 'name' field.")

        # Validate types array if present
        if "types" in q:
            types_value = q["types"]
            if not isinstance(types_value, list):
                raise ValueError(f"ArtifactQuery at index {i}: 'types' must be an array.")
            # Validate each type value
            valid_types = {"model", "dataset", "code"}
            for t in types_value:
                if t not in valid_types:
                    raise ValueError(
                        f"ArtifactQuery at index {i}: invalid type '{t}'. "
                        f"Must be one of: {valid_types}"
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

    Special case: name="*" enumerates all artifacts (per OpenAPI spec line 133).

    OR semantics:
        - If multiple queries are provided, results are unioned.
        - If types array is provided, matches any of those types.
    """
    results: List[BaseArtifact] = []

    for q in queries:
        name = q.get("name")
        types_filter = q.get("types", [])  # Plural "types" per spec

        # Special case: "*" means enumerate all artifacts
        if name == "*":
            # If types filter is specified, filter by those types
            if types_filter:
                for artifact_type in types_filter:
                    matched = [a for a in all_artifacts if a.artifact_type == artifact_type]
                    results.extend(matched)
            else:
                # No type filter: return all artifacts
                results.extend(all_artifacts)
        else:
            # Normal name-based filtering
            fields: Dict[str, Any] = {}
            if name:
                fields["name"] = name

            # If types filter provided, query each type separately
            if types_filter:
                for artifact_type in types_filter:
                    matched = load_all_artifacts_by_fields(
                        fields=fields,
                        artifact_type=artifact_type,
                        artifact_list=all_artifacts,
                    )
                    results.extend(matched)
            else:
                # No type filter: search across all types
                matched = load_all_artifacts_by_fields(
                    fields=fields,
                    artifact_type=None,
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
@log_lambda_handler("POST /artifacts", log_request_body=True)
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
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

    # ---------------------------------------------------------------------
    # Step 2 - Parse and validate request body
    # ---------------------------------------------------------------------
    raw_body = event.get("body")

    if isinstance(raw_body, str):
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

    try:
        artifact_queries = _parse_artifact_queries(body)
    except ValueError as e:
        return error_response(
            400,
            str(e),
            error_code="INVALID_REQUEST_BODY",
        )

    # ---------------------------------------------------------------------
    # Step 3 - Load all artifacts from DynamoDB
    # ---------------------------------------------------------------------
    try:
        all_artifacts = load_all_artifacts()
    except Exception as e:
        clogger.exception(
            "Failed to load artifact list",
            extra={"error_type": type(e).__name__},
        )
        return error_response(
            500,
            "Failed to load artifacts",
            error_code="DYNAMO_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 4 - Apply ArtifactQuery filters
    # ---------------------------------------------------------------------
    filtered = _filter_artifacts(all_artifacts, artifact_queries)

    # ---------------------------------------------------------------------
    # Step 4.1 - Check for too many results (413 Payload Too Large)
    # ---------------------------------------------------------------------
    if len(filtered) > MAX_QUERY_RESULTS:
        clogger.warning(
            f"[post_artifacts] Query returned {len(filtered)} artifacts, "
            f"exceeds maximum of {MAX_QUERY_RESULTS}"
        )
        return error_response(
            413,
            f"Query returned {len(filtered)} artifacts, "
            f"exceeds maximum of {MAX_QUERY_RESULTS}. Use more specific filters.",
            error_code="TOO_MANY_RESULTS",
        )

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

    return json_response(
        200,
        response_items,
        headers=headers,
    )
