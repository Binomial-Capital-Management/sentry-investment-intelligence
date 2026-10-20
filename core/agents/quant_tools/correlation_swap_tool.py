"""
Correlation Swap Pricing Tool

Prices correlation swap derivatives using zero-mean correlation convention.
Agent has full control over pricing parameters, data sources, and output format.

NO HARDCODING: Uses dynamic field discovery for market data.
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Agent framework
from agents import function_tool

# Internal utilities
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


def _discover_price_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the price field in FMP data without hardcoding.

    Args:
        data: FMP API response dictionary

    Returns:
        Key name containing price data, or None if not found
    """
    if not data or not isinstance(data, dict):
        return None

    # Priority order for price-related keys (case-insensitive search)
    price_indicators = ['close', 'price', 'adj_close', 'adjusted']

    available_keys = list(data.keys())

    # Search for price-related keys
    for indicator in price_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:  # Ensure non-empty
                    return key

    return None


def _discover_date_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the date field in FMP data without hardcoding.

    Args:
        data: FMP API response dictionary

    Returns:
        Key name containing date data, or None if not found
    """
    if not data or not isinstance(data, dict):
        return None

    date_indicators = ['date', 'time', 'timestamp']
    available_keys = list(data.keys())

    for indicator in date_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key

    return None


async def _fetch_price_data(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_days: int
) -> pd.DataFrame:
    """
    Fetch historical price data with dynamic field discovery.

    Args:
        fmp_server: Connected FMP server instance
        ticker: Stock symbol
        lookback_days: Days of historical data

    Returns:
        DataFrame with date and price columns

    Raises:
        ValueError: If data cannot be fetched or parsed
    """
    # Calculate exact date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    result = await fmp_server.call_tool("get_historical_data", {
        "symbol": ticker,
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    })

    if not result or not hasattr(result, 'content'):
        raise ValueError(f"No data returned for {ticker}")

    data = safe_parse_json(result)

    if not data or not isinstance(data, dict):
        raise ValueError(f"Invalid data structure for {ticker}")

    # Dynamic field discovery
    date_field = _discover_date_field(data)
    price_field = _discover_price_field(data)

    if not date_field:
        raise ValueError(f"No date field found in data for {ticker}. Available keys: {list(data.keys())}")

    if not price_field:
        raise ValueError(f"No price field found in data for {ticker}. Available keys: {list(data.keys())}")

    dates = data[date_field]
    prices = data[price_field]

    if not dates or not prices:
        raise ValueError(f"Empty data for {ticker}")

    if len(dates) != len(prices):
        raise ValueError(f"Date/price length mismatch for {ticker}: {len(dates)} vs {len(prices)}")

    # Create DataFrame
    df = pd.DataFrame({
        'date': pd.to_datetime(dates),
        'price': prices
    })

    df = df.sort_values('date').reset_index(drop=True)
    df = df.dropna()

    return df


def _calculate_log_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate log returns from price series.

    Args:
        prices: Price time series

    Returns:
        Log return series
    """
    return np.log(prices / prices.shift(1)).dropna()


def _calculate_zero_mean_correlation(returns_x: pd.Series, returns_y: pd.Series) -> float:
    """
    Calculate zero-mean correlation using correlation swap convention.

    This is NOT the standard Pearson correlation. Correlation swaps use
    a zero-mean convention where correlation is defined as:
    ρ = Σ(R×S) / [√(ΣR²) × √(ΣS²)]

    Args:
        returns_x: Log returns for asset X
        returns_y: Log returns for asset Y

    Returns:
        Zero-mean correlation coefficient

    Raises:
        ValueError: If insufficient data or zero variance
    """
    if len(returns_x) != len(returns_y):
        raise ValueError(f"Return series length mismatch: {len(returns_x)} vs {len(returns_y)}")

    if len(returns_x) < 2:
        raise ValueError(f"Insufficient data for correlation: {len(returns_x)} points (need 2+)")

    # Align series (ensure matching indices)
    returns_x = returns_x.values
    returns_y = returns_y.values

    # Zero-mean correlation formula (correlation swap convention)
    numerator = np.sum(returns_x * returns_y)
    denominator = np.sqrt(np.sum(returns_x**2)) * np.sqrt(np.sum(returns_y**2))

    if denominator == 0:
        raise ValueError("Zero variance detected - cannot calculate correlation")

    correlation = numerator / denominator

    # Ensure result is in valid range [-1, 1]
    correlation = np.clip(correlation, -1.0, 1.0)

    return float(correlation)


