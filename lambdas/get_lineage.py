"""
GET /artifact/model/{id}/lineage
Return the lineage graph for a model artifact.
"""

from typing import Any, Dict
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.artifacts.artifactory import load_artifact_metadata
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)
from src.artifacts.base_artifact import BaseArtifact
from src.artifacts.model_artifact import ModelArtifact

# ============================================================================
# Helpers
# ============================================================================


def add_ancestors(root: ModelArtifact, nodes: list, edges: list) -> None:
    """
    Recursively add ancestor nodes and edges to the lineage graph.
    """
    parent_id: str | None = getattr(root, "parent_model_id", None)
    if parent_id:
        parent: BaseArtifact | None = load_artifact_metadata(parent_id)
        if parent and isinstance(parent, ModelArtifact):
            nodes.append(
                {
                    "artifact_id": parent.artifact_id,
                    "name": parent.name,
                    "source": root.parent_model_source,
                }
            )
            edges.append(
                {
                    "from": parent.artifact_id,
                    "to": root.artifact_id,
                    "relationship": root.parent_model_relationship,
                }
            )
            add_ancestors(parent, nodes, edges)


def add_descendants(root: ModelArtifact, nodes: list, edges: list) -> None:
    """
    Recursively add descendant nodes and edges to the lineage graph.
    """
    for child_model_id in getattr(root, "child_model_ids", []):
        child: BaseArtifact | None = load_artifact_metadata(child_model_id)
        if child and isinstance(child, ModelArtifact):
            nodes.append(
                {
                    "artifact_id": child.artifact_id,
                    "name": child.name,
                    "source": child.parent_model_source,
                }
            )
            edges.append(
                {
                    "from": root.artifact_id,
                    "to": child.artifact_id,
                    "relationship": child.parent_model_relationship,
                }
            )
            add_descendants(child, nodes, edges)


# =============================================================================
# Lambda Handler: GET /artifact/model/{id}/lineage
# =============================================================================
#
# Responsibilities:
#   1. Authenticate caller
#   2. Validate model id
#   3. Load model artifact metadata
#   4. Build lineage graph by scanning all artifacts
#   5. Return lineage graph response
#
# Error codes:
#   400 - missing id parameter
#   403 - auth failure (handled by @auth_required)
#   404 - artifact not found
#   500 - unexpected errors (handled by @translate_exceptions)
# =============================================================================


@translate_exceptions
@with_logging
@auth_required
def lambda_handler(
    event: Dict[str, Any],
    context: Any,
    auth: AuthContext,
) -> LambdaResponse:
    logger.info("[get_lineage] Handling lineage graph request")

    # ------------------------------------------------------------------
    # Step 1 - Extract id parameter
    # ------------------------------------------------------------------
    path_params = event.get("pathParameters") or {}
    artifact_id = path_params.get("id")

    if not artifact_id:
        return error_response(
            400,
            "Missing required path parameter: id",
            error_code="INVALID_REQUEST",
        )

    logger.debug(f"[get_lineage] Loading artifact with id={artifact_id}")

    # ------------------------------------------------------------------
    # Step 2 - Load the root model artifact
    # ------------------------------------------------------------------
    root = load_artifact_metadata(artifact_id)
    if root is None:
        return error_response(
            404,
            f"Artifact with id '{artifact_id}' does not exist",
            error_code="NOT_FOUND",
        )
    if not isinstance(root, ModelArtifact):
        return error_response(
            400,
            f"Artifact with id '{artifact_id}' is not a model",
            error_code="INVALID_ARTIFACT_TYPE",
        )

    # ------------------------------------------------------------------
    # Step 3 - Build lineage graph
    # ------------------------------------------------------------------
    nodes: list[dict] = []
    edges: list[dict] = []

    # Add root node
    nodes.append(
        {
            "artifact_id": root.artifact_id,
            "name": root.name,
            "source": getattr(root, "parent_model_source", "config_json"),
        }
    )

    # Recursively add ancestors (parents, grandparents, etc.)
    add_ancestors(root, nodes, edges)

    # Recursively add descendants (children, grandchildren, etc.)
    add_descendants(root, nodes, edges)

    graph = {"nodes": nodes, "edges": edges}
    return json_response(200, graph)
