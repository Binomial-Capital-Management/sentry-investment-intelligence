"""
Chart tools for LangGraph/Agent integration.

Provides domain-specific chart catalog and build tools for agents to discover
and generate charts dynamically without any hardcoding.

Split into 5 groups to reduce token usage from 200K to ~30K per domain.
Uses strict SDK wrappers with flexible JSON payloads to satisfy
OpenAI Agents SDK requirements while maintaining flexibility.
"""

from typing import Optional, Literal
import logging
import json
from pydantic import ValidationError

# Import the function tool decorator from agents
try:
    from agents import function_tool
except ImportError:
    # Fallback for testing without agents
    def function_tool(func):
        return func

from .registry import chart_registry
from .models import ChartSpec, ChartType, ChartPriority

logger = logging.getLogger(__name__)


# Reuse one shared market server instance to avoid re-instantiation and missing env
_SHARED_MCP_SERVERS = None

def _get_shared_mcp_servers():
    global _SHARED_MCP_SERVERS
    if _SHARED_MCP_SERVERS is not None:
        return _SHARED_MCP_SERVERS
    try:
        from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
        import os
        api_key = os.getenv('FMP_API_KEY')
        if not api_key:
            raise ValueError("FMP_API_KEY not found in environment")
        fmp = FMPMarketDataServer(api_key=api_key)
        _SHARED_MCP_SERVERS = {"fmp": fmp, "market": fmp}
        logger.info("[CHART] Using shared FMPMarketDataServer for charts")
        return _SHARED_MCP_SERVERS
    except Exception as e:
        logger.info(f"[CHART] FMP unavailable ({e}); falling back to YFinanceServer")
        try:
            from core.mcp_servers.YFinanceServer import YFinanceServer
            yf = YFinanceServer()
            _SHARED_MCP_SERVERS = {"yfinance": yf, "market": yf}
            return _SHARED_MCP_SERVERS
        except Exception:
            _SHARED_MCP_SERVERS = {}
            return _SHARED_MCP_SERVERS

# Small normalizer to accept common inline shapes without relying on exact keys
def _normalize_inputs_for_inline(inputs: dict) -> dict:
    try:
        if not isinstance(inputs, dict):
            return inputs

        # series: [[x,y], ...] or [{x:..., y:...}, ...]
        if 'data' not in inputs and 'series' in inputs and isinstance(inputs['series'], list):
            series = inputs['series']
            if series and all(isinstance(pt, (list, tuple)) and len(pt) == 2 for pt in series):
                inputs['dates'] = [pt[0] for pt in series]
                inputs['data'] = [pt[1] for pt in series]
            elif series and all(isinstance(pt, dict) and 'x' in pt and 'y' in pt for pt in series):
                inputs['dates'] = [pt['x'] for pt in series]
                inputs['data'] = [pt['y'] for pt in series]

        # values + x → map to data + dates
        if 'data' not in inputs and 'values' in inputs and isinstance(inputs['values'], list):
            inputs['data'] = inputs['values']
            if 'x' in inputs and isinstance(inputs['x'], list) and 'dates' not in inputs:
                inputs['dates'] = inputs['x']
        
        # y + x → map to data + dates (common agent pattern)
        if 'data' not in inputs and 'y' in inputs and isinstance(inputs['y'], list):
            inputs['data'] = inputs['y']
            if 'x' in inputs and isinstance(inputs['x'], list) and 'dates' not in inputs:
                inputs['dates'] = inputs['x']

        # prices_dict aliasing to data_dict
        if 'data_dict' not in inputs and 'prices_dict' in inputs and isinstance(inputs['prices_dict'], dict):
            inputs['data_dict'] = inputs['prices_dict']

        # prices alias to data for simple line builders
        if 'data' not in inputs and 'prices' in inputs and isinstance(inputs['prices'], list):
            inputs['data'] = inputs['prices']
        
        # FMP returns plural OHLC field names - normalize to singular for chart builders
        if 'opens' in inputs and 'open' not in inputs:
            inputs['open'] = inputs['opens']
        if 'highs' in inputs and 'high' not in inputs:
            inputs['high'] = inputs['highs']
        if 'lows' in inputs and 'low' not in inputs:
            inputs['low'] = inputs['lows']
        if 'closes' in inputs and 'close' not in inputs:
            inputs['close'] = inputs['closes']

    except Exception:
        # Be conservative; normalization is best-effort
        pass
    return inputs

