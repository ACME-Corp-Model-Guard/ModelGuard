"""
Tests for metadata storage utilities.
"""

import os
import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from src.artifacts.utils.metadata_storage import (
    save_artifact_to_dynamodb,
    load_artifact_from_dynamodb,
)


class TestMetadataStorage:
    """Test metadata storage functions."""

    @patch.dict(os.environ, {"ARTIFACTS_TABLE": "test-table"})
    @patch("src.artifacts.utils.metadata_storage.boto3")
    def test_save_artifact(self, mock_boto3):
        """Test saving artifact to DynamoDB."""
        # Setup
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        mock_artifact = Mock()
        mock_artifact.artifact_id = "test-123"
        mock_artifact.to_dict.return_value = {"artifact_id": "test-123", "name": "test"}

        # Test
        save_artifact_to_dynamodb(mock_artifact)

        # Verify
        mock_artifact.to_dict.assert_called_once()
        mock_table.put_item.assert_called_once_with(
            Item={"artifact_id": "test-123", "name": "test"}
        )

    @patch.dict(os.environ, {"ARTIFACTS_TABLE": "test-table"})
    @patch("src.artifacts.utils.metadata_storage.boto3")
    def test_load_artifact_success(self, mock_boto3):
        """Test loading artifact from DynamoDB."""
        # Setup
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "artifact_id": "test-123",
                "artifact_type": "model",
                "name": "test-model",
            }
        }
        mock_boto3.resource.return_value.Table.return_value = mock_table

        mock_artifact = Mock()
        with patch("src.artifacts.base_artifact.BaseArtifact") as mock_base:
            mock_base.create.return_value = mock_artifact

            # Test
            result = load_artifact_from_dynamodb("test-123")

            # Verify
            assert result == mock_artifact
            mock_base.create.assert_called_once_with(
                "model", artifact_id="test-123", name="test-model"
            )

    @patch.dict(os.environ, {"ARTIFACTS_TABLE": "test-table"})
    @patch("src.artifacts.utils.metadata_storage.boto3")
    def test_load_artifact_not_found(self, mock_boto3):
        """Test loading non-existent artifact returns None."""
        # Setup
        mock_table = Mock()
        mock_table.get_item.return_value = {}  # No Item
        mock_boto3.resource.return_value.Table.return_value = mock_table

        # Test
        result = load_artifact_from_dynamodb("nonexistent")

        # Verify
        assert result is None

    def test_missing_env_var(self):
        """Test functions fail when ARTIFACTS_TABLE not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="ARTIFACTS_TABLE env var must be set"):
                save_artifact_to_dynamodb(Mock())

            with pytest.raises(ValueError, match="ARTIFACTS_TABLE env var must be set"):
                load_artifact_from_dynamodb("test-123")

    @patch.dict(os.environ, {"ARTIFACTS_TABLE": "test-table"})
    @patch("src.artifacts.utils.metadata_storage.boto3")
    def test_dynamodb_error(self, mock_boto3):
        """Test DynamoDB errors are propagated."""
        # Setup
        mock_table = Mock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException"}}, "PutItem"
        )
        mock_boto3.resource.return_value.Table.return_value = mock_table

        # Test
        with pytest.raises(ClientError):
            save_artifact_to_dynamodb(Mock())
