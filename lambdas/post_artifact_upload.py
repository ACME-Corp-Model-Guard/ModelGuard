"""
Lambda function for POST /artifact/{artifact_type} endpoint
Upload/Create new artifact
"""

import json
from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Stub handler for POST /artifact/{artifact_type} - Upload new artifact
    Register a new artifact by providing downloadable source URL
    """
    return {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "metadata": {
                    "name": "bert-base-uncased",
                    "id": "9078563412",
                    "type": "model",
                },
                "data": {"url": "https://huggingface.co/google-bert/bert-base-uncased"},
            }
        ),
    }
