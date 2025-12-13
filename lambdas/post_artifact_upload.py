# TODO: OpenAPI Compliance Issues
# - [ ] 202 Accepted: Implement async ingestion with deferred rating
#       (artifact stored but rating computed asynchronously; /rate returns 404 until ready)
"""
POST /artifact/{artifact_type}
Ingest a new artifact from a source URL and store metadata in DynamoDB.
Downloads and archives the artifact into S3. Returns ArtifactResponse as
defined in the OpenAPI specification.
"""

from __future__ import annotations

import json
from typing import Any, Dict, cast

from src.artifacts.artifactory import (
    create_artifact,
    load_all_artifacts_by_fields,
    save_artifact_metadata,
)
from src.artifacts.types import ArtifactType
from src.auth import AuthContext, auth_required
from src.logutil import clogger, log_lambda_handler
from src.settings import ARTIFACTS_BUCKET, MINIMUM_METRIC_THRESHOLD
from src.storage.downloaders.dispatchers import FileDownloadError
from src.storage.s3_utils import delete_objects, generate_s3_download_url
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
@log_lambda_handler("POST /artifact/{type}", log_request_body=True, log_response_body=True)
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
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

    clogger.info(
        "Processing artifact upload",
        extra={
            "artifact_type": artifact_type,
            "user": auth.get("username"),
        },
    )

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
    name = body.get("name")  # Optional: autograder may provide this
    if not url:
        return error_response(
            400,
            "Missing required field 'url'",
            error_code="MISSING_URL",
        )

    # ---------------------------------------------------------------------
    # Step 2.1 — Check for duplicate artifact (409 Conflict)
    # ---------------------------------------------------------------------
    existing = load_all_artifacts_by_fields({"source_url": url})
    if existing:
        clogger.info(f"[post_artifact] Duplicate artifact detected: {existing[0].artifact_id}")
        return error_response(
            409,
            f"Artifact already exists with this source URL (id: {existing[0].artifact_id})",
            error_code="ARTIFACT_EXISTS",
        )

    # ---------------------------------------------------------------------
    # Step 3 — Fetch upstream metadata and create artifact object
    # ---------------------------------------------------------------------
    try:
        artifact = create_artifact(artifact_type, source_url=url, name=name)
    except FileDownloadError as e:
        # The metadata-fetching process can raise FileDownloadError
        clogger.error(
            "Upstream metadata fetch failed",
            extra={
                "artifact_type": artifact_type,
                "source_url": url,
                "error_type": type(e).__name__,
            },
        )
        return error_response(
            404,
            "Artifact metadata could not be retrieved from upstream source",
            error_code="SOURCE_NOT_FOUND",
        )
    except Exception as e:
        clogger.exception(
            "Unexpected metadata ingestion failure",
            extra={
                "artifact_type": artifact_type,
                "source_url": url,
                "error_type": type(e).__name__,
            },
        )
        return error_response(
            500,
            "Unexpected error during metadata ingestion",
            error_code="INGESTION_FAILURE",
        )

    clogger.info(
        "Artifact created successfully",
        extra=artifact.to_dict(),
    )

    # ---------------------------------------------------------------------
    # Step 3.1 — Check quality threshold for models (424 Failed Dependency)
    # ---------------------------------------------------------------------
    if artifact.artifact_type == "model":
        scores = getattr(artifact, "scores", {})
        failing_metrics = []

        # Check each non-latency metric against threshold
        for metric_name, score_value in scores.items():
            # Skip special cases and handle Size dict
            if isinstance(score_value, dict):
                # Size metric has per-platform scores - check each one
                for platform, platform_score in score_value.items():
                    if isinstance(platform_score, (int, float)):
                        if platform_score < MINIMUM_METRIC_THRESHOLD:
                            failing_metrics.append(f"Size.{platform}={platform_score:.2f}")
            elif isinstance(score_value, (int, float)):
                if score_value < MINIMUM_METRIC_THRESHOLD:
                    failing_metrics.append(f"{metric_name}={score_value:.2f}")

        if failing_metrics:
            clogger.warning(
                f"[post_artifact] Model {artifact.artifact_id} rejected: "
                f"metrics below threshold ({MINIMUM_METRIC_THRESHOLD}): {failing_metrics}"
            )
            # Clean up S3 object since we're rejecting
            if artifact.s3_key and ARTIFACTS_BUCKET:
                try:
                    delete_objects(ARTIFACTS_BUCKET, [artifact.s3_key])
                    clogger.info(f"[post_artifact] Cleaned up S3 object: {artifact.s3_key}")
                except Exception as cleanup_err:
                    clogger.warning(f"[post_artifact] Failed to clean up S3: {cleanup_err}")

            return error_response(
                424,
                f"Model rejected: metrics below threshold ({MINIMUM_METRIC_THRESHOLD}): "
                f"{', '.join(failing_metrics)}",
                error_code="QUALITY_THRESHOLD_NOT_MET",
            )

    # ---------------------------------------------------------------------
    # Step 4 — Save metadata to DynamoDB
    # ---------------------------------------------------------------------
    try:
        save_artifact_metadata(artifact)
        clogger.info(
            f"Artifact saved to DynamoDB: {artifact.artifact_id}",
            extra={
                "artifact_id": artifact.artifact_id,
                "artifact_type": artifact_type,
                "artifact_name": artifact.name,
            },
        )
    except Exception as e:
        clogger.exception(
            "Failed to save metadata",
            extra={
                "artifact_id": artifact.artifact_id,
                "error_type": type(e).__name__,
            },
        )
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