async def _get_discount_factor(tenor_days: int, risk_free_rate: Optional[float] = None) -> float:
    """
    Calculate discount factor for present value calculation.

    Args:
        tenor_days: Time to maturity in days
        risk_free_rate: Annual risk-free rate (default: 0.04 = 4%)

    Returns:
        Discount factor
    """
    if risk_free_rate is None:
        # Fetch current risk-free rate from FRED
        try:
            from core.mcp_servers.EconomicDataServer import EconomicDataServer
            fred_server = EconomicDataServer()
            await fred_server.connect()

            try:
                # Use 3-month Treasury as risk-free proxy
                fred_result = await fred_server.get_series_data(series_id="DGS3MO")

                if fred_result and fred_result.get("data") and len(fred_result["data"]) > 0:
                    # FRED returns rates as percentages, convert to decimal
                    risk_free_rate = fred_result["data"][-1]["value"] / 100.0
                    logger.info(f"Fetched risk-free rate from FRED: {risk_free_rate:.4f}")
                else:
                    risk_free_rate = 0.04
                    logger.warning("FRED returned no data for risk-free rate, using fallback 4%")
            finally:
                await fred_server.cleanup()

        except Exception as e:
            logger.warning(f"Failed to fetch risk-free rate from FRED: {e}")
            risk_free_rate = 0.04

    # Convert days to years (252 trading days)
    time_to_maturity = tenor_days / 252.0

    # Continuous compounding: DF = exp(-r × T)
    discount_factor = np.exp(-risk_free_rate * time_to_maturity)

    return float(discount_factor)


