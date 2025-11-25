"""
GET /artifacts/{artifact_type}/{id}
Retrieve an artifact's metadata and return a presigned S3 URL for downloading
the stored artifact bundle.
"""

from __future__ import annotations

from typing import Any, Dict, cast

from src.artifacts.types import ArtifactType
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.artifacts.artifactory import load_artifact_metadata
from src.storage.s3_utils import generate_s3_download_url
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


# =============================================================================
# Lambda Handler: GET /artifacts/{artifact_type}/{id}
# =============================================================================
#
# Responsibilities:
#   1. Authenticate user
#   2. Validate path parameters
#   3. Fetch artifact metadata from DynamoDB
#   4. Generate presigned S3 download URL
#   5. Return Artifact response per spec
#
# Error codes:
#   400 - invalid artifact_type or id missing/malformed
#   403 - auth failure (handled by @auth_required)
#   404 - artifact not found
#   500 - catchall (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    logger.info("[get_artifact] Handling artifact retrieval request")

    # ---------------------------------------------------------------------
    # Step 1 - Extract path parameters
    # ---------------------------------------------------------------------
    path_params = event.get("pathParameters") or {}
    artifact_type = path_params.get("artifact_type")
    artifact_id = path_params.get("id")

    if not artifact_type or not artifact_id:
        return error_response(
            400,
            "Missing required path parameters: artifact_type or id",
            error_code="INVALID_REQUEST",
        )

    # ---------------------------------------------------------------------
    # Step 2 - Validate artifact_type against allowed literals
    # ---------------------------------------------------------------------
    if artifact_type not in ("model", "dataset", "code"):
        return error_response(
            400,
            f"Invalid artifact_type '{artifact_type}'",
            error_code="INVALID_ARTIFACT_TYPE",
        )
    artifact_type = cast(ArtifactType, artifact_type)

    logger.debug(
        f"[get_artifact] artifact_type={artifact_type}, artifact_id={artifact_id}"
    )

    # ---------------------------------------------------------------------
    # Step 3 - Load metadata from DynamoDB
    # ---------------------------------------------------------------------
    artifact = load_artifact_metadata(artifact_id)
    if artifact is None:
        return error_response(404, f"Artifact '{artifact_id}' does not exist")

    # ---------------------------------------------------------------------
    # Step 4 - Construct S3 key
    # ---------------------------------------------------------------------
    # Convention: <artifact_type>/<artifact_id>.tar.gz
    # We can adjust this if our system should use a different storage layout.
    # ---------------------------------------------------------------------
    s3_key = f"{artifact_type}/{artifact_id}.tar.gz"

    try:
        download_url = generate_s3_download_url(artifact_id, s3_key=s3_key)
    except Exception as e:
        logger.error(
            f"[get_artifact] Failed to generate presigned URL: {e}", exc_info=True
        )
        return error_response(
            500, "Failed to generate download URL", error_code="S3_ERROR"
        )

    # ---------------------------------------------------------------------
    # Step 5 - Build the returned Artifact object per OpenAPI spec
    # ---------------------------------------------------------------------
    response_body = {
        "metadata": {
            "name": artifact.name,
            "id": artifact.artifact_id,
            "type": artifact.artifact_type,
        },
        "data": {
            "url": artifact.source_url,  # original ingest URL
            "download_url": download_url,  # presigned S3 URL
        },
    }

    return json_response(200, response_body)
