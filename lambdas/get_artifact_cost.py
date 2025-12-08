"""
GET /artifact/{artifact_type}/{id}/cost
Return the size cost (in MB) of an artifact and optionally its dependencies.
Measured by the S3 object size of the stored artifact bundle.
"""

from __future__ import annotations

from typing import Any, Dict

from src.auth import AuthContext, auth_required
from src.aws.clients import get_s3
from src.logger import logger, with_logging
from src.settings import ARTIFACTS_BUCKET
from src.artifacts.artifactory import load_artifact_metadata
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)

VALID_TYPES = {"model", "dataset", "code"}


# =============================================================================
# Helper: Get artifact size in MB
# =============================================================================


def _get_artifact_size_mb(artifact_id: str, s3_key: str) -> float:
    """
    Get the size of an artifact in MB from S3.
    Returns 0.0 if the object doesn't exist or an error occurs.
    """
    s3 = get_s3()
    try:
        logger.debug(f"[artifact_cost] HEAD s3://{ARTIFACTS_BUCKET}/{s3_key}")
        head = s3.head_object(Bucket=ARTIFACTS_BUCKET, Key=s3_key)
        size_bytes = int(head.get("ContentLength", 0))
        size_mb = size_bytes / (1024 * 1024)  # Convert bytes to MB
        return round(size_mb, 2)
    except Exception as e:
        logger.warning(f"[artifact_cost] Failed HEAD for artifact {artifact_id}: {e}")
        return 0.0


def _calculate_costs_with_dependencies(
    artifact_id: str,
    visited: set[str] | None = None,
) -> Dict[str, Dict[str, float]]:
    """
    Recursively calculate costs for an artifact and all its dependencies.
    Returns a dict mapping artifact_id -> {"standalone_cost": X, "total_cost": Y}
    """
    if visited is None:
        visited = set()

    # Avoid circular dependencies
    if artifact_id in visited:
        return {}

    visited.add(artifact_id)
    costs: Dict[str, Dict[str, float]] = {}

    # Load artifact metadata
    artifact = load_artifact_metadata(artifact_id)
    if artifact is None:
        return {}

    # Calculate standalone cost for this artifact
    standalone_cost = _get_artifact_size_mb(artifact_id, artifact.s3_key)
    total_cost = standalone_cost

    # Get connected artifacts (dependencies)
    connected_ids = getattr(artifact, "connected_artifacts", [])

    # Recursively calculate costs for dependencies
    for dep_id in connected_ids:
        dep_costs = _calculate_costs_with_dependencies(dep_id, visited)
        costs.update(dep_costs)

        # Add dependency's total cost to this artifact's total
        if dep_id in dep_costs:
            total_cost += dep_costs[dep_id]["total_cost"]

    # Store this artifact's costs
    costs[artifact_id] = {
        "standalone_cost": standalone_cost,
        "total_cost": total_cost,
    }

    return costs


# =============================================================================
# Lambda Handler: GET /artifact/{artifact_type}/{id}/cost
# =============================================================================
#
# Responsibilities:
#   1. Authenticate user
#   2. Validate artifact_type and id path parameters
#   3. Parse dependency query parameter
#   4. Load artifact metadata from DynamoDB
#   5. Perform S3 HEAD request to fetch object size
#   6. If dependency=true, recursively calculate costs for all dependencies
#   7. Return ArtifactCost response per OpenAPI spec
#
# Error codes:
#   400 - invalid artifact_type or missing/malformed id
#   403 - authentication failure (handled by @auth_required)
#   404 - artifact not found in DynamoDB
#   500 - S3 HEAD failure or internal error (handled by @translate_exceptions)
# =============================================================================


@with_logging
@translate_exceptions
@auth_required
def lambda_handler(
    event: Dict[str, Any], context: Any, auth: AuthContext
) -> LambdaResponse:
    logger.info("[artifact_cost] Handling artifact cost request")

    # ----------------------------------------------------------------------
    # Step 1 - Extract path parameters
    # ----------------------------------------------------------------------
    path_params = event.get("pathParameters") or {}
    artifact_type = (path_params.get("artifact_type") or "").lower().strip()
    artifact_id = path_params.get("id")

    if not artifact_type or not artifact_id:
        return error_response(
            400,
            "Missing required path parameters: artifact_type or id",
            error_code="INVALID_REQUEST",
        )

    # ----------------------------------------------------------------------
    # Step 2 - Validate artifact_type
    # ----------------------------------------------------------------------
    if artifact_type not in VALID_TYPES:
        return error_response(
            400,
            f"Invalid artifact_type '{artifact_type}'",
            error_code="INVALID_ARTIFACT_TYPE",
        )

    # ----------------------------------------------------------------------
    # Step 3 - Parse dependency query parameter
    # ----------------------------------------------------------------------
    query_params = event.get("queryStringParameters") or {}
    dependency_param = query_params.get("dependency", "false").lower()
    include_dependencies = dependency_param in ("true", "1", "yes")

    logger.debug(
        f"[artifact_cost] artifact_type={artifact_type}, artifact_id={artifact_id}, "
        f"include_dependencies={include_dependencies}"
    )

    # ----------------------------------------------------------------------
    # Step 4 - Load metadata from DynamoDB
    # ----------------------------------------------------------------------
    artifact = load_artifact_metadata(artifact_id)
    if artifact is None:
        return error_response(404, f"Artifact '{artifact_id}' does not exist")

    # Validate type consistency
    if artifact.artifact_type != artifact_type:
        return error_response(
            400,
            f"Artifact {artifact_id} is type '{artifact.artifact_type}', not '{artifact_type}'",
            error_code="TYPE_MISMATCH",
        )

    # ----------------------------------------------------------------------
    # Step 5 - Calculate costs based on dependency parameter
    # ----------------------------------------------------------------------
    response_body: Dict[str, Any]

    if include_dependencies:
        # Include dependencies: return all artifacts with standalone + total costs
        costs = _calculate_costs_with_dependencies(artifact_id)
        response_body = costs
    else:
        # No dependencies: return only this artifact with total_cost
        size_mb = _get_artifact_size_mb(artifact_id, artifact.s3_key)
        response_body = {
            artifact_id: {
                "total_cost": size_mb,
            }
        }

    return json_response(200, response_body)
