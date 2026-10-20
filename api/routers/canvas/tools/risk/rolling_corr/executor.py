"""Canvas executor for Rolling Correlation.

Analyzes time-varying correlation between two assets or portfolios using rolling windows.
Provides Pearson or zero-mean (correlation swap) correlation with confidence intervals.
"""

import logging
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple

from core.agents.risk_tools import calculate_rolling_correlation_internal
from core.services.portfolio_service import PortfolioService
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from .charts import (
    build_correlation_timeseries_chart,
    build_confidence_intervals_chart,
    build_returns_scatter_chart
)

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, replacing NaN/Inf with default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


async def _get_portfolio_returns(
    portfolio_id: str,
    user_id: str,
    period: str,
    returns_type: str
) -> Tuple[pd.Series, str]:
    """
    Fetch portfolio and calculate weighted returns.
    
    Returns:
        Tuple of (returns_series, portfolio_label)
    """
    try:
        # Fetch portfolio (signature: user_id, portfolio_id_or_name)
        portfolio_service = PortfolioService()
        result = await portfolio_service.get_portfolio(user_id, portfolio_id)
        
        if result.get("status") != "success":
            raise ValueError(f"Portfolio {portfolio_id} not found: {result.get('message', 'Unknown error')}")
        
        portfolio = result["portfolio"]
        tickers = portfolio.get("tickers", [])
        weights = portfolio.get("weights", [])
        portfolio_name = portfolio.get("name", portfolio_id)
        
        if not tickers or not weights:
            raise ValueError(f"Portfolio {portfolio_id} has no tickers or weights")
        
        if len(tickers) != len(weights):
            raise ValueError(f"Tickers and weights length mismatch in portfolio {portfolio_id}")
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight <= 0:
            raise ValueError(f"Portfolio {portfolio_id} has invalid weights (sum <= 0)")
        weights = [w / total_weight for w in weights]
        
        # Fetch historical data for all tickers
        fmp_server = FMPMarketDataServer()
        await fmp_server.connect()
        
        all_returns = {}
        for ticker in tickers:
            try:
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })
                
                if not result or not hasattr(result, 'content'):
                    logger.warning(f"No data for {ticker} in portfolio {portfolio_id}")
                    continue
                
                data = safe_parse_json(result)
                dates = data.get("dates", [])
                prices = data.get("prices", []) or data.get("closes", [])
                
                if not dates or not prices:
                    logger.warning(f"Missing data for {ticker} in portfolio {portfolio_id}")
                    continue
                
                # Create DataFrame
                df = pd.DataFrame({
                    "date": pd.to_datetime(dates),
                    "price": prices
                })
                df = df.sort_values("date").drop_duplicates(subset='date')
                
                # Calculate returns
                if returns_type == "simple":
                    returns = df['price'].pct_change()
                elif returns_type == "logarithmic":
                    returns = np.log(df['price'] / df['price'].shift(1))
                else:  # absolute
                    returns = df['price'].pct_change().abs()
                
                returns_df = pd.DataFrame({
                    'date': df['date'].values,
                    'returns': returns.values
                })
                returns_df = returns_df.dropna()
                returns_df = returns_df.set_index('date')
                
                all_returns[ticker] = returns_df['returns']
                
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker} in portfolio {portfolio_id}: {e}")
                continue
        
        await fmp_server.cleanup()
        
        if not all_returns:
            raise ValueError(f"No valid data for any ticker in portfolio {portfolio_id}")
        
        # Align all returns to common dates
        returns_df = pd.DataFrame(all_returns)
        returns_df = returns_df.dropna()  # Only keep dates with all tickers
        
        if len(returns_df) < 30:
            raise ValueError(f"Insufficient common data for portfolio {portfolio_id}: {len(returns_df)} days")
        
        # Calculate weighted portfolio returns
        portfolio_returns = pd.Series(0.0, index=returns_df.index)
        for i, ticker in enumerate(tickers):
            if ticker in returns_df.columns:
                portfolio_returns += returns_df[ticker] * weights[i]
        
        label = f"Portfolio: {portfolio_name}"
        return portfolio_returns, label
        
    except Exception as e:
        logger.error(f"Failed to get portfolio returns for {portfolio_id}: {e}", exc_info=True)
        raise


