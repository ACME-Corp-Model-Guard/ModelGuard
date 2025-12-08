"""
Tests for POST /artifact/byRegEx endpoint with README search support.
"""

import os

# Set environment variables BEFORE any imports that might trigger boto3 clients
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("ARTIFACTS_TABLE", "ArtifactsTestTable")
os.environ.setdefault("TOKENS_TABLE", "TokensTestTable")
os.environ.setdefault("ARTIFACTS_BUCKET", "test-bucket")
os.environ.setdefault("USER_POOL_ID", "fakepool")
os.environ.setdefault("USER_POOL_CLIENT_ID", "fakeclient")
os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
os.environ.setdefault("BEDROCK_REGION", "us-east-2")

import json  # noqa: E402
import tarfile  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

import boto3  # noqa: E402
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402

from src.artifacts.model_artifact import ModelArtifact  # noqa: E402


# =============================================================================
# Fixtures for Mocking Auth (must come before imports)
# =============================================================================


@pytest.fixture(autouse=True)
def mock_jwks(mocker):
    """Mock JWKS loading before auth module import."""
    mock_req = mocker.patch(
        "urllib3.PoolManager.request",
        return_value=SimpleNamespace(json=lambda: {"keys": [{"kid": "testkid"}]}),
    )
    return mock_req


@pytest.fixture(autouse=True)
def mock_ddb_table(mocker):
    """Mock DynamoDB table for tokens."""
    mock_table = MagicMock()
    mocker.patch(
        "boto3.resource", return_value=MagicMock(Table=lambda name: mock_table)
    )
    return mock_table


# =============================================================================
# Helper Functions
# =============================================================================


def create_tar(tmp_path: Path, files: dict[str, str]) -> str:
    """Create a tar.gz file with named entries and contents."""
    tar_path = tmp_path / "test.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name, content in files.items():
            file_path = tmp_path / name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            tar.add(file_path, arcname=name)
    return str(tar_path)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_s3():
    """Mock S3 service."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-2")
        s3.create_bucket(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "us-east-2"},
        )
        yield s3


@pytest.fixture
def sample_artifact():
    """Create a sample artifact for testing."""
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com/model",
        s3_key="models/test-123",
        metadata={"description": "A test model"},
    )
    artifact.artifact_id = "test-123"
    artifact.artifact_type = "model"
    return artifact


# =============================================================================
# Unit Tests: _extract_readme_from_s3()
# =============================================================================


def test_extract_readme_from_s3_success(mock_s3, sample_artifact, tmp_path):
    """Test successful README extraction from S3."""
    from lambdas.post_search_by_regex import _extract_readme_from_s3

    # Create tar.gz with README
    tar_path = create_tar(
        tmp_path, {"README.md": "# Test Model\n\nThis is a test model README."}
    )

    # Upload to S3
    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=sample_artifact.s3_key, Body=f)

    # Test extraction
    readme_text = _extract_readme_from_s3(sample_artifact)

    assert "Test Model" in readme_text
    assert "test model README" in readme_text


def test_extract_readme_from_s3_no_readme(mock_s3, sample_artifact, tmp_path):
    """Test extraction when no README exists in artifact."""
    from lambdas.post_search_by_regex import _extract_readme_from_s3

    # Create tar.gz without README
    tar_path = create_tar(tmp_path, {"model.py": "print('hello')"})

    # Upload to S3
    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=sample_artifact.s3_key, Body=f)

    # Test extraction
    readme_text = _extract_readme_from_s3(sample_artifact)

    assert readme_text == ""


def test_extract_readme_from_s3_no_s3_key(sample_artifact):
    """Test extraction when artifact has no s3_key."""
    from lambdas.post_search_by_regex import _extract_readme_from_s3

    sample_artifact.s3_key = None

    readme_text = _extract_readme_from_s3(sample_artifact)

    assert readme_text == ""


def test_extract_readme_from_s3_s3_error(sample_artifact):
    """Test graceful handling of S3 download errors."""
    from lambdas.post_search_by_regex import _extract_readme_from_s3

    # Don't upload to S3, so download will fail
    readme_text = _extract_readme_from_s3(sample_artifact)

    assert readme_text == ""


def test_extract_readme_from_s3_prioritizes_readme(mock_s3, sample_artifact, tmp_path):
    """Test that README files are prioritized over other text files."""
    from lambdas.post_search_by_regex import _extract_readme_from_s3

    # Create tar.gz with README and other files
    tar_path = create_tar(
        tmp_path,
        {
            "README.md": "This is the README",
            "notes.txt": "These are just notes",
            "a.txt": "Another text file",
        },
    )

    # Upload to S3
    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=sample_artifact.s3_key, Body=f)

    # Test extraction
    readme_text = _extract_readme_from_s3(sample_artifact)

    # Should get README, not other files
    assert "This is the README" in readme_text
    assert "just notes" not in readme_text


# =============================================================================
# Unit Tests: _build_search_text()
# =============================================================================


def test_build_search_text_with_readme():
    """Test building search text with README content."""
    from lambdas.post_search_by_regex import _build_search_text

    artifact = ModelArtifact(
        name="my-model",
        source_url="https://example.com",
        metadata={"description": "test description"},
    )

    search_text = _build_search_text(artifact, readme_text="README content here")

    assert "my-model" in search_text
    assert "test description" in search_text
    assert "README content here" in search_text


def test_build_search_text_without_readme():
    """Test building search text without README (backward compatibility)."""
    from lambdas.post_search_by_regex import _build_search_text

    artifact = ModelArtifact(
        name="my-model",
        source_url="https://example.com",
        metadata={"description": "test description"},
    )

    search_text = _build_search_text(artifact)

    assert "my-model" in search_text
    assert "test description" in search_text


def test_build_search_text_empty_readme():
    """Test building search text with empty README string."""
    from lambdas.post_search_by_regex import _build_search_text

    artifact = ModelArtifact(
        name="my-model",
        source_url="https://example.com",
        metadata={},
    )

    search_text = _build_search_text(artifact, readme_text="")

    assert "my-model" in search_text


# =============================================================================
# Integration Tests: _search_artifacts()
# =============================================================================


def test_search_artifacts_matches_readme(mock_s3, tmp_path):
    """Test searching for text that only appears in README."""
    from lambdas.post_search_by_regex import _search_artifacts
    import re

    # Create artifact with README
    artifact = ModelArtifact(
        name="basic-model",
        source_url="https://example.com",
        s3_key="models/test-readme",
        metadata={},
    )
    artifact.artifact_id = "test-readme"
    artifact.artifact_type = "model"

    # Create tar.gz with README containing unique text
    tar_path = create_tar(
        tmp_path, {"README.md": "This model uses UNIQUE_SEARCH_TERM technology"}
    )

    # Upload to S3
    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=artifact.s3_key, Body=f)

    # Mock load_all_artifacts to return our test artifact
    with patch("lambdas.post_search_by_regex.load_all_artifacts") as mock_load:
        mock_load.return_value = [artifact]

        # Search for the unique term
        pattern = re.compile("UNIQUE_SEARCH_TERM", flags=re.IGNORECASE)
        matches = _search_artifacts(pattern)

        assert len(matches) == 1
        assert matches[0]["id"] == "test-readme"
        assert matches[0]["name"] == "basic-model"


def test_search_artifacts_no_match_in_readme(mock_s3, tmp_path):
    """Test search when README doesn't contain the pattern."""
    from lambdas.post_search_by_regex import _search_artifacts
    import re

    artifact = ModelArtifact(
        name="basic-model",
        source_url="https://example.com",
        s3_key="models/test-no-match",
        metadata={},
    )
    artifact.artifact_id = "test-no-match"
    artifact.artifact_type = "model"

    # Create tar.gz with README
    tar_path = create_tar(tmp_path, {"README.md": "Simple model documentation"})

    # Upload to S3
    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=artifact.s3_key, Body=f)

    with patch("lambdas.post_search_by_regex.load_all_artifacts") as mock_load:
        mock_load.return_value = [artifact]

        # Search for non-existent term
        pattern = re.compile("NONEXISTENT", flags=re.IGNORECASE)
        matches = _search_artifacts(pattern)

        assert len(matches) == 0


