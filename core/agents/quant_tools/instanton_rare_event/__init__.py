"""
Instanton Rare Event Analyzer - Physics-Based Crash Probability Tool

Computes rare event (crash) probabilities using instanton methods from
path integral theory. Finds the "most likely path to a crash" analytically
rather than simulating millions of paths.

Key Features:
- Crash probability via instanton action (not Monte Carlo)
- Severity distribution across multiple thresholds
- Path distribution with uncertainty cone
- Portfolio crash decomposition (which assets drive risk)
- Correlation regime analysis (normal vs crash correlations)

Supports:
- Single asset analysis
- Portfolio with weights
- Multi-scenario crash analysis
"""

from .tool import analyze_instanton_crash, analyze_instanton_crash_internal

__all__ = ["analyze_instanton_crash", "analyze_instanton_crash_internal"]
