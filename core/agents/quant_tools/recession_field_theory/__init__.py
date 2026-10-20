"""
Recession Field Theory - Physics-Inspired Economic Early Warning System

A quantitative tool that applies concepts from statistical mechanics and
phase transition theory to detect recession risk early.

Components:
- data_fetcher: FRED economic indicators + FMP market data
- field_builder: Composite economic field construction
- physics_stats: Critical slowing down, correlation length, susceptibility
- hmm_regime: Hidden Markov Model regime detection
- ml_classifier: Optional ML recession probability
- charts: Visualizations
- tool: Main entry point

Usage:
    from core.agents.quant_tools.recession_field_theory import analyze_recession_field
    
    result = await analyze_recession_field(lookback_years=5)
"""

from .tool import analyze_recession_field

__all__ = [
    "analyze_recession_field"
]

