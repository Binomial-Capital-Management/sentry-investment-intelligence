"""
Hedge Ratio Canvas Executor
Optimal hedge ratio calculation for pairs trading using OLS, TLS, or Kalman methods.
Supports both individual tickers and portfolios.
"""
from typing import Dict, Any, Optional
import logging
import pandas as pd
import numpy as np
from core.agents.quant_tools.hedge_ratio_tool import calculate_hedge_ratio_internal
from core.services.portfolio_service import PortfolioService
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


async def _get_portfolio_weighted_prices(
    user_id: str,
    portfolio_id: str,
    period: str
) -> tuple[pd.Series, str]:
    """
    Fetch portfolio and calculate weighted price series.
    
    Returns:
        Tuple of (price_series, portfolio_name)
    """
    try:
        # Fetch portfolio
        portfolio_service = PortfolioService()
        result = await portfolio_service.get_portfolio(user_id, portfolio_id)
        
        if result.get("status") != "success":
            raise ValueError(f"Portfolio not found: {result.get('message', 'Unknown error')}")
        
        portfolio = result.get("portfolio", {})
        tickers = portfolio.get("tickers", [])
        weights = portfolio.get("weights", [])
        portfolio_name = portfolio.get("name", portfolio_id)
        
        if not tickers or not weights or len(tickers) != len(weights):
            raise ValueError(f"Invalid portfolio data")
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight <= 0:
            raise ValueError(f"Invalid weights (sum <= 0)")
        weights = [w / total_weight for w in weights]
        
        # Fetch historical data for all tickers
        fmp_server = FMPMarketDataServer()
        await fmp_server.connect()
        
        all_prices = {}
        for ticker in tickers:
            try:
                # Map period to lookback days
                period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}.get(period, 365)
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=period_days)
                
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })
                
                if not result or not hasattr(result, 'content'):
                    logger.warning(f"No data for {ticker}")
                    continue
                
                data = safe_parse_json(result)
                dates = data.get("dates", [])
                prices = data.get("prices", []) or data.get("closes", [])
                
                if not dates or not prices:
                    logger.warning(f"Missing data for {ticker}")
                    continue
                
                # Create DataFrame
                df = pd.DataFrame({"date": pd.to_datetime(dates), "price": prices})
                df = df.sort_values("date").set_index("date")
                all_prices[ticker] = df["price"]
                
            except Exception as e:
                logger.warning(f"Error fetching {ticker}: {e}")
                continue
        
        await fmp_server.cleanup()
        
        if not all_prices:
            raise ValueError("No valid ticker data in portfolio")
        
        # Align all series
        price_df = pd.DataFrame(all_prices)
        price_df = price_df.dropna()
        
        if len(price_df) < 30:
            raise ValueError(f"Insufficient data after alignment: {len(price_df)} days")
        
        # Calculate weighted portfolio price
        weighted_prices = np.zeros(len(price_df))
        for i, ticker in enumerate(tickers):
            if ticker in price_df.columns:
                weighted_prices += price_df[ticker].values * weights[i]
        
        portfolio_series = pd.Series(weighted_prices, index=price_df.index)
        
        return portfolio_series, portfolio_name
        
    except Exception as e:
        logger.error(f"Portfolio data fetch failed: {e}")
        raise


