"""
GET /artifact/byName/{name}
Look up an artifact by its human-readable name and return its metadata
along with its S3 download URL.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.settings import ARTIFACTS_TABLE
from src.artifacts.artifactory import load_artifact_metadata, load_all_artifacts_by_field
from src.storage.s3_utils import generate_s3_download_url
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
#   2. Look up artifact by name via table scan
#   3. Load full artifact metadata using artifact_id
#   4. Generate presigned S3 download URL
#   5. Return Artifact response per spec
#
# Error codes:
#   400 - missing name parameter
#   403 - auth failure (handled by @auth_required)
#   404 - artifact not found
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
    # Step 2 - Scan DynamoDB for an item with this name, and get the first matching artifact
    # ------------------------------------------------------------------
    artifacts = load_all_artifacts_by_field(ARTIFACTS_TABLE, "name", name)

    if not artifacts:
        return error_response(
            404,
            f"Artifact with name '{name}' does not exist",
            error_code="NOT_FOUND",
        )

    artifact = artifacts[0]
    logger.info(f"[get_artifact_by_name] Found artifact_id={artifact.artifact_id}")

    # ------------------------------------------------------------------
    # Step 3 - Construct S3 key and presigned download URL
    # ------------------------------------------------------------------
    s3_key = artifact.s3_key

    try:
        download_url = generate_s3_download_url(artifact.artifact_id, s3_key=s3_key)
    except Exception as e:
        logger.error(
            f"[get_artifact_by_name] Failed to generate presigned URL: {e}",
            exc_info=True,
        )
        return error_response(500, "Failed to generate download URL", "S3_ERROR")

    # ------------------------------------------------------------------
    # Step 4 - Build response
    # ------------------------------------------------------------------
    response_body = {
        "metadata": {
            "name": artifact.name,
            "id": artifact.artifact_id,
            "type": artifact.artifact_type,
        },
        "data": {
            "url": artifact.source_url,
            "download_url": download_url,
        },
    }

    return json_response(200, response_body)
