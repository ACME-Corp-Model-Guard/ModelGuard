import json
from src.artifacts.artifactory.persistence import load_all_artifacts
from src.artifacts.artifactory.package_confusion import is_suspected_package_confusion
from src.artifacts.model_artifact import ModelArtifact
from src.logutil import log_lambda_handler, clogger
from src.utils.http import translate_exceptions
from src.auth import auth_required


@translate_exceptions
@log_lambda_handler("POST /artifact/byRegEx", log_request_body=True)
@auth_required
def lambda_handler(event, context):
    """
    Lambda entrypoint for the PackageConfusionAudit endpoint.
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
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"suspected": suspected}),
    }
