"""
POST /artifact/{artifact_type}
Ingest a new artifact from a source URL and store metadata in DynamoDB.
Downloads and archives the artifact into S3. Returns ArtifactResponse as
defined in the OpenAPI specification.
"""

from __future__ import annotations

import json
from typing import Any, Dict, cast

from src.artifacts.artifactory import create_artifact, save_artifact_metadata
from src.artifacts.types import ArtifactType
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.storage.downloaders.dispatchers import FileDownloadError
from src.storage.s3_utils import generate_s3_download_url
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)

# =============================================================================
# Lambda Handler: POST /artifact/{artifact_type}
# =============================================================================
#
# Responsibilities:
#   1. Authenticate caller
#   2. Validate artifact_type
#   3. Parse request body { "url": "<string>" }
#   4. Fetch metadata from upstream source
#   5. Upload packaged artifact to S3
#   6. Save metadata to DynamoDB
#   7. Return ArtifactResponse (metadata + data.url + data.download_url)
#
# Status codes:
#   202 - TODO: Implement: artifact ingest accepted; rating deferred
#
# Error codes:
#   400 - invalid artifact_type, missing url, malformed JSON
#   403 - unauthorized (handled by @auth_required)
#   404 - upstream artifact not found
#   500 - internal errors (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    logger.info("[post_artifact] Handling POST /artifact request")

    # ---------------------------------------------------------------------
    # Step 1 — Extract artifact_type
    # ---------------------------------------------------------------------
    path_params = event.get("pathParameters") or {}
    artifact_type_raw = path_params.get("artifact_type")

    if not artifact_type_raw:
        return error_response(
            400,
            "Missing required path parameter: artifact_type",
            error_code="INVALID_ARTIFACT_TYPE",
        )

    if artifact_type_raw not in ("model", "dataset", "code"):
        return error_response(
            400,
            f"Invalid artifact_type '{artifact_type_raw}'",
            error_code="INVALID_ARTIFACT_TYPE",
        )
    artifact_type = cast(ArtifactType, artifact_type_raw)

    logger.info(f"[post_artifact] artifact_type={artifact_type}")

    # ---------------------------------------------------------------------
    # Step 2 — Parse request body
    # ---------------------------------------------------------------------
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error_response(
            400,
            "Request body must be valid JSON",
            error_code="INVALID_JSON",
        )

    url = body.get("url")
    if not url:
        return error_response(
            400,
            "Missing required field 'url'",
            error_code="MISSING_URL",
        )

    logger.info(f"[post_artifact] ingest_url={url}")

    # ---------------------------------------------------------------------
    # Step 3 — Fetch upstream metadata and create artifact object
    # ---------------------------------------------------------------------
    try:
        artifact = create_artifact(artifact_type, source_url=url)
    except FileDownloadError as e:
        # The metadata-fetching process can raise FileDownloadError
        logger.error(
            f"[post_artifact] Upstream metadata fetch failed: {e}",
        )
        return error_response(
            404,
            "Artifact metadata could not be retrieved from upstream source",
            error_code="SOURCE_NOT_FOUND",
        )
    except Exception as e:
        logger.error(
            f"[post_artifact] Unexpected metadata ingestion failure: {e}",
        )
        return error_response(
            500,
            "Unexpected error during metadata ingestion",
            error_code="INGESTION_FAILURE",
        )

    logger.info(f"[post_artifact] Created artifact: id={artifact.artifact_id}")

    # ---------------------------------------------------------------------
    # Step 4 — Save metadata to DynamoDB
    # ---------------------------------------------------------------------
    try:
        save_artifact_metadata(artifact)
    except Exception as e:
        logger.error(f"[post_artifact] Failed to save metadata: {e}")
        return error_response(
            500,
            "Failed to save artifact metadata",
            error_code="DDB_SAVE_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 5 — Build ArtifactResponse
    # ---------------------------------------------------------------------
    # Generate presigned download URL (same as GET /artifacts/{type}/{id})
    download_url = generate_s3_download_url(artifact.artifact_id, s3_key=artifact.s3_key)

    response_body = {
        "metadata": {
            "id": artifact.artifact_id,
            "name": artifact.name,
            "type": artifact.artifact_type,
        },
        "data": {
            "url": artifact.source_url,
            "download_url": download_url,
        },
    }

    return json_response(201, response_body)
