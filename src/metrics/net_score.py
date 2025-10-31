from statistics import mean
from typing import Dict, Union


def calculate_net_score(scores: Dict[str, Union[float, Dict[str, float]]]) -> float:
    """
    Calculate weighted composite score from individual metric scores.

    Args:
        scores: Dictionary of metric names to scores (0.0-1.0)
                Values can be floats or nested dicts of scores (which are averaged)
                Expected keys: availability, bus_factor, code_quality,
                dataset_quality, license, performance_claims, ramp_up,
                size, reproducibility, reviewedness, tree_score

    Returns:
        Weighted net score clamped to [0.0, 1.0]
    """
    weights = {
        "availability": 0.07,
        "bus_factor": 0.05,
        "code_quality": 0.09,
        "dataset_quality": 0.09,
        "license": 0.20,
        "performance_claims": 0.05,
        "ramp_up": 0.09,
        "size": 0.10,
        "reproducibility": 0.10,
        "reviewedness": 0.06,
        "tree_score": 0.10,
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
