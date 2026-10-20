"""
Tearsheet Forecast Tools - ARIMA/ARIMAX forecasting for uploaded fund returns data

Tools for analyzing and forecasting returns from uploaded private fund
tearsheets, prospectuses, and performance reports.

Includes:
- forecast_tearsheet_returns: Basic ARIMA forecasting from uploaded returns
- forecast_tearsheet_with_macro: ARIMAX with macroeconomic indicators
- compare_fund_returns: Compare multiple funds from uploaded data
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

from core.agents.risk_tools.shared import register_chart_handle

warnings.filterwarnings("ignore", message=".*force_all_finite.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")

logger = logging.getLogger(__name__)

# Macro indicator search terms for FRED discovery
MACRO_CATEGORIES = {
    "rates": ["federal funds rate", "10 year treasury", "2 year treasury"],
    "inflation": ["consumer price index", "PCE price index"],
    "employment": ["unemployment rate", "initial claims"],
    "growth": ["real GDP", "industrial production"],
    "financial_conditions": ["VIX", "credit spread"],
}


@function_tool
async def forecast_tearsheet_returns(
    returns: List[float],
    dates: Optional[List[str]] = None,
    fund_name: str = "Fund",
    forecast_periods: int = 12,
    frequency: str = "monthly",
    confidence_level: float = 0.95
) -> dict:
    """
    Forecast future returns from uploaded tearsheet/private fund historical returns.
    
    Use this after extracting returns data from an uploaded fund document, tearsheet,
    or performance report. Pass the historical returns directly to generate forecasts.
    
    Args:
        returns: List of historical returns (e.g., [0.02, -0.01, 0.03, ...] for 2%, -1%, 3%)
                 Can be decimal (0.02) or percentage (2.0) - tool auto-detects format.
        dates: Optional list of date strings matching returns (e.g., ["2024-01", "2024-02"])
               If not provided, generates sequential period labels.
        fund_name: Name of the fund for chart labeling (default: "Fund")
        forecast_periods: Number of periods ahead to forecast (default: 12)
        frequency: Data frequency - "monthly", "quarterly", "annual" (default: "monthly")
        confidence_level: Confidence interval level (default: 0.95 for 95%)
    
    Returns:
        Forecasted returns with confidence intervals, model diagnostics, and charts.
    
    Example:
        # After parsing a tearsheet with monthly returns
        returns = [0.012, -0.008, 0.025, 0.018, -0.003, 0.031, ...]
        dates = ["2023-01", "2023-02", "2023-03", ...]
        
        await forecast_tearsheet_returns(
            returns=returns,
            dates=dates,
            fund_name="ABC Private Equity Fund",
            forecast_periods=12,
            frequency="monthly"
        )
    """
    try:
        from pmdarima import auto_arima
        
        returns_arr = np.array(returns, dtype=float)
        
        # Auto-detect percentage format
        if np.max(np.abs(returns_arr)) > 1:
            returns_arr = returns_arr / 100.0
            logger.info("Detected percentage format, converted to decimal")
        
        if len(returns_arr) < 12:
            return {
                "status": "error",
                "error": f"Insufficient data: {len(returns_arr)} periods (need at least 12)",
                "suggestion": "Provide more historical return periods from the tearsheet"
            }
        
        if np.isnan(returns_arr).any():
            returns_arr = pd.Series(returns_arr).ffill().bfill().values
        
        if dates is None or len(dates) != len(returns_arr):
            dates = [f"Period {i+1}" for i in range(len(returns_arr))]
        
        seasonal_period = {"monthly": 12, "quarterly": 4, "annual": 1}.get(frequency, 12)
        use_seasonal = seasonal_period > 1 and len(returns_arr) >= 2 * seasonal_period
        
        model = auto_arima(
            returns_arr,
            start_p=1, start_q=1,
            max_p=5, max_q=5, max_d=2,
            seasonal=use_seasonal,
            m=seasonal_period if use_seasonal else 1,
            stepwise=True,
            suppress_warnings=True,
            error_action='ignore'
        )
        
        fitted = model.predict_in_sample()
        forecast, conf_int = model.predict(
            n_periods=forecast_periods,
            return_conf_int=True,
            alpha=1 - confidence_level
        )
        
        forecast_dates = [f"Forecast {i+1}" for i in range(forecast_periods)]
        
        residuals = returns_arr - fitted
        mape = np.mean(np.abs(residuals / returns_arr[returns_arr != 0])) * 100 if np.any(returns_arr != 0) else 0
        
        # Build chart
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=[f"<b>{fund_name}</b> — Return Forecast", "Model Fit"],
            vertical_spacing=0.14,
            row_heights=[0.65, 0.35]
        )
        
        fig.add_trace(go.Scatter(
            x=dates[-24:], y=(returns_arr[-24:] * 100).tolist(),
            mode='lines+markers', name='Historical',
            line=dict(color='#1E3A5F', width=2),
            marker=dict(size=5)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=forecast_dates, y=(forecast * 100).tolist(),
            mode='lines+markers', name='Forecast',
            line=dict(color='#E85D04', width=2),
            marker=dict(size=6)
        ), row=1, col=1)
        
        conf_pct = int(confidence_level * 100)
        fig.add_trace(go.Scatter(
            x=forecast_dates + forecast_dates[::-1],
            y=(np.concatenate([conf_int[:, 1], conf_int[:, 0][::-1]]) * 100).tolist(),
            fill='toself',
            fillcolor='rgba(232, 93, 4, 0.15)',
            line=dict(color='rgba(0,0,0,0)'),
            name=f'{conf_pct}% CI'
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=dates, y=(returns_arr * 100).tolist(),
            mode='lines', name='Actual',
            line=dict(color='#1E3A5F', width=1.5)
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=(fitted * 100).tolist(),
            mode='lines', name='Fitted',
            line=dict(color='#3D8B7A', width=1.5, dash='dash')
        ), row=2, col=1)
        
        fig.update_layout(
            template='plotly_white', height=600,
            legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center')
        )
        fig.update_yaxes(title_text='Return (%)', row=1, col=1)
        fig.update_yaxes(title_text='Return (%)', row=2, col=1)
        
        return {
            "status": "success",
            "fund_name": fund_name,
            "forecast": {
                "periods": forecast_dates,
                "returns": (forecast * 100).tolist(),
                "confidence_interval": {
                    "lower": (conf_int[:, 0] * 100).tolist(),
                    "upper": (conf_int[:, 1] * 100).tolist()
                }
            },
            "summary": {
                "historical_periods": len(returns_arr),
                "avg_historical_return": float(np.mean(returns_arr) * 100),
                "volatility": float(np.std(returns_arr) * 100),
                "forecast_avg_return": float(np.mean(forecast) * 100),
                "model_order": model.order,
                "mape": float(mape)
            },
            "charts": [register_chart_handle(
                fig.to_dict(),
                chart_type="tearsheet_forecast",
                title=f"Return Forecast — {fund_name}",
                alt_text=f"ARIMA return forecast for {fund_name}",
                chart_id=f"tearsheet_forecast_{fund_name.lower().replace(' ', '_')}"
            )]
        }
        
    except Exception as e:
        logger.error(f"Tearsheet forecast failed: {e}")
        return {"status": "error", "error": str(e)}


@function_tool(strict_mode=False)  # Uses dict input (fund_returns) which is not strict-schema compatible
async def compare_fund_returns(
    fund_returns: dict,
    benchmark_returns: Optional[List[float]] = None,
    benchmark_name: str = "Benchmark",
    forecast_periods: int = 12
) -> dict:
    """
    Compare and forecast returns for multiple funds from uploaded tearsheet data.
    
    Use this to compare performance across multiple private funds or products
    from uploaded documents. Forecasts each fund and provides comparative analysis.
    
    Args:
        fund_returns: Dict mapping fund names to their return lists.
                      e.g., {"Fund A": [0.02, 0.01, ...], "Fund B": [0.03, -0.01, ...]}
        benchmark_returns: Optional benchmark returns for comparison
        benchmark_name: Name of benchmark (default: "Benchmark")
        forecast_periods: Periods ahead to forecast (default: 12)
    
    Returns:
        Comparative forecasts, risk metrics, and comparison charts.
    
    Example:
        await compare_fund_returns(
            fund_returns={
                "Private Equity Fund A": [0.025, 0.018, -0.005, ...],
                "Hedge Fund B": [0.012, 0.008, 0.015, ...],
            },
            benchmark_returns=[0.01, 0.008, 0.012, ...],
            benchmark_name="S&P 500"
        )
    """
    try:
        from pmdarima import auto_arima
        
        results = {}
        all_forecasts = {}
        
        for fund_name, returns in fund_returns.items():
            returns_arr = np.array(returns, dtype=float)
            
            if np.max(np.abs(returns_arr)) > 1:
                returns_arr = returns_arr / 100.0
            
            if len(returns_arr) < 8:
                results[fund_name] = {"status": "skipped", "reason": "insufficient data"}
                continue
            
            model = auto_arima(
                returns_arr,
                max_p=3, max_q=3, max_d=1,
                seasonal=False, stepwise=True,
                suppress_warnings=True, error_action='ignore'
            )
            
            forecast, conf_int = model.predict(
                n_periods=forecast_periods,
                return_conf_int=True, alpha=0.05
            )
            
            all_forecasts[fund_name] = forecast
            
            results[fund_name] = {
                "historical_avg": float(np.mean(returns_arr) * 100),
                "historical_vol": float(np.std(returns_arr) * 100),
                "sharpe_ratio": float(np.mean(returns_arr) / np.std(returns_arr)) if np.std(returns_arr) > 0 else 0,
                "forecast_avg": float(np.mean(forecast) * 100),
                "forecast_range": [float(forecast.min() * 100), float(forecast.max() * 100)],
                "model_order": model.order
            }
        
        if benchmark_returns:
            bench_arr = np.array(benchmark_returns, dtype=float)
            if np.max(np.abs(bench_arr)) > 1:
                bench_arr = bench_arr / 100.0
            results[benchmark_name] = {
                "historical_avg": float(np.mean(bench_arr) * 100),
                "historical_vol": float(np.std(bench_arr) * 100),
                "sharpe_ratio": float(np.mean(bench_arr) / np.std(bench_arr)) if np.std(bench_arr) > 0 else 0,
                "is_benchmark": True
            }
        
        fig = go.Figure()
        colors = ['#1E3A5F', '#E85D04', '#3D8B7A', '#9333EA', '#0891B2', '#B91C1C']
        
        for idx, (name, forecast) in enumerate(all_forecasts.items()):
            fig.add_trace(go.Scatter(
                x=list(range(1, forecast_periods + 1)),
                y=(forecast * 100).tolist(),
                mode='lines+markers',
                name=name,
                line=dict(color=colors[idx % len(colors)], width=2)
            ))
        
        fig.update_layout(
            title="<b>Fund Return Forecasts Comparison</b>",
            template='plotly_white',
            xaxis_title="Forecast Period",
            yaxis_title="Return (%)",
            height=450,
            legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center')
        )
        
        return {
            "status": "success",
            "funds_analyzed": len(results),
            "results": results,
            "ranking": sorted(
                [(k, v["forecast_avg"]) for k, v in results.items() if "forecast_avg" in v],
                key=lambda x: x[1], reverse=True
            ),
            "charts": [register_chart_handle(
                fig.to_dict(),
                chart_type="fund_comparison",
                title="Fund Return Forecasts Comparison",
                alt_text=f"Comparison of return forecasts for {len(all_forecasts)} funds",
                chart_id="fund_comparison"
            )]
        }
        
    except Exception as e:
        logger.error(f"Fund comparison failed: {e}")
        return {"status": "error", "error": str(e)}


@function_tool
async def forecast_tearsheet_with_macro(
    returns: List[float],
    dates: List[str],
    fund_name: str = "Fund",
    forecast_periods: int = 12,
    macro_categories: Optional[List[str]] = None,
    confidence_level: float = 0.95
) -> dict:
    """
    Forecast fund returns using ARIMAX with macroeconomic indicators as drivers.
    
    Use this after extracting returns from an uploaded tearsheet when you want to
    understand how macro factors (rates, inflation, employment) influence the fund.
    Fetches FRED economic data and finds correlations with the fund's returns.
    
    Best for:
    - Rate-sensitive funds (bond funds, REITs, financials)
    - Inflation-linked products
    - Funds with macro exposure
    - Understanding what economic factors drive fund performance
    
    Args:
        returns: List of historical returns from tearsheet (decimal or percentage)
        dates: List of date strings matching returns (e.g., ["2023-01", "2023-02", ...])
               REQUIRED for aligning with macro data.
        fund_name: Name of the fund for labeling (default: "Fund")
        forecast_periods: Periods ahead to forecast (default: 12)
        macro_categories: Which macro factors to analyze. Options:
            - "rates": Treasury rates, fed funds
            - "inflation": CPI, PCE
            - "employment": Unemployment, jobless claims
            - "growth": GDP, industrial production
            - "financial_conditions": VIX, credit spreads
            Default: ["rates", "inflation"]
        confidence_level: Confidence interval level (default: 0.95)
    
    Returns:
        Forecasted returns with macro correlations showing which indicators
        most influence the fund's performance.
    
    Example:
        # After extracting monthly returns from a bond fund tearsheet
        await forecast_tearsheet_with_macro(
            returns=[0.005, -0.008, 0.012, 0.003, ...],
            dates=["2022-01", "2022-02", "2022-03", ...],
            fund_name="ABC Fixed Income Fund",
            macro_categories=["rates", "inflation"],
            forecast_periods=12
        )
    """
    try:
        from pmdarima import auto_arima
        from core.mcp_servers.EconomicDataServer import EconomicDataServer
        
        # Convert returns
        returns_arr = np.array(returns, dtype=float)
        if np.max(np.abs(returns_arr)) > 1:
            returns_arr = returns_arr / 100.0
        
        if len(returns_arr) < 12:
            return {
                "status": "error",
                "error": f"Need at least 12 periods, got {len(returns_arr)}",
                "suggestion": "Provide more historical returns from the tearsheet"
            }
        
        if len(dates) != len(returns_arr):
            return {
                "status": "error",
                "error": "dates and returns must have same length",
                "suggestion": "Ensure each return has a corresponding date"
            }
        
        # Parse dates and create DataFrame
        try:
            parsed_dates = pd.to_datetime(dates)
        except Exception:
            return {
                "status": "error", 
                "error": "Could not parse dates. Use format like '2023-01' or '2023-01-15'"
            }
        
        fund_df = pd.DataFrame({
            "date": parsed_dates,
            "returns": returns_arr
        }).set_index("date").sort_index()
        
        # Default macro categories
        if not macro_categories:
            macro_categories = ["rates", "inflation"]
        
        # Fetch macro data
        econ_server = None
        macro_data = {}
        correlations = {}
        
        try:
            econ_server = EconomicDataServer()
            await econ_server.connect()
            
            start_date = fund_df.index.min().strftime("%Y-%m-%d")
            end_date = fund_df.index.max().strftime("%Y-%m-%d")
            
            # Discover and fetch indicators
            for category in macro_categories:
                if category not in MACRO_CATEGORIES:
                    continue
                    
                for search_term in MACRO_CATEGORIES[category][:2]:  # Limit per category
                    try:
                        results = await econ_server.search_series(search_term, limit=1)
                        if not results:
                            continue
                            
                        series_id = results[0].get("series_id")
                        if not series_id:
                            continue
                        
                        data = await econ_server.get_series_data(series_id, start_date, end_date)
                        if data and "data" in data and len(data["data"]) > 5:
                            df = pd.DataFrame(data["data"])
                            df["date"] = pd.to_datetime(df["date"])
                            df = df.set_index("date").sort_index()
                            df.columns = [series_id]
                            macro_data[series_id] = df
                            logger.info(f"Fetched {series_id}: {len(df)} points")
                    except Exception as e:
                        logger.warning(f"Failed to fetch {search_term}: {e}")
        finally:
            if econ_server:
                try:
                    await econ_server.cleanup()
                except Exception:
                    pass
        
        # Align macro data with fund returns (monthly resampling)
        fund_monthly = fund_df.resample('M').last()
        exog_data = []
        exog_names = []
        
        for name, df in macro_data.items():
            # Resample macro to monthly and align
            macro_monthly = df.resample('M').last()
            merged = fund_monthly.join(macro_monthly, how='inner')
            
            if len(merged) >= 12:
                # Compute correlation
                corr = merged["returns"].corr(merged[name])
                if pd.notna(corr) and abs(corr) >= 0.15:
                    correlations[name] = float(corr)
                    exog_data.append(merged[name].values)
                    exog_names.append(name)
        
        # Build exogenous matrix if we have valid indicators
        exog = None
        exog_forecast = None
        aligned_returns = fund_monthly["returns"].values
        
        if exog_data:
            # Find common length
            min_len = min(len(aligned_returns), *[len(x) for x in exog_data])
            aligned_returns = aligned_returns[-min_len:]
            exog = np.column_stack([x[-min_len:] for x in exog_data])
            # For forecast, assume indicators stay at last value
            exog_forecast = np.repeat(exog[-1:, :], forecast_periods, axis=0)
            logger.info(f"Using {len(exog_names)} macro indicators: {exog_names}")
        
        # Fit ARIMAX or ARIMA
        model = auto_arima(
            aligned_returns,
            X=exog,
            start_p=1, start_q=1,
            max_p=5, max_q=5, max_d=2,
            seasonal=False,
            stepwise=True,
            suppress_warnings=True,
            error_action='ignore'
        )
        
        fitted = model.predict_in_sample(X=exog) if exog is not None else model.predict_in_sample()
        
        if exog is not None and exog_forecast is not None:
            forecast, conf_int = model.predict(
                n_periods=forecast_periods,
                X=exog_forecast,
                return_conf_int=True,
                alpha=1 - confidence_level
            )
        else:
            forecast, conf_int = model.predict(
                n_periods=forecast_periods,
                return_conf_int=True,
                alpha=1 - confidence_level
            )
        
        # Build chart
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=[
                f"<b>{fund_name}</b> — ARIMAX Macro Forecast",
                "<b>Macro Indicator Correlations</b>"
            ],
            vertical_spacing=0.15,
            row_heights=[0.65, 0.35]
        )
        
        # Historical and forecast
        hist_dates = [f"T-{len(aligned_returns)-i}" for i in range(len(aligned_returns))]
        forecast_dates = [f"F+{i+1}" for i in range(forecast_periods)]
        
        fig.add_trace(go.Scatter(
            x=hist_dates[-24:], y=(aligned_returns[-24:] * 100).tolist(),
            mode='lines+markers', name='Historical',
            line=dict(color='#1E3A5F', width=2)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=forecast_dates, y=(forecast * 100).tolist(),
            mode='lines+markers', name='Forecast',
            line=dict(color='#E85D04', width=2)
        ), row=1, col=1)
        
        # CI band
        fig.add_trace(go.Scatter(
            x=forecast_dates + forecast_dates[::-1],
            y=(np.concatenate([conf_int[:, 1], conf_int[:, 0][::-1]]) * 100).tolist(),
            fill='toself', fillcolor='rgba(232, 93, 4, 0.15)',
            line=dict(color='rgba(0,0,0,0)'),
            name=f'{int(confidence_level*100)}% CI'
        ), row=1, col=1)
        
        # Correlation bars
        if correlations:
            names = list(correlations.keys())
            corrs = list(correlations.values())
            colors = ['#22763F' if c > 0 else '#B91C1C' for c in corrs]
            
            fig.add_trace(go.Bar(
                x=names, y=corrs,
                marker_color=colors,
                text=[f"{c:+.2f}" for c in corrs],
                textposition='outside',
                showlegend=False
            ), row=2, col=1)
            fig.add_hline(y=0, line=dict(color='gray', width=1), row=2, col=1)
        
        fig.update_layout(
            template='plotly_white', height=650,
            legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center')
        )
        fig.update_yaxes(title_text='Return (%)', row=1, col=1)
        fig.update_yaxes(title_text='Correlation', range=[-1, 1], row=2, col=1)
        
        return {
            "status": "success",
            "fund_name": fund_name,
            "model_type": "ARIMAX" if exog is not None else "ARIMA",
            "macro_indicators_used": exog_names,
            "forecast": {
                "periods": forecast_dates,
                "returns": (forecast * 100).tolist(),
                "confidence_interval": {
                    "lower": (conf_int[:, 0] * 100).tolist(),
                    "upper": (conf_int[:, 1] * 100).tolist()
                }
            },
            "macro_correlations": correlations,
            "interpretation": {
                "positive_correlation": "Fund returns move with this indicator",
                "negative_correlation": "Fund returns move opposite to this indicator"
            },
            "summary": {
                "historical_periods": len(aligned_returns),
                "avg_historical_return": float(np.mean(aligned_returns) * 100),
                "forecast_avg_return": float(np.mean(forecast) * 100),
                "model_order": model.order
            },
            "charts": [register_chart_handle(
                fig.to_dict(),
                chart_type="tearsheet_macro_forecast",
                title=f"ARIMAX Macro Forecast — {fund_name}",
                alt_text=f"ARIMAX macro-driven forecast for {fund_name}",
                chart_id=f"tearsheet_macro_{fund_name.lower().replace(' ', '_')}"
            )]
        }
        
    except Exception as e:
        logger.error(f"Tearsheet macro forecast failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
