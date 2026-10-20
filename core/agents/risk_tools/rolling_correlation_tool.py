"""
Rolling Correlation Tool with Correlation Swap Convention Support
GS Quant-style implementation with zero-mean mode for correlation swaps
Based on pca_analysis_tool.py template and GS Quant timeseries/econometrics.py::correlation()
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.charts.models import ChartSpec, ChartType, ChartPriority
from core.utils.risk_adapter import jsonify_results
from core.agents.risk_tools.shared import register_chart_handle
import plotly.graph_objects as go
from plotly.subplots import make_subplots

load_dotenv()
logger = logging.getLogger(__name__)


async def _build_correlation_timeseries(
    correlation: pd.Series,
    dates: List[pd.Timestamp],
    ticker_x: str,
    ticker_y: str,
    chart_id: str
) -> Dict[str, Any]:
    """Build correlation time series chart with reference lines"""

    try:
        # Create color gradient: green for positive, red for negative
        colors = ['#2E7D32' if corr > 0 else '#C62828' for corr in correlation]

        fig = go.Figure()

        # Main correlation line with color-coded markers
        fig.add_trace(go.Scatter(
            x=dates,
            y=correlation,
            mode='lines+markers',
            name='Correlation',
            line=dict(color='#1976D2', width=2),
            marker=dict(
                size=4,
                color=correlation,
                colorscale=[[0, '#C62828'], [0.5, '#FFF176'], [1, '#2E7D32']],
                showscale=True,
                colorbar=dict(
                    title="ρ",
                    thickness=15,
                    len=0.7,
                    x=1.12
                ),
                cmin=-1,
                cmax=1
            ),
            hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Correlation: %{y:.4f}<extra></extra>'
        ))

        # Reference lines for correlation strength
        fig.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1,
                     annotation_text="Zero", annotation_position="right")
        fig.add_hline(y=0.5, line_dash="dash", line_color="green", opacity=0.5,
                     annotation_text="Weak Positive", annotation_position="right")
        fig.add_hline(y=-0.5, line_dash="dash", line_color="red", opacity=0.5,
                     annotation_text="Weak Negative", annotation_position="right")
        fig.add_hline(y=0.8, line_dash="dot", line_color="darkgreen", opacity=0.5,
                     annotation_text="Strong Positive", annotation_position="right")
        fig.add_hline(y=-0.8, line_dash="dot", line_color="darkred", opacity=0.5,
                     annotation_text="Strong Negative", annotation_position="right")

        fig.update_layout(
            title=f"Rolling Correlation: {ticker_x} vs {ticker_y}",
            xaxis_title="Date",
            yaxis_title="Correlation Coefficient (ρ)",
            yaxis=dict(range=[-1.05, 1.05]),
            template="plotly_white",
            height=500,
            hovermode='x unified',
            showlegend=True
        )

        return {
            'id': f"{chart_id}_timeseries",
            'title': f"Rolling Correlation: {ticker_x} vs {ticker_y}",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Correlation timeseries chart generation failed: {e}")
        return None


async def _build_confidence_intervals(
    correlation: pd.Series,
    upper_bound: pd.Series,
    lower_bound: pd.Series,
    dates: List[pd.Timestamp],
    ticker_x: str,
    ticker_y: str,
    chart_id: str
) -> Dict[str, Any]:
    """Build confidence interval chart with shaded bands (Fisher transformation)"""

    try:
        fig = go.Figure()

        # Upper confidence bound
        fig.add_trace(go.Scatter(
            x=dates,
            y=upper_bound,
            mode='lines',
            name='Upper 95% CI',
            line=dict(color='rgba(0,100,80,0)', width=0),
            showlegend=True,
            hovertemplate='Upper CI: %{y:.4f}<extra></extra>'
        ))

        # Lower confidence bound with fill to upper
        fig.add_trace(go.Scatter(
            x=dates,
            y=lower_bound,
            mode='lines',
            name='Lower 95% CI',
            line=dict(color='rgba(0,100,80,0)', width=0),
            fill='tonexty',
            fillcolor='rgba(68,138,255,0.2)',
            showlegend=True,
            hovertemplate='Lower CI: %{y:.4f}<extra></extra>'
        ))

        # Main correlation line on top
        fig.add_trace(go.Scatter(
            x=dates,
            y=correlation,
            mode='lines',
            name='Correlation',
            line=dict(color='#1976D2', width=2.5),
            hovertemplate='Correlation: %{y:.4f}<extra></extra>'
        ))

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        fig.update_layout(
            title=f"Correlation with 95% Confidence Intervals: {ticker_x} vs {ticker_y}",
            xaxis_title="Date",
            yaxis_title="Correlation Coefficient (ρ)",
            yaxis=dict(range=[-1.05, 1.05]),
            template="plotly_white",
            height=500,
            hovermode='x unified',
            showlegend=True,
            legend=dict(x=0.01, y=0.99)
        )

        return {
            'id': f"{chart_id}_confidence",
            'title': f"Confidence Intervals: {ticker_x} vs {ticker_y}",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Confidence intervals chart generation failed: {e}")
        return None


async def _build_returns_scatter(
    returns_x: pd.Series,
    returns_y: pd.Series,
    ticker_x: str,
    ticker_y: str,
    current_corr: float,
    chart_id: str
) -> Dict[str, Any]:
    """Build scatter plot of returns relationship with regression line"""

    try:
        # Create time-based color gradient (blue to red)
        n_points = len(returns_x)
        time_colors = np.linspace(0, 1, n_points)

        fig = go.Figure()

        # Scatter plot
        fig.add_trace(go.Scatter(
            x=returns_x,
            y=returns_y,
            mode='markers',
            name='Returns',
            marker=dict(
                size=6,
                color=time_colors,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Time",
                    tickvals=[0, 0.5, 1],
                    ticktext=['Early', 'Mid', 'Recent'],
                    thickness=15,
                    len=0.7
                ),
                opacity=0.6
            ),
            text=[f"{returns_x.index[i].strftime('%Y-%m-%d')}" for i in range(n_points)],
            hovertemplate='<b>%{text}</b><br>%{xaxis.title.text}: %{x:.4f}<br>%{yaxis.title.text}: %{y:.4f}<extra></extra>'
        ))

        # OLS regression line
        if len(returns_x) > 1:
            # Calculate regression coefficients
            coefficients = np.polyfit(returns_x, returns_y, 1)
            regression_line = np.poly1d(coefficients)

            # Create smooth line
            x_range = np.linspace(returns_x.min(), returns_x.max(), 100)
            y_fit = regression_line(x_range)

            fig.add_trace(go.Scatter(
                x=x_range,
                y=y_fit,
                mode='lines',
                name=f'OLS Fit (ρ={current_corr:.4f})',
                line=dict(color='red', width=2, dash='dash'),
                hovertemplate='Fitted Line<extra></extra>'
            ))

        # Add origin lines
        fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.3)
        fig.add_vline(x=0, line_dash="dot", line_color="gray", opacity=0.3)

        # Add correlation annotation
        fig.add_annotation(
            text=f"Current Correlation: {current_corr:.4f}",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            bgcolor="white",
            bordercolor="black",
            borderwidth=1,
            font=dict(size=12)
        )

        fig.update_layout(
            title=f"Returns Scatter: {ticker_x} vs {ticker_y}",
            xaxis_title=f"{ticker_x} Returns",
            yaxis_title=f"{ticker_y} Returns",
            template="plotly_white",
            height=600,
            width=700,
            hovermode='closest',
            showlegend=True
        )

        return {
            'id': f"{chart_id}_scatter",
            'title': f"Returns Scatter: {ticker_x} vs {ticker_y}",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Returns scatter chart generation failed: {e}")
        return None


async def calculate_rolling_correlation_internal(
    ticker_x: str,
    ticker_y: str,
    window: int,
    returns_type: str = "logarithmic",
    zero_mean_mode: bool = False,
    period: str = "2Y"
) -> Dict[str, Any]:
    """
    Internal version for Canvas integration.
    Calculate rolling correlation between two assets with correlation swap convention support.

    Implements both standard Pearson correlation and zero-mean correlation (used in correlation swaps).
    The zero-mean method follows GS Quant's exact implementation for correlation swap pricing.
    Provides confidence intervals using Fisher z-transformation.

    Args:
        ticker_x: First asset ticker symbol
        ticker_y: Second asset ticker symbol (must differ from ticker_x)
        window: Rolling window size in days (minimum 2, recommended ≥20 for stable estimates)
        returns_type: Type of returns calculation:
            - "simple": (P_t - P_{t-1}) / P_{t-1}
            - "logarithmic": ln(P_t / P_{t-1}) - recommended for correlation swaps
            - "absolute": |simple_returns|
        zero_mean_mode: Use zero-mean correlation for correlation swap convention (default: False)
            - False: Standard Pearson ρ = Σ[(R-R̄)(S-S̄)] / [(N-1)σ_R σ_S]
            - True: Zero-mean ρ = Σ(R*S) / [√(ΣR²) * √(ΣS²)]
        period: Historical data period (default: "2Y"). Options: "1M", "3M", "6M", "1Y", "2Y", "5Y", "max"

    Returns:
        Raw dict containing correlation data, charts, and metadata
    """
    try:
        # Validation
        if window < 2:
            raise ValueError(f"Window must be at least 2, got {window}")

        if returns_type not in ["simple", "logarithmic", "absolute"]:
            raise ValueError(f"returns_type must be 'simple', 'logarithmic', or 'absolute', got '{returns_type}'")

        if ticker_x == ticker_y:
            raise ValueError(f"Tickers must be different. Got {ticker_x} == {ticker_y}")

        # Minimum data requirement for meaningful rolling correlation
        min_required_points = window + 30

        logger.info(f"Calculating rolling correlation: {ticker_x} vs {ticker_y}, window={window}, type={returns_type}, zero_mean={zero_mean_mode}")

        # Initialize FMP server
        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Fetch historical data for both tickers
            logger.info(f"Fetching {period} data for {ticker_x} and {ticker_y}...")

            results = {}
            for ticker in [ticker_x, ticker_y]:
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })

                if not result or not hasattr(result, 'content'):
                    raise ValueError(f"No data returned for {ticker}")

                data = safe_parse_json(result)

                if not data or "dates" not in data:
                    raise ValueError(f"No date data for {ticker}")

                dates = data.get("dates", [])
                prices = data.get("prices", []) or data.get("closes", [])

                if not dates or not prices:
                    raise ValueError(f"Missing price data for {ticker}")

                if len(dates) < min_required_points:
                    raise ValueError(
                        f"Insufficient data for {ticker}: {len(dates)} points "
                        f"(need at least {min_required_points} for window={window})"
                    )

                # Create DataFrame
                df = pd.DataFrame({
                    "date": pd.to_datetime(dates),
                    "price": prices
                })
                df = df.sort_values("date").drop_duplicates(subset='date')

                results[ticker] = df

            # Align dates (intersection of available dates)
            dates_x = set(results[ticker_x]['date'])
            dates_y = set(results[ticker_y]['date'])
            common_dates = sorted(list(dates_x.intersection(dates_y)))

            if len(common_dates) < min_required_points:
                raise ValueError(
                    f"Insufficient common dates: {len(common_dates)} "
                    f"(need at least {min_required_points})"
                )

            # Filter to common dates
            df_x = results[ticker_x][results[ticker_x]['date'].isin(common_dates)].sort_values('date')
            df_y = results[ticker_y][results[ticker_y]['date'].isin(common_dates)].sort_values('date')

            # Calculate returns based on type
            if returns_type == "simple":
                returns_x = df_x['price'].pct_change()
                returns_y = df_y['price'].pct_change()
            elif returns_type == "logarithmic":
                returns_x = np.log(df_x['price'] / df_x['price'].shift(1))
                returns_y = np.log(df_y['price'] / df_y['price'].shift(1))
            else:  # absolute
                returns_x = df_x['price'].pct_change().abs()
                returns_y = df_y['price'].pct_change().abs()

            # Create aligned DataFrame
            returns_df = pd.DataFrame({
                'date': df_x['date'].values,
                'returns_x': returns_x.values,
                'returns_y': returns_y.values
            })
            returns_df = returns_df.dropna()

            if len(returns_df) < window + 10:
                raise ValueError(
                    f"Insufficient valid returns: {len(returns_df)} "
                    f"(need at least {window + 10})"
                )

            # Handle NaN/Inf values
            if returns_df[['returns_x', 'returns_y']].isna().any().any() or \
               np.isinf(returns_df[['returns_x', 'returns_y']]).any().any():
                logger.warning("NaN or Inf detected in returns, cleaning...")
                returns_df = returns_df.replace([np.inf, -np.inf], np.nan).dropna()

            # Check for constant returns (zero variance)
            if returns_df['returns_x'].std() < 1e-10:
                raise ValueError(f"{ticker_x} has constant returns (zero variance)")
            if returns_df['returns_y'].std() < 1e-10:
                raise ValueError(f"{ticker_y} has constant returns (zero variance)")

            # Calculate rolling correlation
            logger.info(f"Computing rolling correlation with window={window}...")

            if zero_mean_mode:
                # Zero-mean correlation (GS Quant correlation swap convention)
                # ρ = Σ(R*S) / [√(ΣR²) * √(ΣS²)]
                def zero_mean_corr(x_vals, y_vals):
                    numerator = (x_vals * y_vals).sum()
                    denominator = np.sqrt((x_vals**2).sum()) * np.sqrt((y_vals**2).sum())
                    return numerator / denominator if denominator > 1e-10 else np.nan

                # Apply rolling correlation to numeric series only
                correlation = pd.Series(index=returns_df.index, dtype=float)
                for i in range(window - 1, len(returns_df)):
                    window_x = returns_df['returns_x'].iloc[i - window + 1:i + 1].values
                    window_y = returns_df['returns_y'].iloc[i - window + 1:i + 1].values
                    correlation.iloc[i] = zero_mean_corr(window_x, window_y)
            else:
                # Standard Pearson correlation
                # ρ = Σ[(R-R̄)(S-S̄)] / [(N-1)σ_R σ_S]
                correlation = returns_df['returns_x'].rolling(window=window).corr(returns_df['returns_y'])

            # Drop NaN values from correlation
            valid_indices = ~correlation.isna()
            correlation = correlation[valid_indices]
            dates_series = returns_df['date'][valid_indices]

            if len(correlation) < 10:
                raise ValueError(f"Insufficient valid correlation values: {len(correlation)}")

            # Calculate confidence intervals using Fisher z-transformation
            # z = 0.5 * ln((1+ρ)/(1-ρ))
            # SE_z = 1/√(n-3)
            # CI: z ± 1.96*SE_z, then transform back

            # Clip correlation to avoid ln(0) or division by zero
            correlation_clipped = correlation.clip(-0.9999, 0.9999)

            # Fisher transformation
            z = 0.5 * np.log((1 + correlation_clipped) / (1 - correlation_clipped))

            # Standard error
            se_z = 1 / np.sqrt(window - 3)

            # 95% confidence interval in z-space
            z_upper = z + 1.96 * se_z
            z_lower = z - 1.96 * se_z

            # Transform back to correlation space
            # ρ = (e^(2z) - 1) / (e^(2z) + 1)
            upper_bound = (np.exp(2 * z_upper) - 1) / (np.exp(2 * z_upper) + 1)
            lower_bound = (np.exp(2 * z_lower) - 1) / (np.exp(2 * z_lower) + 1)

            # Clip bounds to [-1, 1]
            upper_bound = upper_bound.clip(-1, 1)
            lower_bound = lower_bound.clip(-1, 1)

            # Generate charts
            chart_id = f"corr_{abs(hash(f'{ticker_x}_{ticker_y}_{window}'))&0xFFFF:04x}"
            charts = []

            # Chart 1: Correlation time series
            corr_chart = await _build_correlation_timeseries(
                correlation, dates_series.tolist(), ticker_x, ticker_y, chart_id
            )
            if corr_chart:
                charts.append(
                    register_chart_handle(
                        corr_chart.get('plotly', {}),
                        chart_type="rolling_correlation_timeseries",
                        title=corr_chart.get('title', f"Rolling Correlation: {ticker_x} vs {ticker_y}"),
                        alt_text=corr_chart.get('title', f"Rolling Correlation: {ticker_x} vs {ticker_y}"),
                        chart_id=corr_chart.get('id')
                    )
                )

            # Chart 2: Confidence intervals
            ci_chart = await _build_confidence_intervals(
                correlation, upper_bound, lower_bound, dates_series.tolist(),
                ticker_x, ticker_y, chart_id
            )
            if ci_chart:
                charts.append(
                    register_chart_handle(
                        ci_chart.get('plotly', {}),
                        chart_type="rolling_correlation_confidence",
                        title=ci_chart.get('title', f"Confidence Intervals: {ticker_x} vs {ticker_y}"),
                        alt_text=ci_chart.get('title', f"Confidence Intervals: {ticker_x} vs {ticker_y}"),
                        chart_id=ci_chart.get('id')
                    )
                )

            # Chart 3: Returns scatter with regression
            # Use all returns (not just rolling window dates)
            current_corr = float(correlation.iloc[-1])
            scatter_chart = await _build_returns_scatter(
                returns_df['returns_x'], returns_df['returns_y'],
                ticker_x, ticker_y, current_corr, chart_id
            )
            if scatter_chart:
                charts.append(
                    register_chart_handle(
                        scatter_chart.get('plotly', {}),
                        chart_type="rolling_correlation_scatter",
                        title=scatter_chart.get('title', f"Returns Scatter: {ticker_x} vs {ticker_y}"),
                        alt_text=scatter_chart.get('title', f"Returns Scatter: {ticker_x} vs {ticker_y}"),
                        chart_id=scatter_chart.get('id')
                    )
                )

            # Prepare results
            results = {
                'correlation_series': correlation.tolist(),
                'dates': [d.strftime('%Y-%m-%d') for d in dates_series],
                'statistics': {
                    'mean_correlation': float(correlation.mean()),
                    'std_correlation': float(correlation.std()),
                    'min_correlation': float(correlation.min()),
                    'max_correlation': float(correlation.max()),
                    'current_correlation': current_corr
                },
                'confidence_intervals': {
                    'upper_bound': upper_bound.tolist(),
                    'lower_bound': lower_bound.tolist()
                },
                'metadata': {
                    'ticker_x': ticker_x,
                    'ticker_y': ticker_y,
                    'window': window,
                    'returns_type': returns_type,
                    'zero_mean_mode': zero_mean_mode,
                    'n_observations': len(correlation),
                    'n_returns': len(returns_df),
                    'date_range': [
                        dates_series.iloc[0].strftime('%Y-%m-%d'),
                        dates_series.iloc[-1].strftime('%Y-%m-%d')
                    ],
                    'period': period
                }
            }

            return {
                'status': 'success',
                'results': results,
                'charts': charts
            }

        except Exception as e:
            logger.error(f"Rolling correlation calculation failed: {e}")
            error_type = 'data_error' if any(
                kw in str(e).lower() for kw in ['no data', 'insufficient', 'constant', 'missing']
            ) else 'calculation_error'

            return {
                'status': 'error',
                'error': str(e),
                'error_type': error_type,
                'calculation_type': 'rolling_correlation'
            }
        finally:
            # Properly close FMP server connection
            try:
                await fmp_server.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error closing FMP server: {cleanup_error}")

    except Exception as e:
        logger.error(f"Rolling correlation tool failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'calculation_type': 'rolling_correlation'
        }


@function_tool
async def calculate_rolling_correlation(
    ticker_x: str,
    ticker_y: str,
    window: int,
    returns_type: str = "logarithmic",
    zero_mean_mode: bool = False,
    period: str = "2Y"
) -> dict:
    """
    Calculate rolling correlation between two assets with correlation swap convention support.

    Implements both standard Pearson correlation and zero-mean correlation (used in correlation swaps).
    The zero-mean method follows GS Quant's exact implementation for correlation swap pricing.
    Provides confidence intervals using Fisher z-transformation.

    Args:
        ticker_x: First asset ticker symbol
        ticker_y: Second asset ticker symbol (must differ from ticker_x)
        window: Rolling window size in days (minimum 2, recommended ≥20 for stable estimates)
        returns_type: Type of returns calculation:
            - "simple": (P_t - P_{t-1}) / P_{t-1}
            - "logarithmic": ln(P_t / P_{t-1}) - recommended for correlation swaps
            - "absolute": |simple_returns|
        zero_mean_mode: Use zero-mean correlation for correlation swap convention (default: False)
            - False: Standard Pearson ρ = Σ[(R-R̄)(S-S̄)] / [(N-1)σ_R σ_S]
            - True: Zero-mean ρ = Σ(R*S) / [√(ΣR²) * √(ΣS²)]
        period: Historical data period (default: "2Y"). Options: "1M", "3M", "6M", "1Y", "2Y", "5Y", "max"

    Returns:
        Dict containing:
        - correlation_series: Rolling correlation values
        - statistics: Mean, std, min, max, current correlation
        - confidence_intervals: Fisher-transformed 95% CI bounds
        - metadata: Configuration and data range info
        - charts: 3 interactive Plotly visualizations
            1. Correlation time series with reference lines
            2. Confidence intervals with shaded bands
            3. Returns scatter plot with regression line
    """
    result = await calculate_rolling_correlation_internal(
        ticker_x, ticker_y, window, returns_type, zero_mean_mode, period
    )
    return jsonify_results(result)
