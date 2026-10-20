"""
Optional ML modules for sector rotation analysis.

These are only imported when the corresponding use_* flag is True.
"""

from .regime import RegimeClassifier
from .lead_lag import LeadLagDetector
from .anomaly import AnomalyDetector
from .ensemble import EnsembleModel

__all__ = [
    "RegimeClassifier",
    "LeadLagDetector",
    "AnomalyDetector",
    "EnsembleModel",
]
