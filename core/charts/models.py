"""
Pydantic v2 models for chart specifications.

Clean, strict validation without defensive programming bloat.
Uses orjson for fast serialization when available.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
from typing import Dict, Any, Optional, List

# Try to use orjson for performance, fallback to standard json
try:
    import orjson
    def orjson_dumps(v, *, default):
        return orjson.dumps(v, default=default).decode()
except ImportError:
    import json
    orjson_dumps = json.dumps


class ChartType(str, Enum):
    """All supported chart types"""
    # Market/Price
    PRICE_LINE = "price_line"
    CANDLESTICK = "candlestick"
    MA_OVERLAY = "ma_overlay"
    PRICE_OVERLAY_COMPARE = "price_overlay_compare"

    # Generic / visualization primitives
    BAR = "bar"
    SCATTER = "scatter"
    HEATMAP = "heatmap"

    # Statistical
    HISTOGRAM = "histogram"
    DENSITY_KDE = "density_kde"
    
    # Risk/Portfolio
    MONTE_CARLO_PATHS = "monte_carlo_paths"
    RETURNS_HISTOGRAM = "returns_histogram"
    DRAWDOWN_CURVE = "drawdown_curve"
    ROLLING_VOLATILITY = "rolling_volatility"
    ROLLING_CORRELATION = "rolling_correlation"
    CORRELATION_MATRIX = "correlation_matrix"
    ALLOCATION_PIE = "allocation_pie"
    SECTOR_ALLOCATION_BAR = "sector_allocation_bar"
    BETA_SCATTER = "beta_scatter"
    EFFICIENT_FRONTIER = "efficient_frontier"
    FACTOR_EXPOSURE = "factor_exposure"
    FACTOR_CONTRIBUTION_BAR = "factor_contribution_bar"
    VAR_CONE = "var_cone"


class ChartPriority(int, Enum):
    """Chart display priority"""
    CRITICAL = 1    # Must show
    HIGH = 2        # Should show
    MEDIUM = 3      # Nice to have
    LOW = 4         # Optional
    PRIMARY = HIGH
    SECONDARY = MEDIUM
    TERTIARY = LOW


class ChartSpec(BaseModel):
    """Chart specification from agent"""
    model_config = ConfigDict(
        json_encoders={bytes: lambda v: orjson_dumps(v)},
        validate_assignment=True,
        extra='forbid'  # Strict validation - no unknown fields
    )
    
    id: str = Field(..., pattern="^[a-z0-9_]+$", max_length=50)
    type: ChartType
    title: Optional[str] = Field(None, max_length=200)
    inputs: Dict[str, Any]  # Type-specific inputs
    options: Optional[Dict[str, Any]] = None
    priority: ChartPriority = ChartPriority.MEDIUM
    
    @field_validator('inputs')
    @classmethod
    def validate_inputs_size(cls, v):
        """Ensure inputs are reasonable size (100KB limit)"""
        # Simple size check without serialization overhead
        if isinstance(v, dict):
            # Rough estimate: key + value strings
            size_estimate = sum(
                len(str(k)) + len(str(val)) 
                for k, val in v.items()
            )
            if size_estimate > 100_000:
                raise ValueError("Inputs too large (>100KB)")
        return v


class ChartFigure(BaseModel):
    """Generated chart with Plotly data"""
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    id: str = Field(..., max_length=50)
    title: str = Field(..., max_length=200)
    alt_text: str = Field(..., max_length=500)  # Accessibility & PDF captions
    plotly: Dict[str, Any]  # Plotly figure dict
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('plotly')
    @classmethod
    def validate_plotly_size(cls, v):
        """Cap Plotly JSON size at 500KB"""
        # Rough size estimate
        if isinstance(v, dict):
            # Check data array sizes
            if 'data' in v and isinstance(v['data'], list):
                total_points = 0
                for trace in v['data']:
                    if isinstance(trace, dict):
                        # Count x/y data points
                        if 'x' in trace and isinstance(trace['x'], list):
                            total_points += len(trace['x'])
                        if 'y' in trace and isinstance(trace['y'], list):
                            total_points += len(trace['y'])
                
                # Rough estimate: 50 bytes per point
                if total_points * 50 > 500_000:
                    raise ValueError(f"Chart data too large ({total_points} points)")
        return v


class ChartListItem(BaseModel):
    """Chart type description for discovery"""
    model_config = ConfigDict(validate_assignment=True)
    
    type: ChartType
    inputs_schema: Dict[str, Any]  # JSON Schema
    description: str = Field(..., max_length=500)
    example_inputs: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None
    
    @field_validator('inputs_schema')
    @classmethod
    def validate_schema(cls, v):
        """Ensure it's a valid JSON Schema structure"""
        if not isinstance(v, dict):
            raise ValueError("inputs_schema must be a dict")
        if 'type' not in v:
            v['type'] = 'object'
        return v


# Default chart attachments by analysis type
DEFAULT_CHARTS = {
    "monte_carlo": [
        ChartType.MONTE_CARLO_PATHS,
        ChartType.RETURNS_HISTOGRAM,
        ChartType.VAR_CONE,
    ],
    "var_analysis": [
        ChartType.RETURNS_HISTOGRAM,
        ChartType.VAR_CONE,
    ],
    "portfolio_rundown": [
        ChartType.ALLOCATION_PIE,
        ChartType.CORRELATION_MATRIX,
        ChartType.SECTOR_ALLOCATION_BAR,
    ],
    "efficient_frontier": [
        ChartType.EFFICIENT_FRONTIER,
        ChartType.BETA_SCATTER,
    ],
    "factor_exposure": [
        ChartType.FACTOR_EXPOSURE,
        ChartType.FACTOR_CONTRIBUTION_BAR,
    ],
    "price_trend": [
        ChartType.PRICE_LINE,
        ChartType.MA_OVERLAY,
        ChartType.ROLLING_VOLATILITY,
    ],
    "performance_summary": [
        ChartType.DRAWDOWN_CURVE,
        ChartType.RETURNS_HISTOGRAM,
        ChartType.ROLLING_VOLATILITY,
    ],
}
