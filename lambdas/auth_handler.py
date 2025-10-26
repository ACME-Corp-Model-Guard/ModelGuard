"""
Authentication Lambda Handler
Handles: PUT /authenticate
"""

import json


def lambda_handler(event, context):
    """Stub handler for authentication"""
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Authentication endpoint stub"}),
    }
