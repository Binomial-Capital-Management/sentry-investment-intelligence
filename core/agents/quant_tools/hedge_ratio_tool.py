"""
Hedge Ratio Calculation Tool
Calculate dynamic hedge ratios between two assets using OLS, TLS, or Kalman filter methods
Based on PCA analysis tool pattern
"""

from agents import function_tool
from typing import List, Optional, Dict, Any, Tuple
import logging
import numpy as np
import pandas as pd
from scipy.linalg import svd
from scipy import stats
import statsmodels.api as sm
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import durbin_watson
from pykalman import KalmanFilter
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from datetime import datetime, timedelta

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

load_dotenv()
logger = logging.getLogger(__name__)


async def _fetch_price_data(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_period: int
) -> pd.DataFrame:
    """
    Fetch historical price data for a ticker.

    Args:
        fmp_server: FMP market data server instance
        ticker: Stock ticker
        lookback_period: Number of calendar days to fetch

    Returns:
        DataFrame with date and price columns
    """
    try:
        # Calculate explicit date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_period)

        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })

        if not result or not hasattr(result, 'content'):
            raise ValueError(f"No data returned for {ticker}")

        data = safe_parse_json(result)

        if not data or "dates" not in data:
            raise ValueError(f"No date data for {ticker}")

        dates = data.get("dates", [])
        prices = data.get("prices", []) or data.get("closes", [])

        if not dates or not prices:
            raise ValueError(f"No price data for {ticker}")

        # Create DataFrame
        df = pd.DataFrame({
            "date": pd.to_datetime(dates),
            "price": prices
        })
        df = df.sort_values("date").reset_index(drop=True)

        # Handle NaN
        df = df.dropna()

        return df

    except Exception as e:
        logger.error(f"Failed to fetch data for {ticker}: {e}")
        raise


async def _build_hedge_ratio_chart(
    hedge_ratios: np.ndarray,
    dates: List[str],
    method: str,
    chart_id: str,
    confidence_bands: Optional[Tuple[np.ndarray, np.ndarray]] = None
) -> Dict[str, Any]:
    """
    Build time series plot of dynamic hedge ratio.

    For rolling OLS: Shows beta over time with rolling window
    For Kalman: Shows state estimate with ±2σ confidence bands
    """
    if len(hedge_ratios) == 0 or len(dates) == 0:
        return None

    fig = go.Figure()

    # Main hedge ratio line
    fig.add_trace(go.Scatter(
        x=dates,
        y=hedge_ratios,
        mode='lines',
        name=f'Hedge Ratio ({method.upper()})',
        line=dict(color='#2E86AB', width=2),
        hovertemplate='<b>%{x}</b><br>β: %{y:.4f}<extra></extra>'
    ))

    # Add confidence bands for Kalman
    if confidence_bands and method == "kalman":
        lower, upper = confidence_bands
        dates_reversed = list(reversed(dates))
        fig.add_trace(go.Scatter(
            x=dates + dates_reversed,
            y=np.concatenate([upper, lower[::-1]]),
            fill='toself',
            fillcolor='rgba(46,134,171,0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            name='95% Confidence',
            showlegend=True
        ))

    # Add zero line
    fig.add_hline(
        y=0, line_dash="dash", line_color="gray",
        annotation_text="β=0 (no hedge)"
    )

    fig.update_layout(
        title=f"Dynamic Hedge Ratio: {method.upper()} Method",
        xaxis_title="Date",
        yaxis_title="Hedge Ratio (β)",
        template="plotly_white",
        height=500,
        hovermode='x unified'
    )

    return {
        'id': f"{chart_id}_ratio_ts",
        'title': "Hedge Ratio Time Series",
        'plotly': fig.to_dict()
    }


