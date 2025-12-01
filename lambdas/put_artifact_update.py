"""
PUT /artifacts/{artifact_type}/{id}
Update an existing artifact with a new upstream URL.

High-level behavior:
  1. Load existing artifact metadata for the supplied id (previous version).
  2. Create a *new* candidate artifact from the provided URL.
  3. For model artifacts, compare the candidate's new NetScore against the
     previous artifact's NetScore:
       - If the new NetScore is LOWER than the previous:
           • Delete the new artifact's S3 object.
           • Keep the old artifact (no metadata changes).
       - If the new NetScore is GREATER OR EQUAL:
           • Delete the old artifact's S3 object.
           • Overwrite the old artifact's metadata with the new artifact's
             metadata (re-using the original artifact_id).
  4. For non-model artifacts, we always accept the update (no NetScore check).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, cast

from src.artifacts.artifactory import (
    create_artifact,
    load_artifact_metadata,
    save_artifact_metadata,
)
from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.types import ArtifactType
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.metrics.registry import METRICS
from src.settings import ARTIFACTS_BUCKET
from src.storage.downloaders.dispatchers import FileDownloadError
from src.storage.s3_utils import delete_objects
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse the request body as JSON and return it as a dict.

    The expected body format (same as POST /artifact/{artifact_type}):
        {"url": "<new_source_url>"}
    """
    raw_body = event.get("body") or "{}"

    if isinstance(raw_body, dict):
        return raw_body

    if not isinstance(raw_body, str):
        raise ValueError("Request body must be a JSON object or JSON string.")

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Request body must be valid JSON: {exc}") from exc


def _get_net_score(artifact: BaseArtifact) -> Optional[float]:
    """
    Extract NetScore from a ModelArtifact's scores dict, if present.

    Returns:
        float NetScore in [0.0, 1.0], or None if not applicable/not available/missing.
    """
    scores = getattr(artifact, "scores", None)
    if not isinstance(scores, dict):
        return None

    raw = scores.get("NetScore")
    if raw is None:
        return None

    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# =============================================================================
