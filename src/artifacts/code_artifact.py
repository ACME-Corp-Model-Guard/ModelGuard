"""
Code artifact class.
"""

from typing import Dict, Any, Optional
from src.storage.dynamo_utils import (
    save_artifact_metadata,
    load_all_artifacts_by_field,
)
from src.settings import ARTIFACTS_TABLE
from typing import List

from .base_artifact import BaseArtifact
from .model_artifact import ModelArtifact


class CodeArtifact(BaseArtifact):
    """
    Code artifact.

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
        model_artifacts: List[BaseArtifact] = load_all_artifacts_by_field(
            field_name="code_name",
            field_value=self.name,
            artifact_type="model",
        )

        # Update linked model artifacts to reference this code artifact
        for model_artifact in model_artifacts:
            if not isinstance(model_artifact, ModelArtifact):
                continue
            model_artifact: ModelArtifact = model_artifact
            model_artifact.code_artifact_id = self.artifact_id
            save_artifact_metadata(model_artifact)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize CodeArtifact to dictionary for DynamoDB storage.
        """
        return self._base_to_dict()
