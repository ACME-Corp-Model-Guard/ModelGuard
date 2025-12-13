"""
DELETE /artifacts/{artifact_type}/{id}
Delete an artifact by ID - removes both metadata from DynamoDB and file from S3.
"""

from __future__ import annotations

from typing import Any, Dict, cast

from src.artifacts.types import ArtifactType
from src.auth import AuthContext, auth_required
from src.logutil import clogger, log_lambda_handler
from src.artifacts.artifactory import load_artifact_metadata
from src.settings import ARTIFACTS_BUCKET, ARTIFACTS_TABLE
from src.storage.dynamo_utils import delete_item
from src.storage.s3_utils import delete_objects
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


# =============================================================================
# Lambda Handler: DELETE /artifacts/{artifact_type}/{id}
# =============================================================================
#
# Responsibilities:
#   1. Authenticate user
#   2. Validate path parameters
#   3. Verify artifact exists in DynamoDB
#   4. Delete artifact metadata from DynamoDB
#   5. Delete artifact file from S3
#   6. Return success response
#
# Error codes:
#   400 - invalid artifact_type or id missing/malformed
#   403 - auth failure (handled by @auth_required)
#   404 - artifact not found
#   500 - catchall (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@log_lambda_handler("DELETE /artifacts/{type}/{id}")
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
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

    # ---------------------------------------------------------------------
    # Step 3 - Verify artifact exists in DynamoDB
    # ---------------------------------------------------------------------
    artifact = load_artifact_metadata(artifact_id)
    if artifact is None:
        return error_response(
            404,
            f"Artifact '{artifact_id}' does not exist",
            error_code="NOT_FOUND",
        )

    # ---------------------------------------------------------------------
    # Step 4 - Delete artifact metadata from DynamoDB
    # ---------------------------------------------------------------------
    try:
        delete_item(ARTIFACTS_TABLE, "artifact_id", artifact_id)
        clogger.info(
            "Deleted artifact metadata from DynamoDB",
            extra={"artifact_id": artifact_id, "artifact_type": artifact_type},
        )
    except Exception as e:
        clogger.exception(
            "Failed to delete artifact metadata from DynamoDB",
            extra={
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "error_type": type(e).__name__,
            },
        )
        return error_response(
            500,
            "Failed to delete artifact metadata",
            error_code="DYNAMO_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 5 - Delete artifact file from S3
    # ---------------------------------------------------------------------
    s3_key = f"{artifact_type}/{artifact_id}.tar.gz"
    try:
        deleted_count = delete_objects(ARTIFACTS_BUCKET, [s3_key])
        clogger.info(
            "Deleted artifact file from S3",
            extra={
                "artifact_id": artifact_id,
                "s3_key": s3_key,
                "deleted_count": deleted_count,
            },
        )
    except Exception as e:
        # Log but don't fail - metadata is already deleted
        clogger.warning(
            "Failed to delete artifact file from S3 (metadata already deleted)",
            extra={
                "artifact_id": artifact_id,
                "s3_key": s3_key,
                "error_type": type(e).__name__,
            },
        )

    # ---------------------------------------------------------------------
    # Step 6 - Return success response per OpenAPI spec
    # ---------------------------------------------------------------------
    return json_response(200, {"message": "Artifact is deleted"})
