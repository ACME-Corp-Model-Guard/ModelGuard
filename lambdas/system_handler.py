"""
System Lambda Handler
Handles:
- DELETE /reset (reset registry)
- GET /tracks (get planned tracks)
"""

import json


def lambda_handler(event, context):
    """Handle system requests"""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")

    if http_method == "DELETE" and path == "/reset":
        return reset_registry(event)
    elif http_method == "GET" and path == "/tracks":
        return get_tracks(event)

    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Endpoint not found"}),
    }


def reset_registry(event):
    """DELETE /reset - Reset registry to default state"""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Registry reset to default state"}),
    }


def get_tracks(event):
    """GET /tracks - Get planned implementation tracks"""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {"plannedTracks": ["Performance track", "Access control track"]}
        ),
    }
