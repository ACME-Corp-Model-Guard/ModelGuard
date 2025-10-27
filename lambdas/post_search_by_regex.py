"""
Lambda function for POST /artifact/byRegEx endpoint
Search artifacts using regular expressions
"""

import json


def lambda_handler(event, context):
    """
    Stub handler for POST /artifact/byRegEx - Search by regex
    Search for artifacts using regular expression over names and READMEs
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            [
                {"name": "audience-classifier", "id": "3847247294", "type": "model"},
                {"name": "bert-base-uncased", "id": "9078563412", "type": "model"},
            ]
        ),
    }
