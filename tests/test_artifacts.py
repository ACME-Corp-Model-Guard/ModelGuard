"""
Simple tests for artifact classes and utilities.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.artifacts import (
    BaseArtifact,
    ModelArtifact,
    DatasetArtifact,
    CodeArtifact,
    IngestionError,
)


class TestBaseArtifact:
    """Tests for BaseArtifact factory and serialization."""

    def test_create_model_artifact(self):
        """Test factory creates ModelArtifact."""
        artifact = BaseArtifact.create(
            artifact_type="model",
            name="test-model",
            source_url="https://example.com/model",
        )
        assert isinstance(artifact, ModelArtifact)
        assert artifact.artifact_type == "model"
        assert artifact.name == "test-model"
        assert artifact.source_url == "https://example.com/model"

    def test_create_dataset_artifact(self):
        """Test factory creates DatasetArtifact."""
        artifact = BaseArtifact.create(
            artifact_type="dataset",
            name="test-dataset",
            source_url="https://example.com/dataset",
        )
        assert isinstance(artifact, DatasetArtifact)
        assert artifact.artifact_type == "dataset"

    def test_create_code_artifact(self):
        """Test factory creates CodeArtifact."""
        artifact = BaseArtifact.create(
            artifact_type="code",
            name="test-code",
            source_url="https://example.com/code",
        )
        assert isinstance(artifact, CodeArtifact)
        assert artifact.artifact_type == "code"

    def test_invalid_artifact_type(self):
        """Test invalid artifact type raises error."""
        with pytest.raises(ValueError, match="Invalid artifact_type"):
            BaseArtifact.create(
                artifact_type="invalid", name="test", source_url="https://example.com"
            )

    def test_to_dict_includes_source_url(self):
        """Test serialization includes source_url."""
        artifact = BaseArtifact.create(
            artifact_type="code", name="test", source_url="https://github.com/test/repo"
        )
        data = artifact.to_dict()
        assert data["source_url"] == "https://github.com/test/repo"
        assert data["artifact_type"] == "code"
        assert data["name"] == "test"


class TestModelArtifact:
    """Tests for ModelArtifact."""

    def test_model_artifact_creation(self):
        """Test ModelArtifact initialization."""
        model = ModelArtifact(
            name="bert-base",
            source_url="https://huggingface.co/bert-base-uncased",
            size=440000000,
            license="apache-2.0",
            auto_score=False,
        )
        assert model.name == "bert-base"
        assert model.size == 440000000
        assert model.license == "apache-2.0"
        assert model.artifact_type == "model"

    def test_model_to_dict(self):
        """Test ModelArtifact serialization."""
        model = ModelArtifact(
            name="test-model",
            source_url="https://example.com",
            size=1000,
            license="mit",
            auto_score=False,
        )
        data = model.to_dict()
        assert data["size"] == 1000
        assert data["license"] == "mit"
        assert data["source_url"] == "https://example.com"


class TestFromURL:
    """Tests for from_url class method."""

    @patch("src.artifacts.utils.api_ingestion.fetch_artifact_metadata")
    def test_from_url_creates_artifact(self, mock_fetch):
        """Test from_url creates artifact with metadata."""
        mock_fetch.return_value = {
            "name": "bert-base-uncased",
            "size": 440000000,
            "license": "apache-2.0",
            "metadata": {"downloads": 1000000},
        }

        artifact = BaseArtifact.from_url(
            "https://huggingface.co/bert-base-uncased", artifact_type="model"
        )

        assert isinstance(artifact, ModelArtifact)
        assert artifact.name == "bert-base-uncased"
        assert artifact.source_url == "https://huggingface.co/bert-base-uncased"
        mock_fetch.assert_called_once()

    @patch("src.artifacts.utils.api_ingestion.fetch_artifact_metadata")
    def test_from_url_sets_source_url(self, mock_fetch):
        """Test from_url stores source URL."""
        mock_fetch.return_value = {"name": "test"}

        url = "https://github.com/pytorch/pytorch"
        artifact = BaseArtifact.from_url(url, artifact_type="code")

        assert artifact.source_url == url


class TestAPIIngestion:
    """Tests for API ingestion utilities."""

    @patch("src.artifacts.utils.api_ingestion.requests.get")
    def test_fetch_huggingface_model_metadata(self, mock_get):
        """Test HuggingFace model metadata fetching."""
        from src.artifacts.utils.api_ingestion import fetch_huggingface_model_metadata

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "downloads": 5000000,
            "likes": 1000,
            "safetensors": {"total": 440000000},
            "cardData": {"license": "apache-2.0"},
        }
        mock_get.return_value = mock_response

        result = fetch_huggingface_model_metadata(
            "https://huggingface.co/bert-base-uncased"
        )

        assert result["name"] == "bert-base-uncased"
        assert result["size"] == 440000000
        assert result["license"] == "apache-2.0"

    @patch("src.artifacts.utils.api_ingestion.requests.get")
    def test_fetch_github_code_metadata(self, mock_get):
        """Test GitHub repo metadata fetching."""
        from src.artifacts.utils.api_ingestion import fetch_github_code_metadata

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "pytorch",
            "stargazers_count": 50000,
            "forks_count": 10000,
            "size": 100000,
            "language": "Python",
            "license": {"spdx_id": "BSD-3-Clause"},
        }
        mock_get.return_value = mock_response

        result = fetch_github_code_metadata("https://github.com/pytorch/pytorch")

        assert result["name"] == "pytorch"
        assert result["metadata"]["stars"] == 50000
        assert result["metadata"]["language"] == "Python"

    def test_invalid_url_raises_error(self):
        """Test invalid URL raises IngestionError."""
        from src.artifacts.utils.api_ingestion import fetch_artifact_metadata

        with pytest.raises(IngestionError):
            fetch_artifact_metadata("https://invalid.com", "model")


class TestMetadataStorage:
    """Tests for DynamoDB metadata storage."""

    @patch("src.artifacts.utils.metadata_storage.boto3.resource")
    @patch.dict("os.environ", {"ARTIFACTS_TABLE": "test-table"})
    def test_save_artifact_to_dynamodb(self, mock_boto):
        """Test saving artifact to DynamoDB."""
        from src.artifacts.utils.metadata_storage import save_artifact_to_dynamodb

        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        artifact_dict = {
            "artifact_id": "test-id",
            "artifact_type": "model",
            "name": "test-model",
            "source_url": "https://example.com",
        }

        save_artifact_to_dynamodb(artifact_dict)

        mock_table.put_item.assert_called_once_with(Item=artifact_dict)

    def test_save_without_env_var_raises_error(self):
        """Test saving without ARTIFACTS_TABLE env var raises error."""
        from src.artifacts.utils.metadata_storage import save_artifact_to_dynamodb

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ARTIFACTS_TABLE"):
                save_artifact_to_dynamodb({"artifact_id": "test"})


class TestFileStorage:
    """Tests for S3 file storage utilities."""

    @patch("src.artifacts.utils.file_storage.boto3.client")
    @patch("src.artifacts.utils.file_storage._download_direct_url")
    @patch.dict("os.environ", {"ARTIFACTS_BUCKET": "test-bucket"})
    def test_upload_artifact_to_s3_direct_url(self, mock_download, mock_boto):
        """Test uploading artifact from direct URL."""
        from src.artifacts.utils.file_storage import upload_artifact_to_s3

        mock_download.return_value = "/tmp/test-file"
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        upload_artifact_to_s3(
            artifact_id="test-id",
            s3_key="models/test-id",
            source_url="https://example.com/model.bin",
        )

        mock_s3.upload_file.assert_called_once()

    @patch("src.artifacts.utils.file_storage.boto3.client")
    @patch.dict("os.environ", {"ARTIFACTS_BUCKET": "test-bucket"})
    def test_download_artifact_from_s3(self, mock_boto):
        """Test downloading artifact from S3."""
        from src.artifacts.utils.file_storage import download_artifact_from_s3

        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        download_artifact_from_s3(
            artifact_id="test-id", s3_key="models/test-id", local_path="/tmp/output"
        )

        mock_s3.download_file.assert_called_once_with(
            "test-bucket", "models/test-id", "/tmp/output"
        )
