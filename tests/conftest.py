import os
from types import SimpleNamespace

import pytest


def pytest_configure(config):
    # Set environment variables for AWS mocking
    os.environ.setdefault("AWS_REGION", "us-east-2")
    os.environ.setdefault("ARTIFACTS_TABLE", "ArtifactsTestTable")
    os.environ.setdefault("REJECTED_ARTIFACTS_TABLE", "RejectedArtifactsTestTable")
    os.environ.setdefault("TOKENS_TABLE", "TokensTestTable")
    os.environ.setdefault("FINGERPRINTS_TABLE", "FingerprintsTestTable")
    os.environ.setdefault("USER_PERMISSIONS_TABLE", "UserPermissionsTestTable")
    os.environ.setdefault("ARTIFACTS_BUCKET", "test-bucket")
    os.environ.setdefault("USER_POOL_ID", "fakepool")
    os.environ.setdefault("USER_POOL_CLIENT_ID", "fakeclient")
    os.environ.setdefault("JS_RUNNER_LAMBDA_NAME", "js-runner-test-lambda")
    os.environ.setdefault("JS_PROGRAMS_BUCKET", "js-programs-test-bucket")

    # Patch urllib3 before any modules are imported during collection.
    # This is necessary because src/auth.py loads JWKS at import time.
    mock_response = SimpleNamespace(json=lambda: {"keys": [{"kid": "testkid"}]})

    import urllib3

    original_request = urllib3.PoolManager.request

    def mock_request(self, method, url, *args, **kwargs):
        if "jwks.json" in url:
            return mock_response
        return original_request(self, method, url, *args, **kwargs)

    urllib3.PoolManager.request = mock_request


@pytest.fixture(autouse=True)
def reset_aws_clients():
    """
    Reset cached AWS clients before each test.

    This ensures that moto mocking works correctly when tests are run together.
    Without this, a client cached outside the @mock_aws context would persist
    and point to real AWS instead of the mocked AWS.
    """
    from src.aws.clients import reset_clients

    reset_clients()
    yield
    reset_clients()
