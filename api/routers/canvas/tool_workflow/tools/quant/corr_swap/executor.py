"""Canvas executor for Correlation Swap pricing."""

import logging
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

from core.agents.quant_tools import price_correlation_swap_internal
from core.agents.quant_tools.correlation_swap_tool import (
    _calculate_zero_mean_correlation,
    _get_discount_factor,
    _calculate_rolling_correlation,
    _calculate_log_returns
)
from core.services.portfolio_service import PortfolioService
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from .charts import (
    build_correlation_timeseries_chart,
    build_payoff_breakdown_chart,
    build_sensitivity_chart,
    build_monte_carlo_distribution_chart,
    build_correlation_distribution_chart,
    build_sensitivity_chart_with_confidence,
    build_price_paths_chart
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
    lookback_days: int
) -> Tuple[pd.Series, str, pd.Series]:
    """
    Fetch portfolio and calculate weighted log returns.
    
    Returns:
        Tuple of (returns_series, portfolio_label, dates_series)
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
        all_dates = {}
        for ticker in tickers:
            try:
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "lookback_days": lookback_days
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
                df = pd.DataFrame({"date": pd.to_datetime(dates), "price": prices})
                df = df.sort_values("date").drop_duplicates(subset='date')
                
                # Calculate log returns
                log_returns = np.log(df['price'] / df['price'].shift(1)).dropna()
                
                all_returns[ticker] = pd.Series(log_returns.values, index=df['date'].iloc[1:].values)
                all_dates[ticker] = df['date'].iloc[1:].values
                
            except Exception as e:
                logger.warning(f"Error fetching {ticker} for portfolio {portfolio_id}: {e}")
                continue
        
        await fmp_server.cleanup()
        
        if not all_returns:
            raise ValueError(f"No data available for any ticker in portfolio {portfolio_id}")
        
        # Align all returns to common dates
        returns_df = pd.DataFrame(all_returns)
        returns_df = returns_df.dropna()
        
        if len(returns_df) == 0:
            raise ValueError(f"No overlapping data for portfolio {portfolio_id}")
        
        # Calculate weighted portfolio returns
        portfolio_returns = pd.Series(0.0, index=returns_df.index)
        for i, ticker in enumerate(tickers):
            if ticker in returns_df.columns:
                portfolio_returns += returns_df[ticker] * weights[i]
        
        dates_series = pd.Series(returns_df.index)
        
        return portfolio_returns, portfolio_name, dates_series
        
    except Exception as e:
        logger.error(f"Failed to get portfolio returns for {portfolio_id}: {e}")
        raise


async def execute_corr_swap(
    user_id: str,
    org_id: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Correlation Swap pricing for Canvas.
    
    Args:
        user_id: User ID for RLS context
        org_id: Organization ID for RLS context
        params: Tool parameters from frontend
    
    Returns:
        Canvas-formatted result with metrics, charts, summary
    """
    try:
        # 1. EXTRACT AND VALIDATE PARAMETERS
        input_type_x = params.get("input_type_x", "ticker")
        input_type_y = params.get("input_type_y", "ticker")
        asset_x = params.get("asset_x", "").upper().strip() if params.get("asset_x") else None
        asset_y = params.get("asset_y", "").upper().strip() if params.get("asset_y") else None
        portfolio_id_x = params.get("x_portfolio_id", "").strip() if params.get("x_portfolio_id") else None
        portfolio_id_y = params.get("y_portfolio_id", "").strip() if params.get("y_portfolio_id") else None
        
        notional = float(params.get("notional", 1000000))
        strike_correlation = float(params.get("strike_correlation", 0.5))
        tenor = int(params.get("tenor", 63))
        risk_free_rate = params.get("risk_free_rate")
        if risk_free_rate is not None:
            risk_free_rate = float(risk_free_rate) / 100.0  # Convert from % to decimal
        rolling_window = int(params.get("rolling_window", 20))
        
        # Monte Carlo parameters
        pricing_mode = params.get("pricing_mode", "realized")
        days_remaining = params.get("days_remaining")
        if days_remaining is not None:
            days_remaining = int(days_remaining)
        num_simulations = int(params.get("num_simulations", 10000))
        
        # Validate forward mode requirements
        if pricing_mode == "forward":
            if days_remaining is None:
                return {
                    "status": "error",
                    "error": "⚠️ Missing Days Remaining",
                    "details": "Forward pricing (Monte Carlo) requires the 'days_remaining' parameter. Please specify days until maturity (1-252 days).",
                    "tool_id": "corr_swap",
                    "tickers": [],
                    "weights": []
                }
            if days_remaining > tenor:
                return {
                    "status": "error",
                    "error": "⚠️ Days Remaining Exceeds Tenor",
                    "details": f"Days remaining ({days_remaining}) cannot exceed tenor ({tenor} days). The swap can't have more days left than its original maturity. Please reduce days_remaining to ≤ {tenor}.",
                    "tool_id": "corr_swap",
                    "tickers": [],
                    "weights": []
                }
        
        # 2. VALIDATE required parameters based on input types
        if input_type_x == "ticker" and not asset_x:
            return {
                "status": "error",
                "error": "asset_x is required when input_type_x is 'ticker'",
                "tool_id": "corr_swap",
                "tickers": [],
                "weights": []
            }
        if input_type_x == "portfolio" and not portfolio_id_x:
            return {
                "status": "error",
                "error": "x_portfolio_id is required when input_type_x is 'portfolio'",
                "tool_id": "corr_swap",
                "tickers": [],
                "weights": []
            }
        if input_type_y == "ticker" and not asset_y:
            return {
                "status": "error",
                "error": "asset_y is required when input_type_y is 'ticker'",
                "tool_id": "corr_swap",
                "tickers": [],
                "weights": []
            }
        if input_type_y == "portfolio" and not portfolio_id_y:
            return {
                "status": "error",
                "error": "y_portfolio_id is required when input_type_y is 'portfolio'",
                "tool_id": "corr_swap",
                "tickers": [],
                "weights": []
            }
        
        # Determine what we're actually comparing
        use_ticker_x = (input_type_x == "ticker")
        use_ticker_y = (input_type_y == "ticker")
        
        # Validate Monte Carlo mode requirements
        if pricing_mode == "forward" and (not use_ticker_x or not use_ticker_y):
            return {
                "status": "error",
                "error": "Monte Carlo forward pricing currently only supports ticker-ticker pairs. Portfolio-based correlation swaps only support realized pricing.",
                "tool_id": "corr_swap",
                "tickers": [],
                "weights": []
            }
        
        # Determine labels for display
        label_x = asset_x if use_ticker_x else f"Portfolio {portfolio_id_x}"
        label_y = asset_y if use_ticker_y else f"Portfolio {portfolio_id_y}"
        
        # 3. CALL INTERNAL FUNCTION or COMPUTE PORTFOLIO CORRELATION
        if use_ticker_x and use_ticker_y:
            # Both tickers - use internal function with MC support
            result = await price_correlation_swap_internal(
                asset_x=asset_x,
                asset_y=asset_y,
                notional=notional,
                strike_correlation=strike_correlation,
                tenor=tenor,
                risk_free_rate=risk_free_rate,
                include_rolling_corr=True,
                rolling_window=rolling_window,
                pricing_mode=pricing_mode,
                days_remaining=days_remaining,
                num_simulations=num_simulations
            )
        else:
            # At least one portfolio - compute correlation directly
            try:
                lookback_days = tenor + rolling_window + 30  # Extra buffer for holidays
                
                # Get returns for X
                if use_ticker_x:
                    # Fetch ticker data
                    fmp_server = FMPMarketDataServer()
                    await fmp_server.connect()
                    try:
                        result_x = await fmp_server.call_tool("get_historical_data", {
                            "symbol": asset_x,
                            "lookback_days": lookback_days
                        })
                        data_x = safe_parse_json(result_x)
                        dates_x = data_x.get("dates", [])
                        prices_x = data_x.get("prices", []) or data_x.get("closes", [])
                        
                        df_x = pd.DataFrame({"date": pd.to_datetime(dates_x), "price": prices_x})
                        df_x = df_x.sort_values("date").drop_duplicates(subset='date')
                        returns_x = _calculate_log_returns(df_x['price'])
                        returns_x = pd.Series(returns_x.values, index=df_x['date'].iloc[1:].values)
                        asset_x_label = asset_x
                    finally:
                        await fmp_server.cleanup()
                else:
                    # Get portfolio returns
                    returns_x, asset_x_label, _ = await _get_portfolio_returns(
                        portfolio_id_x, user_id, lookback_days
                    )
                
                # Get returns for Y
                if use_ticker_y:
                    # Fetch ticker data
                    fmp_server = FMPMarketDataServer()
                    await fmp_server.connect()
                    try:
                        result_y = await fmp_server.call_tool("get_historical_data", {
                            "symbol": asset_y,
                            "lookback_days": lookback_days
                        })
                        data_y = safe_parse_json(result_y)
                        dates_y = data_y.get("dates", [])
                        prices_y = data_y.get("prices", []) or data_y.get("closes", [])
                        
                        df_y = pd.DataFrame({"date": pd.to_datetime(dates_y), "price": prices_y})
                        df_y = df_y.sort_values("date").drop_duplicates(subset='date')
                        returns_y = _calculate_log_returns(df_y['price'])
                        returns_y = pd.Series(returns_y.values, index=df_y['date'].iloc[1:].values)
                        asset_y_label = asset_y
                    finally:
                        await fmp_server.cleanup()
                else:
                    # Get portfolio returns
                    returns_y, asset_y_label, _ = await _get_portfolio_returns(
                        portfolio_id_y, user_id, lookback_days
                    )
                
                # Align returns to common dates
                returns_df = pd.DataFrame({"x": returns_x, "y": returns_y})
                returns_df = returns_df.dropna()
                
                if len(returns_df) < 2:
                    return {
                        "status": "error",
                        "error": f"Insufficient common data: {len(returns_df)} days (need at least 2)",
                        "tool_id": "corr_swap",
                        "tickers": [],
                        "weights": []
                    }
                
                # Calculate realized correlation (zero-mean convention)
                avg_realized_correlation = _calculate_zero_mean_correlation(
                    returns_df['x'],
                    returns_df['y']
                )
                
                # Calculate rolling correlation time series
                correlation_series = []
                if len(returns_df) >= rolling_window:
                    correlation_series = await _calculate_rolling_correlation(
                        returns_df['x'],
                        returns_df['y'],
                        returns_df.index.to_series().reset_index(drop=True),
                        window=rolling_window
                    )
                
                # Calculate swap payoff and value
                correlation_difference = avg_realized_correlation - strike_correlation
                payoff_at_maturity = notional * correlation_difference
                
                # Get discount factor
                discount_factor = await _get_discount_factor(tenor, risk_free_rate)
                swap_value = payoff_at_maturity * discount_factor
                
                # Use provided risk_free_rate or default
                if risk_free_rate is None:
                    risk_free_rate = 0.04
                
                # Build result in same format as internal function
                result = {
                    "status": "success",
                    "swap_value": float(swap_value),
                    "payoff_at_maturity": float(payoff_at_maturity),
                    "realized_correlation": float(avg_realized_correlation),
                    "strike_correlation": float(strike_correlation),
                    "correlation_difference": float(correlation_difference),
                    "notional": float(notional),
                    "tenor_days": int(tenor),
                    "discount_factor": float(discount_factor),
                    "risk_free_rate": float(risk_free_rate),
                    "correlation_series": correlation_series,
                    "correlation_method": "zero_mean",
                    "asset_x": asset_x_label,
                    "asset_y": asset_y_label
                }
                
                # Update labels for later use
                label_x = asset_x_label
                label_y = asset_y_label
                
            except Exception as e:
                logger.error(f"Portfolio correlation failed: {e}", exc_info=True)
                return {
                    "status": "error",
                    "error": f"Portfolio correlation failed: {str(e)}",
                    "tool_id": "corr_swap",
                    "tickers": [],
                    "weights": []
                }
        
        # 3. CHECK FOR ERRORS
        if result.get("status") == "error" or "error" in result:
            error_msg = result.get("error", "Unknown error")
            details = result.get("details", "")
            return {
                "status": "error",
                "error": f"Correlation swap pricing failed: {error_msg}",
                "details": details,
                "tool_id": "corr_swap",
                "tickers": [asset_x, asset_y],
                "weights": []
            }
        
        # 4. EXTRACT DATA (check if Monte Carlo mode)
        is_monte_carlo = (result.get("pricing_mode") == "forward")
        
        swap_value = _safe_float(result.get("swap_value", 0))
        payoff_at_maturity = _safe_float(result.get("payoff_at_maturity", 0))
        realized_correlation = _safe_float(result.get("realized_correlation", 0))
        strike_corr = _safe_float(result.get("strike_correlation", strike_correlation))
        correlation_diff = _safe_float(result.get("correlation_difference", 0))
        discount_factor = _safe_float(result.get("discount_factor", 1.0))
        risk_free_rate_used = _safe_float(result.get("risk_free_rate", 0.04))
        correlation_series = result.get("correlation_series", [])
        
        # Monte Carlo specific fields
        mc_data = {}
        if is_monte_carlo:
            mc_data = {
                "expected_pv": _safe_float(result.get("expected_pv", 0)),
                "pv_std_dev": _safe_float(result.get("pv_std_dev", 0)),
                "prob_profit": _safe_float(result.get("prob_profit", 0)),
                "percentiles": result.get("percentiles", {}),
                "payoff_distribution": result.get("payoff_distribution", []),
                "correlation_distribution": result.get("correlation_distribution", []),
                "mean_simulated_correlation": _safe_float(result.get("mean_simulated_correlation", 0)),
                "historical_correlation": _safe_float(result.get("historical_correlation", 0)),
                "num_simulations": result.get("num_simulations", num_simulations),
                "days_remaining": result.get("days_remaining", days_remaining),
                "sample_paths_x": result.get("sample_paths_x", []),
                "sample_paths_y": result.get("sample_paths_y", []),
                "current_price_x": _safe_float(result.get("current_price_x", 0)),
                "current_price_y": _safe_float(result.get("current_price_y", 0))
            }
        
        # 5. BUILD METRIC CARDS
        if is_monte_carlo:
            # Monte Carlo mode - show probabilistic metrics
            expected_pv = mc_data["expected_pv"]
            prob_profit = mc_data["prob_profit"]
            pv_std_dev = mc_data["pv_std_dev"]
            mean_corr = mc_data["mean_simulated_correlation"]
            
            pnl_direction = "expected profit" if expected_pv > 0 else "expected loss" if expected_pv < 0 else "breakeven"
            pnl_color = "green" if expected_pv > 0 else "red" if expected_pv < 0 else "gray"
            
            metric_cards = [
                {
                    "label": "Expected PV (Monte Carlo)",
                    "value": f"${expected_pv:,.0f}",
                    "subtext": f"{pnl_direction.capitalize()}",
                    "color": pnl_color
                },
                {
                    "label": "Probability of Profit",
                    "value": f"{prob_profit:.1%}",
                    "subtext": f"({mc_data['num_simulations']:,} simulations)"
                },
                {
                    "label": "PV Standard Deviation",
                    "value": f"${pv_std_dev:,.0f}",
                    "subtext": "Uncertainty range"
                },
                {
                    "label": "Mean Simulated Corr",
                    "value": f"{mean_corr:.4f}",
                    "subtext": f"vs Strike {strike_corr:.4f}"
                }
            ]
        else:
            # Realized mode - show actual metrics
            pnl_direction = "profit" if swap_value > 0 else "loss" if swap_value < 0 else "breakeven"
            pnl_color = "green" if swap_value > 0 else "red" if swap_value < 0 else "gray"
            
            correlation_status = (
                "Above Strike" if realized_correlation > strike_corr
                else "Below Strike" if realized_correlation < strike_corr
                else "At Strike"
            )
            
            metric_cards = [
                {
                    "label": "Swap Present Value",
                    "value": f"${swap_value:,.0f}",
                    "subtext": f"{pnl_direction.capitalize()} for buyer",
                    "color": pnl_color
                },
                {
                    "label": "Realized Correlation",
                    "value": f"{realized_correlation:.4f}",
                    "subtext": f"{correlation_status}"
                },
                {
                    "label": "Payoff at Maturity",
                    "value": f"${payoff_at_maturity:,.0f}",
                    "subtext": f"Undiscounted payoff"
                },
                {
                    "label": "Correlation Spread",
                    "value": f"{correlation_diff:+.4f}",
                    "subtext": "Realized - Strike"
                }
            ]
        
        # 6. BUILD STATS TABLE
        if is_monte_carlo:
            # Monte Carlo stats table
            percentiles = mc_data["percentiles"]
            stats_table = [
                {"category": "Monte Carlo", "metric": "Expected PV", "value": f"${mc_data['expected_pv']:,.2f}"},
                {"category": "Monte Carlo", "metric": "PV Std Dev", "value": f"${mc_data['pv_std_dev']:,.2f}"},
                {"category": "Monte Carlo", "metric": "Probability of Profit", "value": f"{mc_data['prob_profit']:.2%}"},
                {"category": "Monte Carlo", "metric": "5th Percentile PV", "value": f"${percentiles.get('p5', 0):,.2f}"},
                {"category": "Monte Carlo", "metric": "Median PV", "value": f"${percentiles.get('p50', 0):,.2f}"},
                {"category": "Monte Carlo", "metric": "95th Percentile PV", "value": f"${percentiles.get('p95', 0):,.2f}"},
                {"category": "Monte Carlo", "metric": "Number of Simulations", "value": f"{mc_data['num_simulations']:,}"},
                {"category": "Correlation", "metric": "Mean Simulated Corr", "value": f"{mc_data['mean_simulated_correlation']:.6f}"},
                {"category": "Correlation", "metric": "Historical Correlation", "value": f"{mc_data['historical_correlation']:.6f}"},
                {"category": "Correlation", "metric": "Strike Correlation", "value": f"{strike_corr:.6f}"},
                {"category": "Parameters", "metric": "Days Remaining", "value": f"{mc_data['days_remaining']}"},
                {"category": "Parameters", "metric": "Notional Amount", "value": f"${notional:,.0f}"},
                {"category": "Parameters", "metric": "Risk-Free Rate", "value": f"{risk_free_rate_used:.2%}"},
                {"category": "Parameters", "metric": "Correlation Method", "value": "Zero-Mean (Swap Convention)"}
            ]
        else:
            # Realized stats table
            stats_table = [
                {"category": "Valuation", "metric": "Swap Present Value", "value": f"${swap_value:,.2f}"},
                {"category": "Valuation", "metric": "Payoff at Maturity", "value": f"${payoff_at_maturity:,.2f}"},
                {"category": "Valuation", "metric": "Notional Amount", "value": f"${notional:,.0f}"},
                {"category": "Correlation", "metric": "Realized Correlation", "value": f"{realized_correlation:.6f}"},
                {"category": "Correlation", "metric": "Strike Correlation", "value": f"{strike_corr:.6f}"},
                {"category": "Correlation", "metric": "Correlation Difference", "value": f"{correlation_diff:+.6f}"},
                {"category": "Parameters", "metric": "Tenor (Days)", "value": f"{tenor}"},
                {"category": "Parameters", "metric": "Discount Factor", "value": f"{discount_factor:.6f}"},
                {"category": "Parameters", "metric": "Risk-Free Rate", "value": f"{risk_free_rate_used:.2%}"},
                {"category": "Parameters", "metric": "Correlation Method", "value": "Zero-Mean (Swap Convention)"},
                {"category": "Parameters", "metric": "Rolling Window", "value": f"{rolling_window} days"},
                {"category": "Parameters", "metric": "Data Points", "value": f"{len(correlation_series)}"}
            ]
        
        # 7. BUILD CHARTS
        charts = {}
        
        if is_monte_carlo:
            # Monte Carlo specific charts
            mc_chart1 = build_price_paths_chart(
                sample_paths_x=mc_data["sample_paths_x"],
                sample_paths_y=mc_data["sample_paths_y"],
                current_price_x=mc_data["current_price_x"],
                current_price_y=mc_data["current_price_y"],
                days_remaining=mc_data["days_remaining"],
                asset_x=label_x,
                asset_y=label_y
            )
            if mc_chart1:
                charts["mc_price_paths"] = mc_chart1
            
            mc_chart2 = build_monte_carlo_distribution_chart(
                payoff_distribution=mc_data["payoff_distribution"],
                expected_value=mc_data["expected_pv"],
                percentiles=mc_data["percentiles"],
                asset_x=label_x,
                asset_y=label_y
            )
            if mc_chart2:
                charts["mc_payoff_distribution"] = mc_chart2
            
            mc_chart3 = build_correlation_distribution_chart(
                correlation_distribution=mc_data["correlation_distribution"],
                mean_correlation=mc_data["mean_simulated_correlation"],
                strike_correlation=strike_corr,
                historical_correlation=mc_data["historical_correlation"],
                asset_x=label_x,
                asset_y=label_y
            )
            if mc_chart3:
                charts["mc_correlation_distribution"] = mc_chart3
            
            mc_chart4 = build_sensitivity_chart_with_confidence(
                notional=notional,
                strike_correlation=strike_corr,
                realized_correlation=mc_data["mean_simulated_correlation"],
                discount_factor=discount_factor,
                percentiles=mc_data["percentiles"],
                asset_x=label_x,
                asset_y=label_y
            )
            if mc_chart4:
                charts["mc_pnl_sensitivity"] = mc_chart4
        else:
            # Realized mode charts
            # Chart 1: Correlation timeseries
            if correlation_series:
                chart1 = build_correlation_timeseries_chart(
                    correlation_series=correlation_series,
                    strike_correlation=strike_corr,
                    realized_correlation=realized_correlation,
                    asset_x=label_x,
                    asset_y=label_y
                )
                if chart1:
                    charts["correlation_timeseries"] = chart1
            
            # Chart 2: Payoff breakdown
            chart2 = build_payoff_breakdown_chart(
                swap_value=swap_value,
                payoff_at_maturity=payoff_at_maturity,
                notional=notional,
                correlation_difference=correlation_diff,
                discount_factor=discount_factor
            )
            if chart2:
                charts["payoff_breakdown"] = chart2
            
            # Chart 3: P&L sensitivity
            chart3 = build_sensitivity_chart(
                notional=notional,
                strike_correlation=strike_corr,
                realized_correlation=realized_correlation,
                discount_factor=discount_factor,
                asset_x=label_x,
                asset_y=label_y
            )
            if chart3:
                charts["pnl_sensitivity"] = chart3
        
        # 8. BUILD SUMMARY
        if is_monte_carlo:
            # Monte Carlo summary
            expected_pv = mc_data["expected_pv"]
            prob_profit = mc_data["prob_profit"]
            pv_std_dev = mc_data["pv_std_dev"]
            mean_corr = mc_data["mean_simulated_correlation"]
            percentiles = mc_data["percentiles"]
            
            outcome = "expected profit" if expected_pv > 0 else "expected loss" if expected_pv < 0 else "expected breakeven"
            
            summary = (
                f"**{label_x} vs {label_y} Correlation Swap - Monte Carlo Forward Pricing**\n\n"
                f"**Monte Carlo Results ({mc_data['num_simulations']:,} simulations):**\n"
                f"- **Expected PV**: ${expected_pv:,.2f} ({outcome})\n"
                f"- **PV Standard Deviation**: ${pv_std_dev:,.2f}\n"
                f"- **Probability of Profit**: {prob_profit:.1%}\n"
                f"- **5th Percentile (VaR)**: ${percentiles.get('p5', 0):,.2f}\n"
                f"- **Median PV**: ${percentiles.get('p50', 0):,.2f}\n"
                f"- **95th Percentile**: ${percentiles.get('p95', 0):,.2f}\n\n"
                f"**Correlation Analysis:**\n"
                f"- **Mean Simulated Correlation**: {mean_corr:.6f}\n"
                f"- **Historical Correlation**: {mc_data['historical_correlation']:.6f}\n"
                f"- **Strike Correlation**: {strike_corr:.6f}\n"
                f"- **Spread (Mean Sim - Strike)**: {mean_corr - strike_corr:+.6f}\n\n"
                f"**Swap Parameters:**\n"
                f"- **Days Remaining to Maturity**: {mc_data['days_remaining']} days\n"
                f"- **Notional Amount**: ${notional:,.0f}\n"
                f"- **Risk-Free Rate**: {risk_free_rate_used:.2%}\n"
                f"- **Correlation Method**: Zero-mean (swap convention)\n\n"
                f"**Interpretation:**\n"
                f"This is a **forward pricing** (pre-maturity) using Monte Carlo simulation. "
                f"The expected present value of ${expected_pv:,.2f} represents the mean outcome across "
                f"{mc_data['num_simulations']:,} simulated scenarios with {mc_data['days_remaining']} days remaining. "
            )
            
            if prob_profit > 0.6:
                summary += (
                    f"With a {prob_profit:.1%} probability of profit, the swap is **likely favorable** "
                    f"for the buyer (long correlation). "
                )
            elif prob_profit < 0.4:
                summary += (
                    f"With only a {prob_profit:.1%} probability of profit, the swap is **likely unfavorable** "
                    f"for the buyer (long correlation). "
                )
            else:
                summary += (
                    f"With a {prob_profit:.1%} probability of profit, the swap outcome is **uncertain**. "
                )
            
            summary += (
                f"The 90% confidence interval ranges from ${percentiles.get('p5', 0):,.2f} (5th percentile) "
                f"to ${percentiles.get('p95', 0):,.2f} (95th percentile).\n\n"
                f"**Risk Metrics:**\n"
                f"- **Value at Risk (5%)**: ${abs(percentiles.get('p5', 0)):,.2f}\n"
                f"- **Expected Shortfall**: Based on left tail of distribution\n"
                f"- **Volatility (PV Std Dev)**: ${pv_std_dev:,.2f}\n\n"
                f"**Zero-Mean Correlation:**\n"
                f"Correlation swaps use zero-mean correlation: ρ = Σ(R×S) / [√(ΣR²) × √(ΣS²)]. "
                f"This market convention differs from Pearson correlation and better reflects "
                f"pure directional co-movement for hedging purposes."
            )
        else:
            # Realized summary
            buyer_position = "profitable" if swap_value > 0 else "unprofitable" if swap_value < 0 else "at breakeven"
            correlation_relationship = (
                "higher than" if realized_correlation > strike_corr
                else "lower than" if realized_correlation < strike_corr
                else "equal to"
            )
            
            pnl_per_bp = (notional * discount_factor) / 10000  # P&L per 0.01% correlation move
            
            summary = (
                f"**{label_x} vs {label_y} Correlation Swap Pricing**\n\n"
                f"**Swap Valuation:**\n"
                f"- **Present Value**: ${swap_value:,.2f} ({pnl_direction})\n"
                f"- **Payoff at Maturity**: ${payoff_at_maturity:,.2f}\n"
                f"- **Notional**: ${notional:,.0f}\n"
                f"- **Discount Factor**: {discount_factor:.4f} (r = {risk_free_rate_used:.2%})\n\n"
                f"**Correlation Analysis:**\n"
                f"- **Realized**: {realized_correlation:.6f} ({len(correlation_series)} periods)\n"
                f"- **Strike**: {strike_corr:.6f}\n"
                f"- **Spread**: {correlation_diff:+.6f}\n"
                f"- Realized correlation is **{correlation_relationship}** the strike\n\n"
                f"**Swap Structure:**\n"
                f"- **Tenor**: {tenor} days (~{tenor/252:.1f} years)\n"
                f"- **Method**: Zero-mean correlation (correlation swap convention)\n"
                f"- **Rolling Window**: {rolling_window} trading days\n"
                f"- **P&L Sensitivity**: ${pnl_per_bp:,.0f} per 0.0001 correlation change\n\n"
                f"**Interpretation:**\n"
            )
            
            if swap_value > 0:
                summary += (
                    f"The swap is **{buyer_position}** for the buyer (long correlation) because realized "
                    f"correlation ({realized_correlation:.4f}) exceeded the strike ({strike_corr:.4f}). "
                    f"The buyer receives ${payoff_at_maturity:,.0f} at maturity, worth ${swap_value:,.0f} today. "
                )
            elif swap_value < 0:
                summary += (
                    f"The swap is **{buyer_position}** for the buyer (long correlation) because realized "
                    f"correlation ({realized_correlation:.4f}) fell short of the strike ({strike_corr:.4f}). "
                    f"The buyer pays ${abs(payoff_at_maturity):,.0f} at maturity, costing ${abs(swap_value):,.0f} today. "
                )
            else:
                summary += (
                    f"The swap is **at breakeven** because realized correlation exactly matched the strike. "
                )
            
            summary += (
                f"\n\n**Zero-Mean Correlation:**\n"
                f"Correlation swaps use zero-mean correlation: ρ = Σ(R×S) / [√(ΣR²) × √(ΣS²)]. "
                f"This is the market convention and differs from Pearson correlation (which subtracts means first). "
                f"Zero-mean correlation better reflects pure directional co-movement for hedging purposes."
            )
        
        # 9. BUILD TICKERS LIST
        tickers_list = []
        if use_ticker_x:
            tickers_list.append(asset_x)
        if use_ticker_y:
            tickers_list.append(asset_y)
        
        # 10. BUILD METRICS DICT
        metrics_dict = {
            "notional": notional,
            "strike_correlation": strike_corr,
            "tenor_days": tenor,
            "discount_factor": discount_factor,
            "risk_free_rate": risk_free_rate_used
        }
        
        if is_monte_carlo:
            # Add Monte Carlo specific metrics
            metrics_dict.update({
                "pricing_mode": "forward",
                "expected_pv": mc_data["expected_pv"],
                "pv_std_dev": mc_data["pv_std_dev"],
                "prob_profit": mc_data["prob_profit"],
                "mean_simulated_correlation": mc_data["mean_simulated_correlation"],
                "historical_correlation": mc_data["historical_correlation"],
                "num_simulations": mc_data["num_simulations"],
                "days_remaining": mc_data["days_remaining"],
                "p5": mc_data["percentiles"].get("p5", 0),
                "p50": mc_data["percentiles"].get("p50", 0),
                "p95": mc_data["percentiles"].get("p95", 0)
            })
        else:
            # Add realized pricing metrics
            metrics_dict.update({
                "pricing_mode": "realized",
                "swap_value": swap_value,
                "payoff_at_maturity": payoff_at_maturity,
                "realized_correlation": realized_correlation,
                "correlation_difference": correlation_diff
            })
        
        # 11. RETURN CANVAS FORMAT
        return {
            "status": "success",
            "tool_id": "corr_swap",
            "tickers": tickers_list,
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": metrics_dict,
            "summary": summary
        }
    
    except ValueError as e:
        logger.error(f"Parameter validation error: {e}")
        return {
            "status": "error",
            "error": f"Invalid parameters: {str(e)}",
            "tool_id": "corr_swap",
            "tickers": [],
            "weights": []
        }
    except Exception as e:
        logger.error(f"Correlation swap execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"Execution failed: {str(e)}",
            "tool_id": "corr_swap",
            "tickers": [],
            "weights": []
        }
