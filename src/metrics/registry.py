from src.metrics.availability_metric import AvailabilityMetric
from src.metrics.bus_factor_metric import BusFactorMetric
from src.metrics.code_quality_metric import CodeQualityMetric
from src.metrics.dataset_quality_metric import DatasetQualityMetric
from src.metrics.license_metric import LicenseMetric
from src.metrics.performance_claims_metric import PerformanceClaimsMetric
from src.metrics.ramp_up_metric import RampUpMetric
from src.metrics.size_metric import SizeMetric
from src.metrics.treescore_metric import TreescoreMetric

METRICS = [
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
