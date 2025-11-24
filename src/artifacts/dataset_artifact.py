"""
Dataset artifact class.
"""

from typing import Dict, Any, Optional

from .base_artifact import BaseArtifact


class DatasetArtifact(BaseArtifact):
    """
    Dataset artifact with minimal fields.

    Inherits all base functionality from BaseArtifact.
    Future enhancements may add dataset-specific fields (e.g., schema, row_count, etc.).
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
        model_dicts: List[Dict[str, Any]] = search_table_by_field(
            table_name=ARTIFACTS_TABLE,
            field_name="dataset_name",
            field_value=self.name,
        )

        # Update linked model artifacts to reference this dataset artifact
        for model_dict in model_dicts:
            model_artifact: ModelArtifact = load_artifact_metadata(model_dict.get("artifact_id"))
            model_artifact.dataset_artifact_id = self.artifact_id
            save_artifact_metadata(model_artifact)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize DatasetArtifact to dictionary for DynamoDB storage.
        """
        return self._base_to_dict()
