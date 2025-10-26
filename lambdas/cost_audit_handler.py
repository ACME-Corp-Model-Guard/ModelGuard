"""
Cost & Audit Lambda Handler
Handles:
- GET /artifact/{artifact_type}/{id}/cost (get artifact cost)
- GET /artifact/{artifact_type}/{id}/audit (get audit trail)
"""

import json


def lambda_handler(event, context):
    """Handle cost and audit requests"""
    path = event.get("path", "")

    if "/cost" in path:
        return get_artifact_cost(event)
    elif "/audit" in path:
        return get_audit_trail(event)

    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Endpoint not found"}),
    }


def get_artifact_cost(event):
    """GET /artifact/{artifact_type}/{id}/cost - Get artifact cost"""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"123456789": {"total_cost": 412.5}}),
    }


def get_audit_trail(event):
    """GET /artifact/{artifact_type}/{id}/audit - Get audit trail"""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            [
                {
                    "user": {"name": "Stub User", "is_admin": True},
                    "date": "2024-10-26T14:22:05Z",
                    "artifact": {
                        "name": "stub-artifact",
                        "id": "123456789",
                        "type": "model",
                    },
                    "action": "CREATE",
                }
            ]
        ),
    }