async def _build_residuals_chart(
    residuals: np.ndarray,
    dates: List[str],
    fitted_values: np.ndarray,
    chart_id: str
) -> Dict[str, Any]:
    """
    Build comprehensive residuals diagnostic plot.

    4 panels:
    1. Residuals over time (check for autocorrelation)
    2. Q-Q plot (check for normality)
    3. Residuals vs fitted values (check for heteroscedasticity)
    4. Histogram of residuals (check for normality)
    """
    if len(residuals) == 0 or len(dates) == 0 or len(fitted_values) == 0:
        return None

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Residuals Over Time",
            "Q-Q Plot (Normality Test)",
            "Residuals vs Fitted Values",
            "Residual Distribution"
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.10
    )

    # Panel 1: Time series
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=residuals,
            mode='markers',
            marker=dict(size=4, color='#2E86AB'),
            name='Residuals',
            hovertemplate='<b>%{x}</b><br>Residual: %{y:.4f}<extra></extra>'
        ),
        row=1, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="red", row=1, col=1)

    # Panel 2: Q-Q plot
    theoretical_quantiles = stats.norm.ppf(np.linspace(0.01, 0.99, len(residuals)))
    sample_quantiles = np.sort(residuals)

    fig.add_trace(
        go.Scatter(
            x=theoretical_quantiles,
            y=sample_quantiles,
            mode='markers',
            marker=dict(size=4, color='#A23B72'),
            name='Q-Q',
            hovertemplate='Theoretical: %{x:.2f}<br>Sample: %{y:.2f}<extra></extra>'
        ),
        row=1, col=2
    )
    # 45-degree reference line
    qq_min = min(theoretical_quantiles.min(), sample_quantiles.min())
    qq_max = max(theoretical_quantiles.max(), sample_quantiles.max())
    fig.add_trace(
        go.Scatter(
            x=[qq_min, qq_max], y=[qq_min, qq_max],
            mode='lines',
            line=dict(color='red', dash='dash'),
            showlegend=False
        ),
        row=1, col=2
    )

    # Panel 3: Residuals vs fitted
    fig.add_trace(
        go.Scatter(
            x=fitted_values,
            y=residuals,
            mode='markers',
            marker=dict(size=4, color='#F18F01'),
            name='Fitted vs Residuals',
            hovertemplate='Fitted: %{x:.2f}<br>Residual: %{y:.4f}<extra></extra>'
        ),
        row=2, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="red", row=2, col=1)

    # Panel 4: Histogram
    fig.add_trace(
        go.Histogram(
            x=residuals,
            nbinsx=30,
            marker=dict(color='#06A77D'),
            name='Distribution',
            hovertemplate='Bin: %{x:.2f}<br>Count: %{y}<extra></extra>'
        ),
        row=2, col=2
    )

    # Update axes
    fig.update_xaxes(title_text="Date", row=1, col=1)
    fig.update_xaxes(title_text="Theoretical Quantiles", row=1, col=2)
    fig.update_xaxes(title_text="Fitted Values", row=2, col=1)
    fig.update_xaxes(title_text="Residual Value", row=2, col=2)

    fig.update_yaxes(title_text="Residual", row=1, col=1)
    fig.update_yaxes(title_text="Sample Quantiles", row=1, col=2)
    fig.update_yaxes(title_text="Residual", row=2, col=1)
    fig.update_yaxes(title_text="Frequency", row=2, col=2)

    fig.update_layout(
        title="Residuals Diagnostic Plots",
        height=700,
        width=1000,
        showlegend=False,
        template="plotly_white"
    )

    return {
        'id': f"{chart_id}_residuals",
        'title': "Residuals Analysis",
        'plotly': fig.to_dict()
    }


