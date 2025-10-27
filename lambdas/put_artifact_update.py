"""
Lambda function for PUT /artifacts/{artifact_type}/{id} endpoint
Update existing artifact
"""

import json


def lambda_handler(event, context):
    """
    Stub handler for PUT /artifacts/{artifact_type}/{id} - Update artifact
    Update the content of an existing artifact
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Artifact updated successfully"}),
    }
