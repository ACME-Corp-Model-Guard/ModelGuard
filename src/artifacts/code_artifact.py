"""
Code artifact class.
"""

from typing import Dict, Any, Optional

from .base_artifact import BaseArtifact
from src.logger import logger


class CodeArtifact(BaseArtifact):
    """
    Code artifact with minimal fields.

    Inherits all base functionality from BaseArtifact.
    Future enhancements may add code-specific fields (e.g., language, framework, etc.).
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
        Initialize CodeArtifact.

        Args:
            artifact_id: Optional UUID (generated if not provided)
            name: Code artifact name
            source_url: URL where code was sourced from
            s3_key: Optional S3 storage key
            metadata: Optional dict for additional code-specific data
        """
        super().__init__(
            artifact_id=artifact_id,
            artifact_type="code",
            name=name,
            source_url=source_url,
            s3_key=s3_key,
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize CodeArtifact to dictionary for DynamoDB storage.
        """
        return self._base_to_dict()
