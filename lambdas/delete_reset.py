"""
DELETE /reset
Reset the system to default state:
- Clear all items from the DynamoDB artifacts table
- Clear all objects from the S3 artifacts bucket
"""

from __future__ import annotations

from typing import Any, Dict

from src.auth import authorize
from src.logger import logger
from src.settings import ARTIFACTS_BUCKET, ARTIFACTS_TABLE
from src.storage.dynamo_utils import clear_table
from src.storage.s3_utils import clear_bucket
from src.utils.decorators import translate_exceptions, with_logging
from src.utils.http import LambdaResponse, json_response


# ======================================================================
# Lambda Handler
# ======================================================================
@with_logging
@translate_exceptions
def lambda_handler(event: Dict[str, Any], context: Any) -> LambdaResponse:
    """
    DELETE /reset
    Reset all system state (DynamoDB + S3).
    """
    logger.info("[/reset] Processing DELETE /reset")

    # Reset DynamoDB
    logger.info(f"[/reset] Clearing DynamoDB table: {ARTIFACTS_TABLE}")
    clear_table(ARTIFACTS_TABLE, key_name="artifact_id")

    # Reset S3
    logger.info(f"[/reset] Clearing S3 bucket: {ARTIFACTS_BUCKET}")
    clear_bucket(ARTIFACTS_BUCKET)

    # Build success response
    return json_response(
        status_code=200,
        body={
            "message": "System reset successfully",
            "status": "ok",
        },
    )
