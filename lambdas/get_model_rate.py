"""
Lambda function for GET /artifact/model/{id}/rate endpoint
Get ratings for model artifacts
"""

import json


def lambda_handler(event, context):
    """
    Stub handler for GET /artifact/model/{id}/rate - Rate model
    Return model rating with all required metrics from the OpenAPI spec
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "name": "stub-model",
                "category": "nlp",
                "net_score": 0.8,
                "net_score_latency": 1.5,
                "ramp_up_time": 0.7,
                "ramp_up_time_latency": 0.5,
                "bus_factor": 0.6,
                "bus_factor_latency": 0.3,
                "performance_claims": 0.9,
                "performance_claims_latency": 2.1,
                "license": 0.8,
                "license_latency": 0.2,
                "dataset_and_code_score": 0.7,
                "dataset_and_code_score_latency": 1.8,
                "dataset_quality": 0.6,
                "dataset_quality_latency": 1.2,
                "code_quality": 0.8,
                "code_quality_latency": 0.9,
                "reproducibility": 0.5,
                "reproducibility_latency": 3.2,
                "reviewedness": 0.4,
                "reviewedness_latency": 0.7,
                "tree_score": 0.7,
                "tree_score_latency": 1.1,
                "size_score": {
                    "raspberry_pi": 0.2,
                    "jetson_nano": 0.5,
                    "desktop_pc": 0.8,
                    "aws_server": 0.9,
                },
                "size_score_latency": 0.8,
            }
        ),
    }
