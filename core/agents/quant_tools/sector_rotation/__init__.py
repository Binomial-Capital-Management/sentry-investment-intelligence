"""
Sector Rotation Flow Tool - RenTec-Style Multi-Factor Analysis

Detects capital rotation between sectors using options flow data.
Combines multiple weak signals into strong predictions.

Usage:
    from core.agents.quant_tools.sector_rotation import analyze_sector_rotation_flow
    
    # Simplest call - just delta flow z-scores
    result = await analyze_sector_rotation_flow()
    
    # Full ML mode
    result = await analyze_sector_rotation_flow(
        include_vega_flow=True,
        include_correlations=True,
        use_regime_classifier=True,
        use_ensemble=True,
        generate_trade=True,
    )
"""

from .tool import analyze_sector_rotation_flow, analyze_sector_rotation_flow_internal

__all__ = ["analyze_sector_rotation_flow", "analyze_sector_rotation_flow_internal"]
