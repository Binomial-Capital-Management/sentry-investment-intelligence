"""
Chart builders module.

Organizes chart builders by category and exports the registry mapping.
"""

from typing import Dict, Any
from ..models import ChartType

# Import builders from each category
from .market import (
    build_price_line,
    build_candlestick,
    build_ma_overlay,
    build_price_compare,
    PRICE_LINE_SCHEMA,
    CANDLESTICK_SCHEMA,
    MA_OVERLAY_SCHEMA,
    PRICE_COMPARE_SCHEMA,
)
from .risk import (
    build_monte_carlo_paths,
    build_returns_histogram,
    build_var_cone,
    build_drawdown_curve,
    build_rolling_volatility,
    build_rolling_correlation,
    MONTE_CARLO_SCHEMA,
    RETURNS_HISTOGRAM_SCHEMA,
    VAR_CONE_SCHEMA,
    DRAWDOWN_SCHEMA,
    ROLLING_VOL_SCHEMA,
    ROLLING_CORR_SCHEMA,
)
from .portfolio import (
    build_allocation_pie,
    build_correlation_matrix,
    ALLOCATION_PIE_SCHEMA,
    CORRELATION_MATRIX_SCHEMA,
)

from .statistical import (
    build_histogram,
    build_density_kde,
    HISTOGRAM_SCHEMA,
    DENSITY_KDE_SCHEMA,
)
from .advanced import (
    build_sector_allocation_bar,
    build_beta_scatter,
    build_efficient_frontier,
    build_factor_exposure,
    build_factor_contribution_bar,
    SECTOR_ALLOCATION_SCHEMA,
    BETA_SCATTER_SCHEMA,
    EFFICIENT_FRONTIER_SCHEMA,
    FACTOR_EXPOSURE_SCHEMA,
    FACTOR_CONTRIBUTION_SCHEMA,
)

# Registry of all chart builders
CHART_BUILDERS: Dict[ChartType, Dict[str, Any]] = {
    # Market charts
    ChartType.PRICE_LINE: {
        'builder': build_price_line,
        'schema': PRICE_LINE_SCHEMA
    },
    ChartType.CANDLESTICK: {
        'builder': build_candlestick,
        'schema': CANDLESTICK_SCHEMA
    },
    ChartType.MA_OVERLAY: {
        'builder': build_ma_overlay,
        'schema': MA_OVERLAY_SCHEMA
    },
    ChartType.PRICE_OVERLAY_COMPARE: {
        'builder': build_price_compare,
        'schema': PRICE_COMPARE_SCHEMA
    },
    
    # Statistical charts
    ChartType.HISTOGRAM: {
        'builder': build_histogram,
        'schema': HISTOGRAM_SCHEMA
    },
    ChartType.DENSITY_KDE: {
        'builder': build_density_kde,
        'schema': DENSITY_KDE_SCHEMA
    },
    
    # Risk charts
    ChartType.MONTE_CARLO_PATHS: {
        'builder': build_monte_carlo_paths,
        'schema': MONTE_CARLO_SCHEMA
    },
    ChartType.RETURNS_HISTOGRAM: {
        'builder': build_returns_histogram,
        'schema': RETURNS_HISTOGRAM_SCHEMA
    },
    ChartType.VAR_CONE: {
        'builder': build_var_cone,
        'schema': VAR_CONE_SCHEMA
    },
    ChartType.DRAWDOWN_CURVE: {
        'builder': build_drawdown_curve,
        'schema': DRAWDOWN_SCHEMA
    },
    ChartType.ROLLING_VOLATILITY: {
        'builder': build_rolling_volatility,
        'schema': ROLLING_VOL_SCHEMA
    },
    ChartType.ROLLING_CORRELATION: {
        'builder': build_rolling_correlation,
        'schema': ROLLING_CORR_SCHEMA
    },
    
    # Portfolio charts
    ChartType.ALLOCATION_PIE: {
        'builder': build_allocation_pie,
        'schema': ALLOCATION_PIE_SCHEMA
    },
    ChartType.CORRELATION_MATRIX: {
        'builder': build_correlation_matrix,
        'schema': CORRELATION_MATRIX_SCHEMA
    },
    
    # Advanced charts
    ChartType.SECTOR_ALLOCATION_BAR: {
        'builder': build_sector_allocation_bar,
        'schema': SECTOR_ALLOCATION_SCHEMA
    },
    ChartType.BETA_SCATTER: {
        'builder': build_beta_scatter,
        'schema': BETA_SCATTER_SCHEMA
    },
    ChartType.EFFICIENT_FRONTIER: {
        'builder': build_efficient_frontier,
        'schema': EFFICIENT_FRONTIER_SCHEMA
    },
    ChartType.FACTOR_EXPOSURE: {
        'builder': build_factor_exposure,
        'schema': FACTOR_EXPOSURE_SCHEMA
    },
    ChartType.FACTOR_CONTRIBUTION_BAR: {
        'builder': build_factor_contribution_bar,
        'schema': FACTOR_CONTRIBUTION_SCHEMA
    },
}