async def _build_scatter_chart(
    price_x: np.ndarray,
    price_y: np.ndarray,
    alpha: float,
    beta: float,
    r_squared: float,
    asset_x: str,
    asset_y: str,
    method: str,
    chart_id: str
) -> Dict[str, Any]:
    """
    Build scatter plot of asset prices with fitted regression line.
    Shows quality of linear relationship.
    """
    if len(price_x) == 0 or len(price_y) == 0:
        return None

    fig = go.Figure()

    # Scatter points
    fig.add_trace(go.Scatter(
        x=price_x,
        y=price_y,
        mode='markers',
        marker=dict(size=5, color='#2E86AB', opacity=0.6),
        name='Price Data',
        hovertemplate=f'<b>{asset_x}</b>: %{{x:.2f}}<br><b>{asset_y}</b>: %{{y:.2f}}<extra></extra>'
    ))

    # Regression line
    x_range = np.array([price_x.min(), price_x.max()])
    y_pred = alpha + beta * x_range

    fig.add_trace(go.Scatter(
        x=x_range,
        y=y_pred,
        mode='lines',
        line=dict(color='red', width=2),
        name=f'{method.upper()} Fit',
        hovertemplate=f'Y = {alpha:.4f} + {beta:.4f}X<extra></extra>'
    ))

    # Add regression equation as annotation
    fig.add_annotation(
        x=0.05, y=0.95,
        xref='paper', yref='paper',
        text=f'<b>{asset_y} = {alpha:.4f} + {beta:.4f} × {asset_x}</b><br>R² = {r_squared:.4f}',
        showarrow=False,
        bgcolor='rgba(255,255,255,0.8)',
        bordercolor='black',
        borderwidth=1,
        align='left'
    )

    fig.update_layout(
        title=f"Price Scatter: {asset_y} vs {asset_x}",
        xaxis_title=f"{asset_x} Price",
        yaxis_title=f"{asset_y} Price",
        template="plotly_white",
        height=600,
        width=700,
        hovermode='closest'
    )

    return {
        'id': f"{chart_id}_scatter",
        'title': f"Price Scatter: {asset_y} vs {asset_x}",
        'plotly': fig.to_dict()
    }


def _validate_regression_diagnostics(
    residuals: np.ndarray,
    X: np.ndarray,
    Y: np.ndarray
) -> Dict[str, Any]:
    """
    Check OLS regression assumptions.

    Returns dict with diagnostic tests and pass/fail status.
    """
    try:
        diagnostics = {}

        # 1. Normality of residuals (Jarque-Bera test)
        jb_stat, jb_pvalue = stats.jarque_bera(residuals)
        diagnostics['normality'] = {
            'test': 'Jarque-Bera',
            'statistic': float(jb_stat),
            'p_value': float(jb_pvalue),
            'pass': jb_pvalue > 0.05,
            'interpretation': 'Residuals are normally distributed' if jb_pvalue > 0.05 else 'Residuals deviate from normality'
        }

        # 2. Autocorrelation (Durbin-Watson test)
        dw_stat = durbin_watson(residuals)
        diagnostics['autocorrelation'] = {
            'test': 'Durbin-Watson',
            'statistic': float(dw_stat),
            'pass': 1.5 < dw_stat < 2.5,
            'interpretation': (
                'No autocorrelation' if 1.5 < dw_stat < 2.5 else
                'Positive autocorrelation' if dw_stat < 1.5 else
                'Negative autocorrelation'
            )
        }

        # 3. Heteroscedasticity (Breusch-Pagan test)
        X_with_const = sm.add_constant(X)
        bp_stat, bp_pvalue, _, _ = het_breuschpagan(residuals, X_with_const)

        diagnostics['heteroscedasticity'] = {
            'test': 'Breusch-Pagan',
            'statistic': float(bp_stat),
            'p_value': float(bp_pvalue),
            'pass': bp_pvalue > 0.05,
            'interpretation': 'Homoscedastic (constant variance)' if bp_pvalue > 0.05 else 'Heteroscedastic (non-constant variance)'
        }

        return diagnostics

    except Exception as e:
        logger.warning(f"Diagnostic validation failed: {e}")
        return {}


