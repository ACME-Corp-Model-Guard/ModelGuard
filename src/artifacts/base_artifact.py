"""
Base artifact class providing common functionality for all artifact types.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import os

import boto3
from botocore.exceptions import ClientError

from src.logger import logger


class BaseArtifact(ABC):
    """
    Abstract base class for all artifact types (models, datasets, code).

    Provides:
    - Factory method for creating type-specific artifacts
    - Common fields (artifact_id, artifact_type, name, version, etc.)
    - Serialization (to_dict/from_dict)
    - DynamoDB/S3 integration stubs
    """

    # Valid artifact types
    VALID_TYPES = {"model", "dataset", "code"}

    def __init__(
        self,
        artifact_id: Optional[str] = None,
        artifact_type: str = None,
        name: str = None,
        source_url: str = None,
        s3_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize base artifact fields.

        Args:
            artifact_id: Optional UUID (generated if not provided)
            artifact_type: One of 'model', 'dataset', 'code'
            name: Artifact name
            source_url: URL where artifact was sourced from
            s3_key: Optional S3 storage key
            metadata: Optional dict for additional artifact-specific data
        """
        if artifact_type not in self.VALID_TYPES:
            logger.error(f"Invalid artifact_type: {artifact_type}")
            raise ValueError(
                f"Invalid artifact_type: {artifact_type}. Must be one of {self.VALID_TYPES}"
            )

        self.artifact_id = artifact_id or str(uuid.uuid4())
        self.artifact_type = artifact_type
        self.name = name
        self.source_url = source_url
        self.s3_key = s3_key or f"{artifact_type}s/{self.artifact_id}"
        self.metadata = metadata or {}

        logger.debug(
            f"Initialized {artifact_type} artifact: {self.artifact_id}, name={name}"
        )

    @staticmethod
    def create(artifact_type: str, **kwargs) -> "BaseArtifact":
        """
        Factory method to create the appropriate artifact subclass.

        Args:
            artifact_type: One of 'model', 'dataset', 'code'
            **kwargs: Arguments passed to the subclass constructor

        Returns:
            Instance of ModelArtifact, DatasetArtifact, or CodeArtifact

        Raises:
            ValueError: If artifact_type is invalid
        """
        logger.debug(f"Creating artifact of type: {artifact_type}")

        # Import here to avoid circular imports
        from .model_artifact import ModelArtifact
        from .dataset_artifact import DatasetArtifact
        from .code_artifact import CodeArtifact

        artifact_map = {
            "model": ModelArtifact,
            "dataset": DatasetArtifact,
            "code": CodeArtifact,
        }

        if artifact_type not in artifact_map:
            logger.error(f"Invalid artifact_type in factory: {artifact_type}")
            raise ValueError(
                f"Invalid artifact_type: {artifact_type}. Must be one of {BaseArtifact.VALID_TYPES}"
            )

        artifact_class = artifact_map[artifact_type]
        artifact = artifact_class(**kwargs)
        logger.info(f"Created {artifact_type} artifact: {artifact.artifact_id}")
        return artifact

    @classmethod
    def from_url(cls, url: str, artifact_type: str) -> "BaseArtifact":
        """
        Create an artifact by fetching metadata from external source (HuggingFace or GitHub).

        Args:
            url: URL to artifact (HuggingFace model/dataset or GitHub repo)
            artifact_type: One of 'model', 'dataset', 'code'

        Returns:
            Instance of appropriate artifact subclass with fetched metadata

        Raises:
            IngestionError: If fetching or parsing fails
            ValueError: If artifact_type is invalid

        Example:
            >>> model = BaseArtifact.from_url(
            ...     "https://huggingface.co/bert-base-uncased",
            ...     artifact_type="model"
            ... )
        """
        logger.info(f"Creating {artifact_type} artifact from URL: {url}")

        from .utils.api_ingestion import fetch_artifact_metadata

        # Fetch metadata from external source
        metadata = fetch_artifact_metadata(url, artifact_type)

        # Ensure artifact_type and source_url are set
        metadata["artifact_type"] = artifact_type
        metadata["source_url"] = url

        # Create artifact using factory method
        artifact = cls.create(artifact_type, **metadata)
        logger.info(
            f"Successfully created {artifact_type} artifact from URL: {artifact.artifact_id}"
        )

        return artifact

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize artifact to dictionary for DynamoDB storage.
        Subclasses must implement to include type-specific fields.
        """
        pass

    def _base_to_dict(self) -> Dict[str, Any]:
        """
        Helper method to serialize common base fields.
        Subclasses call this and extend with their own fields.
        """
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "name": self.name,
            "source_url": self.source_url,
            "s3_key": self.s3_key,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(artifact_id='{self.artifact_id}', name='{self.name}')"