# ============================================================================
# MARKET CHARTS (for GeneralistAgent)
# ============================================================================

@function_tool
async def market_chart_catalog_tool() -> str:
    """
    List available market-related chart types with minimal schemas and examples.
    Used for price movements, market data visualization.
    Returns: JSON string list of {type, description, inputs_schema, example_inputs}
    """
    try:
        market_types = [
            ChartType.PRICE_LINE,
            ChartType.CANDLESTICK,
            ChartType.MA_OVERLAY,
            ChartType.PRICE_OVERLAY_COMPARE,
            ChartType.HISTOGRAM,
            ChartType.DENSITY_KDE,
        ]

        items = []
        for ct in market_types:
            item = chart_registry.get_schema(ct)
            if item:
                items.append({
                    "type": item.type.value,
                    "description": item.description,
                    # Keep schemas compact to avoid token bloat
                    "inputs_schema": item.inputs_schema,
                    # Provide a tiny example to guide inline data usage
                    "example_inputs": item.example_inputs if hasattr(item, 'example_inputs') else None,
                })

        return json.dumps(items)
    except Exception as e:
        logger.info(f"market_chart_catalog failed: {e}")
        return None


@function_tool
async def market_chart_build_tool(
    chart_type: Literal[
        "price_line", "candlestick", "ma_overlay", "price_overlay_compare",
        "histogram", "density_kde"
    ],
    spec_json: str,
    title: Optional[str] = None,
    priority: Literal["critical", "high", "medium", "low"] = "medium"
) -> str:
    """
    Build a market-related chart.
    
    Args:
        chart_type: Market chart type to build
        spec_json: JSON string with 'inputs' and optional 'options'
        title: Optional chart title
        priority: Display priority
    
    Returns: JSON string with chart result or None on error
    """
    try:
        logger.info(f"[CHART DEBUG] Tool called with chart_type={chart_type}, spec_json={spec_json[:200]}")
        # Parse flexible payload
        raw = json.loads(spec_json or "{}")
        inputs = raw.get("inputs", {})
        inputs = _normalize_inputs_for_inline(inputs)
        options = raw.get("options", None)
        
        # Build strict ChartSpec
        spec = ChartSpec(
            id=f"{chart_type}_{abs(hash(spec_json)) & 0xFFFFFF:06x}",
            type=ChartType(chart_type),
            title=title,
            inputs=inputs,
            options=options,
            priority={
                "critical": ChartPriority.CRITICAL,
                "high": ChartPriority.HIGH,
                "medium": ChartPriority.MEDIUM,
                "low": ChartPriority.LOW,
            }[priority],
        )
        
        # Build via registry
        fig = await chart_registry.build_chart(spec, timeout=1.5)
        if not fig:
            # Return actionable hint to encourage inline data in spec_json
            return json.dumps({
                "ok": False,
                "error": "no_data",
                "hint": "Include small series via spec_json.inputs.data (and optional inputs.dates/label) or provide prices/ohlc as per catalog example_inputs."
            })
        
        # Return simple JSON string
        out = {
            "id": fig.id,
            "title": fig.title,
            "alt_text": fig.alt_text,
            "plotly": fig.plotly,
        }
        if fig.metadata:
            out["metadata"] = fig.metadata
        return json.dumps(out)
        
    except Exception as e:
        logger.error(f"[DEBUG CHART] market_chart_build failed with error: {e}")
        import traceback
        logger.error(f"[DEBUG CHART] Traceback: {traceback.format_exc()}")
        return None


# ============================================================================
# VAR CHARTS (for calculate_var tool)
# ============================================================================