def test_search_artifacts_matches_metadata_and_readme(mock_s3, tmp_path):
    """Test search that could match both metadata and README."""
    from lambdas.post_search_by_regex import _search_artifacts
    import re

    artifact = ModelArtifact(
        name="advanced-model",
        source_url="https://example.com",
        s3_key="models/test-both",
        metadata={"description": "Model with SEARCH_TERM in metadata"},
    )
    artifact.artifact_id = "test-both"
    artifact.artifact_type = "model"

    # Create tar.gz with README also containing the term
    tar_path = create_tar(tmp_path, {"README.md": "README also mentions SEARCH_TERM"})

    # Upload to S3
    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=artifact.s3_key, Body=f)

    with patch("lambdas.post_search_by_regex.load_all_artifacts") as mock_load:
        mock_load.return_value = [artifact]

        # Search for the term
        pattern = re.compile("SEARCH_TERM", flags=re.IGNORECASE)
        matches = _search_artifacts(pattern)

        # Should find exactly one match (not duplicated)
        assert len(matches) == 1
        assert matches[0]["id"] == "test-both"


def test_search_artifacts_handles_missing_s3_key():
    """Test search handles artifacts without s3_key gracefully."""
    from lambdas.post_search_by_regex import _search_artifacts
    import re

    artifact = ModelArtifact(
        name="incomplete-model",
        source_url="https://example.com",
        s3_key=None,  # No S3 key
        metadata={"description": "FIND_ME"},
    )
    artifact.artifact_id = "test-no-key"
    artifact.artifact_type = "model"

    with patch("lambdas.post_search_by_regex.load_all_artifacts") as mock_load:
        mock_load.return_value = [artifact]

        # Should still match on metadata
        pattern = re.compile("FIND_ME", flags=re.IGNORECASE)
        matches = _search_artifacts(pattern)

        assert len(matches) == 1
        assert matches[0]["id"] == "test-no-key"


