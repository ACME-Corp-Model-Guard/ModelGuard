import os
from types import SimpleNamespace


def pytest_configure(config):
    # Set environment variables for AWS mocking
    os.environ.setdefault("AWS_REGION", "us-east-2")
    os.environ.setdefault("ARTIFACTS_TABLE", "ArtifactsTestTable")
    os.environ.setdefault("REJECTED_ARTIFACTS_TABLE", "RejectedArtifactsTestTable")
    os.environ.setdefault("TOKENS_TABLE", "TokensTestTable")
    os.environ.setdefault("FINGERPRINTS_TABLE", "FingerprintsTestTable")
    os.environ.setdefault("ARTIFACTS_BUCKET", "test-bucket")
    os.environ.setdefault("USER_POOL_ID", "fakepool")
    os.environ.setdefault("USER_POOL_CLIENT_ID", "fakeclient")

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
