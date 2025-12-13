import os


def pytest_configure():
    os.environ.setdefault("AWS_REGION", "us-east-2")
    os.environ.setdefault("ARTIFACTS_TABLE", "ArtifactsTestTable")
    os.environ.setdefault("REJECTED_ARTIFACTS_TABLE", "RejectedArtifactsTestTable")
    os.environ.setdefault("TOKENS_TABLE", "TokensTestTable")
    os.environ.setdefault("FINGERPRINTS_TABLE", "FingerprintsTestTable")
    os.environ.setdefault("ARTIFACTS_BUCKET", "test-bucket")
    os.environ.setdefault("USER_POOL_ID", "fakepool")
    os.environ.setdefault("USER_POOL_CLIENT_ID", "fakeclient")
