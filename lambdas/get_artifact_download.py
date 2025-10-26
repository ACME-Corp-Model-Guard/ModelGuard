"""
Lambda function for GET /artifacts/{artifact_type}/{id} endpoint
Download/Retrieve artifact by type and ID
"""

import json


def lambda_handler(event, context):
    """
    Stub handler for GET /artifacts/{artifact_type}/{id} - Download artifact
    Return artifact metadata and data URL
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "metadata": {
                "name": "openai-whisper",
                "id": "7364518290",
                "type": "code"
            },
            "data": {
                "url": "https://github.com/openai/whisper"
            }
        })
    }