# Lambda Handler: PUT /artifacts/{artifact_type}/{id}
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,  # Use for auth side effects
    # ) -> Dict[str, Any]:
) -> LambdaResponse:
    logger.info("[put_artifact_update] Handling artifact upodate request")

    # ------------------------------------------------------------------
    # Step 1 - Extract & validate path parameters
    # ------------------------------------------------------------------
    path_params = event.get("pathParameters") or {}
    artifact_type_raw = path_params.get("artifact_type")
    artifact_id = path_params.get("id")

    if not artifact_type_raw or not artifact_id:
        return error_response(
            400,
            "Missing requiured path parameters: artifact_type or id",
            error_code="INVALID_REQUEST",
        )
    if artifact_type_raw not in ("model", "dataset", "code"):
        return error_response(
            400,
            f"Invalid artifact_type '{artifact_type_raw}'",
            error_code="INVALID_ARTIFACT_TYPE",
        )

    artifact_type = cast(ArtifactType, artifact_type_raw)
    logger.debug(
        f"[put_artifact_update] artifact_type = {artifact_type}, artifact_id = {artifact_id}"
    )

    # ------------------------------------------------------------------
    # Step 2 - Parse and validate request body
    # ------------------------------------------------------------------
    try:
        body = _parse_body(event)
    except ValueError as exc:
        logger.warning(f"[put_artifact_update] Invalid JSON body: {exc}")
        return error_response(400, str(exc), error_code="INVALID_JSON")
    url = body.get("url")
    if not isinstance(url, str) or not url.strip():
        return error_response(
            400, "Mising required field 'url'", error_code="MISSING_URL"
        )
    logger.info(f"[put_artifact_update] update_url = {url}")

    # ------------------------------------------------------------------
    # Step 3 - Load existing artifact metadata (previous version)
    # ------------------------------------------------------------------
    old_artifact = load_artifact_metadata(artifact_id)
    if old_artifact is None:
        logger.warning(f"[put_artifact_update] Artifact '{artifact_id}' does not exist")
        return error_response(
            404, f"Artifact '{artifact_id}' does not exist", error_code="NOT_FOUND"
        )

    old_s3_key = getattr(old_artifact, "s3_key", None)
    logger.debug(
        f"[put_artifact_update] Loaded old artifact"
        f"id = {old_artifact.artifact_id}, s3_key = {old_s3_key}"
    )

    # ------------------------------------------------------------------
    # Step 4 - Create a new candidate artifact from the new URL
    # ------------------------------------------------------------------

    """
    Note: Let create_artifact generate a fresh artifact_id.
    - If the updaete is accepted, we will overwwrite it with the original id before
    saving metadata, so the logical artifact id stays stable.
    """
    try:
        new_artifact = create_artifact(artifact_type, source_url=url, metrics=METRICS)
    except FileDownloadError as exc:
        logger.error(
            f"[put_artifact_update] Upstream artifact download/metadata failed: {exc}"
        )
        return error_response(
            404,
            "Artifact metadata could not be fetched from the source URL",
            error_code="SOURCE_NOT_FOUND",
        )
    
    # except Exception as exc:  # pragma: no cover - safety net
    #     logger.error(
    #         f"[put_artifact_update] Unexpected error during artifact creation: {exc}"
    #     )
    #     return error_response(
    #         500,
    #         "Unexpected error during artifact update",
    #         error_code="INGESTION_FAILURE",
    #     )

    logger.info(
        f"[put_artifact_update] Created candidate artifact: "
        f"id={new_artifact.artifact_id}, type={new_artifact.artifact_type}, "
        f"s3_key={getattr(new_artifact, 's3_key', None)}"
    )

    # ------------------------------------------------------------------
    # Step 5 - For models, compare NetScore against previous version
    # ------------------------------------------------------------------
    accept_update = True

    if artifact_type == "model":
        new_score = _get_net_score(new_artifact)
        old_score = _get_net_score(old_artifact)

        if new_score is None:
            logger.warning(
                "[put_artifact_update] NetScore missing for new model; "
                "treating as 0.0 for comparison"
            )
            new_score = 0.0

        """
        If the previous model had no NetScore (legacy data), treat its threshold as 0.0
        to avoid permanently blocking updates.
        """
        threshold = 0.0 if old_score is None else old_score

        logger.info(
            "[put_artifact_update] NetScore comparison: "
            f"old={threshold:.4f}, new={new_score:.4f}"
        )

        # Only accept the update if the new score is at least as good as the old score
        if new_score < threshold:
            accept_update = False

    # ------------------------------------------------------------------
    # Step 5.1 - Reject update: delete *new* S3 object, keep old artifact
    # ------------------------------------------------------------------
    if not accept_update:
        new_s3_key = getattr(new_artifact, "s3_key", None)
        if ARTIFACTS_BUCKET and new_s3_key:
            logger.info(
                f"[put_artifact_update] Update rejected; deleting new S3 object "
                f"s3://{ARTIFACTS_BUCKET}/{new_s3_key}"
            )
            try:
                delete_objects(ARTIFACTS_BUCKET, [new_s3_key])
            except Exception as exc:  # pragma: no cover - best effort cleanup
                logger.error(
                    f"[put_artifact_update] Failed to delete new artifact S3 key "
                    f"{new_s3_key}: {exc}"
                )

        return error_response(
            400,
            "Updated artifact failed NetScore threshold (lower than previous); "
            "original artifact preserved",
            error_code="LOW_NET_SCORE",
        )

    # ------------------------------------------------------------------
    # Step 5.2 - Accept update:
    #   - Delete old S3 object
    #   - Overwrite old metadata with new artifact metadata
    # ------------------------------------------------------------------
    if ARTIFACTS_BUCKET and old_s3_key:
        logger.info(
            f"[put_artifact_update] Update accepted; deleting old S3 object "
            f"s3://{ARTIFACTS_BUCKET}/{old_s3_key}"
        )
        try:
            delete_objects(ARTIFACTS_BUCKET, [old_s3_key])
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.error(
                f"[put_artifact_update] Failed to delete old artifact S3 key "
                f"{old_s3_key}: {exc}"
            )

    # Align IDs so we overwrite the existing artifact row in DynamoDB.
    new_artifact.artifact_id = old_artifact.artifact_id
    new_artifact.artifact_type = old_artifact.artifact_type

    try:
        save_artifact_metadata(new_artifact)
    except Exception as exc:
        logger.error(
            f"[put_artifact_update] Failed to save updated artifact metadata: {exc}"
        )
        return error_response(
            500,
            "Failed to save updated artifact metadata",
            error_code="DDB_SAVE_ERROR",
        )

    # ------------------------------------------------------------------
    # Step 6 - Build response (same shape as POST /artifact/{artifact_type})
    # ------------------------------------------------------------------
    response_body = {
        "metadata": {
            "id": new_artifact.artifact_id,
            "name": new_artifact.name,
            "type": new_artifact.artifact_type,
        },
        "data": {
            "url": new_artifact.source_url,
            # The spec requires a download_url field; we return the stored
            # S3 key here, consistent with POST /artifact/{artifact_type}.
            "download_url": getattr(new_artifact, "s3_key", None),
        },
    }
    logger.info(
        f"[put_artifact_update] Artifact update succeeded for id={new_artifact.artifact_id}"
    )
    return json_response(200, response_body)
