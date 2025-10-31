"""
Lambda function for PUT /artifacts/{artifact_type}/{id} endpoint
Update existing artifact
"""

import json
from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Stub handler for PUT /artifacts/{artifact_type}/{id} - Update artifact
    Update the content of an existing artifact
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Artifact updated successfully"}),
    }