def _build_monte_carlo_distribution_chart(
    payoff_distribution: List[float],
    expected_value: float,
    percentiles: Dict[str, float],
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build histogram of Monte Carlo payoff distribution for agent.
    
    Args:
        payoff_distribution: List of simulated PV values
        expected_value: Mean PV
        percentiles: Dict with p5, p25, p50, p75, p95
        asset_x, asset_y: Asset labels
    
    Returns:
        Chart dict with Plotly histogram or None if error
    """
    try:
        import plotly.graph_objects as go
        
        # Downsample if needed for ChartSpec size limit
        if len(payoff_distribution) > 1000:
            sampled = np.random.choice(payoff_distribution, size=1000, replace=False)
            payoff_distribution = sorted(sampled)
        
        # Create histogram
        fig = go.Figure()
        
        # Histogram bars
        fig.add_trace(go.Histogram(
            x=payoff_distribution,
            nbinsx=50,
            name='Payoff Distribution',
            marker=dict(
                color=payoff_distribution,
                colorscale=[[0, '#ef4444'], [0.5, '#94a3b8'], [1, '#10b981']],
                line=dict(color='white', width=0.5)
            ),
            hovertemplate='P&L: $%{x:,.0f}<br>Count: %{y}<extra></extra>'
        ))
        
        # Expected value line
        fig.add_vline(
            x=expected_value,
            line_dash="solid",
            line_color="#3b82f6",
            line_width=3,
            annotation_text=f"Expected: ${expected_value:,.0f}",
            annotation_position="top"
        )
        
        # Percentile lines
        fig.add_vline(x=percentiles['p5'], line_dash="dash", line_color="#ef4444", line_width=1.5, annotation_text="P5", annotation_position="bottom left")
        fig.add_vline(x=percentiles['p95'], line_dash="dash", line_color="#10b981", line_width=1.5, annotation_text="P95", annotation_position="bottom right")
        
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - Monte Carlo Payoff Distribution",
            xaxis_title="Swap Present Value ($)",
            yaxis_title="Frequency",
            showlegend=False,
            template="plotly_white",
            height=400,
            width=700
        )
        
        return {
            "id": f"mc_payoff_{asset_x.lower()}_{asset_y.lower()}",
            "title": f"{asset_x} vs {asset_y} Monte Carlo Distribution",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        logger.error(f"Error building MC distribution chart: {e}")
        return None


def _build_correlation_distribution_chart(
    correlation_distribution: List[float],
    mean_correlation: float,
    strike_correlation: float,
    historical_correlation: float,
    asset_x: str,
    asset_y: str
) -> Optional[Dict[str, Any]]:
    """
    Build histogram of simulated correlation values for agent.
    
    Args:
        correlation_distribution: List of simulated correlation values
        mean_correlation: Mean simulated correlation
        strike_correlation: Strike level
        historical_correlation: Historical correlation used for simulation
        asset_x, asset_y: Asset labels
    
    Returns:
        Chart dict with Plotly histogram or None if error
    """
    try:
        import plotly.graph_objects as go
        
        # Downsample if needed
        if len(correlation_distribution) > 1000:
            sampled = np.random.choice(correlation_distribution, size=1000, replace=False)
            correlation_distribution = sorted(sampled)
        
        fig = go.Figure()
        
        # Histogram
        fig.add_trace(go.Histogram(
            x=correlation_distribution,
            nbinsx=40,
            name='Correlation Distribution',
            marker=dict(color='#3b82f6', opacity=0.7),
            hovertemplate='Correlation: %{x:.4f}<br>Count: %{y}<extra></extra>'
        ))
        
        # Strike line
        fig.add_vline(
            x=strike_correlation,
            line_dash="dash",
            line_color="#ef4444",
            line_width=2,
            annotation_text=f"Strike: {strike_correlation:.3f}",
            annotation_position="top"
        )
        
        # Mean simulated line
        fig.add_vline(
            x=mean_correlation,
            line_dash="solid",
            line_color="#10b981",
            line_width=2,
            annotation_text=f"Mean: {mean_correlation:.3f}",
            annotation_position="top right"
        )
        
        # Historical line
        fig.add_vline(
            x=historical_correlation,
            line_dash="dot",
            line_color="#f59e0b",
            line_width=2,
            annotation_text=f"Historical: {historical_correlation:.3f}",
            annotation_position="bottom"
        )
        
        fig.update_layout(
            title=f"{asset_x} vs {asset_y} - Simulated Correlation Distribution",
            xaxis_title="Correlation",
            yaxis_title="Frequency",
            showlegend=False,
            template="plotly_white",
            height=400,
            width=700
        )
        
        fig.update_xaxes(range=[-1.05, 1.05])
        
        return {
            "id": f"corr_dist_{asset_x.lower()}_{asset_y.lower()}",
            "title": f"{asset_x} vs {asset_y} Correlation Distribution",
            "plotly": fig.to_dict()
        }
    
    except Exception as e:
        logger.error(f"Error building correlation distribution chart: {e}")
        return None


async def _calculate_rolling_correlation(
    returns_x: pd.Series,
    returns_y: pd.Series,
    dates: pd.Series,
    window: int = 20
) -> List[Tuple[str, float]]:
    """
    Calculate rolling zero-mean correlation time series.

    Args:
        returns_x: Log returns for asset X
        returns_y: Log returns for asset Y
        dates: Date index for returns
        window: Rolling window size in days

    Returns:
        List of (date, correlation) tuples
    """
    correlation_series = []

    # Reset indices to align
    returns_x = returns_x.reset_index(drop=True)
    returns_y = returns_y.reset_index(drop=True)
    dates = dates.reset_index(drop=True)

    for i in range(window, len(returns_x)):
        window_returns_x = returns_x.iloc[i-window:i]
        window_returns_y = returns_y.iloc[i-window:i]

        try:
            correlation = _calculate_zero_mean_correlation(window_returns_x, window_returns_y)
            correlation_series.append((str(dates.iloc[i]), correlation))
        except Exception as e:
            logger.warning(f"Failed to calculate rolling correlation at index {i}: {e}")
            continue

    return correlation_series


def _simulate_correlated_gbm_paths(
    S0_x: float,
    S0_y: float,
    mu_x: float,
    mu_y: float,
    sigma_x: float,
    sigma_y: float,
    correlation: float,
    days: int,
    num_simulations: int,
    seed: Optional[int] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Simulate correlated Geometric Brownian Motion paths for two assets.
    
    Args:
        S0_x: Initial price for asset X
        S0_y: Initial price for asset Y
        mu_x: Drift (annualized) for asset X
        mu_y: Drift (annualized) for asset Y
        sigma_x: Volatility (annualized) for asset X
        sigma_y: Volatility (annualized) for asset Y
        correlation: Historical correlation between assets
        days: Number of days to simulate
        num_simulations: Number of Monte Carlo paths
        seed: Random seed for reproducibility
    
    Returns:
        Tuple of (paths_x, paths_y) each of shape (num_simulations, days+1)
    """
    if seed is not None:
        np.random.seed(seed)
    
    dt = 1 / 252  # Daily time step
    
    # Initialize price arrays
    paths_x = np.zeros((num_simulations, days + 1))
    paths_y = np.zeros((num_simulations, days + 1))
    paths_x[:, 0] = S0_x
    paths_y[:, 0] = S0_y
    
    # Generate correlated random shocks using Cholesky decomposition
    for t in range(1, days + 1):
        # Independent random variables
        z1 = np.random.standard_normal(num_simulations)
        z2 = np.random.standard_normal(num_simulations)
        
        # Correlated shocks via Cholesky
        shock_x = z1
        shock_y = correlation * z1 + np.sqrt(1 - correlation**2) * z2
        
        # GBM updates
        paths_x[:, t] = paths_x[:, t-1] * np.exp(
            (mu_x - 0.5 * sigma_x**2) * dt + sigma_x * np.sqrt(dt) * shock_x
        )
        paths_y[:, t] = paths_y[:, t-1] * np.exp(
            (mu_y - 0.5 * sigma_y**2) * dt + sigma_y * np.sqrt(dt) * shock_y
        )
    
    return paths_x, paths_y


async def _monte_carlo_forward_pricing(
    asset_x: str,
    asset_y: str,
    current_price_x: float,
    current_price_y: float,
    mu_x: float,
    mu_y: float,
    sigma_x: float,
    sigma_y: float,
    historical_correlation: float,
    days_remaining: int,
    notional: float,
    strike_correlation: float,
    risk_free_rate: float,
    num_simulations: int = 10000,
    seed: Optional[int] = 42
) -> Dict[str, Any]:
    """
    Monte Carlo forward pricing for correlation swap before maturity.
    
    Args:
        asset_x, asset_y: Asset tickers
        current_price_x, current_price_y: Current spot prices
        mu_x, mu_y: Drift parameters (annualized)
        sigma_x, sigma_y: Volatilities (annualized)
        historical_correlation: Historical correlation (used for simulation)
        days_remaining: Days until maturity
        notional: Swap notional
        strike_correlation: Strike correlation
        risk_free_rate: Risk-free rate for discounting
        num_simulations: Number of MC paths
        seed: Random seed
    
    Returns:
        Dict with expected value, payoff distribution, percentiles, prob of profit
    """
    logger.info(f"Running Monte Carlo with {num_simulations} simulations for {days_remaining} days")
    
    # Simulate paths
    paths_x, paths_y = _simulate_correlated_gbm_paths(
        S0_x=current_price_x,
        S0_y=current_price_y,
        mu_x=mu_x,
        mu_y=mu_y,
        sigma_x=sigma_x,
        sigma_y=sigma_y,
        correlation=historical_correlation,
        days=days_remaining,
        num_simulations=num_simulations,
        seed=seed
    )
    
    # Calculate log returns for each path
    returns_x = np.log(paths_x[:, 1:] / paths_x[:, :-1])
    returns_y = np.log(paths_y[:, 1:] / paths_y[:, :-1])
    
    # Calculate realized correlation for each simulation
    realized_correlations = np.zeros(num_simulations)
    for i in range(num_simulations):
        try:
            # Zero-mean correlation
            numerator = np.sum(returns_x[i] * returns_y[i])
            denominator = np.sqrt(np.sum(returns_x[i]**2)) * np.sqrt(np.sum(returns_y[i]**2))
            if denominator > 1e-10:
                realized_correlations[i] = numerator / denominator
            else:
                realized_correlations[i] = 0.0
        except Exception as e:
            logger.warning(f"Error calculating correlation for simulation {i}: {e}")
            realized_correlations[i] = 0.0
    
    # Clip to valid range
    realized_correlations = np.clip(realized_correlations, -1.0, 1.0)
    
    # Calculate payoffs
    correlation_diffs = realized_correlations - strike_correlation
    payoffs = notional * correlation_diffs
    
    # Discount factor
    tenor_years = days_remaining / 252.0
    discount_factor = np.exp(-risk_free_rate * tenor_years)
    present_values = payoffs * discount_factor
    
    # Statistics
    expected_value = float(np.mean(present_values))
    std_dev = float(np.std(present_values))
    median_value = float(np.median(present_values))
    
    # Percentiles for confidence intervals
    percentiles = {
        "p5": float(np.percentile(present_values, 5)),
        "p25": float(np.percentile(present_values, 25)),
        "p50": float(np.percentile(present_values, 50)),
        "p75": float(np.percentile(present_values, 75)),
        "p95": float(np.percentile(present_values, 95))
    }
    
    # Probability of profit (for buyer)
    prob_profit = float(np.mean(present_values > 0))
    
    # Mean realized correlation
    mean_realized_corr = float(np.mean(realized_correlations))
    
    # Sample paths for visualization (to avoid overwhelming charts)
    num_sample_paths = min(50, num_simulations)
    sample_indices = np.random.choice(num_simulations, size=num_sample_paths, replace=False)
    sample_paths_x = paths_x[sample_indices, :].tolist()
    sample_paths_y = paths_y[sample_indices, :].tolist()
    
    return {
        "expected_value": expected_value,
        "std_dev": std_dev,
        "median_value": median_value,
        "percentiles": percentiles,
        "prob_profit": prob_profit,
        "mean_realized_correlation": mean_realized_corr,
        "payoff_distribution": present_values.tolist(),  # Full distribution for charting
        "correlation_distribution": realized_correlations.tolist(),
        "num_simulations": num_simulations,
        "days_simulated": days_remaining,
        "sample_paths_x": sample_paths_x,  # Sample paths for visualization
        "sample_paths_y": sample_paths_y,
        "current_price_x": current_price_x,
        "current_price_y": current_price_y
    }


async def price_correlation_swap_internal(
    asset_x: str,
    asset_y: str,
    notional: float,
    strike_correlation: float,
    tenor: int,
    pricing_mode: str = "realized",
    days_remaining: Optional[int] = None,
    num_simulations: int = 10000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    risk_free_rate: Optional[float] = None,
    include_rolling_corr: bool = True,
    rolling_window: int = 20
) -> Dict[str, Any]:
    """
    Internal version for Canvas integration.
    Returns raw dictionary without JSON serialization.
    
    Price correlation swap derivative using zero-mean correlation convention.

    **What This Tool Does:**
    - Prices correlation swaps (derivatives betting on realized correlation)
    - Uses zero-mean correlation (correlation swap market convention)
    - Fetches market data automatically from FMP
    - Calculates payoff: Notional × (Realized_Corr - Strike_Corr)
    - Discounts to present value using risk-free rate

    **How to Use:**
    Just call with asset tickers and swap parameters. Data fetching is automatic.
    Example: price_correlation_swap(asset_x='SPY', asset_y='QQQ', notional=1000000,
                                     strike_correlation=0.75, tenor=252)

    **Understanding Results:**
    - Positive swap_value: Realized correlation > Strike (buyer profits)
    - Negative swap_value: Realized correlation < Strike (seller profits)
    - correlation_series: Time series showing correlation evolution

    **Correlation Swap Convention:**
    Uses zero-mean correlation: ρ = Σ(R×S) / [√(ΣR²) × √(ΣS²)]
    This is NOT standard Pearson correlation (which subtracts means first).

    Args:
        asset_x: First underlying asset ticker
        asset_y: Second underlying asset ticker
        notional: Swap notional amount ($)
        strike_correlation: Strike correlation level (e.g., 0.5 for 50% correlation)
        tenor: Days to maturity
        realized_corr: Optional pre-calculated correlation series (if None, will fetch data)
        start_date: Optional start date for historical data (YYYY-MM-DD)
        end_date: Optional end date for historical data (YYYY-MM-DD)
        risk_free_rate: Annual risk-free rate for discounting (default: 0.04 = 4%)
        include_rolling_corr: Include rolling correlation time series (default: True)
        rolling_window: Window size for rolling correlation (default: 20 days)

    Returns:
        Dict containing:
        {
            "swap_value": float - Present value of swap ($)
            "payoff_at_maturity": float - Undiscounted payoff ($)
            "realized_correlation": float - Average realized correlation
            "strike_correlation": float - Contract strike
            "correlation_difference": float - Realized - Strike
            "notional": float - Notional amount ($)
            "tenor_days": int - Days to maturity
            "discount_factor": float - PV discount factor
            "risk_free_rate": float - Rate used for discounting
            "correlation_series": List[Tuple[str, float]] - Time series of correlations
            "summary": str - Human-readable summary
            "correlation_method": str - "zero_mean" (swap convention)
        }

        On error, returns:
        {
            "error": str - Error message
            "details": str - Additional details
        }

    Examples:
        # Basic correlation swap pricing
        result = await price_correlation_swap(
            asset_x='SPY',
            asset_y='QQQ',
            notional=1000000,
            strike_correlation=0.75,
            tenor=63  # ~3 months
        )
        print(f"Swap Value: ${result['swap_value']:,.2f}")
        print(f"Realized Correlation: {result['realized_correlation']:.4f}")

        # Custom date range and risk-free rate
        result = await price_correlation_swap(
            asset_x='GLD',
            asset_y='GDX',
            notional=500000,
            strike_correlation=0.60,
            tenor=126,  # ~6 months
            start_date='2023-01-01',
            end_date='2024-01-01',
            risk_free_rate=0.05  # 5% risk-free rate
        )
    """
    try:
        # Input validation
        if notional <= 0:
            return {
                "error": "Invalid notional",
                "details": f"Notional must be positive: {notional}"
            }

        if not -1 <= strike_correlation <= 1:
            return {
                "error": "Invalid strike correlation",
                "details": f"Strike must be between -1 and 1: {strike_correlation}"
            }

        if tenor <= 0:
            return {
                "error": "Invalid tenor",
                "details": f"Tenor must be positive: {tenor} days"
            }
        
        # Validate pricing mode
        if pricing_mode not in ["realized", "forward"]:
            return {
                "error": "Invalid pricing mode",
                "details": f"pricing_mode must be 'realized' or 'forward', got: {pricing_mode}"
            }
        
        # For forward pricing, validate days_remaining
        if pricing_mode == "forward":
            if days_remaining is None or days_remaining <= 0:
                return {
                    "error": "⚠️ Invalid Days Remaining",
                    "details": f"For forward pricing (Monte Carlo), days_remaining must be a positive number. Got: {days_remaining}. Please enter a value between 1 and {tenor} days."
                }
            if days_remaining > tenor:
                return {
                    "error": "⚠️ Days Remaining Exceeds Tenor",
                    "details": f"days_remaining ({days_remaining} days) cannot exceed tenor ({tenor} days). The swap can't have more days remaining than its original maturity. Please reduce days_remaining to {tenor} or less."
                }

        # Fetch data and calculate correlation
        # Connect to FMP server
        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Determine lookback period
            if start_date and end_date:
                # Calculate days between dates
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                lookback_days = (end - start).days
            else:
                # Use tenor + buffer for rolling calculation
                lookback_days = tenor + rolling_window + 30  # Extra buffer for holidays

            # Fetch price data for both assets
            logger.info(f"Fetching {lookback_days} days of data for {asset_x} and {asset_y}")

            df_x = await _fetch_price_data(fmp_server, asset_x, lookback_days)
            df_y = await _fetch_price_data(fmp_server, asset_y, lookback_days)

            # Merge on date
            merged = pd.merge(df_x, df_y, on='date', suffixes=('_x', '_y'))

            if len(merged) < 2:
                return {
                    "error": "Insufficient overlapping data",
                    "details": f"Only {len(merged)} common trading days found"
                }

            # Calculate log returns
            returns_x = _calculate_log_returns(merged['price_x'])
            returns_y = _calculate_log_returns(merged['price_y'])

            # Align returns (drop NaN from log return calculation)
            merged_returns = pd.DataFrame({
                'date': merged['date'].iloc[1:].reset_index(drop=True),
                'returns_x': returns_x.reset_index(drop=True),
                'returns_y': returns_y.reset_index(drop=True)
            })

            # Calculate historical parameters for Monte Carlo (if forward pricing)
            if pricing_mode == "forward":
                # Current prices (latest)
                current_price_x = float(merged['price_x'].iloc[-1])
                current_price_y = float(merged['price_y'].iloc[-1])
                
                # Historical drift and volatility (annualized)
                mu_x = float(returns_x.mean() * 252)
                mu_y = float(returns_y.mean() * 252)
                sigma_x = float(returns_x.std() * np.sqrt(252))
                sigma_y = float(returns_y.std() * np.sqrt(252))
                
                # Historical correlation
                historical_correlation = _calculate_zero_mean_correlation(
                    merged_returns['returns_x'],
                    merged_returns['returns_y']
                )
                
                logger.info(f"Historical params: μ_x={mu_x:.4f}, σ_x={sigma_x:.4f}, μ_y={mu_y:.4f}, σ_y={sigma_y:.4f}, ρ={historical_correlation:.4f}")
            
            # Calculate realized correlation (zero-mean convention)
            avg_realized_correlation = _calculate_zero_mean_correlation(
                merged_returns['returns_x'],
                merged_returns['returns_y']
            )

            # Calculate rolling correlation time series
            if include_rolling_corr and len(merged_returns) >= rolling_window:
                correlation_series = await _calculate_rolling_correlation(
                    merged_returns['returns_x'],
                    merged_returns['returns_y'],
                    merged_returns['date'],
                    window=rolling_window
                )
            else:
                correlation_series = []

        except Exception as e:
            logger.error(f"Data fetching failed: {e}", exc_info=True)
            return {
                "error": "Failed to fetch market data",
                "details": str(e),
                "asset_x": asset_x,
                "asset_y": asset_y
            }
        finally:
            await fmp_server.cleanup()

        # Get risk-free rate if not provided
        if risk_free_rate is None:
            discount_factor = await _get_discount_factor(tenor, None)
            # Extract rate from discount factor (approximate)
            risk_free_rate = -np.log(discount_factor) / (tenor / 252.0) if discount_factor > 0 else 0.04
        
        # BRANCH: Forward pricing (Monte Carlo)
        if pricing_mode == "forward":
            logger.info(f"Forward pricing mode: simulating {days_remaining} days with {num_simulations} paths")
            
            mc_result = await _monte_carlo_forward_pricing(
                asset_x=asset_x,
                asset_y=asset_y,
                current_price_x=current_price_x,
                current_price_y=current_price_y,
                mu_x=mu_x,
                mu_y=mu_y,
                sigma_x=sigma_x,
                sigma_y=sigma_y,
                historical_correlation=historical_correlation,
                days_remaining=days_remaining,
                notional=notional,
                strike_correlation=strike_correlation,
                risk_free_rate=risk_free_rate,
                num_simulations=num_simulations
            )
            
            # Build summary for forward pricing
            expected_value = mc_result["expected_value"]
            prob_profit = mc_result["prob_profit"]
            mean_realized_corr = mc_result["mean_realized_correlation"]
            
            summary = (
                f"**Monte Carlo Forward Pricing: {asset_x}/{asset_y} Correlation Swap**\n\n"
                f"**Expected Valuation** (with {days_remaining} days remaining):\n"
                f"- **Expected PV**: ${expected_value:,.2f}\n"
                f"- **Std Dev**: ${mc_result['std_dev']:,.2f}\n"
                f"- **Median**: ${mc_result['median_value']:,.2f}\n"
                f"- **Probability of Profit**: {prob_profit:.1%}\n\n"
                f"**Confidence Intervals:**\n"
                f"- **95% Range**: ${mc_result['percentiles']['p5']:,.0f} to ${mc_result['percentiles']['p95']:,.0f}\n"
                f"- **50% Range** (IQR): ${mc_result['percentiles']['p25']:,.0f} to ${mc_result['percentiles']['p75']:,.0f}\n\n"
                f"**Expected Correlation:**\n"
                f"- **Mean Simulated**: {mean_realized_corr:.4f}\n"
                f"- **Strike**: {strike_correlation:.4f}\n"
                f"- **Historical**: {historical_correlation:.4f}\n\n"
                f"**Simulation Parameters:**\n"
                f"- **Simulations**: {num_simulations:,} paths\n"
                f"- **Days Forward**: {days_remaining} trading days\n"
                f"- **Notional**: ${notional:,.0f}\n"
                f"- **Risk-Free Rate**: {risk_free_rate:.2%}\n\n"
                f"**Interpretation:**\n"
                f"Forward pricing uses Monte Carlo simulation to estimate the swap's value before maturity. "
                f"The expected PV of ${expected_value:,.0f} represents the probability-weighted average across "
                f"{num_simulations:,} scenarios. With a {prob_profit:.1%} chance of profit, the position "
                f"{'favors the buyer' if prob_profit > 0.5 else 'favors the seller'}."
            )
            
            # Build Monte Carlo charts for agent
            charts = []
            
            # Chart 1: Payoff distribution histogram
            payoff_chart = _build_monte_carlo_distribution_chart(
                payoff_distribution=mc_result["payoff_distribution"],
                expected_value=expected_value,
                percentiles=mc_result["percentiles"],
                asset_x=asset_x,
                asset_y=asset_y
            )
            if payoff_chart:
                charts.append(payoff_chart)
            
            # Chart 2: Correlation distribution histogram
            corr_chart = _build_correlation_distribution_chart(
                correlation_distribution=mc_result["correlation_distribution"],
                mean_correlation=mean_realized_corr,
                strike_correlation=strike_correlation,
                historical_correlation=historical_correlation,
                asset_x=asset_x,
                asset_y=asset_y
            )
            if corr_chart:
                charts.append(corr_chart)
            
            return {
                "status": "success",
                "pricing_mode": "forward",
                "swap_value": expected_value,
                "expected_pv": expected_value,  # For Canvas executor
                "expected_value": expected_value,  # For backward compat
                "pv_std_dev": mc_result["std_dev"],  # For Canvas executor
                "std_dev": mc_result["std_dev"],  # For backward compat
                "median_value": mc_result["median_value"],
                "prob_profit": mc_result["prob_profit"],  # For Canvas executor
                "percentiles": mc_result["percentiles"],  # For Canvas executor
                "payoff_distribution": mc_result["payoff_distribution"],  # For Canvas executor
                "correlation_distribution": mc_result["correlation_distribution"],  # For Canvas executor
                "mean_simulated_correlation": mc_result["mean_realized_correlation"],  # For Canvas executor
                "sample_paths_x": mc_result["sample_paths_x"],  # For Canvas executor
                "sample_paths_y": mc_result["sample_paths_y"],  # For Canvas executor
                "current_price_x": mc_result["current_price_x"],  # For Canvas executor
                "current_price_y": mc_result["current_price_y"],  # For Canvas executor
                "payoff_at_maturity": expected_value,  # For forward pricing, this is the same as expected PV
                "realized_correlation": mean_realized_corr,
                "historical_correlation": historical_correlation,
                "strike_correlation": float(strike_correlation),
                "correlation_difference": mean_realized_corr - strike_correlation,
                "notional": float(notional),
                "tenor_days": int(tenor),
                "days_remaining": days_remaining,
                "discount_factor": np.exp(-risk_free_rate * (days_remaining / 252.0)),
                "risk_free_rate": float(risk_free_rate),
                "correlation_series": correlation_series,
                "correlation_method": "zero_mean",
                "summary": summary,
                "asset_x": asset_x,
                "asset_y": asset_y,
                "monte_carlo": mc_result,  # Full MC results (backward compat)
                "num_simulations": num_simulations,
                "charts": wrap_plotly_charts(charts, default_type="correlation_swap")
            }
        
        # BRANCH: Realized pricing (historical)
        else:
            # Calculate swap payoff and value
            correlation_difference = avg_realized_correlation - strike_correlation
            payoff_at_maturity = notional * correlation_difference

            # Get discount factor
            discount_factor = await _get_discount_factor(tenor, risk_free_rate)
            swap_value = payoff_at_maturity * discount_factor

            # Build summary
            direction = "profitable" if swap_value > 0 else "unprofitable"
            summary = (
                f"Correlation swap on {asset_x}/{asset_y} with strike {strike_correlation:.4f} "
                f"has realized correlation of {avg_realized_correlation:.4f}. "
                f"Payoff at maturity: ${payoff_at_maturity:,.2f}. "
                f"Present value (discounted at {risk_free_rate:.2%}): ${swap_value:,.2f}. "
                f"Position is {direction} for the buyer."
            )

            return {
                "status": "success",
                "pricing_mode": "realized",
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
                "summary": summary,
                "asset_x": asset_x,
                "asset_y": asset_y,
                # Removed: data.returns_x/returns_y/dates (large arrays, embedded in charts)
                "data_summary": {
                    "n_observations": len(returns_x) if hasattr(returns_x, '__len__') else 0,
                    "date_range": {
                        "start": merged_returns['date'].iloc[0].strftime('%Y-%m-%d') if len(merged_returns) > 0 else None,
                        "end": merged_returns['date'].iloc[-1].strftime('%Y-%m-%d') if len(merged_returns) > 0 else None
                    }
                }
            }

    except Exception as e:
        logger.error(f"Correlation swap pricing failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "Correlation swap pricing failed",
            "details": str(e)
        }


@function_tool
async def price_correlation_swap(
    asset_x: str,
    asset_y: str,
    notional: float,
    strike_correlation: float,
    tenor: int,
    pricing_mode: str = "realized",
    days_remaining: Optional[int] = None,
    num_simulations: int = 10000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    risk_free_rate: Optional[float] = None,
    include_rolling_corr: bool = True,
    rolling_window: int = 20
) -> str:
    """
    Price correlation swap derivative using zero-mean correlation convention.
    
    Supports both realized (historical) and forward (Monte Carlo) pricing modes.
    
    Agent-facing wrapper that returns JSON string.
    See price_correlation_swap_internal for full documentation.
    """
    result = await price_correlation_swap_internal(
        asset_x=asset_x,
        asset_y=asset_y,
        notional=notional,
        strike_correlation=strike_correlation,
        tenor=tenor,
        pricing_mode=pricing_mode,
        days_remaining=days_remaining,
        num_simulations=num_simulations,
        start_date=start_date,
        end_date=end_date,
        risk_free_rate=risk_free_rate,
        include_rolling_corr=include_rolling_corr,
        rolling_window=rolling_window
    )
    return jsonify_results(result)
