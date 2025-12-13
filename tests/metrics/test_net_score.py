from src.metrics.net_score import calculate_net_score

# The weights from the implementation (reviewedness/reproducibility removed)
WEIGHTS = {
    "availability": 0.08,
    "bus_factor": 0.06,
    "code_quality": 0.10,
    "dataset_quality": 0.10,
    "license": 0.22,
    "performance_claims": 0.06,
    "ramp_up": 0.10,
    "size": 0.12,
    "tree_score": 0.16,
}


def test_all_metrics_perfect_scores():
    """If all metrics are exactly 1.0, the net score must be 1.0."""
    scores = {metric: 1.0 for metric in WEIGHTS}
    result = calculate_net_score(scores)
    assert result == 1.0


def test_all_metrics_zero_scores():
    """If all metrics are zero, the weighted sum must be zero."""
    scores = {metric: 0.0 for metric in WEIGHTS}
    result = calculate_net_score(scores)
    assert result == 0.0


def test_missing_some_metrics():
    """Missing metrics should simply be excluded from the weighted average."""
    scores = {
        "availability": 1.0,
        "license": 0.0,
        # All others missing
    }

    total = WEIGHTS["availability"] * 1.0 + WEIGHTS["license"] * 0.0
    weight_sum = WEIGHTS["availability"] + WEIGHTS["license"]

    expected = total / weight_sum
    result = calculate_net_score(scores)

    assert result == expected


def test_dict_metric_average():
    """Dict-valued metrics should be averaged before weighting."""
    scores = {
        "availability": {"a": 1.0, "b": 0.0},  # avg = 0.5
        "license": 1.0,
    }

    avg_availability = 0.5

    total = WEIGHTS["availability"] * avg_availability + WEIGHTS["license"] * 1.0
    weight_sum = WEIGHTS["availability"] + WEIGHTS["license"]

    expected = total / weight_sum
    result = calculate_net_score(scores)

    assert abs(result - expected) < 1e-9


def test_empty_dict_nested_metric():
    """Empty dict should be treated as zero."""
    scores = {
        "availability": {},
        "license": 1.0,
    }

    total = WEIGHTS["availability"] * 0.0 + WEIGHTS["license"] * 1.0
    weight_sum = WEIGHTS["availability"] + WEIGHTS["license"]

    expected = total / weight_sum
    result = calculate_net_score(scores)

    assert result == expected


def test_clamping_individual_scores():
    """Scores >1.0 should clamp to 1.0, <0.0 should clamp to 0.0."""
    scores = {
        "availability": 5.0,  # should clamp to 1
        "license": -10,  # should clamp to 0
    }

    total = WEIGHTS["availability"] * 1.0 + WEIGHTS["license"] * 0.0
    weight_sum = WEIGHTS["availability"] + WEIGHTS["license"]
    expected = total / weight_sum

    result = calculate_net_score(scores)
    assert result == expected


def test_clamps_final_result_to_zero_one():
    """Extreme weighted values should clamp final result to [0, 1]."""
    # Construct scenario that yields >1
    scores = {metric: 10.0 for metric in WEIGHTS}  # all clamp to 1.0
    result = calculate_net_score(scores)
    assert result == 1.0

    # Construct scenario that yields <0
    scores = {metric: -999.0 for metric in WEIGHTS}  # all clamp to 0.0
    result = calculate_net_score(scores)
    assert result == 0.0


def test_empty_input():
    """Empty dict should yield 0.0 (no weight_sum)."""
    result = calculate_net_score({})
    assert result == 0.0


def test_mixed_float_and_dict_metrics():
    """Combination of dict and float metrics must aggregate correctly."""
    scores = {
        "availability": {"a": 0.2, "b": 0.8},  # avg = 0.5
        "bus_factor": 0.3,
        "license": 1.0,
    }

    expected_total = (
        WEIGHTS["availability"] * 0.5 + WEIGHTS["bus_factor"] * 0.3 + WEIGHTS["license"] * 1.0
    )
    expected_sum = WEIGHTS["availability"] + WEIGHTS["bus_factor"] + WEIGHTS["license"]

    expected = expected_total / expected_sum
    result = calculate_net_score(scores)

    assert abs(result - expected) < 1e-9
