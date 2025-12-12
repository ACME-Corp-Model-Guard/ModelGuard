"""
DELETE /reset
Reset the system to default state:
- Clear all items from the DynamoDB artifacts table
- Clear all items from the DynamoDB tokens table
- Clear all objects from the S3 artifacts bucket
- Delete all Cognito users
- Delete all Cognito user groups
- Reinitialize required bootstrap state (default admin user, etc.)
"""

from __future__ import annotations

from typing import Any, Dict

from src.auth import AuthContext, auth_required
from src.logutil import clogger, log_lambda_handler
from src.settings import ARTIFACTS_BUCKET, ARTIFACTS_TABLE
from src.storage.dynamo_utils import clear_table
from src.storage.s3_utils import clear_bucket
from src.utils.bootstrap import bootstrap_system
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


# =============================================================================
# Lambda Handler: DELETE /reset
# =============================================================================
#
# Responsibilities:
#   1. Authenticate caller
#   2. Clear DynamoDB artifacts table
#   3. Clear DynamoDB tokens table
#   4. Clear S3 bucket of all stored artifacts
#   5. Delete all Cognito users
#   6. Delete all Cognito groups
#   7. Reinitialize system bootstrap state
#   8. Return status response
#
# Error codes:
#   401 - authentication failure (handled by @auth_required)
#   500 - catch-all for unexpected errors (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@log_lambda_handler("DELETE /reset")
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    # ---------------------------------------------------------------------
    # Step 0 — Verify admin permission (401 per OpenAPI spec)
    # ---------------------------------------------------------------------
    if "Admin" not in auth["groups"]:
        clogger.warning(
            f"[/reset] Non-admin user attempted reset: {auth['username']}, "
            f"groups={auth['groups']}"
        )
        return error_response(
            401,
            "You do not have permission to reset the registry",
            error_code="ADMIN_REQUIRED",
        )

    # ---------------------------------------------------------------------
    # Step 1 — Clear DynamoDB artifacts table
    # ---------------------------------------------------------------------
    clogger.info(f"Clearing DynamoDB table: {ARTIFACTS_TABLE}")
    clear_table(ARTIFACTS_TABLE, key_name="artifact_id")

    # ---------------------------------------------------------------------
    # Step 2 — Clear S3 artifacts bucket
    # ---------------------------------------------------------------------
    clogger.info(f"Clearing S3 bucket: {ARTIFACTS_BUCKET}")
    clear_bucket(ARTIFACTS_BUCKET)

    # ---------------------------------------------------------------------
    # Step 3 — Run system bootstrap initialization
    # ---------------------------------------------------------------------
    clogger.info("Running system bootstrap...")
    bootstrap_system()

    # ---------------------------------------------------------------------
    # Step 4 — Success response
    # ---------------------------------------------------------------------
    return json_response(
        status_code=200,
        body={
            "message": "System reset and bootstrapped successfully",
            "status": "ok",
        },
    )
