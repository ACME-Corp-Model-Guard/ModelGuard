"""
GET /artifact/byName/{name}
Look up all artifacts by name and return an array of ArtifactMetadata entries.
"""

from __future__ import annotations

from typing import Any, Dict

from src.artifacts.artifactory import load_all_artifacts_by_fields
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)

# =============================================================================
# Lambda Handler: GET /artifact/byName/{name}
# =============================================================================
#
# Responsibilities:
#   1. Authenticate caller
#   2. Look up all artifacts by name via table scan
#   3. Return array of ArtifactMetadata per OpenAPI spec
#
# Error codes:
#   400 - missing name parameter
#   403 - auth failure (handled by @auth_required)
#   404 - no artifacts found
#   500 - unexpected errors (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    logger.info("[get_artifact_by_name] Handling artifact lookup")

    # ------------------------------------------------------------------
    # Step 1 - Extract name parameter
    # ------------------------------------------------------------------
    path_params = event.get("pathParameters") or {}
    name = path_params.get("name")

    if not name:
        return error_response(
            400,
            "Missing required path parameter: name",
            error_code="INVALID_REQUEST",
        )

    logger.debug(f"[get_artifact_by_name] Searching for artifact with name={name}")

    # ------------------------------------------------------------------
    # Step 2 - Scan DynamoDB for all artifacts with this name
    # ------------------------------------------------------------------
    artifacts = load_all_artifacts_by_fields(fields={"name": name})

    if not artifacts:
        return error_response(
            404,
            f"Artifact with name '{name}' does not exist",
            error_code="NOT_FOUND",
        )

    logger.info(
        f"[get_artifact_by_name] Found {len(artifacts)} artifact(s) with name={name}"
    )

    # ------------------------------------------------------------------
    # Step 3 - Build array of ArtifactMetadata per OpenAPI spec
    # ------------------------------------------------------------------
    response_body = [
        {
            "name": artifact.name,
            "id": artifact.artifact_id,
            "type": artifact.artifact_type,
        }
        for artifact in artifacts
    ]

    return json_response(200, response_body)
