"""
Dataset artifact class.
"""

from typing import Dict, Any, Optional, List
from .base_artifact import BaseArtifact


class DatasetArtifact(BaseArtifact):
    """
    Dataset artifact.

    Inherits all base functionality from BaseArtifact.
    """

    def __init__(
        self,
        name: str,
        source_url: str,
        artifact_id: Optional[str] = None,
        s3_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize DatasetArtifact.

        Args:
            artifact_id: Optional UUID (generated if not provided)
            name: Dataset name
            source_url: URL where dataset was sourced from
            s3_key: Optional S3 storage key
            metadata: Optional dict for additional dataset-specific data
        """
        super().__init__(
            artifact_id=artifact_id,
            artifact_type="dataset",
            name=name,
            source_url=source_url,
            s3_key=s3_key,
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize DatasetArtifact to dictionary for DynamoDB storage.
        """
        return self._base_to_dict()
