"""
Artifact module for ModelGuard.
Provides base classes and concrete implementations for model, dataset, and code artifacts.
"""

from .base_artifact import BaseArtifact
from .model_artifact import ModelArtifact
from .dataset_artifact import DatasetArtifact
from .code_artifact import CodeArtifact
from .types import ArtifactType

__all__ = [
    "BaseArtifact",
    "ModelArtifact",
    "DatasetArtifact",
    "CodeArtifact",
    "ArtifactType",
]