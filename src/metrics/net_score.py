from statistics import mean
from typing import Dict, Union


def calculate_net_score(scores: Dict[str, Union[float, Dict[str, float]]]) -> float:
    """
    Calculate weighted composite score from individual metric scores.

    Args:
        scores: Dictionary of metric names to scores (0.0-1.0)
                Values can be floats or nested dicts of scores (which are averaged)
                Keys are PascalCase metric names derived from class names
                (e.g., "Availability", "BusFactor", "CodeQuality")

    Returns:
        Weighted net score clamped to [0.0, 1.0]
    """
    # Weights sum to 1.0 (reviewedness and reproducibility removed per requirements)
    # Keys match the metric class names with "Metric" suffix removed
    weights = {
        "Availability": 0.08,
        "BusFactor": 0.06,
        "CodeQuality": 0.10,
        "DatasetQuality": 0.10,
        "License": 0.22,
        "PerformanceClaims": 0.06,
        "RampUp": 0.10,
        "Size": 0.12,
        "Treescore": 0.16,
    }

    total = 0.0
    weight_sum = 0.0

    for metric_name, weight in weights.items():
        if metric_name in scores:
            raw_score = scores[metric_name]

            # If score is a dict, average its values
            if isinstance(raw_score, dict):
                score = mean(raw_score.values()) if raw_score else 0.0
            else:
                score = float(raw_score)

            # Clamp individual score to [0.0, 1.0]
            score = max(0.0, min(1.0, score))
            total += weight * score
            weight_sum += weight

    # Calculate weighted average
    result = total / weight_sum if weight_sum > 0 else 0.0

    # Clamp final result to [0.0, 1.0]
    return max(0.0, min(1.0, result))
