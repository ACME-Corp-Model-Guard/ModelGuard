"""
Pytest configuration for lambda tests.

This must run before any lambda modules are imported to properly mock AWS services.
"""

import os


def pytest_configure(config):
    """
    Configure pytest before test collection.

    This runs before pytest collects tests, ensuring environment variables
    are set before any imports that might trigger boto3 client creation.
    """
    os.environ.setdefault("AWS_REGION", "us-east-2")
    os.environ.setdefault("ARTIFACTS_TABLE", "ArtifactsTestTable")
    os.environ.setdefault("TOKENS_TABLE", "TokensTestTable")
    os.environ.setdefault("ARTIFACTS_BUCKET", "test-bucket")
    os.environ.setdefault("USER_POOL_ID", "fakepool")
    os.environ.setdefault("USER_POOL_CLIENT_ID", "fakeclient")
    os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
    os.environ.setdefault("BEDROCK_REGION", "us-east-2")
