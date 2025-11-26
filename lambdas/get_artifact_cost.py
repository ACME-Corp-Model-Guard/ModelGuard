"""
GET /artifact/{artifact_type}/{id}/cost
Return the size cost (in bytes) of an artifact, measured by the S3 object size
of the stored artifact bundle.
"""

from __future__ import annotations

from typing import Any, Dict

from src.auth import AuthContext, auth_required
from src.aws.clients import get_s3
from src.logger import logger, with_logging
from src.settings import ARTIFACTS_BUCKET
from src.storage.dynamo_utils import load_artifact_metadata
from src.utils.http import LambdaResponse, error_response, json_response, translate_exceptions

VALID_TYPES = {"model", "dataset", "code"}


# =============================================================================
# Lambda Handler: GET /artifact/{artifact_type}/{id}/cost
# =============================================================================
#
# Responsibilities:
#   1. Authenticate user
#   2. Validate artifact_type and id path parameters
#   3. Load artifact metadata from DynamoDB
#   4. Perform S3 HEAD request to fetch object size
#   5. Return size_bytes and identifying metadata
#
# Error codes:
#   400 - invalid artifact_type or missing/malformed id
#   403 - authentication failure (handled by @auth_required)
#   404 - artifact not found in DynamoDB
#   500 - S3 HEAD failure or internal error (handled by @translate_exceptions)
# =============================================================================


@with_logging
@translate_exceptions
@auth_required
def lambda_handler(event: Dict[str, Any], context: Any, auth: AuthContext) -> LambdaResponse:
    logger.info("[artifact_cost] Handling artifact cost request")

    # ----------------------------------------------------------------------
    # Step 1 - Extract path parameters
    # ----------------------------------------------------------------------
    path_params = event.get("pathParameters") or {}
    artifact_type = (path_params.get("artifact_type") or "").lower().strip()
    artifact_id = path_params.get("id")

    if not artifact_type or not artifact_id:
        return error_response(
            400,
            "Missing required path parameters: artifact_type or id",
            error_code="INVALID_REQUEST",
        )

    # ----------------------------------------------------------------------
    # Step 2 - Validate artifact_type
    # ----------------------------------------------------------------------
    if artifact_type not in VALID_TYPES:
        return error_response(
            400,
            f"Invalid artifact_type '{artifact_type}'",
            error_code="INVALID_ARTIFACT_TYPE",
        )

    logger.debug(
        f"[artifact_cost] artifact_type={artifact_type}, artifact_id={artifact_id}"
    )

    # ----------------------------------------------------------------------
    # Step 3 - Load metadata from DynamoDB
    # ----------------------------------------------------------------------
    artifact = load_artifact_metadata(artifact_id)
    if artifact is None:
        return error_response(404, f"Artifact '{artifact_id}' does not exist")

    # Validate type consistency
    if artifact.artifact_type != artifact_type:
        return error_response(
            400,
            f"Artifact {artifact_id} is type '{artifact.artifact_type}', not '{artifact_type}'",
            error_code="TYPE_MISMATCH",
        )

    # ----------------------------------------------------------------------
    # Step 4 - Perform S3 HEAD to get size
    # ----------------------------------------------------------------------
    s3 = get_s3()

    try:
        logger.debug(
            f"[artifact_cost] HEAD s3://{ARTIFACTS_BUCKET}/{artifact.s3_key}"
        )
        head = s3.head_object(Bucket=ARTIFACTS_BUCKET, Key=artifact.s3_key)
    except Exception as e:
        logger.error(
            f"[artifact_cost] Failed HEAD for artifact {artifact_id}: {e}",
            exc_info=True,
        )
        return error_response(
            500,
            "Failed to retrieve artifact size",
            error_code="S3_ERROR",
        )

    size_bytes = int(head.get("ContentLength", 0))

    # ----------------------------------------------------------------------
    # Step 5 - Build response body
    # ----------------------------------------------------------------------
    response_body = {
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "size_bytes": size_bytes,
    }

    return json_response(200, response_body)
