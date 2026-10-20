"""
Correlation Stress Test Tool

Stress tests portfolio risk under correlation shock scenarios.
Uses multivariate Monte Carlo simulation to show how portfolio distribution
changes when asset correlations surge (e.g., market crash).

NO HARDCODING - uses dynamic field discovery for market data.
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.utils.validation import validate_weights, validate_confidence_level, validate_portfolio_value
from core.constants import DEFAULT_PORTFOLIO_VALUE, DEFAULT_PERIOD
from .shared import sanitize_tool_output, register_chart_handle

logger = logging.getLogger(__name__)


def _shock_correlation_matrix(corr_matrix: np.ndarray, target_corr: float) -> np.ndarray:
    """
    Shock correlation matrix to target level while preserving positive semi-definite property.

    Args:
        corr_matrix: Original correlation matrix
        target_corr: Target correlation for off-diagonal elements

    Returns:
        Shocked correlation matrix
    """
    n = corr_matrix.shape[0]
    shocked = np.full((n, n), target_corr)
    np.fill_diagonal(shocked, 1.0)

    # Ensure positive semi-definite via eigenvalue clipping
    eigenvalues, eigenvectors = np.linalg.eigh(shocked)
    eigenvalues = np.maximum(eigenvalues, 1e-8)
    shocked = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T

    # Re-normalize to correlation matrix
    d = np.sqrt(np.diag(shocked))
    shocked = shocked / np.outer(d, d)
    np.fill_diagonal(shocked, 1.0)

    return shocked


def _simulate_multivariate_paths(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    weights: np.ndarray,
    n_simulations: int,
    time_horizon: int,
    initial_value: float
) -> np.ndarray:
    """
    Generate portfolio value paths using multivariate simulation with Cholesky decomposition.

    Args:
        mean_returns: Daily mean returns for each asset (n_assets,)
        cov_matrix: Covariance matrix (n_assets, n_assets)
        weights: Portfolio weights (n_assets,)
        n_simulations: Number of Monte Carlo paths
        time_horizon: Forecast horizon in days
        initial_value: Starting portfolio value

    Returns:
        Portfolio value paths (n_simulations, time_horizon + 1)
    """
    n_assets = len(mean_returns)

    # Cholesky decomposition
    try:
        L = np.linalg.cholesky(cov_matrix)
    except np.linalg.LinAlgError:
        # Fallback: eigenvalue method
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        eigenvalues = np.maximum(eigenvalues, 1e-8)
        L = eigenvectors @ np.diag(np.sqrt(eigenvalues))

    # Generate independent standard normal samples
    Z = np.random.standard_normal((n_simulations, time_horizon, n_assets))

    # Transform to correlated returns: X = μ + L @ Z
    correlated_returns = mean_returns[np.newaxis, np.newaxis, :] + np.einsum('ij,klj->kli', L, Z)

    # Calculate portfolio returns: weighted sum across assets
    portfolio_returns = np.einsum('ijk,k->ij', correlated_returns, weights)

    # Compound returns to portfolio values
    cumulative_returns = np.cumprod(1 + portfolio_returns, axis=1)
    portfolio_values = cumulative_returns * initial_value

    # Prepend initial value
    initial_values = np.full((n_simulations, 1), initial_value)
    portfolio_paths = np.concatenate([initial_values, portfolio_values], axis=1)

    return portfolio_paths


def _calculate_risk_metrics(
    portfolio_paths: np.ndarray,
    confidence_level: float,
    initial_value: float
) -> Dict[str, float]:
    """Calculate VaR, CVaR, and other risk metrics from simulated paths."""
    terminal_values = portfolio_paths[:, -1]
    losses = initial_value - terminal_values

    # VaR: percentile of losses
    var_percentile = (1 - confidence_level) * 100
    var = np.percentile(losses, 100 - var_percentile)

    # CVaR: mean loss beyond VaR
    var_threshold = np.percentile(terminal_values, var_percentile)
    tail_losses = losses[terminal_values <= var_threshold]
    cvar = tail_losses.mean() if len(tail_losses) > 0 else var

    # Statistics
    returns = (terminal_values - initial_value) / initial_value

    return {
        'var': float(var),
        'cvar': float(cvar),
        'expected_value': float(terminal_values.mean()),
        'volatility': float(returns.std()),
        'percentile_5': float(np.percentile(terminal_values, 5)),
        'percentile_50': float(np.percentile(terminal_values, 50)),
        'percentile_95': float(np.percentile(terminal_values, 95))
    }


def _calculate_diversification_benefit(
    portfolio_vol: float,
    individual_vols: np.ndarray,
    weights: np.ndarray
) -> float:
    """
    Calculate diversification benefit.

    Benefit = 1 - (portfolio_vol / weighted_avg_vol)
    High correlation → low benefit
    """
    weighted_avg_vol = np.sum(individual_vols * weights)
    if weighted_avg_vol > 0:
        return max(0.0, 1.0 - (portfolio_vol / weighted_avg_vol))
    return 0.0


def _create_correlation_heatmap(
    baseline_corr: np.ndarray,
    stressed_corr: np.ndarray,
    tickers: List[str]
) -> Dict[str, Any]:
    """Create side-by-side correlation heatmap."""
    n_assets = len(tickers)
    height = max(500, n_assets * 50)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Baseline', 'Extreme Stress'),
        horizontal_spacing=0.15
    )

    # Baseline
    fig.add_trace(
        go.Heatmap(
            z=baseline_corr,
            x=tickers,
            y=tickers,
            colorscale='RdBu_r',
            zmid=0,
            zmin=-1,
            zmax=1,
            text=np.round(baseline_corr, 2),
            texttemplate='%{text}',
            textfont={"size": 10},
            colorbar=dict(x=0.45, title='ρ')
        ),
        row=1, col=1
    )

    # Stressed
    fig.add_trace(
        go.Heatmap(
            z=stressed_corr,
            x=tickers,
            y=tickers,
            colorscale='RdBu_r',
            zmid=0,
            zmin=-1,
            zmax=1,
            text=np.round(stressed_corr, 2),
            texttemplate='%{text}',
            textfont={"size": 10},
            colorbar=dict(x=1.02, title='ρ')
        ),
        row=1, col=2
    )

    fig.update_layout(
        title='Correlation Matrices',
        height=height,
        showlegend=False
    )

    fig.update_xaxes(tickangle=45)

    return {"id": "correlation_heatmap", "title": "Correlation Matrices", "plotly": fig.to_dict()}


def _create_distribution_chart(
    baseline_paths: np.ndarray,
    stressed_paths: np.ndarray,
    initial_value: float
) -> Dict[str, Any]:
    """Create histogram comparing terminal value distributions."""
    baseline_terminal = baseline_paths[:, -1]
    stressed_terminal = stressed_paths[:, -1]

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=baseline_terminal,
        name='Baseline',
        opacity=0.7,
        nbinsx=50,
        marker_color='#3b82f6'
    ))

    fig.add_trace(go.Histogram(
        x=stressed_terminal,
        name='Extreme Stress',
        opacity=0.7,
        nbinsx=50,
        marker_color='#ef4444'
    ))

    fig.add_vline(
        x=initial_value,
        line_dash="dash",
        line_color="gray",
        annotation_text="Initial Value"
    )

    fig.update_layout(
        title='Portfolio Value Distribution',
        xaxis_title='Portfolio Value ($)',
        yaxis_title='Frequency',
        barmode='overlay',
        height=450,
        showlegend=True
    )

    return {"id": "distribution_comparison", "title": "Portfolio Value Distribution", "plotly": fig.to_dict()}


def _create_risk_escalation_chart(
    baseline_metrics: Dict[str, float],
    stressed_scenarios_results: Dict[float, Dict[str, float]],
    correlation_scenarios: List[float],
    portfolio_value: float
) -> Dict[str, Any]:
    """Create chart showing VaR/CVaR escalation across scenarios."""

    scenarios = ['Baseline'] + [f'ρ→{c:.2f}' for c in sorted(correlation_scenarios)]
    var_values = [baseline_metrics['var']]
    cvar_values = [baseline_metrics['cvar']]

    for corr in sorted(correlation_scenarios):
        var_values.append(stressed_scenarios_results[corr]['var_95'])
        cvar_values.append(stressed_scenarios_results[corr]['cvar_95'])

    var_pct = [(v / portfolio_value) * 100 for v in var_values]
    cvar_pct = [(v / portfolio_value) * 100 for v in cvar_values]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=scenarios,
        y=var_pct,
        name='95% VaR',
        mode='lines+markers',
        line=dict(color='#f59e0b', width=2.5),
        marker=dict(size=8)
    ))

    fig.add_trace(go.Scatter(
        x=scenarios,
        y=cvar_pct,
        name='95% CVaR',
        mode='lines+markers',
        line=dict(color='#ef4444', width=2.5),
        marker=dict(size=8)
    ))

    fig.update_layout(
        title='Risk Escalation Across Scenarios',
        xaxis_title='Scenario',
        yaxis_title='Loss (% of Portfolio)',
        height=450,
        showlegend=True,
        hovermode='x unified'
    )

    fig.update_xaxes(tickangle=45)
    fig.update_yaxes(ticksuffix='%')

    return {"id": "risk_escalation", "title": "Risk Escalation Across Scenarios", "plotly": fig.to_dict()}


@function_tool
async def stress_test_correlation(
    tickers: Optional[List[str]] = None,
    portfolio_id: Optional[str] = None,
    period: str = DEFAULT_PERIOD,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    weights: Optional[List[float]] = None,
    correlation_scenarios: Optional[List[float]] = None,
    n_simulations: int = 1000,
    time_horizon: int = 63,
    confidence_level: float = 0.95,
    portfolio_value: float = DEFAULT_PORTFOLIO_VALUE
) -> dict:
    """
    Stress test portfolio under MULTIPLE correlation shock scenarios.

    Simulates portfolio behavior as asset correlations surge across crash scenarios.
    Tests baseline + multiple stress levels to show risk escalation explicitly.
    Uses multivariate Monte Carlo with Cholesky decomposition.

    IMPORTANT: Tests multiple scenarios by default (0.50, 0.75, 0.90, 0.95) to show
    full progression from mild stress to market crash. Override correlation_scenarios
    to test custom levels.

    Args:
        tickers: List of ticker symbols. OPTIONAL if portfolio_id is provided.
        portfolio_id: OPTIONAL - Portfolio ID or name to load tickers/weights from.
        period: Historical data period ('1y', '2y', '5y', etc.). Default: '1y'
                Override to match your analysis horizon.
        start_date: OPTIONAL - Start date (YYYY-MM-DD). OMIT if not needed.
        end_date: OPTIONAL - End date (YYYY-MM-DD). OMIT if not needed.
        weights: OPTIONAL - Portfolio weights. OMIT for equal weighting. Ignored if portfolio_id provided.
        correlation_scenarios: List of correlation levels to test (default [0.50, 0.75, 0.90, 0.95]).
                              Override with custom scenarios like [0.80, 0.90] for targeted stress levels.
                              Values represent target correlations in stressed scenarios.
        n_simulations: Number of Monte Carlo paths (default 1000).
                      Override: 500 for quick tests, 5000+ for high precision.
        time_horizon: Forecast horizon in days (default 63 = ~3 months).
                     Override: 21 for 1 month, 126 for 6 months, 252 for 1 year.
        confidence_level: VaR confidence level (default 0.95).
                         Override: 0.99 for more conservative risk estimates.
        portfolio_value: Total portfolio value in dollars (default $1M).
                        Override with actual portfolio size.

    Returns:
        Structured results with baseline vs multiple stressed scenarios and charts

    Examples:
        ✅ CORRECT: stress_test_correlation(portfolio_id="my_portfolio")
        ✅ CORRECT: stress_test_correlation(tickers=["AAPL", "MSFT", "GOOGL"])
        ❌ WRONG: Don't pass "null" or empty strings for optional parameters
    """
    from .shared import resolve_portfolio_tickers
    
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
                    'calculation_type': 'correlation_stress_test'
                }
        
        # Validate we have tickers
        if not tickers:
            return {
                'status': 'error',
                'error': 'Either tickers or portfolio_id must be provided',
                'error_type': 'validation_error',
                'calculation_type': 'correlation_stress_test'
            }
        # Set default scenarios if not provided
        if correlation_scenarios is None:
            correlation_scenarios = [0.50, 0.75, 0.90, 0.95]

        # Validate inputs
        n_assets = len(tickers)
        if n_assets < 2:
            raise ValueError("Need at least 2 assets for correlation stress test")

        weights = validate_weights(weights, n_assets)
        confidence_level = validate_confidence_level(confidence_level)
        portfolio_value = validate_portfolio_value(portfolio_value)

        # Validate all correlation scenarios
        for corr in correlation_scenarios:
            if not 0 < corr <= 1.0:
                raise ValueError(f"All correlations must be in (0, 1], got {corr}")

        logger.info(f"Correlation stress test: {tickers}, scenarios={correlation_scenarios}")

        # Identify cash tickers (they have zero volatility and zero correlation)
        cash_identifiers = {'CASH', '$CASH', 'USD', 'USDOLLAR', 'MONEY', 'CASH_USD'}
        is_cash = [ticker.upper() in cash_identifiers for ticker in tickers]
        has_cash = any(is_cash)

        if has_cash:
            cash_weight = sum(weights[i] for i, cash in enumerate(is_cash) if cash)
            equity_weight = 1.0 - cash_weight
            logger.info(f"Portfolio contains cash: {cash_weight:.1%} cash, {equity_weight:.1%} equities")

        # Fetch market data using FMP server (FFT pattern)
        fmp_server = FMPMarketDataServer()
        price_data = {}

        try:
            await fmp_server.connect()

            # Fetch data for each ticker (PCA pattern - raise errors immediately)
            for i, ticker in enumerate(tickers):
                # Skip cash tickers - they have zero volatility
                if is_cash[i]:
                    logger.info(f"Skipping data fetch for cash ticker: {ticker}")
                    # Create a flat price series for cash (no volatility)
                    price_data[ticker] = pd.Series([1.0] * 252, index=pd.date_range(end=pd.Timestamp.now(), periods=252, freq='D'))
                    continue

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

                if not dates or not prices or len(dates) < 50:
                    raise ValueError(f"Insufficient data for {ticker}: {len(dates)} points (need 50+)")

                # Store price series
                price_data[ticker] = pd.Series(prices, index=pd.to_datetime(dates))
                logger.info(f"Fetched {len(dates)} data points for {ticker}")

            if not price_data:
                message = "No valid data for requested tickers"
                logger.error("%s. Attempted: %s", message, ", ".join(tickers))
                return jsonify_results({
                    "status": "error",
                    "error": message,
                    "error_type": "data_unavailable",
                    "attempted_tickers": tickers
                })

            # Build price DataFrame
            prices_df = pd.DataFrame(price_data)
            prices_df = prices_df.sort_index()  # Ensure chronological order
            prices_df = prices_df.dropna()  # Drop rows with any missing data

            actual_tickers = list(prices_df.columns)
            logger.info(f"Data available for {len(actual_tickers)}/{n_assets} tickers")

            if len(actual_tickers) < 2:
                message = "Insufficient data to compute correlations (need at least 2 assets)"
                logger.error("%s. Available: %s", message, ", ".join(actual_tickers))
                return jsonify_results({
                    "status": "error",
                    "error": message,
                    "error_type": "insufficient_assets",
                    "attempted_tickers": tickers,
                    "available_tickers": actual_tickers
                })

            # Adjust weights if some tickers failed
            if len(actual_tickers) != n_assets:
                ticker_to_weight = dict(zip(tickers, weights))
                weights = np.array([ticker_to_weight.get(t, 0) for t in actual_tickers])
                weights = weights / weights.sum()  # Re-normalize

            # Calculate log returns
            returns = np.log(prices_df / prices_df.shift(1)).dropna()

            # Force cash returns to zero (zero volatility)
            for i, ticker in enumerate(actual_tickers):
                if is_cash[tickers.index(ticker)]:
                    returns[ticker] = 0.0

            logger.info(f"Returns data: {len(returns)} observations, {len(actual_tickers)} assets")

            if returns.empty:
                message = "Insufficient observations to compute returns"
                logger.error("%s for tickers: %s", message, ", ".join(actual_tickers))
                return jsonify_results({
                    "status": "error",
                    "error": message,
                    "error_type": "insufficient_data",
                    "attempted_tickers": tickers,
                    "available_tickers": actual_tickers
                })

            # Calculate baseline correlation and parameters
            baseline_corr_matrix = returns.corr().values
            baseline_cov_matrix = returns.cov().values
            mean_returns = returns.mean().values
            individual_vols = returns.std().values

            # Force cash correlations and covariances to zero (cash is uncorrelated with equities)
            for i, ticker in enumerate(actual_tickers):
                if is_cash[tickers.index(ticker)]:
                    # Zero correlation with all assets
                    baseline_corr_matrix[i, :] = 0.0
                    baseline_corr_matrix[:, i] = 0.0
                    baseline_corr_matrix[i, i] = 1.0  # Self-correlation = 1

                    # Zero covariance with all assets
                    baseline_cov_matrix[i, :] = 0.0
                    baseline_cov_matrix[:, i] = 0.0

                    # Force individual volatility to zero for cash
                    individual_vols[i] = 0.0

            # Average correlation (off-diagonal)
            n_assets = len(actual_tickers)  # Update count
            mask = ~np.eye(n_assets, dtype=bool)
            baseline_avg_corr = baseline_corr_matrix[mask].mean()

            logger.info(f"Baseline avg correlation: {baseline_avg_corr:.3f}")

            # Baseline simulation
            logger.info(f"Running baseline simulation ({n_simulations} paths, {time_horizon} days)...")
            baseline_paths = _simulate_multivariate_paths(
                mean_returns=mean_returns,
                cov_matrix=baseline_cov_matrix,
                weights=weights,
                n_simulations=n_simulations,
                time_horizon=time_horizon,
                initial_value=portfolio_value
            )

            baseline_metrics = _calculate_risk_metrics(
                portfolio_paths=baseline_paths,
                confidence_level=confidence_level,
                initial_value=portfolio_value
            )

            baseline_div_benefit = _calculate_diversification_benefit(
                portfolio_vol=baseline_metrics['volatility'],
                individual_vols=individual_vols,
                weights=weights
            )

            logger.info(f"Baseline VaR: ${baseline_metrics['var']:,.0f}")

            # Run stress tests for EACH correlation scenario
            stressed_scenarios_results = {}
            all_stressed_paths = []
            all_stressed_corr_matrices = []

            for target_correlation in correlation_scenarios:
                logger.info(f"Testing scenario: ρ→{target_correlation:.2f}...")

                # Map correlation level to market crash severity (annualized returns)
                # Higher correlation = worse crash
                if target_correlation <= 0.50:
                    crash_return_annual = -0.10  # -10% mild stress
                elif target_correlation <= 0.75:
                    crash_return_annual = -0.20  # -20% moderate crisis
                elif target_correlation <= 0.90:
                    crash_return_annual = -0.30  # -30% severe crisis
                else:
                    crash_return_annual = -0.40  # -40% extreme crash

                # Convert annualized crash to daily returns
                crash_return_daily = crash_return_annual / 252

                # Create stressed mean returns (crash all equities, keep cash at 0)
                stressed_mean_returns = mean_returns.copy()
                for i, ticker in enumerate(actual_tickers):
                    if not is_cash[tickers.index(ticker)]:
                        # Apply crash to equities only
                        stressed_mean_returns[i] = crash_return_daily
                    # Cash stays at 0 return

                # Shock correlation matrix (but keep cash at zero correlation)
                stressed_corr_matrix = _shock_correlation_matrix(baseline_corr_matrix, target_correlation)

                # Keep cash correlations at zero in stressed scenario
                for i, ticker in enumerate(actual_tickers):
                    if is_cash[tickers.index(ticker)]:
                        stressed_corr_matrix[i, :] = 0.0
                        stressed_corr_matrix[:, i] = 0.0
                        stressed_corr_matrix[i, i] = 1.0

                # Create stressed covariance matrix
                vol_outer = np.outer(individual_vols, individual_vols)
                stressed_cov_matrix = stressed_corr_matrix * vol_outer

                # Force cash volatility to zero in stressed covariance
                for i, ticker in enumerate(actual_tickers):
                    if is_cash[tickers.index(ticker)]:
                        stressed_cov_matrix[i, :] = 0.0
                        stressed_cov_matrix[:, i] = 0.0

                stressed_avg_corr = stressed_corr_matrix[mask].mean()

                # Stressed simulation for this scenario (BOTH price crash AND correlation spike)
                stressed_paths = _simulate_multivariate_paths(
                    mean_returns=stressed_mean_returns,  # CRASHED returns (negative)
                    cov_matrix=stressed_cov_matrix,  # Shocked covariance (high correlation)
                    weights=weights,
                    n_simulations=n_simulations,
                    time_horizon=time_horizon,
                    initial_value=portfolio_value
                )

                stressed_metrics = _calculate_risk_metrics(
                    portfolio_paths=stressed_paths,
                    confidence_level=confidence_level,
                    initial_value=portfolio_value
                )

                stressed_div_benefit = _calculate_diversification_benefit(
                    portfolio_vol=stressed_metrics['volatility'],
                    individual_vols=individual_vols,
                    weights=weights
                )

                logger.info(f"  ρ={target_correlation:.2f}: VaR=${stressed_metrics['var']:,.0f}, CVaR=${stressed_metrics['cvar']:,.0f}")

                # Calculate impact vs baseline
                var_increase_pct = ((stressed_metrics['var'] - baseline_metrics['var']) /
                                   baseline_metrics['var'] * 100)
                var_increase_dollars = stressed_metrics['var'] - baseline_metrics['var']
                cvar_increase_pct = ((stressed_metrics['cvar'] - baseline_metrics['cvar']) /
                                    baseline_metrics['cvar'] * 100)
                volatility_multiplier = (stressed_metrics['volatility'] / baseline_metrics['volatility']
                                        if baseline_metrics['volatility'] > 0 else 1.0)
                diversification_loss = baseline_div_benefit - stressed_div_benefit

                # Store results for this scenario
                stressed_scenarios_results[target_correlation] = {
                    'average_correlation': float(stressed_avg_corr),
                    'correlation_matrix': stressed_corr_matrix.tolist(),
                    'var_95': float(stressed_metrics['var']),
                    'var_95_pct': float((stressed_metrics['var'] / portfolio_value) * 100),
                    'cvar_95': float(stressed_metrics['cvar']),
                    'cvar_95_pct': float((stressed_metrics['cvar'] / portfolio_value) * 100),
                    'expected_value': float(stressed_metrics['expected_value']),
                    'volatility': float(stressed_metrics['volatility']),
                    'diversification_benefit': float(stressed_div_benefit),
                    'percentile_5': float(stressed_metrics['percentile_5']),
                    'percentile_50': float(stressed_metrics['percentile_50']),
                    'percentile_95': float(stressed_metrics['percentile_95']),
                    'var_increase_pct': float(var_increase_pct),
                    'var_increase_dollars': float(var_increase_dollars),
                    'cvar_increase_pct': float(cvar_increase_pct),
                    'cvar_increase_dollars': float(stressed_metrics['cvar'] - baseline_metrics['cvar']),
                    'volatility_multiplier': float(volatility_multiplier),
                    'diversification_loss': float(diversification_loss)
                }

                all_stressed_paths.append(stressed_paths)
                all_stressed_corr_matrices.append(stressed_corr_matrix)

            # Create visualizations showing ALL scenarios
            logger.info("Creating multi-scenario charts...")

            # Identify worst case (highest correlation)
            worst_case_corr = max(correlation_scenarios)
            worst_case_idx = list(correlation_scenarios).index(worst_case_corr)

            # Chart 1: Risk escalation across all scenarios (most important!)
            risk_escalation_chart = _create_risk_escalation_chart(
                baseline_metrics=baseline_metrics,
                stressed_scenarios_results=stressed_scenarios_results,
                correlation_scenarios=correlation_scenarios,
                portfolio_value=portfolio_value
            )

            # Chart 2: Correlation heatmap (baseline vs worst case)
            heatmap_chart = _create_correlation_heatmap(
                baseline_corr=baseline_corr_matrix,
                stressed_corr=all_stressed_corr_matrices[worst_case_idx],
                tickers=actual_tickers
            )

            # Chart 3: Distribution comparison (baseline vs worst case)
            distribution_chart = _create_distribution_chart(
                baseline_paths=baseline_paths,
                stressed_paths=all_stressed_paths[worst_case_idx],
                initial_value=portfolio_value
            )

            # Return charts in priority order
            charts = [risk_escalation_chart, heatmap_chart, distribution_chart]
            chart_handles: List[Dict[str, Any]] = []
            for chart in charts:
                if isinstance(chart, dict) and chart.get("plotly"):
                    chart_title = chart.get("title") or chart.get("id") or "Chart"
                    chart_handles.append(
                        register_chart_handle(
                            chart["plotly"],
                            chart_type=chart.get("id", "correlation_stress_chart"),
                            title=chart_title,
                            alt_text=chart_title,
                            chart_id=chart.get("id")
                        )
                    )
            charts = chart_handles

            # Generate comprehensive multi-scenario analysis
            conf_pct = int(confidence_level * 100)

            # Calculate baseline percentages
            baseline_var_pct = (baseline_metrics['var'] / portfolio_value) * 100
            baseline_cvar_pct = (baseline_metrics['cvar'] / portfolio_value) * 100

            # Identify dominant risk drivers (largest weight × vol products)
            risk_contributions = weights * individual_vols
            risk_driver_idx = np.argmax(risk_contributions)
            risk_driver = actual_tickers[risk_driver_idx]
            risk_driver_weight = weights[risk_driver_idx]

            # Build scenario comparison table
            scenario_table = f"| Scenario | Avg ρ | {conf_pct}% VaR | {conf_pct}% CVaR | Vol | Div Benefit |\n"
            scenario_table += f"|----------|-------|-------|-------|-----|-------------|\n"
            scenario_table += (
                f"| **Baseline** | {baseline_avg_corr:.3f} | "
                f"${baseline_metrics['var']:,.0f} ({baseline_var_pct:.1f}%) | "
                f"${baseline_metrics['cvar']:,.0f} ({baseline_cvar_pct:.1f}%) | "
                f"{baseline_metrics['volatility']:.1%} | {baseline_div_benefit:.1%} |\n"
            )

            for target_corr in correlation_scenarios:
                s = stressed_scenarios_results[target_corr]
                scenario_table += (
                    f"| **ρ→{target_corr:.2f}** | {s['average_correlation']:.3f} | "
                    f"${s['var_95']:,.0f} ({s['var_95_pct']:.1f}%) | "
                    f"${s['cvar_95']:,.0f} ({s['cvar_95_pct']:.1f}%) | "
                    f"{s['volatility']:.1%} | {s['diversification_benefit']:.1%} |\n"
                )

            # Build crash scenario descriptions
            crash_descriptions = {
                0.50: "Mild stress: -10% annual returns, ρ→0.50",
                0.75: "Moderate crisis: -20% annual returns, ρ→0.75",
                0.90: "Severe crisis: -30% annual returns, ρ→0.90",
                0.95: "Extreme crash: -40% annual returns, ρ→0.95"
            }

            summary = (
                f"## Market Crash Stress Test - Price Drops + Correlation Spikes\n\n"
                f"**Portfolio**: {n_assets} assets, ${portfolio_value:,.0f} total value\n"
                f"**Horizon**: {time_horizon} trading days (~{time_horizon//21} months)\n"
                f"**Simulations**: {n_simulations:,} paths per scenario\n\n"
                f"**Scenarios**: Tests BOTH price crashes AND correlation breakdowns simultaneously:\n"
            )

            # Add scenario descriptions
            for corr in sorted(correlation_scenarios):
                crash_pct = {0.50: '-10%', 0.75: '-20%', 0.90: '-30%', 0.95: '-40%'}.get(corr, 'N/A')
                summary += f"- **ρ→{corr:.2f}**: {crash_pct} annual returns, correlations spike to {corr:.0%}\n"

            summary += (
                f"\n### Risk Escalation Across Scenarios\n\n"
                f"{scenario_table}\n"
                f"### Key Insights\n\n"
                f"**Risk Driver**: {risk_driver} dominates risk ({risk_driver_weight:.1%} weight, highest vol×weight contribution)\n\n"
                f"**Baseline**: Current market conditions (ρ_avg={baseline_avg_corr:.3f}), {conf_pct}% loss is ${baseline_metrics['var']:,.0f} "
                f"({baseline_var_pct:.1f}%), tail losses average ${baseline_metrics['cvar']:,.0f}.\n\n"
            )

            # Add specific insights for each stress scenario
            for target_corr in correlation_scenarios:
                s = stressed_scenarios_results[target_corr]
                summary += (
                    f"**ρ→{target_corr:.2f} Scenario**: {conf_pct}% VaR rises to ${s['var_95']:,.0f} "
                    f"(+${s['var_increase_dollars']:,.0f}, {s['var_increase_pct']:+.1f}%), "
                    f"CVaR hits ${s['cvar_95']:,.0f}. Diversification drops {s['diversification_loss']:.1%}.\n\n"
                )

            # Get worst case for final summary
            worst = stressed_scenarios_results[worst_case_corr]
            summary += (
                f"**Worst Case (ρ→{worst_case_corr:.2f})**: Under extreme crisis correlations, VaR explodes to "
                f"${worst['var_95']:,.0f} (+{worst['var_increase_pct']:.1f}% vs baseline), CVaR reaches ${worst['cvar_95']:,.0f}. "
                f"Portfolio volatility increases {worst['volatility_multiplier']:.2f}x as diversification collapses "
                f"by {worst['diversification_loss']:.1%}. Assets move in lockstep during crashes."
            )

            # Add ticker breakdown
            ticker_breakdown = []
            for i, ticker in enumerate(actual_tickers):
                ticker_breakdown.append({
                    'ticker': ticker,
                    'weight': float(weights[i]),
                    'volatility': float(individual_vols[i]),
                    'risk_contribution': float(risk_contributions[i]),
                    'is_cash': is_cash[tickers.index(ticker)]
                })

            # Sort by risk contribution (descending)
            ticker_breakdown.sort(key=lambda x: x['risk_contribution'], reverse=True)

            # Return structured results with ALL scenarios (following PCA pattern)
            results = {
                "baseline": {
                    "average_correlation": float(baseline_avg_corr),
                    "correlation_matrix": baseline_corr_matrix.tolist(),
                    "var_95": float(baseline_metrics['var']),
                    "var_95_pct": float(baseline_var_pct),
                    "cvar_95": float(baseline_metrics['cvar']),
                    "cvar_95_pct": float(baseline_cvar_pct),
                    "expected_value": float(baseline_metrics['expected_value']),
                    "volatility": float(baseline_metrics['volatility']),
                    "diversification_benefit": float(baseline_div_benefit),
                    "percentile_5": float(baseline_metrics['percentile_5']),
                    "percentile_50": float(baseline_metrics['percentile_50']),
                    "percentile_95": float(baseline_metrics['percentile_95'])
                },
                "stressed_scenarios": stressed_scenarios_results,  # All scenarios keyed by correlation level
                "ticker_breakdown": ticker_breakdown,
                "risk_driver": {
                    "ticker": risk_driver,
                    "weight": float(risk_driver_weight),
                    "contribution": float(risk_contributions[risk_driver_idx])
                },
                "metadata": {
                    "n_simulations": n_simulations,
                    "time_horizon_days": time_horizon,
                    "correlation_scenarios": [float(c) for c in correlation_scenarios],
                    "confidence_level": confidence_level,
                    "portfolio_value": portfolio_value,
                    "n_assets": n_assets,
                    "tickers": actual_tickers,
                    "weights": weights.tolist(),
                    "period": period,
                    "has_cash": has_cash
                }
            }

            # Return following PCA pattern exactly
            return jsonify_results({
                'status': 'success',
                'results': results,
                'summary': summary,
                'tickers': actual_tickers,
                'charts': charts
            })

        except Exception as e:
            logger.error(f"Correlation stress test failed: {e}", exc_info=True)
            return jsonify_results({
                "status": "error",
                "error": str(e),
                "error_type": "execution_error",
                "attempted_tickers": tickers
            })
        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Outer correlation stress test error: {e}", exc_info=True)
        return jsonify_results({
            "status": "error",
            "error": str(e),
            "error_type": "execution_error",
            "details": "Correlation stress test execution failed",
            "attempted_tickers": tickers
        })
