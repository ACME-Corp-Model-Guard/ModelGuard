from pathlib import Path
from typing import Optional, Any, Dict
from abc import ABC, abstractmethod


class Metric(ABC):
    @abstractmethod
    def score(self, model_ref: Any) -> Dict[str, float]:
        
        raise NotImplementedError