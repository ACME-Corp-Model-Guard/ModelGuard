"""
Code artifact class.
"""

from typing import Dict, Any, Optional
from src.storage.dynamo_utils import search_table_by_name, save_artifact_metadata, load_artifact_metadata
from src.settings import ARTIFACTS_TABLE

from .base_artifact import BaseArtifact


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

        # Check if this code is connected to any models
        model_dicts: List[Dict[str, Any]] = search_table_by_field(
            table_name=ARTIFACTS_TABLE,
            field_name="code_name",
            field_value=self.name,
        )

        # Update linked model artifacts to reference this code artifact
        for model_dict in model_dicts:
            model_artifact: ModelArtifact = load_artifact_metadata(model_dict.get("artifact_id"))
            model_artifact.code_artifact_id = self.artifact_id
            save_artifact_metadata(model_artifact)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize CodeArtifact to dictionary for DynamoDB storage.
        """
        return self._base_to_dict()