async def execute_hedge_ratio(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Hedge Ratio for Canvas."""
    from .charts import build_hedge_ratio_timeseries_chart, build_scatter_chart, build_residuals_chart, build_regression_fit_chart
    
    input_type_primary = params.get('input_type_primary', 'ticker')
    input_type_hedge = params.get('input_type_hedge', 'ticker')
    
    primary_asset = params.get('primary_asset')
    hedge_asset = params.get('hedge_asset')
    primary_portfolio_id = params.get('primary_portfolio_id')
    hedge_portfolio_id = params.get('hedge_portfolio_id')
    
    method = params.get('method', 'ols')
    window = params.get('window')
    period = params.get('period', '1Y')
    
    # Determine asset identifiers and labels
    if input_type_primary == 'ticker':
        if not primary_asset:
            return {"status": "error", "error": "Primary asset ticker is required"}
        asset_x = primary_asset
        asset_x_label = primary_asset
    else:  # portfolio
        if not primary_portfolio_id:
            return {"status": "error", "error": "Primary portfolio is required"}
        asset_x = f"portfolio_{primary_portfolio_id}"  # Virtual ticker for internal function
        asset_x_label = f"Portfolio ({primary_portfolio_id})"
    
    if input_type_hedge == 'ticker':
        if not hedge_asset:
            return {"status": "error", "error": "Hedge asset ticker is required"}
        asset_y = hedge_asset
        asset_y_label = hedge_asset
    else:  # portfolio
        if not hedge_portfolio_id:
            return {"status": "error", "error": "Hedge portfolio is required"}
        asset_y = f"portfolio_{hedge_portfolio_id}"  # Virtual ticker for internal function
        asset_y_label = f"Portfolio ({hedge_portfolio_id})"
    
    try:
        logger.info(f"Hedge Ratio: {asset_x_label} vs {asset_y_label}, method={method}, window={window}")
        
        # Handle portfolio inputs
        if input_type_primary == 'portfolio' or input_type_hedge == 'portfolio':
            # Fetch portfolio weighted prices
            price_series_x = None
            price_series_y = None
            
            if input_type_primary == 'portfolio':
                price_series_x, asset_x_label = await _get_portfolio_weighted_prices(user_id, primary_portfolio_id, period)
            
            if input_type_hedge == 'portfolio':
                price_series_y, asset_y_label = await _get_portfolio_weighted_prices(user_id, hedge_portfolio_id, period)
            
            # For portfolios, we need to compute hedge ratio directly since internal function expects tickers
            # For now, only support OLS method with portfolios
            if method != 'ols':
                return {
                    "status": "error",
                    "error": f"Portfolio inputs only support OLS method. Please select OLS or use individual tickers for {method.upper()}."
                }
            
            # Simple OLS computation for portfolios
            import statsmodels.api as sm
            
            # If one is portfolio and one is ticker, fetch the ticker data
            if input_type_primary != 'portfolio':
                fmp_server = FMPMarketDataServer()
                await fmp_server.connect()
                from datetime import datetime, timedelta
                period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}.get(period, 365)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=period_days)
                
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": primary_asset,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })
                data = safe_parse_json(result)
                df = pd.DataFrame({"date": pd.to_datetime(data["dates"]), "price": data["prices"]})
                df = df.sort_values("date").set_index("date")
                price_series_x = df["price"]
                await fmp_server.cleanup()
            
            if input_type_hedge != 'portfolio':
                fmp_server = FMPMarketDataServer()
                await fmp_server.connect()
                from datetime import datetime, timedelta
                period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}.get(period, 365)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=period_days)
                
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": hedge_asset,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })
                data = safe_parse_json(result)
                df = pd.DataFrame({"date": pd.to_datetime(data["dates"]), "price": data["prices"]})
                df = df.sort_values("date").set_index("date")
                price_series_y = df["price"]
                await fmp_server.cleanup()
            
            # Align series
            aligned = pd.DataFrame({"x": price_series_x, "y": price_series_y}).dropna()
            if len(aligned) < 30:
                return {"status": "error", "error": f"Insufficient aligned data: {len(aligned)} days (need 30+)"}
            
            X = aligned["x"].values
            Y = aligned["y"].values
            
            # OLS regression
            X_with_const = sm.add_constant(X)
            model = sm.OLS(Y, X_with_const).fit()
            
            alpha = float(model.params[0])
            beta = float(model.params[1])
            r_squared = float(model.rsquared)
            
            # Store aligned price data for chart building
            portfolio_prices_x = X.tolist()
            portfolio_prices_y = Y.tolist()
            
            # Build simple result
            result = {
                "status": "success",
                "results": {
                    "hedge_ratio": {
                        "method": "ols",
                        "static_estimate": beta,
                        "time_series": [beta],
                        "dates": [aligned.index[-1].strftime("%Y-%m-%d")],
                        "alpha": alpha,
                        "beta": beta,
                        "window": None
                    },
                    "fit_quality": {
                        "r_squared": r_squared,
                        "adj_r_squared": float(model.rsquared_adj),
                        "std_err_beta": float(model.bse[1]),
                        "confidence_interval": model.conf_int(alpha=0.05)[1].tolist(),
                        "f_statistic": float(model.fvalue),
                        "p_value_f": float(model.f_pvalue)
                    },
                    "residuals": {
                        "mean": float(model.resid.mean()),
                        "std": float(model.resid.std()),
                        "min": float(model.resid.min()),
                        "max": float(model.resid.max()),
                        "durbin_watson": 2.0  # Placeholder
                    },
                    "diagnostics": {},
                    "metadata": {
                        "asset_x": asset_x_label,
                        "asset_y": asset_y_label,
                        "n_samples": len(aligned),
                        "period": period,
                        "date_range": [aligned.index[0].strftime("%Y-%m-%d"), aligned.index[-1].strftime("%Y-%m-%d")]
                    }
                },
                "_portfolio_prices_x": portfolio_prices_x,
                "_portfolio_prices_y": portfolio_prices_y
            }
        else:
            # Call internal function (ticker-ticker only)
            result = await calculate_hedge_ratio_internal(
                asset_x=asset_x,
                asset_y=asset_y,
                method=method,
                window=window,
                period=period
            )
        
        if result.get('status') == 'error':
            return result
        
        # Extract results
        hedge_data = result.get('results', {}).get('hedge_ratio', {})
        fit_quality = result.get('results', {}).get('fit_quality', {})
        residuals = result.get('results', {}).get('residuals', {})
        diagnostics = result.get('results', {}).get('diagnostics', {})
        metadata = result.get('results', {}).get('metadata', {})
        
        beta = hedge_data.get('beta', 0)
        alpha = hedge_data.get('alpha', 0)
        r_squared = fit_quality.get('r_squared', 0)
        adj_r_squared = fit_quality.get('adj_r_squared', 0)
        
        time_series = hedge_data.get('time_series', [])
        dates = hedge_data.get('dates', [])
        
        # Metric cards
        metric_cards = [
            {
                "id": "hedge_ratio",
                "label": "Hedge Ratio (β)",
                "value": f"{beta:.4f}",
                "sentiment": "neutral",
            },
            {
                "id": "r_squared",
                "label": "R²",
                "value": f"{r_squared:.4f}",
                "sentiment": "positive" if r_squared > 0.7 else ("neutral" if r_squared > 0.4 else "negative"),
            },
            {
                "id": "intercept",
                "label": "Intercept (α)",
                "value": f"{alpha:.4f}",
                "sentiment": "neutral",
            },
        ]
        
        # Add method-specific card
        if method == 'ols' and fit_quality.get('std_err_beta') is not None:
            std_err = fit_quality['std_err_beta']
            metric_cards.append({
                "id": "std_err",
                "label": "Std Error (β)",
                "value": f"{std_err:.4f}",
                "sentiment": "positive" if std_err < 0.1 else "neutral",
            })
        
        # Stats table
        stats_table = [
            {"category": "Assets", "metric": "Primary Asset (X)", "value": asset_x_label},
            {"category": "Assets", "metric": "Hedge Asset (Y)", "value": asset_y_label},
            {"category": "Regression", "metric": "Method", "value": method.upper()},
            {"category": "Regression", "metric": "Hedge Ratio (β)", "value": f"{beta:.4f}"},
            {"category": "Regression", "metric": "Intercept (α)", "value": f"{alpha:.4f}"},
            {"category": "Fit Quality", "metric": "R²", "value": f"{r_squared:.4f}"},
            {"category": "Fit Quality", "metric": "Adj. R²", "value": f"{adj_r_squared:.4f}"},
        ]
        
        # Add confidence interval if available
        if fit_quality.get('confidence_interval'):
            ci = fit_quality['confidence_interval']
            stats_table.append({
                "category": "Fit Quality",
                "metric": "95% CI for β",
                "value": f"[{ci[0]:.4f}, {ci[1]:.4f}]"
            })
        
        # Add F-statistic if available
        if fit_quality.get('f_statistic'):
            stats_table.append({
                "category": "Fit Quality",
                "metric": "F-statistic",
                "value": f"{fit_quality['f_statistic']:.2f}"
            })
            if fit_quality.get('p_value_f') is not None:
                p_val = fit_quality['p_value_f']
                stats_table.append({
                    "category": "Fit Quality",
                    "metric": "F-test p-value",
                    "value": f"{p_val:.4f}" if p_val >= 0.0001 else "<0.0001"
                })
        
        # Residuals stats
        stats_table.extend([
            {"category": "Residuals", "metric": "─" * 20, "value": "─" * 15},
            {"category": "Residuals", "metric": "Mean", "value": f"{residuals.get('mean', 0):.4f}"},
            {"category": "Residuals", "metric": "Std Dev", "value": f"{residuals.get('std', 0):.4f}"},
            {"category": "Residuals", "metric": "Durbin-Watson", "value": f"{residuals.get('durbin_watson', 0):.3f}"},
        ])
        
        # Diagnostics (if available)
        if diagnostics:
            stats_table.append({"category": "Diagnostics", "metric": "─" * 20, "value": "─" * 15})
            
            if 'normality' in diagnostics:
                norm = diagnostics['normality']
                status = "✓ Pass" if norm.get('pass') else "✗ Fail"
                stats_table.append({
                    "category": "Diagnostics",
                    "metric": "Normality (JB)",
                    "value": f"{status} (p={norm.get('p_value', 0):.3f})"
                })
            
            if 'autocorrelation' in diagnostics:
                auto = diagnostics['autocorrelation']
                status = "✓ Pass" if auto.get('pass') else "✗ Fail"
                stats_table.append({
                    "category": "Diagnostics",
                    "metric": "Autocorrelation (DW)",
                    "value": f"{status} ({auto.get('interpretation', 'N/A')})"
                })
            
            if 'heteroscedasticity' in diagnostics:
                hetero = diagnostics['heteroscedasticity']
                status = "✓ Pass" if hetero.get('pass') else "✗ Fail"
                stats_table.append({
                    "category": "Diagnostics",
                    "metric": "Heteroscedasticity (BP)",
                    "value": f"{status} (p={hetero.get('p_value', 0):.3f})"
                })
        
        # Metadata
        stats_table.extend([
            {"category": "Metadata", "metric": "─" * 20, "value": "─" * 15},
            {"category": "Metadata", "metric": "Period", "value": period},
            {"category": "Metadata", "metric": "Samples", "value": str(metadata.get('n_samples', 0))},
        ])
        
        if window:
            stats_table.append({
                "category": "Metadata",
                "metric": "Rolling Window",
                "value": f"{window} days"
            })
        
        # Build charts - fetch price data and create visualizations
        charts = {}
        
        # Check if we have portfolio prices already computed
        portfolio_prices_x = result.get('_portfolio_prices_x', [])
        portfolio_prices_y = result.get('_portfolio_prices_y', [])
        
        logger.info(f"Chart building: portfolio_prices_x={len(portfolio_prices_x)}, portfolio_prices_y={len(portfolio_prices_y)}")
        
        if portfolio_prices_x and portfolio_prices_y:
            # Use portfolio prices for scatter chart
            logger.info(f"Building scatter chart from portfolio prices")
            scatter_chart = build_scatter_chart(
                portfolio_prices_x,
                portfolio_prices_y,
                alpha,
                beta,
                r_squared,
                asset_x_label,
                asset_y_label
            )
            if scatter_chart:
                charts["scatter"] = scatter_chart
                logger.info(f"Scatter chart built successfully")
        elif input_type_primary == 'ticker' and input_type_hedge == 'ticker':
            # For ticker-ticker, fetch price data for scatter plot
            try:
                fmp_server = FMPMarketDataServer()
                await fmp_server.connect()
                
                from datetime import datetime, timedelta
                period_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}.get(period, 365)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=period_days)
                
                # Fetch primary asset
                result_x = await fmp_server.call_tool("get_historical_data", {
                    "symbol": primary_asset,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })
                data_x = safe_parse_json(result_x)
                
                # Fetch hedge asset
                result_y = await fmp_server.call_tool("get_historical_data", {
                    "symbol": hedge_asset,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })
                data_y = safe_parse_json(result_y)
                
                await fmp_server.cleanup()
                
                # Build scatter chart with actual data
                if data_x and data_y:
                    prices_x = data_x.get("prices", []) or data_x.get("closes", [])
                    prices_y = data_y.get("prices", []) or data_y.get("closes", [])
                    
                    if prices_x and prices_y:
                        # Align lengths
                        min_len = min(len(prices_x), len(prices_y))
                        scatter_chart = build_scatter_chart(
                            prices_x[:min_len],
                            prices_y[:min_len],
                            alpha,
                            beta,
                            r_squared,
                            asset_x_label,
                            asset_y_label
                        )
                        if scatter_chart:
                            charts["scatter"] = scatter_chart
            except Exception as e:
                logger.warning(f"Failed to build scatter chart: {e}")
        
        # Time series chart (if rolling window used)
        if len(time_series) > 1:
            ts_chart = build_hedge_ratio_timeseries_chart(time_series, dates, method, beta)
            if ts_chart:
                charts["timeseries"] = ts_chart
        
        logger.info(f"Final charts dict: {list(charts.keys())}")
        
        # Generate summary
        dynamic_str = f" (rolling {window}-day)" if window and len(time_series) > 1 else ""
        quality_str = "strong" if r_squared > 0.7 else ("moderate" if r_squared > 0.4 else "weak")
        
        summary = (
            f"**Hedge Ratio: {asset_y_label} vs {asset_x_label}**\n\n"
            f"Optimal hedge ratio: **β = {beta:.4f}**{dynamic_str}\n\n"
            f"Regression fit: **{quality_str}** (R² = {r_squared:.4f})\n\n"
            f"Hedging interpretation: For every $1 long in {asset_x_label}, hold **${abs(beta):.2f} {'short' if beta > 0 else 'long'}** in {asset_y_label} to minimize risk.\n\n"
            f"Method: {method.upper()}"
        )
        
        if diagnostics:
            passed = sum(1 for d in diagnostics.values() if isinstance(d, dict) and d.get('pass'))
            total = len([d for d in diagnostics.values() if isinstance(d, dict) and 'pass' in d])
            if total > 0:
                summary += f" | Diagnostics: {passed}/{total} passed"
        
        # Build tickers list (use actual ticker symbols if available)
        tickers_list = []
        if input_type_primary == 'ticker':
            tickers_list.append(primary_asset)
        if input_type_hedge == 'ticker':
            tickers_list.append(hedge_asset)
        
        return {
            "status": "success",
            "tool_id": "hedge_ratio",
            "tickers": tickers_list if tickers_list else [asset_x_label, asset_y_label],
            "weights": [],
            "metrics": {
                "hedge_ratio": beta,
                "r_squared": r_squared,
                "intercept": alpha,
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
            "summary": summary,
        }
    
    except Exception as e:
        logger.error(f"Hedge ratio failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}
