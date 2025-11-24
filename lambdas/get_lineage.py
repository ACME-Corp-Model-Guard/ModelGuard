"""
GET /artifact/model/{id}/lineage
Return the lineage graph for a model artifact.
"""

from typing import Any, Dict
from src.auth import AuthContext, auth_required
from src.logger import logger, with_logging
from src.storage.dynamo_utils import load_artifact_metadata, load_all_artifacts
from src.utils.http import (
    LambdaResponse,
    error_response,
    json_response,
    translate_exceptions,
)
from src.artifacts.model_artifact import ModelArtifact

#============================================================================
# Helpers
#============================================================================

def add_ancestors(root: ModelArtifact, all_artifacts: [ModelArtifact], nodes: list, edges: list):
    """
    Recursively add ancestor nodes and edges to the lineage graph.
    """
    parent_id = getattr(root, "parent_model_id", None)
    if parent_id and parent_id in all_artifacts:
        parent = all_artifacts.get(parent_id)
        if parent:
            nodes.append({
                "artifact_id": parent.artifact_id,
                "name": parent.name,
                "source": root.parent_model_source,
            })
            edges.append({
                "from": parent.artifact_id,
                "to": root.artifact_id,
                "relationship": root.parent_model_relationship,
            })
            add_ancestors(parent, all_artifacts, nodes, edges)

def add_descendants(root: ModelArtifact, all_artifacts: [ModelArtifact], nodes: list, edges: list):
    """
    Recursively add ancestor nodes and edges to the lineage graph.
    """
    for model in all_artifacts.values():
        if model.parent_id == root.artifact_id:
            nodes.append({
                "artifact_id": model.artifact_id,
                "name": model.name,
                "source": model.parent_model_source,
            })
            edges.append({
                "from": root.artifact_id,
                "to": model.artifact_id,
                "relationship": model.parent_model_relationship,
            })
            add_descendants(model, all_artifacts, nodes, edges)


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

	# ------------------------------------------------------------------
	# Step 3 - Scan all artifacts to build lineage
	# ------------------------------------------------------------------
	all_artifacts = load_all_artifacts()
	nodes = []
	edges = []

	# Add root node
	nodes.append({
		"artifact_id": root.artifact_id,
		"name": root.name,
		"source": getattr(root, "parent_model_source", "config_json")
	})

	# Recursively add ancestors (parents, grandparents, etc.)
	add_ancestors(root, all_artifacts, nodes, edges)

	# Recursively add descendants (children, grandchildren, etc.)
	add_descendants(root.artifact_id, all_artifacts, nodes, edges)

	graph = {"nodes": nodes, "edges": edges}
	return json_response(200, graph)
