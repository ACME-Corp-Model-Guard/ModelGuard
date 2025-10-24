#!/usr/bin/env python3
"""
License Metric implementation.
"""

from typing import Union, Dict

from .abstract_metric import AbstractMetric


class LicenseMetric(AbstractMetric):
    """
    License assessment metric.
    Evaluates the licensing information of models.
    """

    def __init__(self):
        super().__init__("license")

    def score(self, model: 'Model') -> Union[float, Dict[str, float]]:
        # TODO: Implement actual license scoring when S3 integration is ready
        # For now, return a placeholder score based on model license
        license_score = self._stable_unit_score(model.license, "license")
        return {"license": license_score}