async def execute_rolling_corr(
    user_id: str,
    org_id: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute rolling correlation for Canvas.
    
    Args:
        user_id: User ID (for RLS/permissions)
        org_id: Organization ID (for RLS/permissions)
        params: Dictionary of parameters from frontend form
        
    Returns:
        Canvas-formatted response with status, charts, metrics, etc.
    """
    try:
        # 1. EXTRACT PARAMETERS
        input_type_x = params.get("input_type_x", "ticker")
        input_type_y = params.get("input_type_y", "ticker")
        
        ticker_x = params.get("ticker_x", "").upper().strip() if params.get("ticker_x") else None
        ticker_y = params.get("ticker_y", "").upper().strip() if params.get("ticker_y") else None
        portfolio_id_x = params.get("x_portfolio_id", "").strip() if params.get("x_portfolio_id") else None
        portfolio_id_y = params.get("y_portfolio_id", "").strip() if params.get("y_portfolio_id") else None
        
        window = params.get("window", 30)
        returns_type = params.get("returns_type", "logarithmic")
        zero_mean_mode = params.get("zero_mean_mode", False)
        period = params.get("period", "2Y")
        
        # 2. VALIDATE required parameters based on input types
        if input_type_x == "ticker" and not ticker_x:
            return {
                "status": "error",
                "error": "Ticker X is required when input type is 'ticker'",
                "tool_id": "rolling_corr",
                "tickers": [],
                "weights": []
            }
        
        if input_type_x == "portfolio" and not portfolio_id_x:
            return {
                "status": "error",
                "error": "Portfolio X is required when input type is 'portfolio'",
                "tool_id": "rolling_corr",
                "tickers": [],
                "weights": []
            }
        
        if input_type_y == "ticker" and not ticker_y:
            return {
                "status": "error",
                "error": "Ticker Y is required when input type is 'ticker'",
                "tool_id": "rolling_corr",
                "tickers": [],
                "weights": []
            }
        
        if input_type_y == "portfolio" and not portfolio_id_y:
            return {
                "status": "error",
                "error": "Portfolio Y is required when input type is 'portfolio'",
                "tool_id": "rolling_corr",
                "tickers": [],
                "weights": []
            }
        
        # If both are tickers, they must be different
        if input_type_x == "ticker" and input_type_y == "ticker" and ticker_x == ticker_y:
            return {
                "status": "error",
                "error": f"Tickers must be different. Both are set to {ticker_x}",
                "tool_id": "rolling_corr",
                "tickers": [ticker_x, ticker_y],
                "weights": []
            }
        
        # Determine what we're actually comparing
        use_ticker_x = (input_type_x == "ticker")
        use_ticker_y = (input_type_y == "ticker")
        
        # Determine labels for display
        label_x = ticker_x if use_ticker_x else f"Portfolio {portfolio_id_x}"
        label_y = ticker_y if use_ticker_y else f"Portfolio {portfolio_id_y}"
        
        logger.info(f"Executing rolling correlation: {label_x} vs {label_y}, window={window}")
        
        # 3. CALL INTERNAL FUNCTION (for ticker vs ticker) OR COMPUTE PORTFOLIO CORRELATION
        # If both are tickers, use existing internal function
        if use_ticker_x and use_ticker_y:
            result = await calculate_rolling_correlation_internal(
                ticker_x=ticker_x,
                ticker_y=ticker_y,
                window=window,
                returns_type=returns_type,
                zero_mean_mode=zero_mean_mode,
                period=period
            )
            asset_x_label = ticker_x
            asset_y_label = ticker_y
            tickers_list = [ticker_x, ticker_y]
        else:
            # At least one is a portfolio - compute correlation with portfolio returns
            try:
                # Get returns for X
                if use_ticker_x:
                    # Fetch single ticker returns
                    fmp_server = FMPMarketDataServer()
                    await fmp_server.connect()
                    result_x = await fmp_server.call_tool("get_historical_data", {
                        "symbol": ticker_x,
                        "period": period
                    })
                    data_x = safe_parse_json(result_x)
                    dates_x = data_x.get("dates", [])
                    prices_x = data_x.get("prices", []) or data_x.get("closes", [])
                    
                    df_x = pd.DataFrame({"date": pd.to_datetime(dates_x), "price": prices_x})
                    df_x = df_x.sort_values("date").drop_duplicates(subset='date')
                    
                    if returns_type == "simple":
                        returns_x = df_x['price'].pct_change()
                    elif returns_type == "logarithmic":
                        returns_x = np.log(df_x['price'] / df_x['price'].shift(1))
                    else:
                        returns_x = df_x['price'].pct_change().abs()
                    
                    returns_x = pd.Series(returns_x.values, index=df_x['date'].values)
                    returns_x = returns_x.dropna()
                    asset_x_label = ticker_x
                    await fmp_server.cleanup()
                else:
                    # Get portfolio returns
                    returns_x, asset_x_label = await _get_portfolio_returns(
                        portfolio_id_x, user_id, period, returns_type
                    )
                
                # Get returns for Y
                if use_ticker_y:
                    # Fetch single ticker returns
                    fmp_server = FMPMarketDataServer()
                    await fmp_server.connect()
                    result_y = await fmp_server.call_tool("get_historical_data", {
                        "symbol": ticker_y,
                        "period": period
                    })
                    data_y = safe_parse_json(result_y)
                    dates_y = data_y.get("dates", [])
                    prices_y = data_y.get("prices", []) or data_y.get("closes", [])
                    
                    df_y = pd.DataFrame({"date": pd.to_datetime(dates_y), "price": prices_y})
                    df_y = df_y.sort_values("date").drop_duplicates(subset='date')
                    
                    if returns_type == "simple":
                        returns_y = df_y['price'].pct_change()
                    elif returns_type == "logarithmic":
                        returns_y = np.log(df_y['price'] / df_y['price'].shift(1))
                    else:
                        returns_y = df_y['price'].pct_change().abs()
                    
                    returns_y = pd.Series(returns_y.values, index=df_y['date'].values)
                    returns_y = returns_y.dropna()
                    asset_y_label = ticker_y
                    await fmp_server.cleanup()
                else:
                    # Get portfolio returns
                    returns_y, asset_y_label = await _get_portfolio_returns(
                        portfolio_id_y, user_id, period, returns_type
                    )
                
                # Align returns to common dates
                returns_df = pd.DataFrame({"x": returns_x, "y": returns_y})
                returns_df = returns_df.dropna()
                
                if len(returns_df) < window + 30:
                    raise ValueError(f"Insufficient common data: {len(returns_df)} days (need at least {window + 30})")
                
                # Calculate rolling correlation
                if zero_mean_mode:
                    # Zero-mean correlation
                    def zero_mean_corr(x_vals, y_vals):
                        numerator = (x_vals * y_vals).sum()
                        denominator = np.sqrt((x_vals**2).sum()) * np.sqrt((y_vals**2).sum())
                        return numerator / denominator if denominator > 1e-10 else np.nan
                    
                    correlation = pd.Series(index=returns_df.index, dtype=float)
                    for i in range(window - 1, len(returns_df)):
                        window_x = returns_df['x'].iloc[i - window + 1:i + 1].values
                        window_y = returns_df['y'].iloc[i - window + 1:i + 1].values
                        correlation.iloc[i] = zero_mean_corr(window_x, window_y)
                else:
                    # Standard Pearson correlation
                    correlation = returns_df['x'].rolling(window=window).corr(returns_df['y'])
                
                correlation = correlation.dropna()
                dates_series = correlation.index  # Use correlation's index after dropna()
                
                # Calculate confidence intervals
                correlation_clipped = correlation.clip(-0.9999, 0.9999)
                z = 0.5 * np.log((1 + correlation_clipped) / (1 - correlation_clipped))
                se_z = 1 / np.sqrt(window - 3)
                z_upper = z + 1.96 * se_z
                z_lower = z - 1.96 * se_z
                upper_bound = (np.exp(2 * z_upper) - 1) / (np.exp(2 * z_upper) + 1)
                lower_bound = (np.exp(2 * z_lower) - 1) / (np.exp(2 * z_lower) + 1)
                upper_bound = upper_bound.clip(-1, 1)
                lower_bound = lower_bound.clip(-1, 1)
                
                # Build result in same format as internal function
                result = {
                    'status': 'success',
                    'results': {
                        'correlation_series': correlation.tolist(),
                        'dates': [d.strftime('%Y-%m-%d') for d in dates_series],
                        'statistics': {
                            'mean_correlation': float(correlation.mean()),
                            'std_correlation': float(correlation.std()),
                            'min_correlation': float(correlation.min()),
                            'max_correlation': float(correlation.max()),
                            'current_correlation': float(correlation.iloc[-1])
                        },
                        'confidence_intervals': {
                            'upper_bound': upper_bound.tolist(),
                            'lower_bound': lower_bound.tolist()
                        },
                        'metadata': {
                            'ticker_x': asset_x_label,
                            'ticker_y': asset_y_label,
                            'window': window,
                            'returns_type': returns_type,
                            'zero_mean_mode': zero_mean_mode,
                            'n_observations': len(correlation),
                            'n_returns': len(returns_df),
                            'date_range': [
                                dates_series[0].strftime('%Y-%m-%d'),
                                dates_series[-1].strftime('%Y-%m-%d')
                            ],
                            'period': period
                        }
                    },
                    'charts': []
                }
                
                tickers_list = []
                if use_ticker_x:
                    tickers_list.append(ticker_x)
                if use_ticker_y:
                    tickers_list.append(ticker_y)
                
            except Exception as e:
                logger.error(f"Portfolio correlation failed: {e}", exc_info=True)
                return {
                    "status": "error",
                    "error": f"Portfolio correlation failed: {str(e)[:200]}",
                    "tool_id": "rolling_corr",
                    "tickers": [],
                    "weights": []
                }
        
        # 4. CHECK FOR ERRORS
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Rolling correlation failed"),
                "tool_id": "rolling_corr",
                "tickers": tickers_list,
                "weights": []
            }
        
        # 5. EXTRACT DATA from result
        results_data = result.get("results", {})
        statistics = results_data.get("statistics", {})
        metadata = results_data.get("metadata", {})
        confidence_intervals = results_data.get("confidence_intervals", {})
        
        # Use labels from metadata if available (for portfolios)
        asset_x_label = metadata.get("ticker_x", asset_x_label)
        asset_y_label = metadata.get("ticker_y", asset_y_label)
        
        mean_corr = _safe_float(statistics.get("mean_correlation", 0))
        std_corr = _safe_float(statistics.get("std_correlation", 0))
        min_corr = _safe_float(statistics.get("min_correlation", 0))
        max_corr = _safe_float(statistics.get("max_correlation", 0))
        current_corr = _safe_float(statistics.get("current_correlation", 0))
        
        n_observations = metadata.get("n_observations", 0)
        
        # 6. BUILD METRIC CARDS
        correlation_strength = "Strong" if abs(current_corr) > 0.7 else "Moderate" if abs(current_corr) > 0.4 else "Weak"
        correlation_direction = "Positive" if current_corr > 0 else "Negative" if current_corr < 0 else "Neutral"
        
        metric_cards = [
            {
                "label": "Current Correlation",
                "value": f"{current_corr:.4f}",
                "subtext": f"{correlation_strength} {correlation_direction}"
            },
            {
                "label": "Mean Correlation",
                "value": f"{mean_corr:.4f}",
                "subtext": f"Avg over {n_observations} periods"
            },
            {
                "label": "Correlation Range",
                "value": f"{min_corr:.3f} to {max_corr:.3f}",
                "subtext": f"Volatility: {std_corr:.4f}"
            }
        ]
        
        # 7. BUILD STATS TABLE
        correlation_mode = "Zero-mean (Swap)" if zero_mean_mode else "Pearson"
        
        stats_table = [
            {"category": "Input", "metric": "Asset Pair", "value": f"{asset_x_label} / {asset_y_label}"},
            {"category": "Input", "metric": "Window Size", "value": f"{window} days"},
            {"category": "Input", "metric": "Returns Type", "value": returns_type.capitalize()},
            {"category": "Input", "metric": "Correlation Mode", "value": correlation_mode},
            {"category": "Input", "metric": "Period", "value": period},
            {"category": "Result", "metric": "Current Correlation", "value": f"{current_corr:.4f}"},
            {"category": "Result", "metric": "Mean Correlation", "value": f"{mean_corr:.4f}"},
            {"category": "Result", "metric": "Std Deviation", "value": f"{std_corr:.4f}"},
            {"category": "Result", "metric": "Min Correlation", "value": f"{min_corr:.4f}"},
            {"category": "Result", "metric": "Max Correlation", "value": f"{max_corr:.4f}"},
            {"category": "Data", "metric": "Observations", "value": str(n_observations)},
        ]
        
        # Add date range if available
        date_range = metadata.get("date_range", [])
        if len(date_range) == 2:
            stats_table.append({
                "category": "Data",
                "metric": "Date Range",
                "value": f"{date_range[0]} to {date_range[1]}"
            })
        
        # 8. BUILD CHARTS
        charts = {}
        
        # Extract chart data
        correlation_series = results_data.get("correlation_series", [])
        dates = results_data.get("dates", [])
        upper_bound = confidence_intervals.get("upper_bound", [])
        lower_bound = confidence_intervals.get("lower_bound", [])
        
        # Chart 1: Correlation time series
        chart1 = build_correlation_timeseries_chart(
            correlation=correlation_series,
            dates=dates,
            ticker_x=asset_x_label,
            ticker_y=asset_y_label
        )
        if chart1:
            charts["timeseries"] = chart1
        
        # Chart 2: Confidence intervals
        chart2 = build_confidence_intervals_chart(
            correlation=correlation_series,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            dates=dates,
            ticker_x=asset_x_label,
            ticker_y=asset_y_label
        )
        if chart2:
            charts["confidence"] = chart2
        
        # Chart 3: Returns scatter (if we have returns data)
        # Note: The internal function doesn't return returns data, so we'll skip this for now
        # or we could call it separately if needed
        
        # 9. BUILD SUMMARY
        regime = "positively correlated" if current_corr > 0.3 else "negatively correlated" if current_corr < -0.3 else "uncorrelated"
        stability = "stable" if std_corr < 0.15 else "moderate" if std_corr < 0.25 else "volatile"
        
        summary = (
            f"**{asset_x_label} vs {asset_y_label} Rolling Correlation Analysis**\n\n"
            f"**Current Relationship:**\n"
            f"- **Correlation**: {current_corr:.4f} ({correlation_strength} {correlation_direction})\n"
            f"- **Assets are currently {regime}** with {stability} correlation behavior\n\n"
            f"**Historical Statistics ({window}-day window):**\n"
            f"- **Mean**: {mean_corr:.4f} (typical correlation level)\n"
            f"- **Range**: {min_corr:.3f} to {max_corr:.3f}\n"
            f"- **Volatility**: {std_corr:.4f} (correlation standard deviation)\n\n"
            f"**Analysis Configuration:**\n"
            f"- Rolling window: {window} trading days\n"
            f"- Returns type: {returns_type}\n"
            f"- Method: {correlation_mode} correlation\n"
            f"- Data points: {n_observations} observations\n\n"
            f"**Interpretation:**\n"
        )
        
        if abs(current_corr) > 0.7:
            summary += f"Strong correlation suggests the assets move together significantly. "
        elif abs(current_corr) > 0.4:
            summary += f"Moderate correlation indicates some relationship but also independent movement. "
        else:
            summary += f"Weak correlation suggests the assets move largely independently. "
        
        if std_corr > 0.25:
            summary += f"High volatility ({std_corr:.3f}) indicates the relationship changes substantially over time, suggesting regime shifts."
        elif std_corr > 0.15:
            summary += f"Moderate volatility ({std_corr:.3f}) shows the relationship varies but remains somewhat stable."
        else:
            summary += f"Low volatility ({std_corr:.3f}) indicates a stable, predictable relationship over time."
        
        # 10. RETURN CANVAS FORMAT
        return {
            "status": "success",
            "tool_id": "rolling_corr",
            "tickers": tickers_list,
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "current_correlation": current_corr,
                "mean_correlation": mean_corr,
                "std_correlation": std_corr,
                "min_correlation": min_corr,
                "max_correlation": max_corr,
                "n_observations": n_observations
            },
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Rolling correlation execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "rolling_corr",
            "tickers": [params.get("ticker_x", ""), params.get("ticker_y", "")],
            "weights": []
        }