@function_tool
async def var_chart_catalog_tool() -> str:
    """
    List available VaR-related chart types and their schemas.
    Used for Value at Risk visualizations.
    
    Returns: JSON string dictionary of {type: description}
    """
    try:
        var_types = [
            ChartType.VAR_CONE,
            ChartType.RETURNS_HISTOGRAM,
            ChartType.MONTE_CARLO_PATHS,
        ]
        
        items = []
        for chart_type in var_types:
            item = chart_registry.get_schema(chart_type)
            if item:
                items.append({
                    "type": item.type.value,
                    "description": item.description,
                    "inputs_schema": item.inputs_schema,
                })
        
        return json.dumps(items)
    except Exception as e:
        logger.info(f"var_chart_catalog failed: {e}")
        return None


@function_tool
async def var_chart_build_tool(
    chart_type: Literal["var_cone", "returns_histogram", "monte_carlo_paths"],
    spec_json: str,
    title: Optional[str] = None,
    priority: Literal["critical", "high", "medium", "low"] = "medium"
) -> str:
    """
    Build a VaR-related chart.
    
    Args:
        chart_type: VaR chart type to build
        spec_json: JSON string with 'inputs' and optional 'options'
        title: Optional chart title
        priority: Display priority
    
    Returns: JSON string with chart result or None on error
    """
    try:
        # Parse flexible payload
        raw = json.loads(spec_json or "{}")
        inputs = raw.get("inputs", {})
        inputs = _normalize_inputs_for_inline(inputs)
        options = raw.get("options", None)
        
        # Build strict ChartSpec
        spec = ChartSpec(
            id=f"{chart_type}_{abs(hash(spec_json)) & 0xFFFFFF:06x}",
            type=ChartType(chart_type),
            title=title,
            inputs=inputs,
            options=options,
            priority={
                "critical": ChartPriority.CRITICAL,
                "high": ChartPriority.HIGH,
                "medium": ChartPriority.MEDIUM,
                "low": ChartPriority.LOW,
            }[priority],
        )
        
        # Build via registry
        fig = await chart_registry.build_chart(spec, timeout=1.5)
        if not fig:
            return json.dumps({
                "ok": False,
                "error": "no_data",
                "hint": "Map your risk calculation arrays to spec_json.inputs as per catalog schemas (e.g., returns/bins/paths)."
            })
        
        # Return simple JSON string
        out = {
            "id": fig.id,
            "title": fig.title,
            "alt_text": fig.alt_text,
            "plotly": fig.plotly,
        }
        if fig.metadata:
            out["metadata"] = fig.metadata
        return json.dumps(out)
        
    except Exception as e:
        logger.info(f"var_chart_build failed: {e}")
        return None


# ============================================================================
# RISK TIME SERIES CHARTS (for risk analysis)
# ============================================================================

@function_tool
async def risk_ts_chart_catalog_tool() -> str:
    """
    List available risk time series chart types and their schemas.
    Used for temporal risk analysis visualizations.
    
    Returns: JSON string dictionary of {type: description}
    """
    try:
        risk_ts_types = [
            ChartType.DRAWDOWN_CURVE,
            ChartType.ROLLING_VOLATILITY,
            ChartType.ROLLING_CORRELATION,
        ]
        
        items = []
        for chart_type in risk_ts_types:
            item = chart_registry.get_schema(chart_type)
            if item:
                items.append({
                    "type": item.type.value,
                    "description": item.description,
                    "inputs_schema": item.inputs_schema,
                })
        
        return json.dumps(items)
    except Exception as e:
        logger.info(f"risk_ts_chart_catalog failed: {e}")
        return None


