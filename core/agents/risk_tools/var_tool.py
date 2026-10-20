"""
Value at Risk (VaR) Calculation Tool
"""

from agents import function_tool
from typing import List, Optional
import logging
import json
import numpy as np

from core.risk_modules.var_analysis import VaRAnalysis
from core.utils.risk_adapter import adapt_mcp_to_prices, jsonify_results
from core.utils.validation import validate_weights, validate_confidence_level, validate_portfolio_value
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.constants import (
    DEFAULT_PORTFOLIO_VALUE, CONFIDENCE_LEVEL_95, CONFIDENCE_LEVEL_99,
    DEFAULT_VAR_HORIZON, DEFAULT_PERIOD
)
from .shared import fetch_market_data_batch, register_chart_handle
from core.charts.builders.risk import build_returns_histogram
from core.charts.models import ChartSpec, ChartType, ChartPriority

logger = logging.getLogger(__name__)


async def calculate_var_internal(
    tickers: List[str],
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    weights: Optional[List[float]] = None,
    method: str = "all",
    confidence_levels: Optional[List[float]] = None,
    portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
    time_horizon: int = DEFAULT_VAR_HORIZON
) -> dict:
    """Internal callable for Canvas - same logic as calculate_var but returns raw data."""
    market_server = None
    skipped_tickers = []
    try:
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        combined_data = await fetch_market_data_batch(market_server, tickers, period, start_date, end_date)
        
        prices = adapt_mcp_to_prices(combined_data, tickers)
        actual_tickers = list(prices.columns)
        
        # Track skipped tickers
        skipped_tickers = [t for t in tickers if t not in actual_tickers]
        if skipped_tickers:
            logger.warning(f"Skipped tickers with no data: {skipped_tickers}")
        
        if len(actual_tickers) < 1:
            return {"error": "No valid tickers", "skipped_tickers": skipped_tickers}
        
        if weights is not None and len(tickers) != len(actual_tickers):
            ticker_to_weight = dict(zip(tickers, weights))
            filtered_weights = [ticker_to_weight[t] for t in actual_tickers if t in ticker_to_weight]
            weights = filtered_weights
        
        weights = validate_weights(weights, len(actual_tickers))
        if confidence_levels is None:
            confidence_levels = [CONFIDENCE_LEVEL_95, CONFIDENCE_LEVEL_99]
        else:
            confidence_levels = [validate_confidence_level(cl) for cl in confidence_levels]
        portfolio_value = validate_portfolio_value(portfolio_value)
        
        var_analyzer = VaRAnalysis(confidence_levels=confidence_levels)
        results = var_analyzer.calculate_var(
            prices=prices,
            weights=weights,
            method=method,
            portfolio_value=portfolio_value
        )
        
        # Compute portfolio returns for charts
        returns = prices.pct_change().dropna()
        portfolio_returns = (returns * weights).sum(axis=1)
        
        # Extract VaR values for display
        var_summary = {}
        for var_method in ['historical_var', 'parametric_var', 'monte_carlo_var']:
            if var_method in results:
                var_data = results[var_method]
                method_name = var_method.replace('_var', '').title()
                for conf_key, var_value in var_data.items():
                    if isinstance(var_value, dict):
                        conf_pct = conf_key.replace('confidence_', '').replace('_', '')
                        if 'percentage' in var_value:
                            var_summary[f"{method_name} {conf_pct}%"] = {
                                "percentage": var_value['percentage'],
                                "dollar": var_value.get('dollar', var_value['percentage'] * portfolio_value)
                            }
        
        return {
            "status": "success",
            "var_results": results,
            "var_summary": var_summary,
            "tickers": actual_tickers,
            "skipped_tickers": skipped_tickers,
            "weights": weights.tolist() if hasattr(weights, 'tolist') else list(weights),
            "portfolio_value": portfolio_value,
            "time_horizon": time_horizon,
            "confidence_levels": confidence_levels,
            "method": method,
            "portfolio_returns": portfolio_returns.tolist(),
            "returns_mean": float(portfolio_returns.mean()),
            "returns_std": float(portfolio_returns.std()),
        }
        
    except Exception as e:
        logger.error(f"VaR calculation failed: {e}", exc_info=True)
        return {"error": str(e), "skipped_tickers": skipped_tickers}
    finally:
        if market_server:
            try:
                await market_server.cleanup()
            except Exception:
                pass


