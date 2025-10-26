"""
Search Lambda Handler
Handles all search endpoints
"""

import json


def lambda_handler(event, context):
    """Stub handler for all search endpoints"""
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Search endpoint stub"}),
    }