@function_tool
async def risk_ts_chart_build_tool(
    chart_type: Literal["drawdown_curve", "rolling_volatility", "rolling_correlation"],
    spec_json: str,
    title: Optional[str] = None,
    priority: Literal["critical", "high", "medium", "low"] = "medium"
) -> str:
    """
    Build a risk time series chart.
    
    Args:
        chart_type: Risk time series chart type to build
        spec_json: JSON string with 'inputs' and optional 'options'
        title: Optional chart title
        priority: Display priority
    
    Returns: JSON string with chart result or None on error
    """
    try:
        # Parse flexible payload
        raw = json.loads(spec_json or "{}")
        inputs = raw.get("inputs", {})
        inputs = _normalize_inputs_for_inline(inputs)
        options = raw.get("options", None)
        
        # Build strict ChartSpec
        spec = ChartSpec(
            id=f"{chart_type}_{abs(hash(spec_json)) & 0xFFFFFF:06x}",
            type=ChartType(chart_type),
            title=title,
            inputs=inputs,
            options=options,
            priority={
                "critical": ChartPriority.CRITICAL,
                "high": ChartPriority.HIGH,
                "medium": ChartPriority.MEDIUM,
                "low": ChartPriority.LOW,
            }[priority],
        )
        
        # Build via registry
        fig = await chart_registry.build_chart(spec, timeout=1.5)
        if not fig:
            return json.dumps({
                "ok": False,
                "error": "no_data",
                "hint": "Provide resolved series via spec_json.inputs (e.g., time/value arrays or correlation inputs) as shown in catalog example_inputs."
            })
        
        # Return simple JSON string
        out = {
            "id": fig.id,
            "title": fig.title,
            "alt_text": fig.alt_text,
            "plotly": fig.plotly,
        }
        if fig.metadata:
            out["metadata"] = fig.metadata
        return json.dumps(out)
        
    except Exception as e:
        logger.info(f"risk_ts_chart_build failed: {e}")
        return None


# ============================================================================
# OPTIMIZATION CHARTS (for optimize_portfolio tool)
# ============================================================================

@function_tool
async def opt_chart_catalog_tool() -> str:
    """
    List available portfolio optimization chart types and their schemas.
    Used for efficient frontier and optimization visualizations.
    
    Returns: JSON string dictionary of {type: description}
    """
    try:
        opt_types = [
            ChartType.EFFICIENT_FRONTIER,
            ChartType.BETA_SCATTER,
            ChartType.CORRELATION_MATRIX,
        ]
        
        items = []
        for chart_type in opt_types:
            item = chart_registry.get_schema(chart_type)
            if item:
                items.append({
                    "type": item.type.value,
                    "description": item.description,
                    "inputs_schema": item.inputs_schema,
                })
        
        return json.dumps(items)
    except Exception as e:
        logger.info(f"opt_chart_catalog failed: {e}")
        return None


@function_tool
async def opt_chart_build_tool(
    chart_type: Literal["efficient_frontier", "beta_scatter", "correlation_matrix"],
    spec_json: str,
    title: Optional[str] = None,
    priority: Literal["critical", "high", "medium", "low"] = "medium"
) -> str:
    """
    Build a portfolio optimization chart.
    
    Args:
        chart_type: Optimization chart type to build
        spec_json: JSON string with 'inputs' and optional 'options'
        title: Optional chart title
        priority: Display priority
    
    Returns: JSON string with chart result or None on error
    """
    try:
        # Parse flexible payload
        raw = json.loads(spec_json or "{}")
        inputs = raw.get("inputs", {})
        inputs = _normalize_inputs_for_inline(inputs)
        options = raw.get("options", None)
        
        # Build strict ChartSpec
        spec = ChartSpec(
            id=f"{chart_type}_{abs(hash(spec_json)) & 0xFFFFFF:06x}",
            type=ChartType(chart_type),
            title=title,
            inputs=inputs,
            options=options,
            priority={
                "critical": ChartPriority.CRITICAL,
                "high": ChartPriority.HIGH,
                "medium": ChartPriority.MEDIUM,
                "low": ChartPriority.LOW,
            }[priority],
        )
        
        # Build via registry
        fig = await chart_registry.build_chart(spec, timeout=1.5)
        if not fig:
            return json.dumps({
                "ok": False,
                "error": "no_data",
                "hint": "Provide optimization/factor inputs in spec_json.inputs according to the selected chart schema (see catalog example_inputs)."
            })
        
        # Return simple JSON string
        out = {
            "id": fig.id,
            "title": fig.title,
            "alt_text": fig.alt_text,
            "plotly": fig.plotly,
        }
        if fig.metadata:
            out["metadata"] = fig.metadata
        return json.dumps(out)
        
    except Exception as e:
        logger.info(f"opt_chart_build failed: {e}")
        return None


# ============================================================================
# FACTOR & ALLOCATION CHARTS (for Barra factors and portfolio allocation)
# ============================================================================