@function_tool
async def calculate_var(
    tickers: Optional[List[str]] = None,
    portfolio_id: Optional[str] = None,
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    weights: Optional[List[float]] = None,
    method: str = "all",
    confidence_levels: Optional[List[float]] = None,
    portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
    time_horizon: int = DEFAULT_VAR_HORIZON
) -> dict:
    """
    Calculate Value at Risk (VaR) for a portfolio. Automatically fetches required market data.
    
    Args:
        tickers: List of ticker symbols. OPTIONAL if portfolio_id is provided.
        portfolio_id: OPTIONAL - Portfolio ID or name to load tickers/weights from. Use this OR tickers.
        period: Historical data period. Use '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'. Default: '1y'
        start_date: OPTIONAL - Start date in YYYY-MM-DD format (e.g., '2023-01-01').
                    ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        end_date: OPTIONAL - End date in YYYY-MM-DD format (e.g., '2024-01-01').
                  ONLY provide if you have a SPECIFIC date. OMIT this parameter entirely if not needed.
        weights: OPTIONAL - Portfolio weights. OMIT for equal weighting. Ignored if portfolio_id provided.
        method: VaR calculation method: 'parametric', 'historical', 'monte_carlo', or 'all' (default: 'all')
        confidence_levels: OPTIONAL - List of confidence levels (e.g., [0.95, 0.99]). OMIT for defaults.
        portfolio_value: Total portfolio value in dollars (default: 1000000)
        time_horizon: Time horizon in days (default: 1)
    
    Returns:
        JSON string of VaR calculations with risk metrics and distribution charts
        
    Examples:
        ✅ CORRECT: calculate_var(portfolio_id="my_portfolio", method="all")
        ✅ CORRECT: calculate_var(tickers=["AAPL", "GOOGL"], period="2y", method="all")
        ❌ WRONG: DO NOT pass "null", "undefined", or empty strings for optional parameters
    """
    from .shared import resolve_portfolio_tickers
    
    market_server = None
    try:
        # Resolve tickers from portfolio if portfolio_id provided
        if portfolio_id:
            try:
                tickers, portfolio_weights = await resolve_portfolio_tickers(portfolio_id)
                weights = list(portfolio_weights.values())
            except Exception as e:
                return {
                    'status': 'error',
                    'error': str(e),
                    'error_type': 'portfolio_error',
                    'calculation_type': 'var'
                }
        
        # Validate we have tickers
        if not tickers:
            return {
                'status': 'error',
                'error': 'Either tickers or portfolio_id must be provided',
                'error_type': 'validation_error',
                'calculation_type': 'var'
            }
        # Create MCP server for data fetching (FMP as primary source)
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Use centralized data fetching
        combined_data = await fetch_market_data_batch(market_server, tickers, period, start_date, end_date)
        
        # Adapt to price DataFrame
        prices = adapt_mcp_to_prices(combined_data, tickers)
        
        # Get the actual tickers that have data (may be subset of requested tickers)
        actual_tickers = list(prices.columns)
        
        # Filter weights to match actual tickers with data
        if weights is not None and len(tickers) != len(actual_tickers):
            ticker_to_weight = dict(zip(tickers, weights))
            filtered_weights = [ticker_to_weight[t] for t in actual_tickers if t in ticker_to_weight]
            weights = filtered_weights
            logger.info(f"Filtered weights from {len(tickers)} to {len(actual_tickers)} tickers")
        
        # Use validation utils
        weights = validate_weights(weights, len(actual_tickers))
        if confidence_levels is None:
            confidence_levels = [CONFIDENCE_LEVEL_95, CONFIDENCE_LEVEL_99]
        else:
            confidence_levels = [validate_confidence_level(cl) for cl in confidence_levels]
        portfolio_value = validate_portfolio_value(portfolio_value)
        
        # Calculate VaR
        var_analyzer = VaRAnalysis(confidence_levels=confidence_levels)
        results = var_analyzer.calculate_var(
            prices=prices,
            weights=weights,
            method=method,
            portfolio_value=portfolio_value
        )
        
        # Generate chart directly (no tool calls)
        chart = None
        try:
            # Prepare returns for chart (already computed)
            returns = prices.pct_change().dropna()
            portfolio_returns = (returns * weights).sum(axis=1)

            # Extract VaR values in correct format for chart builder
            var_lines = {}
            # Process all VaR methods and confidence levels
            for var_method in ['historical_var', 'parametric_var', 'monte_carlo_var']:
                if var_method in results:
                    var_data = results[var_method]
                    for confidence_key, var_value in var_data.items():
                        if isinstance(var_value, dict) and 'percentage' in var_value:
                            # Format confidence level for display (e.g., "95%" instead of "confidence_95")
                            display_key = confidence_key.replace('confidence_', '').replace('_', ' ') + '%'
                            var_lines[display_key] = var_value['percentage']
            
            # Calculate basic statistics for the chart
            stats = {
                'mean': float(portfolio_returns.mean()) if not portfolio_returns.empty else 0.0,
                'std': float(portfolio_returns.std()) if not portfolio_returns.empty else 0.0
            }

            # Build chart spec with returns histogram format
            # Truncate ticker list for title if too long
            ticker_display = ', '.join(actual_tickers[:5])
            if len(actual_tickers) > 5:
                ticker_display += f" +{len(actual_tickers) - 5} more"
            
            chart_spec = ChartSpec(
                id=f"var_{abs(hash(str(tickers)))&0xFFFFFF:06x}",
                type=ChartType.RETURNS_HISTOGRAM,
                title=f"Returns Distribution with VaR - {ticker_display}",
                inputs={
                    'returns': portfolio_returns.tolist(),
                    'var_lines': var_lines,
                    'stats': stats
                },
                priority=ChartPriority.HIGH,
                options=None
            )
            
            # Call builder directly
            chart_figure = await build_returns_histogram(chart_spec, {})
            
            if chart_figure:
                chart = register_chart_handle(
                    chart_figure.plotly,
                    chart_type=ChartType.RETURNS_HISTOGRAM.value,
                    title=chart_figure.title,
                    alt_text=chart_figure.alt_text,
                    metadata=chart_figure.metadata,
                    chart_id=chart_figure.id
                )
        except Exception as e:
            logger.warning(f"Chart generation failed: {e}")
            # Continue without chart
        
        # Normalize units: provide both percentage and USD when possible
        normalized = jsonify_results({
            'status': 'success',
            'var_results': results,
            'tickers': tickers,
            'weights': weights.tolist(),
            'portfolio_value': portfolio_value,
            'time_horizon': time_horizon,
            'confidence_levels': confidence_levels,
            'charts': [chart] if chart else []
        })
        return normalized
        
    except Exception as e:
        logger.error(f"VaR calculation with data failed: {e}")
        error_type = 'data_error' if 'no data' in str(e).lower() else 'general_error'
        return {
            'status': 'error',
            'error': str(e),
            'error_type': error_type,
            'calculation_type': 'var'
        }
    finally:
        # Cleanup FMP server connection
        if market_server:
            try:
                await market_server.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up market server: {cleanup_error}")
