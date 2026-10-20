"""
ARIMA Time Series Forecasting Tool
Based on StockPredictionAI approach with enhancements
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import warnings
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

# Suppress sklearn deprecation warnings from pmdarima
warnings.filterwarnings("ignore", message=".*force_all_finite.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

load_dotenv()
logger = logging.getLogger(__name__)


def _lttb_downsample(x: np.ndarray, y: np.ndarray, threshold: int) -> tuple:
    """
    Largest-Triangle-Three-Buckets (LTTB) downsampling.
    Preserves visual features better than simple stride sampling.
    """
    if len(x) <= threshold:
        return x, y
    
    # Always keep first and last points
    sampled_x = [x[0]]
    sampled_y = [y[0]]
    
    # Bucket size (excluding first and last)
    bucket_size = (len(x) - 2) / (threshold - 2)
    
    a = 0  # Previous selected point index
    
    for i in range(threshold - 2):
        # Calculate bucket boundaries
        bucket_start = int((i + 1) * bucket_size) + 1
        bucket_end = int((i + 2) * bucket_size) + 1
        bucket_end = min(bucket_end, len(x) - 1)
        
        # Calculate average of next bucket for triangle
        next_bucket_start = bucket_end
        next_bucket_end = int((i + 3) * bucket_size) + 1
        next_bucket_end = min(next_bucket_end, len(x))
        
        if next_bucket_start >= next_bucket_end:
            avg_x = x[-1]
            avg_y = y[-1]
        else:
            avg_x = np.mean(x[next_bucket_start:next_bucket_end])
            avg_y = np.mean(y[next_bucket_start:next_bucket_end])
        
        # Find point in current bucket with max triangle area
        max_area = -1
        max_idx = bucket_start
        
        for j in range(bucket_start, bucket_end):
            # Triangle area formula
            area = abs(
                (x[a] - avg_x) * (y[j] - sampled_y[-1]) -
                (x[a] - x[j]) * (avg_y - sampled_y[-1])
            ) * 0.5
            
            if area > max_area:
                max_area = area
                max_idx = j
        
        sampled_x.append(x[max_idx])
        sampled_y.append(y[max_idx])
        a = max_idx
    
    # Always include last point
    sampled_x.append(x[-1])
    sampled_y.append(y[-1])
    
    return np.array(sampled_x), np.array(sampled_y)


async def _build_forecast_chart(
    ticker: str,
    historical_dates: List[str],
    historical_prices: np.ndarray,
    fitted_values: np.ndarray,
    forecast_dates: List[str],
    forecast_mean: np.ndarray,
    confidence_intervals: Dict[float, Dict[str, List[float]]],
    forecast_periods: int,
    max_display_points: int = 150
) -> Optional[Dict[str, Any]]:
    """
    Build ARIMA forecast chart with historical, fitted, and forecast data.
    Uses LTTB downsampling for efficient visualization.
    """
    try:
        # Downsample historical data using LTTB if needed
        hist_len = len(historical_prices)
        if hist_len > max_display_points:
            # Use LTTB for better feature preservation
            idx = np.arange(hist_len)
            sampled_idx, sampled_prices = _lttb_downsample(idx, historical_prices, max_display_points)
            sampled_idx = sampled_idx.astype(int)
            
            chart_hist_dates = [historical_dates[i] for i in sampled_idx]
            chart_hist_prices = sampled_prices.tolist()
            chart_fitted = [fitted_values[i] for i in sampled_idx]
        else:
            chart_hist_dates = historical_dates
            chart_hist_prices = historical_prices.tolist()
            chart_fitted = fitted_values.tolist()
        
        # Get primary (widest) confidence interval
        primary_conf = max(confidence_intervals.keys()) if confidence_intervals else None
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=[
                f"{ticker} ARIMA Forecast ({forecast_periods} days ahead)",
                f"{ticker} Model Fit (Historical)"
            ],
            vertical_spacing=0.12,
            row_heights=[0.65, 0.35]
        )
        
        # === TOP CHART: Forecast with CI ===
        
        # Historical prices (last portion for context)
        context_points = min(60, len(chart_hist_prices))
        context_dates = chart_hist_dates[-context_points:]
        context_prices = chart_hist_prices[-context_points:]
        
        fig.add_trace(go.Scatter(
            x=context_dates,
            y=context_prices,
            mode='lines',
            name='Historical',
            line=dict(color='#2E86AB', width=2),
            hovertemplate='<b>%{x}</b><br>Price: $%{y:.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Forecast mean
        fig.add_trace(go.Scatter(
            x=forecast_dates,
            y=forecast_mean.tolist(),
            mode='lines',
            name='Forecast',
            line=dict(color='#F77F00', width=2, dash='solid'),
            hovertemplate='<b>%{x}</b><br>Forecast: $%{y:.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Confidence interval (filled area)
        if primary_conf and primary_conf in confidence_intervals:
            ci = confidence_intervals[primary_conf]
            conf_pct = int(primary_conf * 100)
            
            # Upper bound
            fig.add_trace(go.Scatter(
                x=forecast_dates,
                y=ci['upper'],
                mode='lines',
                name=f'{conf_pct}% CI Upper',
                line=dict(color='rgba(247, 127, 0, 0.3)', width=1),
                showlegend=False,
                hovertemplate='<b>%{x}</b><br>Upper: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)
            
            # Lower bound with fill
            fig.add_trace(go.Scatter(
                x=forecast_dates,
                y=ci['lower'],
                mode='lines',
                name=f'{conf_pct}% CI',
                line=dict(color='rgba(247, 127, 0, 0.3)', width=1),
                fill='tonexty',
                fillcolor='rgba(247, 127, 0, 0.15)',
                hovertemplate='<b>%{x}</b><br>Lower: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)
        
        # === BOTTOM CHART: Model Fit ===
        
        # Actual prices
        fig.add_trace(go.Scatter(
            x=chart_hist_dates,
            y=chart_hist_prices,
            mode='lines',
            name='Actual',
            line=dict(color='#2E86AB', width=1.5),
            hovertemplate='<b>%{x}</b><br>Actual: $%{y:.2f}<extra></extra>'
        ), row=2, col=1)
        
        # Fitted values
        fig.add_trace(go.Scatter(
            x=chart_hist_dates,
            y=chart_fitted,
            mode='lines',
            name='Fitted',
            line=dict(color='#06A77D', width=1.5, dash='dot'),
            hovertemplate='<b>%{x}</b><br>Fitted: $%{y:.2f}<extra></extra>'
        ), row=2, col=1)
        
        # Layout
        fig.update_layout(
            template='plotly_white',
            height=700,
            hovermode='x unified',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            ),
            margin=dict(l=60, r=30, t=80, b=40)
        )
        
        fig.update_xaxes(title_text='Date', row=2, col=1)
        fig.update_yaxes(title_text='Price ($)', row=1, col=1)
        fig.update_yaxes(title_text='Price ($)', row=2, col=1)
        
        return {
            'id': f"arima_{ticker.lower()}",
            'title': f"ARIMA Forecast - {ticker}",
            'plotly': fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Chart generation failed for {ticker}: {e}")
        return None


async def _build_residuals_chart(
    ticker: str,
    historical_dates: List[str],
    residuals: np.ndarray,
    max_display_points: int = 150
) -> Optional[Dict[str, Any]]:
    """Build residual analysis chart."""
    try:
        # Downsample if needed
        if len(residuals) > max_display_points:
            idx = np.arange(len(residuals))
            sampled_idx, sampled_resid = _lttb_downsample(idx, residuals, max_display_points)
            sampled_idx = sampled_idx.astype(int)
            chart_dates = [historical_dates[i] for i in sampled_idx]
            chart_residuals = sampled_resid
        else:
            chart_dates = historical_dates
            chart_residuals = residuals
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=['Residuals Over Time', 'Residual Distribution'],
            column_widths=[0.65, 0.35]
        )
        
        # Time series of residuals
        colors = ['#06A77D' if r >= 0 else '#D62828' for r in chart_residuals]
        fig.add_trace(go.Scatter(
            x=chart_dates,
            y=chart_residuals.tolist(),
            mode='markers+lines',
            marker=dict(size=4, color=colors),
            line=dict(color='#6b7280', width=1),
            name='Residuals',
            hovertemplate='<b>%{x}</b><br>Residual: %{y:.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Zero line
        fig.add_hline(y=0, line_dash='dash', line_color='black', line_width=1, row=1, col=1)
        
        # Histogram of residuals
        fig.add_trace(go.Histogram(
            y=residuals,
            nbinsy=30,
            name='Distribution',
            marker_color='#2E86AB',
            opacity=0.7
        ), row=1, col=2)
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            showlegend=False,
            margin=dict(l=60, r=30, t=60, b=40)
        )
        
        fig.update_xaxes(title_text='Date', row=1, col=1)
        fig.update_yaxes(title_text='Residual', row=1, col=1)
        fig.update_yaxes(title_text='Residual', row=1, col=2)
        fig.update_xaxes(title_text='Count', row=1, col=2)
        
        return {
            'id': f"arima_residuals_{ticker.lower()}",
            'title': f"ARIMA Residual Analysis - {ticker}",
            'plotly': fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Residuals chart failed for {ticker}: {e}")
        return None


async def forecast_arima_internal(
    tickers: List[str],
    forecast_periods: int = 30,
    arima_order: Optional[List[int]] = None,
    auto_select_params: bool = True,
    confidence_levels: Optional[List[float]] = None,
    period: str = "1Y",
    max_p: int = 10,
    max_q: int = 10,
    max_d: int = 2,
    seasonal: bool = True,
    seasonal_period: int = 5,
    stepwise: bool = True,
) -> dict:
    """
    Internal callable for Canvas - ARIMA time series forecasting.
    
    Uses faster defaults (stepwise=True, lower max_p/q) for interactive Canvas use.
    """
    fmp_server = None
    
    try:
        if not confidence_levels:
            confidence_levels = [0.80, 0.95]

        # Convert list to tuple if provided
        if arima_order is not None:
            arima_order = tuple(arima_order)
        elif not auto_select_params:
            arima_order = (5, 1, 0)  # StockPredictionAI default

        fmp_server = FMPMarketDataServer()
        results = {}
        all_charts = []

        try:
            await fmp_server.connect()

            for ticker in tickers:
                # Fetch via MCP tool
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })

                if not result or not hasattr(result, 'content'):
                    raise ValueError(f"No data for {ticker}")

                data = safe_parse_json(result)

                # FMP returns format: {"dates": [...], "prices": [...], ...}
                if not data or "dates" not in data:
                    raise ValueError(f"No date data for {ticker}")

                dates = data.get("dates", [])
                prices = data.get("prices", []) or data.get("closes", [])

                if not dates or not prices or len(dates) < 100:
                    raise ValueError(f"Insufficient data for ARIMA: {len(dates)} points (need 100+)")

                # Create DataFrame
                df = pd.DataFrame({
                    "date": pd.to_datetime(dates),
                    "price": prices
                })
                df = df.sort_values("date")

                price_series = df["price"].values
                date_series = df["date"]

                # Handle NaN
                if np.isnan(price_series).any():
                    price_series = pd.Series(price_series).ffill().values

                # Use log returns instead of prices for better stationarity
                log_prices = np.log(price_series)

                # ARIMA Model Fitting with aggressive search
                try:
                    forecast_conf_ints_log = {}
                    search_type = "exhaustive" if not stepwise else "stepwise"
                    
                    if auto_select_params:
                        from pmdarima import auto_arima

                        logger.info(f"Running auto ARIMA for {ticker} ({search_type} search, max_p={max_p}, max_q={max_q}, seasonal={seasonal})...")

                        # Build auto_arima kwargs dynamically
                        auto_arima_kwargs = {
                            'start_p': 1,
                            'start_q': 1,
                            'max_p': max_p,
                            'max_q': max_q,
                            'max_d': max_d,
                            'seasonal': seasonal,
                            'stepwise': stepwise,
                            'suppress_warnings': True,
                            'error_action': 'ignore',
                            'trace': False,
                            'information_criterion': 'aic',
                            'test': 'adf',
                            'max_order': None,
                            'n_jobs': -1
                        }

                        # Add seasonal parameters only if seasonal=True
                        if seasonal:
                            auto_arima_kwargs.update({
                                'm': seasonal_period,
                                'max_P': 2,
                                'max_Q': 2,
                                'max_D': 1
                            })

                        model = auto_arima(log_prices, **auto_arima_kwargs)

                        best_order = model.order
                        logger.info(f"Auto ARIMA selected order: {best_order}")

                        # pmdarima exposes predict for in-sample and out-of-sample with CIs
                        fitted_log = model.predict_in_sample()
                        
                        # Get forecast with confidence intervals
                        for conf_level in confidence_levels:
                            forecast_log_mean, conf_int = model.predict(
                                n_periods=forecast_periods,
                                return_conf_int=True,
                                alpha=1 - conf_level
                            )
                            forecast_conf_ints_log[conf_level] = conf_int
                        
                        aic = model.aic()
                        bic = model.bic()
                    else:
                        from statsmodels.tsa.arima.model import ARIMA

                        model = ARIMA(log_prices, order=arima_order).fit()
                        best_order = arima_order
                        fitted_log = model.fittedvalues

                        forecast_result = model.get_forecast(steps=forecast_periods)
                        forecast_log_mean = forecast_result.predicted_mean.to_numpy()

                        for conf_level in confidence_levels:
                            ci = forecast_result.conf_int(alpha=1 - conf_level)
                            forecast_conf_ints_log[conf_level] = ci.to_numpy()

                        aic = model.aic
                        bic = model.bic

                except Exception as e:
                    logger.error(f"ARIMA fitting failed for {ticker}: {e}")
                    raise ValueError(f"ARIMA model fitting failed: {e}")

                # Get fitted values (in-sample predictions) in log space
                fitted_values = np.exp(fitted_log)  # Convert back to price space
                residuals = price_series - fitted_values

                # Calculate in-sample fit metrics
                from scipy import stats

                # R-squared (goodness of fit)
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((price_series - np.mean(price_series))**2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

                # Residual autocorrelation at lag 1
                residuals_standardized = residuals / np.std(residuals) if np.std(residuals) != 0 else residuals
                autocorr_lag1 = np.corrcoef(residuals_standardized[:-1], residuals_standardized[1:])[0, 1] if len(residuals) > 1 else 0

                # Ljung-Box test for residual autocorrelation (up to 10 lags)
                from statsmodels.stats.diagnostic import acorr_ljungbox
                lb_test = acorr_ljungbox(residuals, lags=10, return_df=True)
                lb_pvalue = lb_test['lb_pvalue'].iloc[-1]  # p-value at lag 10

                # Last 60 days backtest
                backtest_window = min(60, len(price_series) - 1)
                backtest_actual = price_series[-backtest_window:]
                backtest_fitted = fitted_values[-backtest_window:]
                backtest_residuals = backtest_actual - backtest_fitted
                backtest_mape = np.mean(np.abs(backtest_residuals / backtest_actual)) * 100 if np.all(backtest_actual != 0) else 0

                # Forecast in log space
                if auto_select_params:
                    forecast_log_mean = np.array(forecast_log_mean)
                    
                # Convert forecasts back to price space
                confidence_intervals = {}
                forecast_mean = np.exp(forecast_log_mean)
                for conf_level, conf_int_log in forecast_conf_ints_log.items():
                    conf_int_price = np.exp(conf_int_log)
                    confidence_intervals[conf_level] = {
                        'lower': conf_int_price[:, 0].tolist(),
                        'upper': conf_int_price[:, 1].tolist()
                    }

                # Generate forecast dates
                last_date = date_series.iloc[-1]
                forecast_dates = pd.date_range(
                    start=last_date + pd.Timedelta(days=1),
                    periods=forecast_periods,
                    freq='D'
                )

                # Model diagnostics (full sample)
                mse = np.mean(residuals**2)
                mae = np.mean(np.abs(residuals))
                mape = np.mean(np.abs(residuals / price_series)) * 100 if np.all(price_series != 0) else 0

                diagnostics = {
                    'aic': float(aic),
                    'bic': float(bic),
                    'mse': float(mse),
                    'mae': float(mae),
                    'mape': float(mape),
                    'order': best_order,
                    'r_squared': float(r_squared),
                    'residual_autocorr_lag1': float(autocorr_lag1),
                    'ljung_box_pvalue': float(lb_pvalue),
                    'historical_fit_quality': {
                        'backtest_window_days': int(backtest_window),
                        'backtest_mape': float(backtest_mape),
                        'backtest_mae': float(np.mean(np.abs(backtest_residuals))),
                        'interpretation': 'Last 60 days fitted vs actual comparison'
                    },
                    'model_note': f'Auto-ARIMA ({search_type} search, max_p={max_p}, max_q={max_q}, seasonal={seasonal}, m={seasonal_period if seasonal else "N/A"}). Order: {best_order}. Ljung-Box p={lb_pvalue:.3f} (>0.05 = good residuals)'
                }

                # Build charts directly with Plotly
                historical_dates_str = date_series.dt.strftime('%Y-%m-%d').tolist()
                forecast_dates_str = forecast_dates.strftime('%Y-%m-%d').tolist()
                
                # Main forecast chart
                forecast_chart = await _build_forecast_chart(
                    ticker=ticker,
                    historical_dates=historical_dates_str,
                    historical_prices=price_series,
                    fitted_values=fitted_values,
                    forecast_dates=forecast_dates_str,
                    forecast_mean=forecast_mean,
                    confidence_intervals=confidence_intervals,
                    forecast_periods=forecast_periods
                )
                if forecast_chart:
                    all_charts.append(forecast_chart)
                
                # Residuals chart
                residuals_chart = await _build_residuals_chart(
                    ticker=ticker,
                    historical_dates=historical_dates_str,
                    residuals=residuals
                )
                if residuals_chart:
                    all_charts.append(residuals_chart)

                # Omit large time series arrays (embedded in cached charts)
                results[ticker] = {
                    'forecast': {
                        'start_date': forecast_dates_str[0] if forecast_dates_str else None,
                        'end_date': forecast_dates_str[-1] if forecast_dates_str else None,
                        'periods': len(forecast_dates_str),
                        # Removed: dates/values arrays (embedded in charts)
                        'confidence_intervals_summary': {
                            str(k): {'low': v['lower'][0], 'high': v['upper'][-1]} 
                            for k, v in confidence_intervals.items()
                        }
                    },
                    'historical': {
                        'start_date': historical_dates_str[0] if historical_dates_str else None,
                        'end_date': historical_dates_str[-1] if historical_dates_str else None,
                        'n_observations': len(price_series),
                        # Removed: prices/fitted_values arrays (embedded in charts)
                    },
                    'diagnostics': diagnostics,
                    'summary': {
                        'last_price': float(price_series[-1]),
                        'forecast_end_price': float(forecast_mean[-1]),
                        'forecast_change_pct': float((forecast_mean[-1] / price_series[-1] - 1) * 100),
                        'model_order': best_order,
                        'r_squared': float(r_squared),
                        'backtest_mape': float(backtest_mape)
                    }
                }

            # Wrap charts for caching
            wrapped_charts = wrap_plotly_charts(all_charts, default_type="arima_chart")

            return jsonify_results({
                'status': 'success',
                'results': results,
                'tickers': tickers,
                'forecast_periods': forecast_periods,
                'period': period,
                'auto_selected_params': auto_select_params,
                'charts': wrapped_charts
            })

        except Exception as e:
            logger.error(f"ARIMA failed: {e}")
            error_type = 'data_error' if any(
                kw in str(e).lower() for kw in ['no data', 'insufficient', 'convergence']
            ) else 'general_error'

            return {
                'status': 'error',
                'error': str(e),
                'error_type': error_type,
                'calculation_type': 'arima_forecast'
            }

    except Exception as e:
        logger.error(f"ARIMA forecasting failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'calculation_type': 'arima_forecast'
        }
    
    finally:
        # Always cleanup FMP server
        if fmp_server:
            try:
                await fmp_server.cleanup()
            except Exception as e:
                logger.warning(f"FMP server cleanup failed: {e}")


@function_tool
async def forecast_arima(
    tickers: List[str],
    forecast_periods: int = 30,
    arima_order: Optional[List[int]] = None,
    auto_select_params: bool = True,
    confidence_levels: Optional[List[float]] = None,
    period: str = "1Y",
    max_p: int = 15,
    max_q: int = 15,
    max_d: int = 2,
    seasonal: bool = True,
    seasonal_period: int = 5,
    stepwise: bool = False
) -> dict:
    """
    Perform ARIMA time series forecasting using log-prices for better stationarity.

    Models are fitted on log-transformed prices and forecasts are converted back to price space.
    By default uses aggressive search (max_p/q=15, seasonal=True, exhaustive search) to find
    complex patterns beyond simple random walks.

    Args:
        tickers: Stock symbols to forecast
        forecast_periods: Number of periods ahead to forecast (default: 30 days)
        arima_order: ARIMA [p,d,q] order as list of 3 integers (default: auto-select via pmdarima)
        auto_select_params: Use auto ARIMA for parameter selection (default: True)
        confidence_levels: Confidence intervals (default: [0.80, 0.95])
        period: Historical period for model training (default: "1Y"). Use "1M", "3M", "6M", "1Y", "2Y", "5Y"
        max_p: Maximum AR order to test (default: 15, use 5-7 for faster/conservative search)
        max_q: Maximum MA order to test (default: 15, use 5-7 for faster/conservative search)
        max_d: Maximum differencing order (default: 2, use 1 for simpler models)
        seasonal: Enable seasonal ARIMA components (default: True)
        seasonal_period: Seasonality period in days (default: 5 for weekly pattern, use 21 for monthly)
        stepwise: Use stepwise search instead of exhaustive (default: False for aggressive search, True for speed)

    Returns:
        Dict with forecasts, fitted values, diagnostics, and charts
    """
    return await forecast_arima_internal(
        tickers=tickers,
        forecast_periods=forecast_periods,
        arima_order=arima_order,
        auto_select_params=auto_select_params,
        confidence_levels=confidence_levels,
        period=period,
        max_p=max_p,
        max_q=max_q,
        max_d=max_d,
        seasonal=seasonal,
        seasonal_period=seasonal_period,
        stepwise=stepwise,
    )
