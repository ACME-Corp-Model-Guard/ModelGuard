"""
DELETE /reset
Reset the system to default state:
- Clear all items from the DynamoDB artifacts table
- Clear all objects from the S3 artifacts bucket
- Reinitialize required bootstrap state (default admin user, etc.)
"""

from __future__ import annotations

from typing import Any, Dict

from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.settings import ARTIFACTS_BUCKET, ARTIFACTS_TABLE
from src.storage.dynamo_utils import clear_table
from src.storage.s3_utils import clear_bucket
from src.utils.bootstrap import bootstrap_system
from src.utils.http import json_response, translate_exceptions


# =============================================================================
# Lambda Handler: DELETE /reset
# =============================================================================
#
# Responsibilities:
#   1. Authenticate caller
#   2. Clear DynamoDB artifacts table
#   3. Clear S3 bucket of all stored artifacts
#   4. Reinitialize system bootstrap state
#   5. Return status response
#
# Error codes:
#   401 - authentication failure (handled by @auth_required)
#   500 - catch-all for unexpected errors (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
):
    logger.info("[/reset] Handling DELETE /reset")

    # ---------------------------------------------------------------------
    # Step 1 — Clear DynamoDB artifacts table
    # ---------------------------------------------------------------------
    logger.info(f"[/reset] Clearing DynamoDB table: {ARTIFACTS_TABLE}")
    clear_table(ARTIFACTS_TABLE, key_name="artifact_id")

    # ---------------------------------------------------------------------
    # Step 2 — Clear S3 artifacts bucket
    # ---------------------------------------------------------------------
    logger.info(f"[/reset] Clearing S3 bucket: {ARTIFACTS_BUCKET}")
    clear_bucket(ARTIFACTS_BUCKET)

    # ---------------------------------------------------------------------
    # Step 3 — Run system bootstrap initialization
    # ---------------------------------------------------------------------
    logger.info("[/reset] Running system bootstrap...")
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
