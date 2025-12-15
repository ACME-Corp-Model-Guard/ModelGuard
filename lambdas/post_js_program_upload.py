"""
POST /artifacts/UploadJSProgram/
Admin endpoint to upload a JS program for a model.
Accepts artifact_id and JS file (base64 or text),
saves JS to S3, and updates the model's js_program_key field in DynamoDB.
"""

import base64
import json
from typing import Any, Dict

from src.auth import AuthContext, auth_required
from src.logutil import clogger, log_lambda_handler
from src.utils.http import (
    LambdaResponse,
    json_response,
    error_response,
    translate_exceptions,
)
from src.artifacts.artifactory.persistence import load_artifact_metadata, save_artifact_metadata
from src.artifacts.model_artifact import ModelArtifact
from src.storage.s3_utils import upload_file
from src.settings import JS_PROGRAMS_BUCKET, JS_PROGRAMS_PREFIX


@translate_exceptions
@log_lambda_handler("POST /artifacts/UploadJSProgram/", log_request_body=True)
@auth_required(admin_only=True)
def lambda_handler(event: Dict[str, Any], context: Any, auth: AuthContext) -> LambdaResponse:
    # Parse body (should be JSON with artifact_id and js_program)
    raw_body = event.get("body")
    if isinstance(raw_body, str):
        try:
            body = json.loads(raw_body)
        except Exception:
            return error_response(
                400, "Request body must be valid JSON.", error_code="INVALID_JSON"
            )
    else:
        body = raw_body

    artifact_id = body.get("artifact_id")
    js_program = body.get("js_program")
    is_base64 = body.get("isBase64Encoded", False)
    if not artifact_id or not js_program:
        return error_response(400, "Missing artifact_id or js_program in request body.")

    # Load model artifact
    artifact = load_artifact_metadata(artifact_id)
    if not isinstance(artifact, ModelArtifact):
        return error_response(404, f"Model artifact '{artifact_id}' not found.")

    # Decode JS program
    try:
        js_bytes = base64.b64decode(js_program) if is_base64 else js_program.encode("utf-8")
    except Exception:
        return error_response(400, "Invalid base64 encoding for js_program.")

    # S3 key: js-programs/{artifact_id}.js
    s3_key = f"{JS_PROGRAMS_PREFIX}{artifact_id}.js"
    tmp_path = f"/tmp/{artifact_id}.js"
    with open(tmp_path, "wb") as f:
        f.write(js_bytes)

    try:
        upload_file(s3_key, tmp_path, bucket=JS_PROGRAMS_BUCKET)
    except Exception as e:
        clogger.error(f"Failed to upload JS program to S3: {e}")
        return error_response(500, "Failed to upload JS program to S3.")

    # Update model's js_program_key and save
    artifact.js_program_key = s3_key
    save_artifact_metadata(artifact)

    return json_response(
        200, {"message": f"JS program uploaded for model {artifact_id}", "s3_key": s3_key}
    )
