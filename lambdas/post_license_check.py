import json
from typing import Any, Dict, Optional

import requests

from src.logger import logger
from src.artifacts.utils.metadata_storage import load_artifact_from_dynamodb


def check_github_license(github_url: str) -> Optional[str]:
    """
    Fetch the license from the GitHub repository.
    Returns SPDX id string if license found, otherwise None.
    """
    try:
        # Extract Owner/Repo From URL
        parts = github_url.rstrip("/").split("/")
        if len(parts) < 2:
            raise ValueError("Invalid GitHub URL")
        owner, repo = parts[-2], parts[-1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        # Fetch License via GitHub API
        response = requests.get(api_url)
        if response.status_code != 200:
            raise ValueError(f"GitHub Repository Not Found: {github_url}")
        license_info = response.json().get("license")

        if not license_info:
            return None

        return license_info.get("spdx_id")

    except Exception as e:
        logger.error(f"Error Fetching License For {github_url}: {e}", exc_info=True)
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for /artifact/model/{id}/license-check.
    Compares the license stored in the artifact metadata to the GitHub repo license.
    """
    # Extract artifact (model) ID
    artifact_id: Optional[str] = event.get("pathParameters", {}).get("id")
    if not artifact_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing Artifact Id In Path"}),
        }

    try:
        # Load artifact (model) from DynamoDB
        artifact = load_artifact_from_dynamodb(artifact_id)
        if not artifact:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Artifact {artifact_id} Not Found"}),
            }

        # Extract GitHub URL from request body
        body = json.loads(event.get("body", "{}"))
        github_url: Optional[str] = body.get("github_url")
        if not github_url:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing Github_Url In Request Body"}),
            }

        # Get the license stored in artifact metadata
        artifact_license: Optional[str] = getattr(artifact, "license", None)
        if not artifact_license:
            logger.warning(
                f"Artifact {artifact_id} does not have a license in metadata"
            )

        # Fetch license from GitHub
        github_license = check_github_license(github_url)

        # Compare artifact license to GitHub license
        is_compatible = artifact_license == github_license

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "artifact_license": artifact_license,
                    "github_license": github_license,
                    "is_compatible": is_compatible,
                }
            ),
        }

    except ValueError as ve:
        logger.error(f"Error Fetching License For {github_url}: {ve}", exc_info=True)
        return {"statusCode": 404, "body": json.dumps({"error": str(ve)})}

    except Exception as e:
        logger.error(f"Error Fetching License For {github_url}: {e}", exc_info=True)
        return {
            "statusCode": 502,
            "body": json.dumps({"error": f"License Check Failed: {str(e)}"}),
        }
