"""
Lambda function for POST /artifacts endpoint
Enumerate/List artifacts from the registry
"""

"""
lambdas/post_artifacts.py
POST /artifacts – list artifacts from the registry with filtering & pagination

This Lambda:
    1) Merges filters from query string + JSON body.
    2) Reads from DynamoDB.
    3) Applies optional substring + regex filters on "name".
    4) Returns a compact list of items and a pagination cursor.

Environment variables:
    ARTIFACTS_TABLE_NAME: (default: "Artifacts")
    ARTIFACTS_TYPE_GSI_NAME: (optional; name of a GSI with partition key "type")
"""

from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import boto3
from boto3.dynamodb.conditions import Attr, Key
from loguru import logger

# Config via env
ARTIFACTS_TABLE_NAME = os.getenv("ARTIFACTS_TABLE_NAME", "Artifacts")
ARTIFACTS_TYPE_GSI_NAME = os.getenv("ARTIFACTS_TYPE_GSI_NAME")                           # Optional

# Create a single, reusable DynamoDB Table client
dynamodb = boto3.resource("dynamodb")
artifacts_table = dynamodb.Table(ARTIFACTS_TABLE_NAME)

# ------------------------- Helpers: Request parsing and Validation -------------------------

def parse_request_params(api_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge query string parameters and JSON body into a single dictionary.
    Body values override query parameters when keys collide.
    """
    merged: Dict[str, Any] = {}

    # Read key = value pairs
    query_params = api_event.get("queryStringParameters") or {}
    
    if isinstance(query_params, dict):
        merged.update({k: v for k, v in query_params.items() if v is not None})

    # Read JSON body (if present)
    body = api_event.get("body:")
    if body:
        try:
            payload = json.loads(body) if isinstance(body, str) else body
            if isinstance(payload, dict):
                merged.updatye(payload)
        except Exception:
            # Non-JSON body is ignored but the request is not failed.
            logger.debug("Request body was not valid JSON; ignoring it")
    return merged

def normalize_limit(raw_limit: Any, default: int = 235, max_allowed: int = 100) -> int:
    """
    Convert 'limit' into a safe integer page size (1..max_allowed).
    """

    try:
        value = int(raw_limit)
    except Exception:
        return default
    return max(1, min(value, max_allowed))


# ---- Data access: DynamoDB (query/scan) -------------------------------------


def scan_artifacts(
    filter_params: Dict[str, Any],
    page_size: int,
    exclusive_start_key: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Fallback path when no GSI is available.
    Uses a Scan with a FilterExpression composed from provided filters.
    Returns (items, LastEvaluatedKey).
    """
    filter_expr = None

    # Optional equality on 'type'
    if filter_params.get("type"):
        filter_expr = Attr("type").eq(filter_params["type"])

    # Optional substring match on 'name'
    if filter_params.get("name_contains"):
        name_expr = Attr("name").contains(str(filter_params["name_contains"]))
        filter_expr = name_expr if filter_expr is None else filter_expr & name_expr

    # Assemble Scan arguments
    scan_kwargs: Dict[str, Any] = {"Limit": page_size}
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr
    if exclusive_start_key:
        scan_kwargs["ExclusiveStartKey"] = exclusive_start_key

    response = artifacts_table.scan(**scan_kwargs)
    return response.get("Items", []), response.get("LastEvaluatedKey")


def query_artifacts_by_type(
        artifact_type: str,
        page_size: int,
        exclusive_start_key: Optional[Dict[str, Any]],
        ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Fast path when a GSI exists on 'type'.
    Falls back to 'scan_artifacts' if ARTIFACTS_TYPE_GSI_NAME is not set.
    """
    if not ARTIFACTS_TYPE_GSI_NAME:
        # If no index available, use filtered scan instead
        return scan_artifacts({"type": artifact_type}, page_size, exclusive_start_key)

    # Query the GSI on partition key 'type'
    query_kwargs: Dict[str, Any] = {
        "IndexName": ARTIFACTS_TYPE_GSI_NAME,
        "KeyConditionExpression": Key("type").eq(artifact_type),
        "Limit": page_size,
    }

    if exclusive_start_key:
        query_kwargs["ExclusiveStartKey"] = exclusive_start_key

    response = artifacts_table.query(**query_kwargs)
    return response.get("Items", []), response.get("LastEvaluatedKey")



# ---- Post-processing: filter & shape response items -------------------------

def filter_and_format_items(
    raw_items: List[Dict[str, Any]], name_regex: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Apply optional regex on 'name' and output a compact, consistent shape:
      { "name", "id", "type", ["version"], ["updated_at"] }
    Unknown or missing items are skipped defensively.
    """
    compiled_regex = None
    if name_regex:
        try:
            compiled_regex = re.compile(name_regex, re.IGNORECASE)
        except re.error:
            logger.warning("Invalid name_regex provided; ignoring: {}", name_regex)

    formatted: List[Dict[str, Any]] = []
    for item in raw_items:
        # Normalize fields that are need with tolerance for differences in ID keys.
        name = item.get("name")
        artifact_id = item.get("id") or item.get("artifact_id") or item.get("pk")
        artifact_type = item.get("type")
        if not (name and artifact_id and artifact_type):
            # Skip partially formed records
            continue

        # Regex filter (if supplied)
        if compiled_regex and not compiled_regex.search(str(name)):
            continue

        # Whitelist a few optional, stable fields
        metadata = {k: v for k, v in item.items() if k in ("version", "updated_at")}
        formatted.append(
            {"name": name, "id": str(artifact_id), "type": artifact_type, **metadata}
        )
    return formatted



# ---- Lambda entrypoint ------------------------------------------------------

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for POST /artifacts.
    Accepts filters in query string or JSON body:
      - type: "model", "dataset", "code", etc.
      - name_contains: substring filter (DynamoDB contains)
      - name_regex: regex on name (applied after read)
      - limit: page size (1..100)
      - cursor: DynamoDB ExclusiveStartKey from previous page
    """
    params = parse_request_params(event)

    # Extract user controls
    artifact_type = params.get("type")
    name_contains = params.get("name_contains")
    name_regex = params.get("name_regex")
    page_size = normalize_limit(params.get("limit", 25))
    exclusive_start_key = params.get("cursor")  # passthrough of DynamoDB key

    logger.bind(route="/artifacts").info(
        "List artifacts",
        type=artifact_type,
        name_contains=name_contains,
        page_size=page_size)

    try:
        # Choose the mose efficient read path based on filters and indexes
        if artifact_type:
            raw_items, next_cursor = query_artifacts_by_type(
                str(artifact_type), page_size, exclusive_start_key
            )
        else:
            raw_items, next_cursor = scan_artifacts(
                {"name_contains": name_contains}, page_size, exclusive_start_key
            )

        # Client-side filtering + output shaping
        artifacts = filter_and_format_items(raw_items, name_regex)

        # Construct HTTP response payload
        response_body = {
            "items": artifacts,
            "count": len(artifacts),
            "cursor": next_cursor or None,
        }
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_body),
        }
    except Exception as exc:
        # Defensive catch-all so that the API callers get a clean 500 with no internals
        logger.exception("POST /artifacts failed: {}", exc)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Internal error"}),
        }





























def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Stub handler for POST /artifacts - Enumerate artifacts
    Returns a list of artifacts based on query parameters
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            [
                {"name": "audience-classifier", "id": "3847247294", "type": "model"},
                {"name": "bookcorpus", "id": "5738291045", "type": "dataset"},
                {"name": "google-research-bert", "id": "9182736455", "type": "code"},
            ]
        ),
    }
