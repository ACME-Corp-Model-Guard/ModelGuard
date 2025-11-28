from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Union

if TYPE_CHECKING:
    from src.artifacts import ModelArtifact


class Metric(ABC):
    """
    Abstract base class for all metrics in the ModelGuard system.
    All concrete metrics must implement the score() method.
    """

    @abstractmethod
    def score(self, model: ModelArtifact) -> Union[float, Dict[str, float]]:
        """
        Score a model and return the result.

        Args:
            model: The ModelArtifact object to score

        Returns:
            Either a float score or a dictionary of scores
        """
        pass
