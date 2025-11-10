"""
Artifact module for ModelGuard.
Provides base classes and concrete implementations for model, dataset, and code artifacts.
"""

from .base_artifact import BaseArtifact
from .model_artifact import ModelArtifact
from .dataset_artifact import DatasetArtifact
from .code_artifact import CodeArtifact
from .utils.types import ArtifactType
from .utils import (
    fetch_artifact_metadata,
    fetch_huggingface_model_metadata,
    fetch_huggingface_dataset_metadata,
    fetch_github_code_metadata,
    IngestionError,
    upload_artifact_to_s3,
    download_artifact_from_s3,
    save_artifact_to_dynamodb,
)

__all__ = [
    "BaseArtifact",
    "ModelArtifact",
    "DatasetArtifact",
    "CodeArtifact",
    "ArtifactType",
    "fetch_artifact_metadata",
    "fetch_huggingface_model_metadata",
    "fetch_huggingface_dataset_metadata",
    "fetch_github_code_metadata",
    "IngestionError",
    "upload_artifact_to_s3",
    "download_artifact_from_s3",
    "save_artifact_to_dynamodb",
]
