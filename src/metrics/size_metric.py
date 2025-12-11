from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Union

from src.logging import clogger

from .metric import Metric

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class SizeMetric(Metric):
    """
    Size metric for evaluating model size across different device types.

    Scores models based on their size in bytes for different deployment targets:
    - Pi: 0.5GB capacity
    - Nano: 1GB capacity
    - Pc: 16GB capacity
    - Server: 64GB capacity

    Each device gets a score based on how well the model fits:
    - Model fits comfortably (< 50% of capacity): 1.0
    - Model fits but tight (50-80% of capacity): 0.7
    - Model barely fits (80-95% of capacity): 0.4
    - Model doesn't fit (> 95% of capacity): 0.0
    """

    # Device capacities in bytes
    PI_CAPACITY = 0.5 * 1024 * 1024 * 1024  # 0.5GB
    NANO_CAPACITY = 1 * 1024 * 1024 * 1024  # 1GB
    PC_CAPACITY = 16 * 1024 * 1024 * 1024  # 16GB
    SERVER_CAPACITY = 64 * 1024 * 1024 * 1024  # 64GB

    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score model size for different device types.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Dictionary with size scores for each device type (Pi, Nano, Pc, Server)
            Each score is between 0.0 and 1.0 (higher is better - model fits better)
        """
        size_bytes = model.size

        # Handle missing or invalid size
        if not size_bytes or size_bytes <= 0:
            clogger.debug(
                f"No valid size information for model {model.artifact_id}, "
                f"returning neutral scores"
            )
            return {
                "size_pi": 0.5,
                "size_nano": 0.5,
                "size_pc": 0.5,
                "size_server": 0.5,
            }

        try:
            scores = {
                "size_pi": self._calculate_device_score(size_bytes, self.PI_CAPACITY),
                "size_nano": self._calculate_device_score(
                    size_bytes, self.NANO_CAPACITY
                ),
                "size_pc": self._calculate_device_score(size_bytes, self.PC_CAPACITY),
                "size_server": self._calculate_device_score(
                    size_bytes, self.SERVER_CAPACITY
                ),
            }

            # Convert to human-readable format for logging
            size_gb = size_bytes / (1024 * 1024 * 1024)
            clogger.debug(
                f"Size scores for {model.artifact_id} (size: {size_gb:.2f} GB): "
                f"Pi={scores['size_pi']:.3f}, Nano={scores['size_nano']:.3f}, "
                f"Pc={scores['size_pc']:.3f}, Server={scores['size_server']:.3f}"
            )

            return scores

        except Exception as e:
            clogger.error(
                f"Failed to calculate size scores for model {model.artifact_id}: {e}",
                exc_info=True,
            )
            return {
                "size_pi": 0.5,
                "size_nano": 0.5,
                "size_pc": 0.5,
                "size_server": 0.5,
            }

    def _calculate_device_score(
        self, size_bytes: float, capacity_bytes: float
    ) -> float:
        """
        Calculate size score for a specific device capacity.

        Args:
            size_bytes: Model size in bytes
            capacity_bytes: Device capacity in bytes

        Returns:
            Score between 0.0 and 1.0 based on how well the model fits
        """
        if size_bytes > capacity_bytes:
            # Model doesn't fit
            return 0.0

        # Calculate utilization percentage
        utilization = size_bytes / capacity_bytes

        if utilization < 0.5:
            # Model fits comfortably (< 50% of capacity)
            return 1.0
        elif utilization < 0.8:
            # Model fits but tight (50-80% of capacity)
            return 0.7
        elif utilization < 0.95:
            # Model barely fits (80-95% of capacity)
            return 0.4
        else:
            # Model is at the limit (95-100% of capacity)
            return 0.1