def test_search_artifacts_multiple_artifacts(mock_s3, tmp_path):
    """Test search across multiple artifacts."""
    from lambdas.post_search_by_regex import _search_artifacts
    import re

    # Artifact 1: Match in README
    artifact1 = ModelArtifact(
        name="model-one",
        source_url="https://example.com",
        s3_key="models/one",
        metadata={},
    )
    artifact1.artifact_id = "one"
    artifact1.artifact_type = "model"

    # Artifact 2: Match in name
    artifact2 = ModelArtifact(
        name="TENSORFLOW model",
        source_url="https://example.com",
        s3_key="models/two",
        metadata={},
    )
    artifact2.artifact_id = "two"
    artifact2.artifact_type = "model"

    # Artifact 3: No match
    artifact3 = ModelArtifact(
        name="other-model",
        source_url="https://example.com",
        s3_key="models/three",
        metadata={},
    )
    artifact3.artifact_id = "three"
    artifact3.artifact_type = "model"

    # Create README for artifact 1
    tar_path = create_tar(tmp_path, {"README.md": "Uses TensorFlow framework"})
    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key="models/one", Body=f)

    # Create empty tar for others
    tar_path2 = create_tar(tmp_path.rename(tmp_path.parent / "tmp2"), {"info.txt": "x"})
    with open(tar_path2, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key="models/two", Body=f)
        mock_s3.put_object(Bucket="test-bucket", Key="models/three", Body=f)

    with patch("lambdas.post_search_by_regex.load_all_artifacts") as mock_load:
        mock_load.return_value = [artifact1, artifact2, artifact3]

        # Search for tensorflow
        pattern = re.compile("tensorflow", flags=re.IGNORECASE)
        matches = _search_artifacts(pattern)

        # Should match artifact 1 (README) and artifact 2 (name)
        assert len(matches) == 2
        match_ids = {m["id"] for m in matches}
        assert "one" in match_ids
        assert "two" in match_ids
        assert "three" not in match_ids


# =============================================================================
# End-to-End Tests: lambda_handler()
# =============================================================================


def test_lambda_handler_readme_search_success(mock_s3, tmp_path, mocker):
    """Test full lambda handler with README search."""
    from lambdas.post_search_by_regex import lambda_handler
    from src.auth import AuthContext

    # Mock auth validation
    mock_auth_context = AuthContext(
        username="testuser", groups=["User"], sub="test-sub", token="test-token"
    )
    mocker.patch("src.auth.authorize", return_value=mock_auth_context)

    # Create artifact
    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        s3_key="models/lambda-test",
        metadata={},
    )
    artifact.artifact_id = "lambda-test"
    artifact.artifact_type = "model"

    # Create tar with README
    tar_path = create_tar(
        tmp_path, {"README.md": "This model supports SPECIAL_FEATURE"}
    )

    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=artifact.s3_key, Body=f)

    with patch("lambdas.post_search_by_regex.load_all_artifacts") as mock_load:
        mock_load.return_value = [artifact]

        # Call lambda handler
        event = {
            "body": json.dumps({"regex": "SPECIAL_FEATURE"}),
            "headers": {"Authorization": "bearer test-token"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body) == 1
        assert body[0]["id"] == "lambda-test"


def test_lambda_handler_no_matches(mock_s3, tmp_path, mocker):
    """Test lambda handler when no artifacts match."""
    from lambdas.post_search_by_regex import lambda_handler
    from src.auth import AuthContext

    # Mock auth validation
    mock_auth_context = AuthContext(
        username="testuser", groups=["User"], sub="test-sub", token="test-token"
    )
    mocker.patch("src.auth.authorize", return_value=mock_auth_context)

    artifact = ModelArtifact(
        name="test-model",
        source_url="https://example.com",
        s3_key="models/no-match",
        metadata={},
    )
    artifact.artifact_id = "no-match"
    artifact.artifact_type = "model"

    tar_path = create_tar(tmp_path, {"README.md": "Simple documentation"})

    with open(tar_path, "rb") as f:
        mock_s3.put_object(Bucket="test-bucket", Key=artifact.s3_key, Body=f)

    with patch("lambdas.post_search_by_regex.load_all_artifacts") as mock_load:
        mock_load.return_value = [artifact]

        event = {
            "body": json.dumps({"regex": "NONEXISTENT"}),
            "headers": {"Authorization": "bearer test-token"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404


def test_lambda_handler_invalid_regex(mocker):
    """Test lambda handler with invalid regex."""
    from lambdas.post_search_by_regex import lambda_handler
    from src.auth import AuthContext

    # Mock auth validation
    mock_auth_context = AuthContext(
        username="testuser", groups=["User"], sub="test-sub", token="test-token"
    )
    mocker.patch("src.auth.authorize", return_value=mock_auth_context)

    event = {
        "body": json.dumps({"regex": "[invalid(regex"}),
        "headers": {"Authorization": "bearer test-token"},
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 400
    assert "Invalid regular expression" in response["body"]
