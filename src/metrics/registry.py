from src.metrics.availability_metric import AvailabilityMetric
from src.metrics.bus_factor_metric import BusFactorMetric
from src.metrics.code_quality_metric import CodeQualityMetric
from src.metrics.dataset_quality_metric import DatasetQualityMetric
from src.metrics.license_metric import LicenseMetric
from src.metrics.performance_claims_metric import PerformanceClaimsMetric
from src.metrics.ramp_up_metric import RampUpMetric
from src.metrics.size_metric import SizeMetric
from src.metrics.treescore_metric import TreescoreMetric
from src.metrics.metric import Metric

METRICS: list[Metric] = [
    AvailabilityMetric(),
    BusFactorMetric(),
    CodeQualityMetric(),
    DatasetQualityMetric(),
    LicenseMetric(),
    PerformanceClaimsMetric(),
    RampUpMetric(),
    SizeMetric(),
    TreescoreMetric(),
]

# Categorized metric lists for targeted reevaluations on new connections
LINEAGE_METRICS: list[Metric] = [
    TreescoreMetric(),
]

CODE_METRICS: list[Metric] = [
    CodeQualityMetric(),
    AvailabilityMetric(),
]

DATASET_METRICS: list[Metric] = [
    DatasetQualityMetric(),
    AvailabilityMetric(),
]
