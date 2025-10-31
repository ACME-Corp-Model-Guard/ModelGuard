"""
Lambda function for POST /artifacts endpoint
Enumerate/List artifacts from the registry
"""

import json
from typing import Any, Dict


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
