"""
Herding Regime Detector - Ising Model-Inspired Crowding Analysis

Physics-inspired early warning system for detecting herding behavior
and contagion risk using magnetization, susceptibility, correlation length,
and critical slowing down computed from sector ETF returns.

Usage:
    # For agents (decorated, wraps charts):
    from core.agents.quant_tools.herding_regime import analyze_herding_regime
    
    result = await analyze_herding_regime(
        lookback_days=252,
        window=21,
        include_hmm=True,
        generate_charts=True
    )
    
    # For Canvas (internal, raw charts):
    from core.agents.quant_tools.herding_regime import analyze_herding_regime_internal
    
    result = await analyze_herding_regime_internal(
        lookback_days=252,
        window=21,
        include_hmm=True,
        generate_charts=False  # Build Canvas charts separately
    )
"""

from .tool import analyze_herding_regime, analyze_herding_regime_internal

__all__ = ["analyze_herding_regime", "analyze_herding_regime_internal"]

