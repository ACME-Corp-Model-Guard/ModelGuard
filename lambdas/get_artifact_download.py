"""
Lambda function for GET /artifacts/{artifact_type}/{id} endpoint
Download/Retrieve artifact by type and ID
"""

import json
from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Stub handler for GET /artifacts/{artifact_type}/{id} - Download artifact
    Return artifact metadata and data URL
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "metadata": {
                    "name": "openai-whisper",
                    "id": "7364518290",
                    "type": "code",
                },
                "data": {"url": "https://github.com/openai/whisper"},
            }
        ),
    }
