"""
Logic for handling JS programs associated with model artifacts.
"""

import json
import os
import boto3

from src.artifacts.model_artifact import ModelArtifact
from src.logutil import clogger
from src.settings import JS_RUNNER_LAMBDA_NAME, JS_PROGRAMS_BUCKET
from src.storage.s3_utils import download_file

lambda_client = boto3.client("lambda")


def run_js_program(model_artifact: ModelArtifact, input_args: dict) -> bool:
    """
    Execute JS program and return True if it succeeds.
    Raises if it fails.

    Args:
        model_artifact: ModelArtifact with associated JS program
        input_args: Dict of input args to pass to the JS program
    """
    js_program_key = model_artifact.js_program_key
    if not js_program_key:
        raise ValueError("No JS program associated with this model artifact.")

    tmp_js_path = f"/tmp/{model_artifact.artifact_id}.js"

    try:
        download_file(
            s3_key=js_program_key,
            local_path=tmp_js_path,
            bucket=JS_PROGRAMS_BUCKET,
        )

        with open(tmp_js_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        payload = {
            "js_code": js_code,
            "input": input_args,
        }

        clogger.info(
            "Invoking JS program",
            extra={"artifact_id": model_artifact.artifact_id},
        )

        response = lambda_client.invoke(
            FunctionName=JS_RUNNER_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8"),
        )

        if "FunctionError" in response:
            error = json.loads(response["Payload"].read())
            raise RuntimeError(f"JS program failed: {error}")

        return True

    finally:
        try:
            os.remove(tmp_js_path)
        except FileNotFoundError:
            pass
