"""
Lambda function for GET /artifact/byName/{name} endpoint
Search artifacts by name
"""

import json
from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Stub handler for GET /artifact/byName/{name} - Search by name
    Return artifact metadata entries that match the provided name
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            [
                {"name": "audience-classifier", "id": "3847247293", "type": "model"},
                {"name": "audience-classifier", "id": "3847247294", "type": "model"},
            ]
        ),
    }
