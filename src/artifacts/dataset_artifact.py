"""
Dataset artifact class.
"""

from typing import Dict, Any, Optional, List
from src.storage.dynamo_utils import (
    save_artifact_metadata,
    load_all_artifacts_by_fields,
)

from .base_artifact import BaseArtifact
from .model_artifact import ModelArtifact


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

        # Check if this dataset is connected to any models
        model_artifacts: List[BaseArtifact] = load_all_artifacts_by_fields(
            fields={"dataset_name": self.name},
            artifact_type="model",
        )

        # Update linked model artifacts to reference this dataset artifact
        for model_artifact in model_artifacts:
            if not isinstance(model_artifact, ModelArtifact) or model_artifact.dataset_artifact_id:
                continue
            model_artifact: ModelArtifact = model_artifact
            model_artifact.dataset_artifact_id = self.artifact_id
            model_artifact._compute_scores() # Recompute scores
            save_artifact_metadata(model_artifact)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize DatasetArtifact to dictionary for DynamoDB storage.
        """
        return self._base_to_dict()
