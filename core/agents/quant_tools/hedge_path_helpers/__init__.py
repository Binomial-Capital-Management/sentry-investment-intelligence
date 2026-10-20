"""
Hedge Path Helpers - Modular components for optimal hedge path finding.

Modules:
- factor_calculator: Portfolio factor analysis (Greeks, beta, sectors, VaR)
- gap_to_screener: Translate factor gaps to UW/FMP screener filters
- path_optimizer: Dijkstra-based multi-objective path optimization
"""

from .factor_calculator import (
    PortfolioFactors,
    FactorTarget,
    calculate_portfolio_factors,
    translate_risk_targets_to_factors,
)
from .gap_to_screener import (
    FactorGap,
    ScreenerFilters,
    ScreenerQuery,
    HedgeCandidate,
    calculate_factor_gaps,
    gap_to_screener_filters,
    parse_uw_screener_response,
    parse_fmp_screener_response,
    _safe_float,
    _safe_int,
)
from .path_optimizer import (
    HedgeState,
    HedgeAction,
    HedgePath,
    HedgePortfolio,
    dijkstra_multi_objective,
    optimize_hedge_portfolio,
)

__all__ = [
    # Factor Calculator
    "PortfolioFactors",
    "FactorTarget",
    "calculate_portfolio_factors",
    "translate_risk_targets_to_factors",
    # Gap to Screener
    "FactorGap",
    "ScreenerFilters",
    "ScreenerQuery",
    "HedgeCandidate",
    "calculate_factor_gaps",
    "gap_to_screener_filters",
    "parse_uw_screener_response",
    "parse_fmp_screener_response",
    "_safe_float",
    "_safe_int",
    # Path Optimizer
    "HedgeState",
    "HedgeAction",
    "HedgePath",
    "HedgePortfolio",
    "dijkstra_multi_objective",
    "optimize_hedge_portfolio",
]
