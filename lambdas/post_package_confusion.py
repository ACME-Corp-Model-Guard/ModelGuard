"""
Lambda function for POST /artifacts/PackageConfusionAudit
Returns a list of suspected package confusion model uploads.

OpenAPI Spec:
Response 200: {
    "suspected": [
        {
            "artifact_id": str,
            "name": str,
            "source_url": str,
            "metadata": dict
        },
        ...
    ]
}
Response 401: Authentication failed.
"""

import json
from src.artifacts.artifactory.persistence import load_all_artifacts
from src.artifacts.artifactory.package_confusion import is_suspected_package_confusion
from src.artifacts.model_artifact import ModelArtifact
from src.logutil import log_lambda_handler, clogger
from src.utils.http import (
    translate_exceptions,
    LambdaResponse,
    json_response,
)
from src.auth import auth_required, AuthContext
from typing import Dict, Any


@translate_exceptions
@log_lambda_handler("POST /artifacts/PackageConfusionAudit", log_request_body=True)
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    """
    Lambda entrypoint for the /artifacts/PackageConfusionAudit endpoint.
    Returns a list of suspected package confusion model uploads.
    """
    # Load all model artifacts
    all_artifacts = load_all_artifacts()
    suspected = []
    for artifact in all_artifacts:
        if isinstance(artifact, ModelArtifact):
            try:
                if is_suspected_package_confusion(artifact):
                    suspected.append(
                        {
                            "artifact_id": artifact.artifact_id,
                            "name": artifact.name,
                            "source_url": artifact.source_url,
                            "metadata": artifact.metadata,
                        }
                    )
            except Exception as e:
                # Log and skip problematic artifacts
                clogger.error(
                    f"Error evaluating package confusion for artifact "
                    f"{artifact.artifact_id}: {e}"
                )
                pass
    return json_response(
        statusCode=200,
        body=json.dumps({"suspected": suspected}),
    )
