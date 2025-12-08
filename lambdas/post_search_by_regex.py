"""
Lambda function for POST /artifact/byRegEx endpoint
Search artifacts using regular expressions over artifact names and README-like metadata.

OpenAPI spec:
- Request body: ArtifactRegEx {"regex": "<pattern>"}
- Response 200: array of ArtifactMetadata objects
- 400: missing/invalid regex
- 403: auth failure (handled by auth_required)
- 404: no artifacts found
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any, Dict, List, Pattern

from src.artifacts.artifactory import load_all_artifacts
from src.artifacts.base_artifact import BaseArtifact
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.storage.file_extraction import extract_relevant_files
from src.storage.s3_utils import download_artifact_from_s3
from src.utils.http import (
    LambdaResponse,
    error_response,
    translate_exceptions,
    DEFAULT_HEADERS,
)

# =============================================================================
# Request Parsing
# =============================================================================


def _load_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse the request body into a dictionary.

    Accepts both a JSON string (normal API Gateway) and a dict (for unit testing).
    Raises ValueError if the body cannot be parsed as JSON.
    """

    raw_body = event.get("body", {})

    # Already a dict (e.g. in tests)
    if isinstance(raw_body, dict):
        return raw_body

    if raw_body is None or raw_body == "":
        return {}

    if not isinstance(raw_body, str):
        raise ValueError("Request body must be a JSON object or JSON string.")

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Request body must be valid JSON: {exc}") from exc


def _parse_regex(event: Dict[str, Any]) -> Pattern[str]:
    """
    Extract and validate the 'regex' field from the request body.

    - Must be present.
    - Must be a non-empty string.
    - Must compile as avalid regular expression.
    """

    body = _load_body(event)

    pattern = body.get("regex")
    if not isinstance(pattern, str) or not pattern.strip():
        raise ValueError("Missing required field: 'regex'")

    try:
        compiled = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}") from exc
    return compiled


# =============================================================================
# Search logic
# =============================================================================


def _extract_readme_from_s3(artifact: BaseArtifact) -> str:
    """
    Download artifact from S3 and extract README content.

    Args:
        artifact: Artifact to extract README from

    Returns:
        README text content, or empty string if no README found or error occurs
    """
    # Skip if no S3 key
    if not artifact.s3_key:
        logger.debug(
            f"[post_search_by_regex] Artifact {artifact.artifact_id} has no s3_key, "
            "skipping README fetch"
        )
        return ""

    tmp_tar = None
    try:
        # Create temp file for download
        tmp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz").name

        # Download artifact from S3
        logger.debug(
            f"[post_search_by_regex] Downloading artifact {artifact.artifact_id} from S3"
        )
        download_artifact_from_s3(
            artifact_id=artifact.artifact_id,
            s3_key=artifact.s3_key,
            local_path=tmp_tar,
        )

        # Extract README (prioritize README files, limit to 1 file)
        files = extract_relevant_files(
            tar_path=tmp_tar,
            include_ext=[".md", ".txt"],
            max_files=1,
            max_chars=4000,
            prioritize_readme=True,
        )

        if not files:
            logger.debug(
                f"[post_search_by_regex] No README found for artifact {artifact.artifact_id}"
            )
            return ""

        # Get first (and only) file content
        readme_text = list(files.values())[0]
        logger.debug(
            f"[post_search_by_regex] Extracted README ({len(readme_text)} chars) "
            f"for artifact {artifact.artifact_id}"
        )
        return readme_text

    except Exception as e:
        logger.warning(
            f"[post_search_by_regex] Failed to extract README for artifact "
            f"{artifact.artifact_id}: {e}"
        )
        return ""

    finally:
        # Clean up temp file
        if tmp_tar and os.path.exists(tmp_tar):
            try:
                os.unlink(tmp_tar)
            except Exception as e:
                logger.warning(
                    f"[post_search_by_regex] Failed to remove temp file {tmp_tar}: {e}"
                )


def _build_search_text(artifact: BaseArtifact, readme_text: str = "") -> str:
    """
    Build a text blob to run the regex against.

    Always include:
    - artifact.name
    - any string-valued metadata fields (this is where README-like content or descriptions
    are likely to reside).
    - README text (if provided)

    Args:
        artifact: Artifact to build search text for
        readme_text: Optional README content to include in search text

    Returns:
        Concatenated text blob for regex matching
    """

    parts: List[str] = []

    if getattr(artifact, "name", None):
        parts.append(str(artifact.name))

    metadata = getattr(artifact, "metadata", None)
    if isinstance(metadata, dict):
        for value in metadata.values():
            parts.append(value)

    # Include README if provided
    if readme_text:
        parts.append(readme_text)

    return "\n".join(parts)


def _search_artifacts(pattern: Pattern[str]) -> List[Dict[str, str]]:
    """
    Apply the regex to all artifacts and return a list of ArtifactMetadata-like
    dicts: { "name": ..., "id": ..., "type": ... }.

    Searches artifact name, metadata, and README content (fetched from S3).
    """
    artifacts = load_all_artifacts()
    logger.info(
        f"[post_search_by_regex] Loaded {len(artifacts)} artifacts for regex search"
    )

    matches: List[Dict[str, str]] = []

    for artifact in artifacts:
        # Extract README from S3 for this artifact
        readme_text = _extract_readme_from_s3(artifact)

        # Build searchable text including README
        haystack = _build_search_text(artifact, readme_text=readme_text)
        if not haystack:
            continue

        if pattern.search(haystack):
            # NOTE: only use valid BaseArtifact attributes here:
            #   - artifact.name
            #   - artifact.artifact_id
            #   - artifact.artifact_type
            matches.append(
                {
                    "name": artifact.name,
                    "id": artifact.artifact_id,
                    "type": artifact.artifact_type,
                }
            )

    logger.info(f"[post_search_by_regex] Found {len(matches)} matching artifacts")
    return matches


# =============================================================================
# Lambda handler: POST /artifact/byRegEx
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any], context: Any, auth: AuthContext
) -> LambdaResponse:
    """
    Stub handler for POST /artifact/byRegEx - Search by regex
    Search for artifacts using regular expression over names and READMEs

    Handle POST /artifact/byRegEx.

    On success:
    - 200 with a JSON array of ArtifactMetadata objects.

    On error:
    - 400 for bad or mission regex.
    - 404 if no artifacts match.
    - 403 / 500 handled by decorators and error_response.
    """
    logger.info("[post_search_by_regex] Handling regex search request")
    # ------------------------------------------------------------------
    # Step 1 - Parse and validate regex from body
    # ------------------------------------------------------------------
    try:
        pattern = _parse_regex(event)
    except ValueError as exc:
        logger.warning(f"[post_search_by_regex] Invalid request: {exc}")
        return error_response(400, str(exc), error_code="INVALID_ARTIFACT_REGEX")

    # ------------------------------------------------------------------
    # Step 2 - Execute search
    # ------------------------------------------------------------------
    results = _search_artifacts(pattern)

    if not results:
        return error_response(
            404, "No artifact found under this regex", error_code="NOT_FOUND"
        )

    # ------------------------------------------------------------------
    # Step 3 - Build response
    # ------------------------------------------------------------------
    # We manually construct the LambdaResponse so we can legally return
    # a top-level JSON array (`results`) without fighting json_response's
    # stricter type annotation.
    return LambdaResponse(
        statusCode=200,
        headers=DEFAULT_HEADERS,
        body=json.dumps(results),
    )