async def calculate_hedge_ratio_internal(
    asset_x: str,
    asset_y: str,
    method: str = "ols",
    window: Optional[int] = None,
    period: str = "1Y",
    confidence_level: float = 0.95,
    min_data_points: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calculate dynamic hedge ratio between two assets for pairs trading.

    Computes optimal hedge ratio Y = α + βX where β is the hedge ratio.
    Three methods supported: OLS (ordinary least squares), TLS (total least squares),
    and Kalman (time-varying state-space model).

    Args:
        asset_x: Primary asset ticker (independent variable)
        asset_y: Hedge asset ticker (dependent variable)
        method: "ols" | "tls" | "kalman" (default: "ols")
            - ols: Simple linear regression (minimizes Y-errors)
            - tls: Total least squares (minimizes perpendicular distance)
            - kalman: Time-varying beta using state-space model
        window: Rolling window size in days (None = full sample static estimate)
            - For OLS: Rolling regression with window-sized lookback
            - For Kalman: Used as observation context (Kalman is inherently dynamic)
            - For TLS: Not supported (raises error if window != None)
        period: Historical period (default: "1Y"). Use "1M", "3M", "6M", "1Y", "2Y", "5Y", "max"
        confidence_level: Confidence level for regression statistics (default: 0.95)
        min_data_points: Minimum required data points (default: 30 for OLS/TLS, 60 for Kalman)

    Returns:
        Dict with hedge_ratio (series or scalar), R², residual stats, alpha, beta, charts
    """
    try:
        # Map period to calendar days
        period_days_map = {
            "1M": 30, "3M": 90, "6M": 180,
            "1Y": 365, "2Y": 730, "5Y": 1825, "max": 7300
        }
        lookback_period = period_days_map.get(period, 365)

        # Set min_data_points defaults based on method
        if min_data_points is None:
            if method == "kalman":
                min_data_points = 60  # Kalman needs more data for convergence
            else:
                min_data_points = 30  # OLS/TLS

        # Input validation
        if not asset_x or not asset_y:
            raise ValueError("Both asset_x and asset_y must be provided")

        if asset_x == asset_y:
            raise ValueError("Cannot calculate hedge ratio for same asset")

        if method not in ["ols", "tls", "kalman"]:
            raise ValueError(f"Invalid method: {method}. Must be 'ols', 'tls', or 'kalman'")

        if method == "tls" and window is not None:
            raise ValueError("TLS method does not support rolling windows. Use method='ols' with window, or method='tls' with window=None")

        if window is not None and window < 20:
            raise ValueError(f"Rolling window too small: {window}. Minimum 20 days for stable estimates")

        # Initialize FMP server
        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Fetch price data for both assets
            logger.info(f"Fetching data for {asset_x} and {asset_y}...")
            df_x = await _fetch_price_data(fmp_server, asset_x, lookback_period)
            df_y = await _fetch_price_data(fmp_server, asset_y, lookback_period)

            # Align data on common dates
            merged = pd.merge(df_x, df_y, on='date', suffixes=('_x', '_y'))

            if len(merged) < min_data_points:
                return {
                    'status': 'error',
                    'error': f"Insufficient common data: {len(merged)} days (need {min_data_points}+)",
                    'error_type': 'insufficient_data',
                    'available_days': len(merged),
                    'calculation_type': 'hedge_ratio'
                }

            # Extract prices
            X = merged['price_x'].values
            Y = merged['price_y'].values
            dates = merged['date'].dt.strftime('%Y-%m-%d').tolist()

            # Check for constant prices (zero variance)
            if np.var(X) < 1e-10 or np.var(Y) < 1e-10:
                constant_asset = asset_x if np.var(X) < 1e-10 else asset_y
                return {
                    'status': 'error',
                    'error': f"Constant prices detected for {constant_asset}. Cannot calculate hedge ratio.",
                    'error_type': 'zero_variance',
                    'calculation_type': 'hedge_ratio'
                }

            # Check for perfect collinearity
            corr = np.corrcoef(X, Y)[0, 1]
            if abs(corr) > 0.9999:
                return {
                    'status': 'error',
                    'error': "Perfect collinearity detected. Assets are perfectly correlated.",
                    'error_type': 'perfect_collinearity',
                    'correlation': float(corr),
                    'calculation_type': 'hedge_ratio'
                }

            # Branch based on method
            if method == "ols":
                if window is None:
                    # Static OLS
                    logger.info("Computing static OLS hedge ratio...")
                    X_with_const = sm.add_constant(X)
                    model = OLS(Y, X_with_const).fit()

                    alpha = float(model.params[0])
                    beta = float(model.params[1])
                    r_squared = float(model.rsquared)
                    adj_r_squared = float(model.rsquared_adj)
                    std_err_beta = float(model.bse[1])
                    confidence_interval = model.conf_int(alpha=1-confidence_level)[1].tolist()
                    f_statistic = float(model.fvalue)
                    p_value_f = float(model.f_pvalue)

                    residuals = model.resid
                    fitted_values = model.fittedvalues

                    # Single-element array for consistency
                    hedge_ratio_series = [beta]
                    hedge_ratio_dates = [dates[-1]]

                    # Diagnostics
                    diagnostics = _validate_regression_diagnostics(residuals, X, Y)

                else:
                    # Rolling OLS
                    logger.info(f"Computing rolling OLS with window={window}...")
                    hedge_ratios = []
                    alphas = []
                    r_squareds = []
                    dates_rolling = []

                    for i in range(window, len(X)):
                        X_window = X[i-window:i]
                        Y_window = Y[i-window:i]

                        X_window_const = sm.add_constant(X_window)
                        model_window = OLS(Y_window, X_window_const).fit()

                        hedge_ratios.append(model_window.params[1])
                        alphas.append(model_window.params[0])
                        r_squareds.append(model_window.rsquared)
                        dates_rolling.append(dates[i])

                    # Use full-sample for overall stats
                    X_with_const = sm.add_constant(X)
                    model_full = OLS(Y, X_with_const).fit()

                    alpha = float(np.mean(alphas))
                    beta = float(np.mean(hedge_ratios))
                    r_squared = float(np.mean(r_squareds))
                    adj_r_squared = float(model_full.rsquared_adj)
                    std_err_beta = float(np.std(hedge_ratios))
                    confidence_interval = [
                        float(beta - 1.96 * std_err_beta),
                        float(beta + 1.96 * std_err_beta)
                    ]
                    f_statistic = float(model_full.fvalue)
                    p_value_f = float(model_full.f_pvalue)

                    residuals = model_full.resid
                    fitted_values = model_full.fittedvalues

                    hedge_ratio_series = hedge_ratios
                    hedge_ratio_dates = dates_rolling

                    # Diagnostics on full sample
                    diagnostics = _validate_regression_diagnostics(residuals, X, Y)

            elif method == "tls":
                # Static TLS using SVD
                logger.info("Computing TLS hedge ratio using SVD...")

                try:
                    # Center data
                    X_centered = X - X.mean()
                    Y_centered = Y - Y.mean()

                    # Stack into matrix
                    data_matrix = np.column_stack([X_centered, Y_centered])

                    # Perform SVD
                    U, S, Vt = svd(data_matrix, full_matrices=False)

                    # Check for singular matrix
                    if S[-1] < 1e-10:
                        raise np.linalg.LinAlgError("Singular matrix detected")

                    # TLS slope
                    beta = float(-Vt[-1, 0] / Vt[-1, 1])
                    alpha = float(Y.mean() - beta * X.mean())

                    # TLS residuals (perpendicular distance)
                    residuals = (Y - alpha - beta * X) / np.sqrt(1 + beta**2)
                    fitted_values = alpha + beta * X

                    # Approximate R² for TLS
                    ss_res = np.sum(residuals**2)
                    ss_tot = np.sum((Y - Y.mean())**2)
                    r_squared = float(1 - (ss_res / ss_tot))

                    # TLS doesn't have these stats
                    adj_r_squared = r_squared
                    std_err_beta = None
                    confidence_interval = None
                    f_statistic = None
                    p_value_f = None

                    # Single-element array
                    hedge_ratio_series = [beta]
                    hedge_ratio_dates = [dates[-1]]

                    # Limited diagnostics for TLS
                    diagnostics = {}

                except np.linalg.LinAlgError:
                    return {
                        'status': 'error',
                        'error': "Singular matrix in TLS calculation. Assets may be perfectly collinear.",
                        'error_type': 'singular_matrix',
                        'calculation_type': 'hedge_ratio'
                    }

            elif method == "kalman":
                # Kalman filter for time-varying beta
                logger.info("Computing Kalman filter hedge ratio...")

                # Auto-tune hyperparameters from OLS
                X_with_const = sm.add_constant(X)
                model_ols = OLS(Y, X_with_const).fit()
                ols_beta = model_ols.params[1]
                ols_residuals = model_ols.resid

                # Observation noise (R): Variance of OLS residuals
                R = np.var(ols_residuals)

                # Transition noise (Q): Beta evolves slowly
                Q = 0.001 * R

                # Initialize Kalman Filter
                # observation_matrices must have shape (n_timesteps, n_dim_obs, n_dim_state)
                # Each observation_matrices[t] = [[X[t]]] for equation Y(t) = X(t) * beta(t) + noise
                observation_matrices = X.reshape(-1, 1, 1)  # Shape: (n_samples, 1, 1)

                kf = KalmanFilter(
                    n_dim_obs=1,
                    n_dim_state=1,
                    initial_state_mean=ols_beta,
                    initial_state_covariance=1,
                    transition_matrices=[[1]],
                    observation_matrices=observation_matrices,
                    observation_covariance=R,
                    transition_covariance=Q
                )

                # Estimate beta over time
                state_means, state_covariances = kf.filter(Y)
                hedge_ratios_kalman = state_means.flatten()
                beta_std = np.sqrt(state_covariances.flatten())

                # Check convergence
                if np.any(state_covariances > 1e6) or np.any(state_covariances < 1e-10):
                    logger.warning("Kalman filter may not have converged")

                # Calculate alpha using mean beta
                beta = float(np.mean(hedge_ratios_kalman))
                alpha = float(Y.mean() - beta * X.mean())

                # Residuals using mean beta
                residuals = Y - alpha - beta * X
                fitted_values = alpha + beta * X

                # R² using mean beta
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((Y - Y.mean())**2)
                r_squared = float(1 - (ss_res / ss_tot))

                # Kalman-specific stats
                adj_r_squared = r_squared
                std_err_beta = float(np.mean(beta_std))
                confidence_interval = [
                    float(beta - 1.96 * std_err_beta),
                    float(beta + 1.96 * std_err_beta)
                ]
                f_statistic = None
                p_value_f = None

                hedge_ratio_series = hedge_ratios_kalman.tolist()
                hedge_ratio_dates = dates

                # Confidence bands for chart
                confidence_bands = (
                    hedge_ratios_kalman - 1.96 * beta_std,
                    hedge_ratios_kalman + 1.96 * beta_std
                )

                # Diagnostics
                diagnostics = _validate_regression_diagnostics(residuals, X, Y)

            # Calculate residual statistics
            residuals_stats = {
                'mean': float(np.mean(residuals)),
                'std': float(np.std(residuals)),
                'min': float(np.min(residuals)),
                'max': float(np.max(residuals)),
                'autocorrelation_lag1': float(np.corrcoef(residuals[:-1], residuals[1:])[0, 1]) if len(residuals) > 1 else 0.0,
                'durbin_watson': float(durbin_watson(residuals))
            }

            # Add Jarque-Bera if not in diagnostics
            if diagnostics.get('normality'):
                residuals_stats['jarque_bera'] = diagnostics['normality']['statistic']
                residuals_stats['p_value_jb'] = diagnostics['normality']['p_value']
            else:
                jb_stat, jb_pvalue = stats.jarque_bera(residuals)
                residuals_stats['jarque_bera'] = float(jb_stat)
                residuals_stats['p_value_jb'] = float(jb_pvalue)

            # Generate charts
            chart_id = f"hedge_{abs(hash(f'{asset_x}_{asset_y}'))&0xFFFF:04x}"
            charts = []

            # Chart 1: Hedge ratio time series (if dynamic)
            if len(hedge_ratio_series) > 1:
                ratio_chart = await _build_hedge_ratio_chart(
                    np.array(hedge_ratio_series),
                    hedge_ratio_dates,
                    method,
                    chart_id,
                    confidence_bands if method == "kalman" else None
                )
                if ratio_chart:
                    charts.append(ratio_chart)

            # Chart 2: Residuals analysis
            residuals_chart = await _build_residuals_chart(
                residuals,
                dates,
                fitted_values,
                chart_id
            )
            if residuals_chart:
                charts.append(residuals_chart)

            # Chart 3: Scatter plot
            scatter_chart = await _build_scatter_chart(
                X, Y, alpha, beta, r_squared,
                asset_x, asset_y, method, chart_id
            )
            if scatter_chart:
                charts.append(scatter_chart)

            charts = wrap_plotly_charts(charts, default_type="hedge_ratio_chart")

            # Prepare results (omit large time series arrays to prevent context overflow)
            results = {
                'hedge_ratio': {
                    'method': method,
                    'static_estimate': float(beta),
                    # Removed: time_series and dates arrays (embedded in charts)
                    'n_observations': len(hedge_ratio_series),
                    'date_range': [hedge_ratio_dates[0], hedge_ratio_dates[-1]] if hedge_ratio_dates else None,
                    'alpha': float(alpha),
                    'beta': float(beta),
                    'window': window
                },
                'fit_quality': {
                    'r_squared': r_squared,
                    'adj_r_squared': adj_r_squared,
                    'std_err_beta': std_err_beta,
                    'confidence_interval': confidence_interval,
                    'f_statistic': f_statistic,
                    'p_value_f': p_value_f
                },
                'residuals': residuals_stats,
                'diagnostics': diagnostics,
                'metadata': {
                    'asset_x': asset_x,
                    'asset_y': asset_y,
                    'n_samples': len(merged),
                    'period': period,
                    'date_range': [dates[0], dates[-1]],
                    'min_data_points': min_data_points,
                    'confidence_level': confidence_level
                }
            }

            return jsonify_results({
                'status': 'success',
                'results': results,
                'charts': charts
            })

        except Exception as e:
            logger.error(f"Hedge ratio calculation failed: {e}")
            error_type = 'data_error' if any(
                kw in str(e).lower() for kw in ['no data', 'insufficient', 'singular', 'constant']
            ) else 'calculation_error'

            return {
                'status': 'error',
                'error': str(e),
                'error_type': error_type,
                'calculation_type': 'hedge_ratio'
            }

    except Exception as e:
        logger.error(f"Hedge ratio calculation failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'calculation_type': 'hedge_ratio'
        }


@function_tool
async def calculate_hedge_ratio(
    asset_x: str,
    asset_y: str,
    method: str = "ols",
    window: Optional[int] = None,
    period: str = "1Y",
    confidence_level: float = 0.95,
    min_data_points: Optional[int] = None
) -> str:
    """
    Calculate dynamic hedge ratio between two assets for pairs trading (agent-facing wrapper).

    Computes optimal hedge ratio Y = α + βX where β is the hedge ratio.
    Three methods supported: OLS, TLS, and Kalman filter.

    Args:
        asset_x: Primary asset ticker (independent variable)
        asset_y: Hedge asset ticker (dependent variable)
        method: "ols" | "tls" | "kalman" (default: "ols")
        window: Rolling window size in days (None = static estimate)
        period: Historical period (default: "1Y")
        confidence_level: Confidence level (default: 0.95)
        min_data_points: Minimum required data points

    Returns:
        JSON string with hedge_ratio, R², residual stats, alpha, beta, charts
    """
    import json
    result = await calculate_hedge_ratio_internal(
        asset_x=asset_x,
        asset_y=asset_y,
        method=method,
        window=window,
        period=period,
        confidence_level=confidence_level,
        min_data_points=min_data_points
    )
    return json.dumps(result)
