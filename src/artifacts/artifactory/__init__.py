"""
Artifact factory, persistence, and connection management.

This module provides the core artifact management functionality for ModelGuard:
- Factory methods to create artifacts from upstream sources
- Persistence operations for DynamoDB storage
- Connection logic to link related artifacts (models to datasets/code)
- Discovery using LLM to extract artifact relationships

Public API (used by Lambda handlers):
    create_artifact() - Create new artifact with metadata fetching and S3 upload
    save_artifact_metadata() - Save artifact to DynamoDB
    load_artifact_metadata() - Load single artifact by ID
    load_all_artifacts() - Load all artifacts from DynamoDB
    load_all_artifacts_by_fields() - Filter artifacts by field values
"""

from .factory import create_artifact
from .persistence import (
    save_artifact_metadata,
    load_artifact_metadata,
    load_all_artifacts,
    load_all_artifacts_by_fields,
)
from .rejection import scores_below_threshold

__all__ = [
    "create_artifact",
    "save_artifact_metadata",
    "load_artifact_metadata",
    "load_all_artifacts",
    "load_all_artifacts_by_fields",
    "scores_below_threshold",
]
