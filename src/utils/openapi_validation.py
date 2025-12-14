"""
OpenAPI schema validation utilities for logging.

Validates requests/responses against OpenAPI spec for compliance tracking.
This module is used by the @log_lambda_handler decorator to detect API spec drift.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# Load OpenAPI spec at module level (cold start once per Lambda instance)
SPEC_PATH = Path(__file__).parent.parent.parent / "ece461_fall_2025_openapi_spec.yaml"

try:
    with open(SPEC_PATH) as f:
        OPENAPI_SPEC = yaml.safe_load(f)
except FileNotFoundError:
    # Graceful fallback if spec file not found
    OPENAPI_SPEC = {}


def _normalize_path(path: str) -> str:
    """
    Normalize API Gateway path to OpenAPI path format.

    API Gateway paths like /artifacts/model/123 need to be normalized to
    /artifacts/{artifact_type}/{id} to match OpenAPI spec.

    Args:
        path: Actual request path from API Gateway

    Returns:
        Normalized path matching OpenAPI spec format
    """
    # Common path normalizations
    # /artifact/model/abc-123 -> /artifact/{artifact_type}/{id}
    # /artifacts/model/abc-123 -> /artifacts/{artifact_type}/{id}
    # /artifact/byName/MyModel -> /artifact/byName/{name}
    # /artifact/model/abc-123/rate -> /artifact/model/{id}/rate

    path = path.rstrip("/")

    # Map of path patterns to OpenAPI spec paths
    path_patterns = [
        (r"/artifacts/(model|dataset|code)/[^/]+$", "/artifacts/{artifact_type}/{id}"),
        (
            r"/artifact/(model|dataset|code)/[^/]+/cost$",
            "/artifact/{artifact_type}/{id}/cost",
        ),
        (r"/artifact/model/[^/]+/rate$", "/artifact/model/{id}/rate"),
        (r"/artifact/model/[^/]+/lineage$", "/artifact/model/{id}/lineage"),
        (r"/artifact/model/[^/]+/license-check$", "/artifact/model/{id}/license-check"),
        (r"/artifact/byName/[^/]+$", "/artifact/byName/{name}"),
        (r"/artifact/(model|dataset|code)$", "/artifact/{artifact_type}"),
    ]

    import re

    for pattern, openapi_path in path_patterns:
        if re.match(pattern, path):
            return openapi_path

    return path


def validate_request(
    endpoint: str,
    method: str,
    headers: Dict[str, Any],
    query_params: Dict[str, Any],
    path_params: Dict[str, Any],
    body: Any,
) -> Tuple[bool, List[str]]:
    """
    Validate request against OpenAPI spec.

    Args:
        endpoint: API Gateway path (e.g., /artifacts/model/123)
        method: HTTP method (GET, POST, PUT, DELETE)
        headers: Request headers dict
        query_params: Query string parameters
        path_params: Path parameters
        body: Request body (string or dict)

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    if not OPENAPI_SPEC:
        return True, []  # Can't validate without spec

    violations = []

    # Normalize path to OpenAPI format
    normalized_path = _normalize_path(endpoint)

    # Find endpoint in spec
    paths = OPENAPI_SPEC.get("paths", {})
    path_spec = paths.get(normalized_path)

    if not path_spec:
        # Try exact match as fallback
        path_spec = paths.get(endpoint)

    if not path_spec:
        violations.append(f"Endpoint {endpoint} not found in OpenAPI spec")
        return False, violations

    # Find method spec
    method_spec = path_spec.get(method.lower())
    if not method_spec:
        violations.append(f"Method {method} not defined for {endpoint} in OpenAPI spec")
        return False, violations

    # Validate required headers
    parameters = method_spec.get("parameters", [])
    for param in parameters:
        if param.get("in") == "header" and param.get("required"):
            param_name = param["name"]
            # Headers are case-insensitive, normalize to lowercase for comparison
            headers_lower = {k.lower(): v for k, v in headers.items()}
            if param_name.lower() not in headers_lower:
                violations.append(f"Missing required header: {param_name}")

    # Validate required query params
    for param in parameters:
        if param.get("in") == "query" and param.get("required"):
            param_name = param["name"]
            if param_name not in query_params:
                violations.append(f"Missing required query param: {param_name}")

    # Validate request body if present
    request_body_spec = method_spec.get("requestBody")
    if request_body_spec:
        if request_body_spec.get("required") and not body:
            violations.append("Missing required request body")

    return len(violations) == 0, violations


def validate_response(
    endpoint: str,
    method: str,
    status_code: int,
    body: Any,
) -> Tuple[bool, List[str]]:
    """
    Validate response against OpenAPI spec.

    Args:
        endpoint: API Gateway path (e.g., /artifacts/model/123)
        method: HTTP method (GET, POST, PUT, DELETE)
        status_code: HTTP response status code
        body: Response body (string or dict)

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    if not OPENAPI_SPEC:
        return True, []  # Can't validate without spec

    violations = []

    # Normalize path to OpenAPI format
    normalized_path = _normalize_path(endpoint)

    # Find endpoint in spec
    paths = OPENAPI_SPEC.get("paths", {})
    path_spec = paths.get(normalized_path)

    if not path_spec:
        # Try exact match as fallback
        path_spec = paths.get(endpoint)

    if not path_spec:
        return True, []  # Can't validate unknown endpoint

    # Find method spec
    method_spec = path_spec.get(method.lower())
    if not method_spec:
        return True, []  # Can't validate unknown method

    # Check if status code is defined
    responses = method_spec.get("responses", {})
    status_str = str(status_code)

    if status_str not in responses:
        # Check for default response
        if "default" not in responses:
            violations.append(
                f"Status code {status_code} not defined in spec for {method} {endpoint}"
            )

    # Could add deeper schema validation here using jsonschema library
    # For now, we only validate that the status code is documented

    return len(violations) == 0, violations