@function_tool
async def factor_alloc_chart_catalog_tool() -> str:
    """
    List available factor analysis and allocation chart types and their schemas.
    Used for Barra factors and portfolio allocation visualizations.
    
    Returns: JSON string dictionary of {type: description}
    """
    try:
        factor_alloc_types = [
            ChartType.FACTOR_EXPOSURE,
            ChartType.FACTOR_CONTRIBUTION_BAR,
            ChartType.ALLOCATION_PIE,
            ChartType.SECTOR_ALLOCATION_BAR,
        ]
        
        items = []
        for chart_type in factor_alloc_types:
            item = chart_registry.get_schema(chart_type)
            if item:
                items.append({
                    "type": item.type.value,
                    "description": item.description,
                    "inputs_schema": item.inputs_schema,
                })
        
        return json.dumps(items)
    except Exception as e:
        logger.info(f"factor_alloc_chart_catalog failed: {e}")
        return None


@function_tool
async def factor_alloc_chart_build_tool(
    chart_type: Literal[
        "factor_exposure", "factor_contribution_bar", 
        "allocation_pie", "sector_allocation_bar"
    ],
    spec_json: str,
    title: Optional[str] = None,
    priority: Literal["critical", "high", "medium", "low"] = "medium"
) -> str:
    """
    Build a factor analysis or allocation chart.
    
    Args:
        chart_type: Factor/allocation chart type to build
        spec_json: JSON string with 'inputs' and optional 'options'
        title: Optional chart title
        priority: Display priority
    
    Returns: JSON string with chart result or None on error
    """
    try:
        # Parse flexible payload
        raw = json.loads(spec_json or "{}")
        inputs = raw.get("inputs", {})
        options = raw.get("options", None)
        
        # Build strict ChartSpec
        spec = ChartSpec(
            id=f"{chart_type}_{abs(hash(spec_json)) & 0xFFFFFF:06x}",
            type=ChartType(chart_type),
            title=title,
            inputs=inputs,
            options=options,
            priority={
                "critical": ChartPriority.CRITICAL,
                "high": ChartPriority.HIGH,
                "medium": ChartPriority.MEDIUM,
                "low": ChartPriority.LOW,
            }[priority],
        )
        
        # Build via registry
        fig = await chart_registry.build_chart(spec, timeout=1.5)
        if not fig:
            return None
        
        # Return simple JSON string
        out = {
            "id": fig.id,
            "title": fig.title,
            "alt_text": fig.alt_text,
            "plotly": fig.plotly,
        }
        if fig.metadata:
            out["metadata"] = fig.metadata
        return json.dumps(out)
        
    except Exception as e:
        logger.info(f"factor_alloc_chart_build failed: {e}")
        return None


# ============================================================================
# LEGACY SUPPORT - Keep original functions for backward compatibility
# ============================================================================



def get_chart_suggestions_prompt(analysis_type: str) -> str:
    """
    Get a prompt template for suggesting charts based on analysis type.
    
    This returns a prompt that guides the LLM to suggest appropriate charts
    based on what data is available, without hardcoding field names.
    
    Args:
        analysis_type: Type of analysis performed
    
    Returns:
        Prompt string for the LLM
    """
    from .models import DEFAULT_CHARTS
    
    # Get default chart types for this analysis
    default_types = DEFAULT_CHARTS.get(analysis_type, [])
    
    if default_types:
        chart_names = [ct.value for ct in default_types[:3]]
        suggestion = f"For {analysis_type}, consider these chart types: {', '.join(chart_names)}"
    else:
        suggestion = f"Choose appropriate charts for {analysis_type}"
    
    return f"""
Based on the analysis results, suggest up to 3 charts to visualize the data.

{suggestion}

First, call the appropriate chart_catalog tool to see available chart types and their schemas.
Then, examine the analysis results to identify what data is available.
Finally, call the corresponding chart_build tool for each appropriate chart, mapping the available data to the required inputs.

Guidelines:
- Only suggest charts where you have the required input data
- Prioritize charts that best illustrate the key findings
- Use "critical" priority for the most important chart
- Adapt the inputs based on what fields are actually present in the results
"""