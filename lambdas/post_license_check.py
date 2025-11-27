"""
POST /artifact/model/{id}/license-check
Assess license compatibility for fine-tune and inference usage.

Spec Summary:
  - Path parameter: id (artifact_id)
  - Body:
        { "github_url": "<repo_url>" }
  - Response: boolean indicating compatibility
  - Errors:
        400 - malformed request
        403 - authentication failure (handled by @auth_required)
        404 - artifact or GitHub project not found
        502 - external license info could not be retrieved
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests

from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.artifacts.artifactory import load_artifact_metadata
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)


# =============================================================================
# Helper: Fetch GitHub License
# =============================================================================


def fetch_github_license(github_url: str) -> Optional[str]:
    """
    Retrieve SPDX license ID for the given GitHub repository.
    Returns None if repo exists but has no license.
    Raises ValueError for invalid or not-found repos.
    """
    try:
        # Extract owner/repo
        parts = github_url.rstrip("/").split("/")
        if len(parts) < 2:
            raise ValueError("Invalid GitHub URL")

        owner, repo = parts[-2], parts[-1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        resp = requests.get(api_url)

        if resp.status_code == 404:
            raise ValueError(f"GitHub Repository Not Found: {github_url}")

        if resp.status_code != 200:
            raise ValueError(
                f"GitHub API Error ({resp.status_code}) for repository {github_url}"
            )

        license_info = resp.json().get("license")
        if not license_info:
            return None

        return license_info.get("spdx_id")

    except Exception as e:
        logger.error(f"[license_check] GitHub license fetch error: {e}")
        raise


# =============================================================================
# Lambda Handler: POST /artifact/model/{id}/license-check
# =============================================================================
#
# Responsibilities:
#   1. Authenticate caller
#   2. Parse path and request body
#   3. Load artifact metadata from DynamoDB
#   4. Fetch GitHub license via external API
#   5. Compare artifact metadata license to GitHub repo license
#   6. Return boolean per spec
#
# Error Codes:
#   400 - missing or malformed body/path
#   403 - authentication failure (@auth_required)
#   404 - artifact or GitHub repo not found
#   502 - GitHub API errors
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    logger.info("[license_check] Handling POST /artifact/model/{id}/license-check")

    # ---------------------------------------------------------------------
    # Step 1 — Extract and validate artifact ID
    # ---------------------------------------------------------------------
    artifact_id = event.get("pathParameters", {}).get("id")
    if not artifact_id:
        return error_response(
            400,
            "Missing required path parameter: id",
            error_code="INVALID_REQUEST",
        )

    # ---------------------------------------------------------------------
    # Step 2 — Load artifact from DynamoDB
    # ---------------------------------------------------------------------
    artifact = load_artifact_metadata(artifact_id)
    if not artifact:
        return error_response(404, f"Artifact '{artifact_id}' not found")

    # License is part of the artifact metadata dict
    artifact_license = artifact.metadata.get("license")

    # ---------------------------------------------------------------------
    # Step 3 — Parse JSON request body
    # ---------------------------------------------------------------------
    raw_body = event.get("body", "{}")

    try:
        body = json.loads(raw_body)
    except Exception:
        return error_response(
            400,
            "Malformed JSON body",
            error_code="INVALID_REQUEST",
        )

    github_url = body.get("github_url")
    if not github_url:
        return error_response(
            400,
            "Missing required field: github_url",
            error_code="INVALID_REQUEST",
        )

    # ---------------------------------------------------------------------
    # Step 4 — Fetch GitHub license using external API
    # ---------------------------------------------------------------------
    try:
        github_license = fetch_github_license(github_url)
    except ValueError as ve:
        # Repo not found or invalid URL
        return error_response(404, str(ve))
    except Exception as e:
        # External API error → 502 per spec
        return error_response(
            502,
            f"Failed to retrieve external license info: {e}",
            error_code="GITHUB_API_ERROR",
        )

    # ---------------------------------------------------------------------
    # Step 5 — Compare licenses → boolean
    # ---------------------------------------------------------------------
    is_compatible = artifact_license == github_license

    # POST /license-check must return **only a boolean**
    return json_response(200, is_compatible)
