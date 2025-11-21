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


# ======================================================================
# Lambda Handler
# ======================================================================
@with_logging
@translate_exceptions
@auth_required
def lambda_handler(event: Dict[str, Any], context: Any, auth: AuthContext) -> Dict[str, Any]:
    """
    DELETE /reset
    Reset all system state (DynamoDB + S3), then run bootstrap initialization.
    """
    logger.info("[/reset] Processing DELETE /reset")

    # 1 — Reset DynamoDB
    logger.info(f"[/reset] Clearing DynamoDB table: {ARTIFACTS_TABLE}")
    clear_table(ARTIFACTS_TABLE, key_name="artifact_id")

    # 2 — Reset S3
    logger.info(f"[/reset] Clearing S3 bucket: {ARTIFACTS_BUCKET}")
    clear_bucket(ARTIFACTS_BUCKET)

    # 3 — Run system bootstrap initialization
    logger.info("[/reset] Running system bootstrap...")
    bootstrap_system()

    # 4 — Success response
    return json_response(
        status_code=200,
        body={
            "message": "System reset and bootstrapped successfully",
            "status": "ok",
        },
    )
