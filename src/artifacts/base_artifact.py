"""
Base artifact class providing common functionality for all artifact types.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.logger import logger
from src.storage.downloaders.dispatchers import fetch_artifact_metadata
from src.artifacts.types import ArtifactType
from src.storage.s3_utils import upload_artifact_to_s3


class BaseArtifact(ABC):
    """
    Abstract base class for all artifact types (models, datasets, code).

    Provides:
    - Factory method for creating type-specific artifacts
    - Common fields (artifact_id, artifact_type, name, version, etc.)
    - Serialization (to_dict/from_dict)
    """

    # Valid artifact types
    VALID_TYPES = {"model", "dataset", "code"}

    def __init__(
        self,
        artifact_type: ArtifactType,
        name: str,
        source_url: str,
        artifact_id: Optional[str] = None,
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

        # If created a new s3_key, upload artifact to S3
        try:
            if not s3_key:
                upload_artifact_to_s3(self.artifact_id, self.artifact_type, self.s3_key, self.source_url)
        except FileDownloadError:
            return error_response(
                404,
                "Upstream artifact not found or download failed",
                error_code="SOURCE_NOT_FOUND",
            )
        except Exception as e:
            logger.error(f"[post_artifact] S3 upload failed: {e}", exc_info=True)
            return error_response(
                500,
                "Failed to upload artifact to S3",
                error_code="S3_UPLOAD_ERROR",
            )

        logger.debug(
            f"Initialized {artifact_type} artifact: {self.artifact_id}, name={name}"
        )

    @staticmethod
    def create(artifact_type: ArtifactType, **kwargs: Any) -> "BaseArtifact":
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
        from .code_artifact import CodeArtifact
        from .dataset_artifact import DatasetArtifact
        from .model_artifact import ModelArtifact

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

        # Create and return the appropriate artifact instance
        artifact_class = artifact_map[artifact_type]
        artifact = artifact_class(**kwargs)
        logger.info(f"Created {artifact_type} artifact: {artifact.artifact_id}")
        return artifact

    @classmethod
    def from_url(cls, url: str, artifact_type: ArtifactType) -> "BaseArtifact":
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

        # Fetch metadata from external source
        metadata = fetch_artifact_metadata(url, artifact_type)

        # Ensure source_url is set
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
