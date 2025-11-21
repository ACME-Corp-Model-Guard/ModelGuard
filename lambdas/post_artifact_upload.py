"""
POST /artifact/{artifact_type}
Ingest a new artifact from a source URL and store metadata in DynamoDB.
Downloads and archives the artifact into S3. Returns ArtifactResponse as
defined in the OpenAPI specification.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from src.artifacts.types import ArtifactType
from src.artifacts.base_artifact import BaseArtifact
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.storage.s3_utils import upload_artifact_to_s3
from src.storage.dynamo_utils import save_artifact_metadata
from src.storage.downloaders.dispatchers import FileDownloadError
from src.utils.http import json_response, error_response, translate_exceptions


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
):
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

    try:
        artifact_type = ArtifactType(artifact_type_raw)
    except ValueError:
        return error_response(
            400,
            f"Invalid artifact_type '{artifact_type_raw}'",
            error_code="INVALID_ARTIFACT_TYPE",
        )

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
        artifact = BaseArtifact.from_url(url, artifact_type)
    except FileDownloadError as e:
        # The metadata-fetching process can raise FileDownloadError
        logger.error(f"[post_artifact] Upstream metadata fetch failed: {e}", exc_info=True)
        return error_response(
            404,
            "Artifact metadata could not be retrieved from upstream source",
            error_code="SOURCE_NOT_FOUND",
        )
    except Exception as e:
        logger.error(f"[post_artifact] Unexpected metadata ingestion failure: {e}", exc_info=True)
        return error_response(
            500,
            "Unexpected error during metadata ingestion",
            error_code="INGESTION_FAILURE",
        )

    logger.info(f"[post_artifact] Created artifact: id={artifact.artifact_id}")

    # ---------------------------------------------------------------------
    # Step 4 — Download upstream content → upload packaged artifact to S3
    # ---------------------------------------------------------------------
    try:
        upload_artifact_to_s3(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact_type,
            s3_key=artifact.s3_key,
            source_url=url,
        )
    except FileDownloadError:
        return error_response(
            404,
            "Upstream artifact not found or download failed",
            error_code="SOURCE_NOT_FOUND",
        )
    except Exception as e:
        logger.error(f"[post_artifact] S3 upload failed: {e}", exc_info=True)
        return error_response(
            500,
            "Failed to upload artifact to S3",
            error_code="S3_UPLOAD_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 5 — Save metadata to DynamoDB
    # ---------------------------------------------------------------------
    try:
        save_artifact_metadata(artifact)
    except Exception as e:
        logger.error(f"[post_artifact] Failed to save metadata: {e}", exc_info=True)
        return error_response(
            500,
            "Failed to save artifact metadata",
            error_code="DDB_SAVE_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 6 — Build ArtifactResponse
    # ---------------------------------------------------------------------
    response_body = {
        "metadata": {
            "id": artifact.artifact_id,
            "name": artifact.name,
            "type": artifact.artifact_type,
        },
        "data": {
            "url": artifact.source_url,
            # TODO: Figure out what this URL should be
            #       Spec requires this field but does not
            #       explicitly require presigned URLs
            "download_url": artifact.s3_key,
        },
    }

    return json_response(200, response_body)
