from abc import ABC, abstractmethod
from typing import Union, Dict


class Metric(ABC):
    """
    Abstract base class for all metrics in the ModelGuard system.
    All concrete metrics must implement the score() method.
    """

    @abstractmethod
    def score(self, model: "Model") -> Union[float, Dict[str, float]]:
        """
        Score a model and return the result.

        Args:
            model: The Model object to score

        Returns:
            Either a float score or a dictionary of scores
        """
        pass
