"""
Squeeze Detection Tool - Configurable ML Pipeline

Detects gamma squeeze and short squeeze setups with:
- Configurable feature groups (gamma, momentum, short, volatility)
- Configurable models (timing, magnitude, path simulation)
- All data fetched in parallel for performance
- Z-score based analysis (no hardcoded thresholds)
"""

from .squeeze_tool import detect_squeeze_setup

__all__ = ["detect_squeeze_setup"]

