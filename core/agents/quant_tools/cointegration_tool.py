"""
Cointegration Analysis Tool for Pairs Trading

Identifies statistically cointegrated pairs using Engle-Granger and Johansen methods.
Agent has full control over which pairs to test, which charts to generate, and output format.

NO HARDCODING: Uses dynamic field discovery for FMP data structure.
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging

# Statistical libraries
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from sklearn.linear_model import LinearRegression

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
    lookback_period: int
) -> pd.DataFrame:
    """
    Fetch historical price data with dynamic field discovery.

    Args:
        fmp_server: Connected FMP server instance
        ticker: Stock symbol
        lookback_period: Days of historical data

    Returns:
        DataFrame with date and price columns

    Raises:
        ValueError: If data cannot be fetched or parsed
    """
    from datetime import datetime, timedelta

    # Calculate exact date range (FMP doesn't recognize "252d" format)
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


def _calculate_hedge_ratio(x: pd.Series, y: pd.Series, method: str = 'ols') -> float:
    """
    Calculate optimal hedge ratio.

    Args:
        x: Price series for stock X
        y: Price series for stock Y
        method: 'ols' for OLS regression or 'min_variance' for minimum variance

    Returns:
        Beta coefficient (hedge ratio)
    """
    if method == 'ols':
        X = x.values.reshape(-1, 1)
        Y = y.values

        model = LinearRegression()
        model.fit(X, Y)

        return model.coef_[0]

    elif method == 'min_variance':
        # Minimum variance hedge ratio: Cov(X,Y) / Var(X)
        covariance = np.cov(x, y)[0, 1]
        variance_x = np.var(x)
        return covariance / variance_x if variance_x != 0 else 0.0

    else:
        raise ValueError(f"Unknown hedge calculation method: {method}")


def _calculate_spread_half_life(spread: np.ndarray) -> float:
    """
    Calculate mean reversion half-life of spread using AR(1) model.

    Args:
        spread: Spread time series

    Returns:
        Half-life in days (time units of input data)
    """
    try:
        # Ornstein-Uhlenbeck (OU) mean reversion model
        # Regress Δspread(t) on spread(t-1): Δspread = α + β*spread(t-1) + ε
        # Where β = -λ (OU mean reversion rate)
        spread_lag = spread[:-1]
        spread_diff = spread[1:] - spread_lag

        # OLS regression
        X = spread_lag.reshape(-1, 1)
        y = spread_diff

        model = LinearRegression()
        model.fit(X, y)

        beta = model.coef_[0]

        # OU half-life: t_1/2 = log(2) / λ = log(2) / (-β)
        if beta >= 0:
            return np.inf  # No mean reversion (β should be negative for OU)

        lambda_param = -beta  # OU mean reversion rate
        half_life = np.log(2) / lambda_param

        return max(0, half_life)

    except Exception:
        return np.inf


def _calculate_hurst_exponent(spread: np.ndarray, max_lag: int = 20) -> float:
    """
    Calculate Hurst exponent to test mean reversion vs trending behavior.

    H < 0.5: Mean reverting
    H = 0.5: Random walk
    H > 0.5: Trending

    Args:
        spread: Spread time series
        max_lag: Maximum lag for R/S analysis

    Returns:
        Hurst exponent
    """
    try:
        # Need minimum data points for meaningful Hurst calculation
        if len(spread) < 10:
            logger.warning(f"Insufficient data for Hurst exponent: {len(spread)} points (need 10+)")
            return 0.5  # Default to random walk assumption

        lags = range(2, min(max_lag, len(spread) // 2))
        tau = []

        for lag in lags:
            # Divide spread into lag-sized chunks
            n_chunks = len(spread) // lag
            chunks = [spread[i*lag:(i+1)*lag] for i in range(n_chunks)]

            rs_values = []
            for chunk in chunks:
                if len(chunk) < 2:
                    continue

                # Mean-adjusted series
                mean_chunk = chunk - np.mean(chunk)

                # Cumulative sum
                cum_sum = np.cumsum(mean_chunk)

                # Range
                R = np.max(cum_sum) - np.min(cum_sum)

                # Standard deviation
                S = np.std(chunk)

                if S > 0:
                    rs_values.append(R / S)

            if rs_values:
                tau.append(np.mean(rs_values))
            else:
                tau.append(np.nan)

        # Remove NaN values
        valid_tau = [(np.log(lags[i]), np.log(tau[i]))
                     for i in range(len(tau)) if not np.isnan(tau[i])]

        if len(valid_tau) < 3:
            return 0.5  # Default to random walk

        log_lags = np.array([x[0] for x in valid_tau])
        log_tau = np.array([x[1] for x in valid_tau])

        # Linear regression
        X = log_lags.reshape(-1, 1)
        model = LinearRegression()
        model.fit(X, log_tau)

        hurst = model.coef_[0]
        return max(0, min(1, hurst))

    except Exception:
        return 0.5  # Default to random walk


def _calculate_spread_sharpe(spread: np.ndarray, annual_factor: int = 252) -> float:
    """
    Calculate annualized Sharpe-like ratio of spread log returns.

    NOTE: This measures spread volatility characteristics, NOT actual strategy returns.
    For actual trading Sharpe, use backtest_strategy=True and check backtest results.

    Args:
        spread: Spread time series
        annual_factor: Annualization factor (252 for daily data)

    Returns:
        Annualized spread return/volatility ratio (mean reversion indicator)
    """
    try:
        # Calculate simple returns (NOT log returns)
        # Pairs trading spread = Y - β*X can be negative, so log(spread) breaks
        # Use simple returns: ΔS / |S| where S is the spread
        spread_changes = np.diff(spread)
        spread_abs = np.abs(spread[:-1])

        # Avoid division by near-zero spread values
        spread_abs[spread_abs < 1e-8] = 1e-8

        # Simple returns = price changes / absolute price level
        spread_returns = spread_changes / spread_abs
        spread_returns = spread_returns[np.isfinite(spread_returns)]

        if len(spread_returns) < 2:
            return 0.0

        mean_return = np.mean(spread_returns)
        std_return = np.std(spread_returns)

        if std_return == 0:
            return 0.0

        # Return ratio (NOT actual strategy Sharpe - spread characteristic only)
        ratio = (mean_return / std_return) * np.sqrt(annual_factor)
        return ratio

    except Exception:
        return 0.0


def _test_rolling_stability(
    data: Dict[str, pd.DataFrame],
    ticker_a: str,
    ticker_b: str,
    window: int,
    significance_level: float
) -> Dict[str, Any]:
    """
    Test cointegration stability in rolling windows.

    Args:
        data: Dictionary mapping tickers to price DataFrames
        ticker_a: First stock symbol
        ticker_b: Second stock symbol
        window: Rolling window size in days
        significance_level: P-value threshold

    Returns:
        Dictionary with stability metrics
    """
    try:
        df_a = data[ticker_a]
        df_b = data[ticker_b]

        merged = pd.merge(df_a, df_b, on='date', suffixes=('_a', '_b'))

        if len(merged) < window * 2:
            return {"stable": False, "reason": "Insufficient data for rolling analysis"}

        rolling_pvalues = []
        dates = []

        for i in range(len(merged) - window):
            window_data = merged.iloc[i:i+window]

            try:
                _, p_value, _ = coint(
                    window_data['price_a'].values,
                    window_data['price_b'].values
                )
                rolling_pvalues.append(p_value)
                dates.append(window_data['date'].iloc[-1])
            except Exception:
                continue

        if not rolling_pvalues:
            return {"stable": False, "reason": "Rolling analysis failed"}

        pvalues_array = np.array(rolling_pvalues)
        significant_windows = np.sum(pvalues_array < significance_level)
        stability_rate = significant_windows / len(rolling_pvalues)

        # Recent stability (last 25% of windows)
        recent_count = max(1, len(rolling_pvalues) // 4)
        recent_pvalues = pvalues_array[-recent_count:]
        recent_stability = np.mean(recent_pvalues < significance_level)

        return {
            "stable": stability_rate > 0.7,
            "overall_stability_rate": float(stability_rate),
            "recent_stability_rate": float(recent_stability),
            "total_windows": len(rolling_pvalues),
            "significant_windows": int(significant_windows),
            "mean_pvalue": float(np.mean(pvalues_array)),
            "std_pvalue": float(np.std(pvalues_array)),
            "rolling_pvalues": pvalues_array.tolist()[-20:],  # Last 20 values
            "dates": [str(d) for d in dates[-20:]]
        }

    except Exception as e:
        return {"stable": False, "reason": str(e)}


def _backtest_pairs_strategy(
    data: Dict[str, pd.DataFrame],
    ticker_a: str,
    ticker_b: str,
    hedge_ratio: float,
    entry_sigma: float = 2.0,
    exit_sigma: float = 0.0,
    stop_loss_sigma: float = 3.0,
    transaction_cost_bps: int = 5,
    capital_base: float = 100000,
    allow_short: bool = True,
    min_holding_period: int = 1,
    max_holding_period: Optional[int] = None
) -> Dict[str, Any]:
    """
    Backtest pairs trading strategy with realistic execution, costs, and risk management.

    **Institutional-Grade Backtesting Features:**
    - Realistic transaction costs (per-leg basis points)
    - Stop-loss and mean reversion exit logic
    - Position holding constraints (min/max days)
    - Optional short-selling restrictions
    - P&L time series tracking for visualization
    - Annualized Sharpe ratio calculation
    - Trade-by-trade performance attribution

    **Strategy Logic:**
    1. Calculate spread: Spread = Price_B - (hedge_ratio × Price_A)
    2. Normalize to z-score: z = (Spread - Mean) / StdDev
    3. Entry signals:
       - LONG spread when z < -entry_sigma (spread is cheap)
       - SHORT spread when z > +entry_sigma (spread is expensive)
    4. Exit signals (whichever comes first):
       - Mean reversion: |z| <= exit_sigma
       - Stop loss: |z| > stop_loss_sigma
       - Max holding period exceeded
       - End of data

    Args:
        data: Dictionary mapping tickers to price DataFrames (with 'date' and 'price' columns)
        ticker_a: First asset ticker (X in the pair)
        ticker_b: Second asset ticker (Y in the pair)
        hedge_ratio: Optimal hedge ratio (β from OLS regression: Y = α + β×X)

        **Entry/Exit Rules:**
        entry_sigma: Z-score threshold for entry (default: 2.0)
                    - Enter LONG spread when z < -entry_sigma
                    - Enter SHORT spread when z > +entry_sigma
        exit_sigma: Z-score threshold for mean reversion exit (default: 0.0)
                   - Exit when |z| <= exit_sigma (position converges to mean)
        stop_loss_sigma: Z-score threshold for stop loss (default: 3.0)
                        - Exit when |z| > stop_loss_sigma (position moves against us)

        **Cost Model:**
        transaction_cost_bps: Transaction costs in basis points PER LEG (default: 5 bps)
                             - Each trade has 2 legs (buy one asset, sell the other)
                             - Entry costs: 2 legs, Exit costs: 2 legs
                             - Example: 5 bps = 0.05% per leg = 0.20% round-trip

        **Position Sizing:**
        capital_base: Notional capital for position sizing (default: $100,000)
                     - Used for calculating percentage returns
                     - P&L reported in absolute dollars

        **Trading Constraints:**
        allow_short: Allow short spread positions (default: True)
                    - If False, only enter when z < -entry_sigma (long spread only)
                    - If True, allow both long and short spread positions
        min_holding_period: Minimum days to hold position (default: 1)
                           - Prevents excessive churning from noise
                           - Exit signals ignored until min period met
        max_holding_period: Maximum days to hold position (default: None = unlimited)
                           - Force exit after N days to prevent stale positions
                           - None = no maximum holding constraint

    Returns:
        Dictionary with comprehensive backtest results:
        {
            "trades": int - Total number of trades executed
            "total_pnl_net": float - Net P&L after all costs ($)
            "win_rate": float - Percentage of winning trades (0.0-1.0)
            "avg_win": float - Average winning trade P&L ($)
            "avg_loss": float - Average losing trade P&L ($)
            "profit_factor": float - Gross wins / Gross losses
            "max_drawdown": float - Maximum peak-to-trough drawdown ($)
            "sharpe_ratio": float - Annualized Sharpe ratio
            "avg_holding_days": float - Average position holding period
            "total_transaction_costs": float - Sum of all transaction costs ($)
            "pnl_series": List[Tuple[str, float]] - Time series of cumulative P&L
                         [(date, cumulative_pnl), ...]
            "trade_details": List[Dict] - Last 10 trades with entry/exit details
        }

        If no trades executed, returns:
        {
            "trades": 0,
            "no_trades_reason": str - Explanation (e.g., "No entry signals")
        }

        On error, returns:
        {
            "trades": 0,
            "error": str - Error message
        }

    Example:
        >>> data = {
        ...     'GLD': pd.DataFrame({'date': [...], 'price': [...]}),
        ...     'GDX': pd.DataFrame({'date': [...], 'price': [...]})
        ... }
        >>> results = _backtest_pairs_strategy(
        ...     data, 'GLD', 'GDX', hedge_ratio=1.47,
        ...     entry_sigma=2.0, exit_sigma=0.5, stop_loss_sigma=3.0,
        ...     capital_base=100000, transaction_cost_bps=5
        ... )
        >>> print(f"Sharpe: {results['sharpe_ratio']:.2f}")
        >>> print(f"Win Rate: {results['win_rate']:.1%}")
    """
    try:
        df_a = data[ticker_a]
        df_b = data[ticker_b]

        merged = pd.merge(df_a, df_b, on='date', suffixes=('_a', '_b'))

        # Calculate spread
        spread = merged['price_b'].values - hedge_ratio * merged['price_a'].values

        # Z-score
        mean_spread = np.mean(spread)
        std_spread = np.std(spread)

        if std_spread == 0:
            return {"trades": 0, "error": "Zero spread volatility"}

        zscore = (spread - mean_spread) / std_spread

        # Simulate trades
        position = 0  # 0: flat, 1: long spread, -1: short spread
        trades = []
        entry_price = 0
        entry_idx = 0
        cumulative_pnl = 0.0
        pnl_series = []  # Track P&L over time: [(date, cumulative_pnl), ...]

        for i in range(len(zscore)):
            current_z = zscore[i]

            # Entry signals
            if position == 0:
                # SHORT spread signal (z > entry_sigma)
                if current_z > entry_sigma and allow_short:
                    # Short spread: sell B, buy A
                    position = -1
                    entry_price = spread[i]
                    entry_idx = i
                # LONG spread signal (z < -entry_sigma)
                elif current_z < -entry_sigma:
                    # Long spread: buy B, sell A
                    position = 1
                    entry_price = spread[i]
                    entry_idx = i

            # Exit signals
            elif position != 0:
                exit_trade = False
                exit_reason = ""
                holding_days = i - entry_idx

                # Check minimum holding period first
                if holding_days < min_holding_period:
                    # Not allowed to exit yet
                    continue

                # Mean reversion exit
                if abs(current_z) <= exit_sigma:
                    exit_trade = True
                    exit_reason = "mean_reversion"

                # Stop loss
                elif abs(current_z) > stop_loss_sigma:
                    exit_trade = True
                    exit_reason = "stop_loss"

                # Max holding period exceeded
                elif max_holding_period is not None and holding_days >= max_holding_period:
                    exit_trade = True
                    exit_reason = "max_holding_period"

                # Force exit on last day
                elif i == len(zscore) - 1:
                    exit_trade = True
                    exit_reason = "end_of_data"

                if exit_trade:
                    exit_price = spread[i]
                    pnl = position * (entry_price - exit_price)

                    # Apply transaction costs (2 legs per trade, weighted by hedge ratio)
                    # Pairs trade: 1 share of B ± hedge_ratio shares of A
                    # Entry cost: transaction_cost_bps * (|price_b| + hedge_ratio * |price_a|)
                    # Exit cost: transaction_cost_bps * (|price_b| + hedge_ratio * |price_a|)
                    cost = (transaction_cost_bps / 10000) * (
                        abs(merged['price_b'].iloc[entry_idx]) +
                        hedge_ratio * abs(merged['price_a'].iloc[entry_idx]) +
                        abs(merged['price_b'].iloc[i]) +
                        hedge_ratio * abs(merged['price_a'].iloc[i])
                    )

                    pnl_after_costs = pnl - cost

                    trades.append({
                        "entry_date": str(merged['date'].iloc[entry_idx]),
                        "exit_date": str(merged['date'].iloc[i]),
                        "entry_zscore": float(zscore[entry_idx]),
                        "exit_zscore": float(current_z),
                        "holding_days": i - entry_idx,
                        "position": "long_spread" if position == 1 else "short_spread",
                        "pnl_gross": float(pnl),
                        "transaction_costs": float(cost),
                        "pnl_net": float(pnl_after_costs),
                        "exit_reason": exit_reason
                    })

                    # Update cumulative P&L and track
                    cumulative_pnl += pnl_after_costs
                    pnl_series.append((str(merged['date'].iloc[i]), float(cumulative_pnl)))

                    position = 0

        if not trades:
            return {
                "trades": 0,
                "no_trades_reason": f"No entry signals (max zscore: {np.max(np.abs(zscore)):.2f})"
            }

        # Calculate statistics (both dollar P&L and % returns)
        pnls = [t['pnl_net'] for t in trades]
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p <= 0]

        total_pnl = sum(pnls)
        win_rate = len(winning_trades) / len(trades)
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if losing_trades and sum(losing_trades) != 0 else 0

        # Normalize by capital_base to get % returns
        # This allows for proper risk-adjusted performance metrics
        pnl_returns = [p / capital_base for p in pnls]
        total_return = total_pnl / capital_base

        # Drawdown (both in dollars and %)
        cumulative_pnl_array = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative_pnl_array)
        drawdown = running_max - cumulative_pnl_array
        max_drawdown = np.max(drawdown)
        max_drawdown_pct = max_drawdown / capital_base

        # Sharpe ratio calculation (annualized, using % returns)
        sharpe_ratio = 0.0
        if len(pnl_returns) > 1:
            mean_return = np.mean(pnl_returns)
            std_return = np.std(pnl_returns, ddof=1)  # Sample standard deviation

            if std_return > 1e-10:  # Avoid division by zero
                # Annualization factor: sqrt(252 trading days / avg holding period)
                avg_holding_days = np.mean([t['holding_days'] for t in trades])
                if avg_holding_days > 0:
                    trades_per_year = 252 / avg_holding_days
                    sharpe_ratio = (mean_return / std_return) * np.sqrt(trades_per_year)
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0  # Zero volatility edge case
        else:
            sharpe_ratio = 0.0  # Single trade edge case

        return {
            "trades": len(trades),
            "total_pnl_net": float(total_pnl),
            "total_return": float(total_return),  # Total P&L as % of capital_base
            "win_rate": float(win_rate),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "profit_factor": float(profit_factor),
            "max_drawdown": float(max_drawdown),
            "max_drawdown_pct": float(max_drawdown_pct),  # Max drawdown as % of capital_base
            "sharpe_ratio": float(sharpe_ratio),  # Now properly calculated using % returns
            "avg_holding_days": float(np.mean([t['holding_days'] for t in trades])),
            "total_transaction_costs": float(sum([t['transaction_costs'] for t in trades])),
            "capital_base": float(capital_base),  # Document the capital base used
            # Removed: full pnl_series (embedded in charts to prevent context overflow)
            "pnl_series_summary": {
                "n_observations": len(pnl_series),
                "start": pnl_series[0] if pnl_series else None,
                "end": pnl_series[-1] if pnl_series else None,
            },
            "trade_details": trades[-10:]  # Last 10 trades
        }

    except Exception as e:
        return {"trades": 0, "error": str(e)}


def _test_engle_granger(
    data: Dict[str, pd.DataFrame],
    ticker_a: str,
    ticker_b: str,
    hedge_method: str = 'ols'
) -> Tuple[float, float, float]:
    """
    Test cointegration between two stocks using Engle-Granger method.

    Args:
        data: Dictionary mapping tickers to price DataFrames
        ticker_a: First stock symbol
        ticker_b: Second stock symbol
        hedge_method: Method for calculating hedge ratio

    Returns:
        Tuple of (p_value, hedge_ratio, spread_adf_stat)
    """
    df_a = data[ticker_a]
    df_b = data[ticker_b]

    # Align dates
    merged = pd.merge(df_a, df_b, on='date', suffixes=('_a', '_b'))

    if len(merged) < 30:
        logger.warning(f"Insufficient data for Engle-Granger test on {ticker_a}/{ticker_b}: {len(merged)} days < 30 minimum")
        return (1.0, 0.0, 0.0)  # Not enough data - return non-cointegrated

    price_a = merged['price_a'].values
    price_b = merged['price_b'].values

    # Cointegration test
    _, p_value, _ = coint(price_a, price_b)

    # Calculate hedge ratio
    hedge_ratio = _calculate_hedge_ratio(merged['price_a'], merged['price_b'], method=hedge_method)

    # Test spread stationarity
    spread = price_b - hedge_ratio * price_a
    adf_result = adfuller(spread)
    adf_stat = adf_result[0]

    return (p_value, hedge_ratio, adf_stat)


def _test_johansen_multivariate(
    data: Dict[str, pd.DataFrame],
    tickers: List[str],
    significance_level: float = 0.05
) -> Dict[str, Any]:
    """
    Test multivariate cointegration using Johansen method.

    Args:
        data: Dictionary mapping tickers to price DataFrames
        tickers: List of stock symbols
        significance_level: Statistical significance threshold

    Returns:
        Dictionary with test results
    """
    if len(tickers) < 2:
        return {"cointegrated": False, "reason": "Need at least 2 tickers"}

    # Merge all price series
    dfs = []
    for ticker in tickers:
        df = data[ticker][['date', 'price']].copy()
        df = df.rename(columns={'price': ticker})
        dfs.append(df)

    merged = dfs[0]
    for df in dfs[1:]:
        merged = pd.merge(merged, df, on='date', how='inner')

    if len(merged) < 30:
        logger.warning(f"Insufficient data for Johansen test on {tickers}: {len(merged)} days < 30 minimum")
        return {"cointegrated": False, "reason": "Insufficient common dates"}

    # Extract price matrix
    price_matrix = merged[[t for t in tickers]].values

    # Johansen test
    result = coint_johansen(price_matrix, det_order=0, k_ar_diff=1)

    # Check trace statistic
    trace_stat = result.lr1
    critical_values = result.cvt

    # Determine cointegration rank
    rank = 0
    for i in range(len(trace_stat)):
        if trace_stat[i] > critical_values[i, 1]:  # 5% significance
            rank = i + 1

    return {
        "cointegrated": rank > 0,
        "rank": rank,
        "trace_statistics": trace_stat.tolist(),
        "critical_values_5pct": critical_values[:, 1].tolist(),
        "eigenvectors": result.evec.tolist()
    }


async def _build_cointegration_heatmap(
    pairwise_results: Dict[Tuple[str, str], float],
    chart_id: str = "coint_heatmap"
) -> Dict[str, Any]:
    """
    Build p-value heatmap for all tested pairs.

    Args:
        pairwise_results: Dict mapping (ticker_a, ticker_b) -> p_value
        chart_id: Unique identifier for chart

    Returns:
        Plotly figure dict
    """
    if not pairwise_results:
        return None

    # Extract unique tickers
    all_tickers = sorted(set([t for pair in pairwise_results.keys() for t in pair]))
    n = len(all_tickers)

    # Create matrix
    matrix = np.ones((n, n))

    for (ticker_a, ticker_b), p_value in pairwise_results.items():
        i = all_tickers.index(ticker_a)
        j = all_tickers.index(ticker_b)
        matrix[i, j] = p_value
        matrix[j, i] = p_value

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=all_tickers,
        y=all_tickers,
        colorscale='RdYlGn_r',
        zmin=0,
        zmax=0.1,
        colorbar=dict(title="P-Value"),
        hovertemplate='%{y} vs %{x}<br>P-Value: %{z:.4f}<extra></extra>'
    ))

    fig.update_layout(
        title="Cointegration P-Value Heatmap",
        xaxis_title="Stock",
        yaxis_title="Stock",
        height=600,
        width=800,
        template="plotly_white"
    )

    return {
        'id': chart_id,
        'title': "Cointegration P-Value Heatmap",
        'plotly': fig.to_dict()
    }


async def _build_hedge_ratio_chart(
    hedge_ratios: Dict[Tuple[str, str], float],
    top_n: int = 10,
    chart_id: str = "hedge_ratios"
) -> Dict[str, Any]:
    """
    Build bar chart of hedge ratios for cointegrated pairs.

    Args:
        hedge_ratios: Dict mapping (ticker_a, ticker_b) -> hedge_ratio
        top_n: Number of pairs to display
        chart_id: Unique identifier for chart

    Returns:
        Plotly figure dict
    """
    if not hedge_ratios:
        return None

    # Sort by absolute hedge ratio
    sorted_pairs = sorted(hedge_ratios.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]

    labels = [f"{pair[0]}/{pair[1]}" for pair, _ in sorted_pairs]
    values = [ratio for _, ratio in sorted_pairs]

    fig = go.Figure(data=go.Bar(
        x=labels,
        y=values,
        marker=dict(color=values, colorscale='Viridis'),
        hovertemplate='<b>%{x}</b><br>Hedge Ratio: %{y:.4f}<extra></extra>'
    ))

    fig.update_layout(
        title=f"Hedge Ratios (Top {len(sorted_pairs)} Pairs)",
        xaxis_title="Pair",
        yaxis_title="Hedge Ratio (β)",
        height=500,
        width=900,
        template="plotly_white",
        xaxis_tickangle=-45
    )

    return {
        'id': chart_id,
        'title': f"Top {len(sorted_pairs)} Hedge Ratios",
        'plotly': fig.to_dict()
    }


async def _build_spread_plot(
    data: Dict[str, pd.DataFrame],
    ticker_a: str,
    ticker_b: str,
    hedge_ratio: float,
    chart_id: str = "spread_plot"
) -> Dict[str, Any]:
    """
    Build spread plot with mean reversion bands.

    Args:
        data: Dictionary mapping tickers to price DataFrames
        ticker_a: First stock symbol
        ticker_b: Second stock symbol
        hedge_ratio: Optimal hedge ratio
        chart_id: Unique identifier for chart

    Returns:
        Plotly figure dict
    """
    df_a = data[ticker_a]
    df_b = data[ticker_b]

    # Merge on date
    merged = pd.merge(df_a, df_b, on='date', suffixes=('_a', '_b'))

    # Calculate spread
    spread = merged['price_b'] - hedge_ratio * merged['price_a']

    # Mean reversion bands
    mean_spread = spread.mean()
    std_spread = spread.std()

    upper_band = mean_spread + 2 * std_spread
    lower_band = mean_spread - 2 * std_spread

    # Create plot
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=merged['date'],
        y=spread,
        mode='lines',
        name='Spread',
        line=dict(color='blue', width=1.5),
        hovertemplate='<b>%{x}</b><br>Spread: %{y:.4f}<extra></extra>'
    ))

    fig.add_hline(
        y=mean_spread,
        line_dash="dash",
        line_color="green",
        annotation_text=f"Mean: {mean_spread:.4f}"
    )
    fig.add_hline(
        y=upper_band,
        line_dash="dot",
        line_color="red",
        annotation_text=f"+2σ: {upper_band:.4f}"
    )
    fig.add_hline(
        y=lower_band,
        line_dash="dot",
        line_color="red",
        annotation_text=f"-2σ: {lower_band:.4f}"
    )

    fig.update_layout(
        title=f"Spread: {ticker_b} - {hedge_ratio:.4f} × {ticker_a}",
        xaxis_title="Date",
        yaxis_title="Spread Value",
        height=500,
        width=1000,
        template="plotly_white",
        hovermode='x unified'
    )

    return {
        'id': chart_id,
        'title': f"Spread Plot: {ticker_b}/{ticker_a}",
        'plotly': fig.to_dict()
    }


@function_tool
async def identify_cointegrated_pairs(
    # Core inputs
    tickers: List[str],
    test_pairs: Optional[List[List[str]]] = None,
    lookback_period: int = 252,

    # Statistical testing
    method: str = "engle_granger",
    significance_level: float = 0.05,
    hedge_calculation_method: str = "ols",

    # ALPHA GENERATION - Mean reversion quality
    calculate_half_life: bool = True,
    calculate_hurst_exponent: bool = True,
    spread_sharpe_ratio: bool = True,

    # ALPHA GENERATION - Stability & validation
    rolling_window_stability: Optional[int] = None,
    train_test_split: Optional[float] = None,

    # ALPHA GENERATION - Trading rules & backtesting
    entry_sigma: Optional[float] = None,
    exit_sigma: Optional[float] = None,
    stop_loss_sigma: Optional[float] = None,
    transaction_cost_bps: Optional[int] = None,
    capital_base: Optional[float] = None,
    allow_short: Optional[bool] = None,
    min_holding_period: Optional[int] = None,
    max_holding_period: Optional[int] = None,
    backtest_strategy: bool = False,
    calculate_current_zscore: bool = False,

    # Efficiency filters
    min_correlation: Optional[float] = None,
    min_common_days: Optional[int] = None,

    # Output control
    generate_heatmap: bool = True,
    generate_hedge_chart: bool = True,
    generate_spread_chart: bool = False,
    spread_pair: Optional[List[str]] = None,
    top_n_results: Optional[int] = None,
    include_johansen: bool = False
) -> dict:
    """
    Statistical cointegration testing for pairs trading with complete data fetching and analysis.

    **What This Tool Does:**
    - Fetches historical price data from FMP automatically (you just pass tickers)
    - Runs Engle-Granger or Johansen cointegration tests
    - If cointegration exists: Provides alpha metrics (half-life, Hurst, Sharpe, backtests, z-scores)
    - If NO cointegration: Returns empty results (this is VALID - means pairs aren't suitable for trading)

    **How to Use:**
    Just call with tickers. DO NOT fetch data separately or code Engle-Granger manually.
    Example: identify_cointegrated_pairs(tickers=['GLD','GDX'], lookback_period=252)

    **Understanding Results:**
    - "cointegrated_pairs" is empty → No statistical cointegration found (p-value > 0.05)
    - "cointegrated_pairs" has data → Cointegration exists, includes all alpha metrics

    **Data Fetching:**
    Tool fetches exact calendar days via start/end dates. Default 252 days (~1 year).
    Longer periods: 504 days (~2 years), 1260 days (~5 years), 2520 days (~10 years).

    Args:
        tickers: List of stock symbols (universe for testing)
        test_pairs: Optional list of specific pairs to test [["A","B"], ["C","D"]].
                    If None, tests all N*(N-1)/2 combinations
        lookback_period: Historical days for testing (default: 252 = ~1 year, can go up to 2520 = ~10 years)

        method: "engle_granger" or "johansen" (default: "engle_granger")
        significance_level: P-value threshold for significance (default: 0.05)
        hedge_calculation_method: "ols" or "min_variance" (default: "ols")

        calculate_half_life: Calculate mean reversion speed (default: True)
        calculate_hurst_exponent: Test mean reversion vs trending (default: True)
        spread_sharpe_ratio: Calculate spread Sharpe ratio (default: True)

        rolling_window_stability: Rolling window size in days for stability testing (default: None = disabled)
        train_test_split: Fraction for training data (default: None = disabled)

        **BACKTESTING PARAMETERS** (only used if backtest_strategy=True):

        entry_sigma: Z-score entry threshold (default: 2.0)
                    - Enter LONG spread when z < -entry_sigma
                    - Enter SHORT spread when z > +entry_sigma
        exit_sigma: Z-score exit threshold for mean reversion (default: 0.0)
                   - Exit when |z| <= exit_sigma (position reverts to mean)
        stop_loss_sigma: Z-score stop loss threshold (default: 3.0)
                        - Exit when |z| > stop_loss_sigma (cut losses)
        transaction_cost_bps: Transaction costs PER LEG in basis points (default: 5 bps)
                             - Each trade has 4 legs total (entry + exit, 2 assets)
                             - Example: 5 bps = 0.20% round-trip cost
        capital_base: Notional capital for position sizing (default: $100,000)
                     - P&L reported in absolute dollars based on this capital
        allow_short: Allow short spread positions (default: True)
                    - If False, only LONG spread (z < -entry_sigma) allowed
                    - If True, both long and short positions allowed
        min_holding_period: Minimum days to hold position (default: 1)
                           - Prevents excessive churning from noise
                           - Exit signals ignored until minimum period met
        max_holding_period: Maximum days to hold position (default: None = unlimited)
                           - Force exit after N days to prevent stale positions
                           - None = no maximum holding constraint
        backtest_strategy: Enable backtesting with the above parameters (default: False)
                          - When True, returns comprehensive backtest metrics
                          - Includes: Sharpe ratio, win rate, max drawdown, P&L series
        calculate_current_zscore: Calculate current z-score for live trading (default: False)
                                 - Returns current signal: LONG_SPREAD, SHORT_SPREAD, or NO_SIGNAL

        min_correlation: Pre-filter pairs by minimum correlation (default: None)
        min_common_days: Minimum overlapping days required (default: 30)

        generate_heatmap: Generate p-value heatmap chart (default: True)
        generate_hedge_chart: Generate hedge ratio bar chart (default: True)
        generate_spread_chart: Generate spread plot for a pair (default: False)
        spread_pair: Specific pair for spread chart as ["A", "B"]. If None and generate_spread_chart=True,
                     uses best cointegrated pair
        top_n_results: Limit number of results returned (default: None = all)
        include_johansen: Also run Johansen multivariate test (default: False)

    Returns:
        Dict containing:
        - cointegrated_pairs: List with p-values, hedge ratios, AND alpha metrics
          (half-life, hurst, sharpe, stability, out-of-sample validation, backtest results)
        - charts: Requested Plotly figures
        - statistics: Summary statistics
        - trading_signals: Current z-scores if calculate_current_zscore=True

    Examples:
        # Full alpha analysis for specific pair
        result = await identify_cointegrated_pairs(
            tickers=["GLD", "GDX"],
            test_pairs=[["GLD", "GDX"]],
            calculate_half_life=True,
            calculate_hurst_exponent=True,
            spread_sharpe_ratio=True,
            backtest_strategy=True,
            calculate_current_zscore=True,
            generate_spread_chart=True
        )

        # Quick cointegration scan without alpha metrics
        result = await identify_cointegrated_pairs(
            tickers=["GLD", "GDX", "SLV", "GDXJ"],
            calculate_half_life=False,
            calculate_hurst_exponent=False,
            spread_sharpe_ratio=False,
            rolling_window_stability=None,
            train_test_split=None,
            backtest_strategy=False,
            top_n_results=10
        )

        # Production trading setup with all validation
        result = await identify_cointegrated_pairs(
            tickers=["SPY", "QQQ", "IWM", "DIA"],
            min_correlation=0.7,
            calculate_half_life=True,
            calculate_hurst_exponent=True,
            spread_sharpe_ratio=True,
            rolling_window_stability=63,
            train_test_split=0.7,
            entry_sigma=2.0,
            exit_sigma=0.0,
            stop_loss_sigma=3.0,
            transaction_cost_bps=5,
            backtest_strategy=True,
            calculate_current_zscore=True
        )
    """
    try:
        # Set defaults if not provided
        if min_common_days is None:
            min_common_days = 30

        # Note: rolling_window_stability and train_test_split remain None if not provided
        # This allows agent to disable these features by not specifying them

        if entry_sigma is None:
            entry_sigma = 2.0

        if exit_sigma is None:
            exit_sigma = 0.0

        if stop_loss_sigma is None:
            stop_loss_sigma = 3.0

        if transaction_cost_bps is None:
            transaction_cost_bps = 5

        # Validation
        if not tickers or len(tickers) < 2:
            return jsonify_results({
                "error": "Need at least 2 tickers to test cointegration",
                "provided_tickers": tickers
            })

        if method not in ["engle_granger", "johansen"]:
            return jsonify_results({
                "error": f"Invalid method: {method}. Use 'engle_granger' or 'johansen'",
                "provided_method": method
            })

        # Connect to FMP server
        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Fetch data for all tickers with dynamic field discovery
            ticker_data = {}
            failed_tickers = []

            logger.info(f"Fetching data for {len(tickers)} tickers...")

            for ticker in tickers:
                try:
                    df = await _fetch_price_data(fmp_server, ticker, lookback_period)

                    if len(df) < min_common_days:
                        failed_tickers.append({
                            "ticker": ticker,
                            "error": f"Insufficient data: {len(df)} days (need {min_common_days}+)"
                        })
                        continue

                    ticker_data[ticker] = df

                except Exception as e:
                    failed_tickers.append({"ticker": ticker, "error": str(e)})

            if len(ticker_data) < 2:
                return jsonify_results({
                    "error": "Insufficient valid data. Need at least 2 tickers with data",
                    "failed_tickers": failed_tickers,
                    "successful_tickers": list(ticker_data.keys())
                })

            valid_tickers = list(ticker_data.keys())
    
            # Determine which pairs to test
            if test_pairs is not None:
                # Test only specified pairs - convert list pairs to tuples
                pairs_to_test = [
                    (pair[0], pair[1]) for pair in test_pairs
                    if len(pair) == 2 and pair[0] in ticker_data and pair[1] in ticker_data
                ]
                logger.info(f"Testing {len(pairs_to_test)} specified pairs")
            else:
                # Test all combinations
                pairs_to_test = [
                    (valid_tickers[i], valid_tickers[j])
                    for i in range(len(valid_tickers))
                    for j in range(i + 1, len(valid_tickers))
                ]
                logger.info(f"Testing all {len(pairs_to_test)} pair combinations")
    
            if not pairs_to_test:
                return jsonify_results({
                    "error": "No valid pairs to test",
                    "valid_tickers": valid_tickers,
                    "requested_pairs": test_pairs
                })
    
            # Pre-filter by correlation if specified
            if min_correlation is not None:
                logger.info(f"Pre-filtering pairs by min correlation: {min_correlation}")
                filtered_pairs = []
                for ticker_a, ticker_b in pairs_to_test:
                    try:
                        df_a = ticker_data[ticker_a]
                        df_b = ticker_data[ticker_b]
                        merged = pd.merge(df_a, df_b, on='date', suffixes=('_a', '_b'))
    
                        if len(merged) >= min_common_days:
                            corr = merged['price_a'].corr(merged['price_b'])
                            if abs(corr) >= min_correlation:
                                filtered_pairs.append((ticker_a, ticker_b))
                    except Exception:
                        continue
    
                pairs_to_test = filtered_pairs
                logger.info(f"Filtered to {len(pairs_to_test)} pairs with correlation >= {min_correlation}")
    
            # Test cointegration using Engle-Granger
            pairwise_results = {}
            hedge_ratios = {}
            cointegrated_pairs = []
    
            for ticker_a, ticker_b in pairs_to_test:
                try:
                    # Merge data for this pair
                    df_a = ticker_data[ticker_a]
                    df_b = ticker_data[ticker_b]
                    merged = pd.merge(df_a, df_b, on='date', suffixes=('_a', '_b'))
    
                    if len(merged) < min_common_days:
                        continue
    
                    # Train/test split if enabled
                    if train_test_split is not None:
                        split_idx = int(len(merged) * train_test_split)
                        train_data = {
                            ticker_a: merged[['date', 'price_a']].iloc[:split_idx].rename(columns={'price_a': 'price'}),
                            ticker_b: merged[['date', 'price_b']].iloc[:split_idx].rename(columns={'price_b': 'price'})
                        }
                        test_data = {
                            ticker_a: merged[['date', 'price_a']].iloc[split_idx:].rename(columns={'price_a': 'price'}),
                            ticker_b: merged[['date', 'price_b']].iloc[split_idx:].rename(columns={'price_b': 'price'})
                        }
    
                        # Test on training data
                        p_value, hedge_ratio, adf_stat = _test_engle_granger(
                            train_data, ticker_a, ticker_b, hedge_method=hedge_calculation_method
                        )
    
                        # Validate on test data
                        p_value_test, _, _ = _test_engle_granger(
                            test_data, ticker_a, ticker_b, hedge_method=hedge_calculation_method
                        )
                        out_of_sample_significant = p_value_test < significance_level
    
                    else:
                        # Full dataset testing
                        p_value, hedge_ratio, adf_stat = _test_engle_granger(
                            ticker_data, ticker_a, ticker_b, hedge_method=hedge_calculation_method
                        )
                        p_value_test = None
                        out_of_sample_significant = None
    
                    pairwise_results[(ticker_a, ticker_b)] = p_value
                    hedge_ratios[(ticker_a, ticker_b)] = hedge_ratio

                    # Include pair if: (1) statistically significant OR (2) explicitly requested via test_pairs
                    is_significant = p_value < significance_level
                    is_explicit_request = test_pairs is not None

                    if is_significant or is_explicit_request:
                        pair_result = {
                            "ticker_a": ticker_a,
                            "ticker_b": ticker_b,
                            "p_value": float(p_value),
                            "hedge_ratio": float(hedge_ratio),
                            "adf_statistic": float(adf_stat),
                            "significant": is_significant
                        }

                        # Calculate spread for alpha metrics
                        spread = merged['price_b'].values - hedge_ratio * merged['price_a'].values
    
                        # ALPHA METRIC: Half-life
                        if calculate_half_life:
                            half_life = _calculate_spread_half_life(spread)
                            pair_result['half_life_days'] = float(half_life)
                            pair_result['mean_reverting'] = half_life < 30  # < 30 days is tradeable
    
                        # ALPHA METRIC: Hurst exponent
                        if calculate_hurst_exponent:
                            hurst = _calculate_hurst_exponent(spread)
                            pair_result['hurst_exponent'] = float(hurst)
                            pair_result['hurst_interpretation'] = (
                                "mean_reverting" if hurst < 0.5 else
                                "random_walk" if 0.45 <= hurst <= 0.55 else
                                "trending"
                            )
    
                        # ALPHA METRIC: Spread Sharpe ratio
                        if spread_sharpe_ratio:
                            sharpe = _calculate_spread_sharpe(spread)
                            pair_result['spread_sharpe_ratio'] = float(sharpe)
    
                        # ALPHA METRIC: Rolling stability
                        if rolling_window_stability is not None:
                            stability = _test_rolling_stability(
                                ticker_data, ticker_a, ticker_b,
                                rolling_window_stability, significance_level
                            )
                            pair_result['rolling_stability'] = stability
    
                        # ALPHA METRIC: Train/test validation
                        if train_test_split is not None:
                            pair_result['out_of_sample_p_value'] = float(p_value_test)
                            pair_result['out_of_sample_significant'] = out_of_sample_significant
                            pair_result['train_test_split'] = train_test_split
    
                        # ALPHA METRIC: Backtest
                        if backtest_strategy:
                            backtest_result = _backtest_pairs_strategy(
                                ticker_data, ticker_a, ticker_b, hedge_ratio,
                                entry_sigma=entry_sigma,
                                exit_sigma=exit_sigma,
                                stop_loss_sigma=stop_loss_sigma,
                                transaction_cost_bps=transaction_cost_bps
                            )
                            pair_result['backtest'] = backtest_result
    
                        # ALPHA METRIC: Current z-score
                        if calculate_current_zscore:
                            mean_spread = np.mean(spread)
                            std_spread = np.std(spread)
                            if std_spread > 0:
                                current_zscore = (spread[-1] - mean_spread) / std_spread
                                pair_result['current_zscore'] = float(current_zscore)
                                pair_result['current_signal'] = (
                                    "LONG_SPREAD" if current_zscore < -entry_sigma else
                                    "SHORT_SPREAD" if current_zscore > entry_sigma else
                                    "NO_SIGNAL"
                                )
    
                        cointegrated_pairs.append(pair_result)
    
                except Exception as e:
                    logger.warning(f"Failed to test pair ({ticker_a}, {ticker_b}): {e}")
                    continue
    
            # Sort by p-value
            cointegrated_pairs.sort(key=lambda x: x['p_value'])
    
            # Apply top_n limit if specified
            if top_n_results is not None and len(cointegrated_pairs) > top_n_results:
                cointegrated_pairs = cointegrated_pairs[:top_n_results]
    
            # Generate requested charts
            charts = []

            if generate_heatmap and pairwise_results:
                heatmap = await _build_cointegration_heatmap(pairwise_results)
                if heatmap:
                    charts.append(heatmap)
    
            if generate_hedge_chart and hedge_ratios:
                # Only show significant pairs in hedge chart
                significant_hedge_ratios = {
                    pair: ratio for pair, ratio in hedge_ratios.items()
                    if pairwise_results.get(pair, 1.0) < significance_level
                }
                if significant_hedge_ratios:
                    top_n_chart = top_n_results if top_n_results else 10
                    hedge_chart = await _build_hedge_ratio_chart(
                        significant_hedge_ratios,
                        top_n=top_n_chart
                    )
                    if hedge_chart:
                        charts.append(hedge_chart)
    
            if generate_spread_chart:
                # Determine which pair to plot
                pair_to_plot = None

                if spread_pair is not None and len(spread_pair) == 2:
                    # Convert list to tuple
                    pair_to_plot = (spread_pair[0], spread_pair[1])
                elif cointegrated_pairs:
                    # Use best cointegrated pair
                    best = cointegrated_pairs[0]
                    pair_to_plot = (best['ticker_a'], best['ticker_b'])
    
                if pair_to_plot:
                    ticker_a, ticker_b = pair_to_plot
                    if ticker_a in ticker_data and ticker_b in ticker_data:
                        hedge_ratio = hedge_ratios.get((ticker_a, ticker_b)) or hedge_ratios.get((ticker_b, ticker_a))
    
                        if hedge_ratio is not None:
                            spread_chart = await _build_spread_plot(
                                ticker_data, ticker_a, ticker_b, hedge_ratio
                            )
                            if spread_chart:
                                charts.append(spread_chart)
    
            # Optional Johansen test
            johansen_result = None
            if include_johansen and len(valid_tickers) >= 2:
                try:
                    johansen_result = _test_johansen_multivariate(
                        ticker_data, valid_tickers, significance_level
                    )
                except Exception as e:
                    logger.warning(f"Johansen test failed: {e}")
    
            # Build response
            charts = wrap_plotly_charts(charts, default_type="cointegration_chart")
            response = {
                "method": method,
                "hedge_calculation_method": hedge_calculation_method,
                "lookback_period": lookback_period,
                "significance_level": significance_level,
                "tickers_tested": valid_tickers,
                "pairs_tested": len(pairwise_results),
                "cointegrated_pairs": cointegrated_pairs,
                "cointegrated_count": len(cointegrated_pairs),
                "failed_tickers": failed_tickers,
                "charts": charts,
                "summary": {
                    "total_pairs_tested": len(pairwise_results),
                    "significant_pairs": len(cointegrated_pairs),
                    "significance_rate": (
                        len(cointegrated_pairs) / len(pairwise_results)
                        if pairwise_results else 0
                    ),
                    "top_n_limit_applied": top_n_results is not None
                }
            }
    
            if johansen_result:
                response["johansen_multivariate"] = johansen_result
    
            return jsonify_results(response)

        except Exception as e:
            logger.error(f"Cointegration analysis failed: {e}", exc_info=True)
            return jsonify_results({
                "error": "Cointegration analysis failed",
                "details": str(e),
                "method": method,
                "tickers": tickers
                })
        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Fatal error in cointegration analysis: {e}", exc_info=True)
        return jsonify_results({
            "error": "Fatal error",
            "details": str(e)
        })


async def identify_cointegrated_pairs_internal(
    tickers: List[str],
    lookback_period: int = 252,
    significance_level: float = 0.05,
    calculate_half_life: bool = True,
    calculate_hurst_exponent: bool = True,
    calculate_current_zscore: bool = True,
) -> dict:
    """
    Internal callable for Canvas - simplified cointegration analysis.
    Returns raw data for Canvas to build charts from.
    """
    try:
        if not tickers or len(tickers) < 2:
            return {"error": "Need at least 2 tickers", "details": f"Got {len(tickers) if tickers else 0}"}
        
        fmp_server = FMPMarketDataServer()
        skipped_tickers = []
        
        try:
            await fmp_server.connect()
            
            ticker_data = {}
            for ticker in tickers:
                try:
                    df = await _fetch_price_data(fmp_server, ticker, lookback_period)
                    if len(df) >= 30:
                        ticker_data[ticker] = df
                    else:
                        skipped_tickers.append({"ticker": ticker, "reason": "insufficient_data"})
                except Exception as e:
                    skipped_tickers.append({"ticker": ticker, "reason": str(e)})
                    continue
            
            valid_tickers = list(ticker_data.keys())
            if len(valid_tickers) < 2:
                return {"error": "Insufficient valid data", "skipped_tickers": skipped_tickers}
            
            # Test all pairs
            pairs_to_test = [
                (valid_tickers[i], valid_tickers[j])
                for i in range(len(valid_tickers))
                for j in range(i + 1, len(valid_tickers))
            ]
            
            pairwise_results = {}
            cointegrated_pairs = []
            
            for ticker_a, ticker_b in pairs_to_test:
                try:
                    df_a = ticker_data[ticker_a]
                    df_b = ticker_data[ticker_b]
                    merged = pd.merge(df_a, df_b, on='date', suffixes=('_a', '_b'))
                    
                    if len(merged) < 30:
                        continue
                    
                    p_value, hedge_ratio, adf_stat = _test_engle_granger(
                        ticker_data, ticker_a, ticker_b, hedge_method='ols'
                    )
                    
                    pairwise_results[(ticker_a, ticker_b)] = p_value
                    
                    pair_result = {
                        "ticker_a": ticker_a,
                        "ticker_b": ticker_b,
                        "p_value": float(p_value),
                        "hedge_ratio": float(hedge_ratio),
                        "adf_statistic": float(adf_stat),
                        "significant": bool(p_value < significance_level),
                    }
                    
                    # Calculate spread for additional metrics
                    spread = merged['price_b'].values - hedge_ratio * merged['price_a'].values
                    
                    if calculate_half_life:
                        half_life = _calculate_spread_half_life(spread)
                        pair_result['half_life_days'] = float(half_life)
                    
                    if calculate_hurst_exponent:
                        hurst = _calculate_hurst_exponent(spread)
                        pair_result['hurst_exponent'] = float(hurst)
                    
                    if calculate_current_zscore:
                        mean_spread = np.mean(spread)
                        std_spread = np.std(spread)
                        if std_spread > 0:
                            current_zscore = (spread[-1] - mean_spread) / std_spread
                            pair_result['current_zscore'] = float(current_zscore)
                            pair_result['current_signal'] = (
                                "LONG_SPREAD" if current_zscore < -2.0 else
                                "SHORT_SPREAD" if current_zscore > 2.0 else
                                "NO_SIGNAL"
                            )
                    
                    # Store spread data for charts
                    pair_result['spread_data'] = {
                        'dates': [str(d) for d in merged['date'].tolist()[-60:]],  # Last 60 days
                        'spread': spread[-60:].tolist(),
                        'mean': float(np.mean(spread)),
                        'std': float(np.std(spread)),
                    }
                    
                    cointegrated_pairs.append(pair_result)
                    
                except Exception as e:
                    logger.warning(f"Failed to test pair ({ticker_a}, {ticker_b}): {e}")
                    continue
            
            # Sort by p-value
            cointegrated_pairs.sort(key=lambda x: x['p_value'])
            
            # Build p-value matrix for heatmap
            pvalue_matrix = []
            for t1 in valid_tickers:
                row = []
                for t2 in valid_tickers:
                    if t1 == t2:
                        row.append(1.0)
                    else:
                        key1 = (t1, t2)
                        key2 = (t2, t1)
                        p = pairwise_results.get(key1) or pairwise_results.get(key2) or 1.0
                        row.append(p)
                pvalue_matrix.append(row)
            
            return {
                "status": "success",
                "tickers": valid_tickers,
                "skipped_tickers": skipped_tickers,
                "pairs_tested": len(pairs_to_test),
                "cointegrated_pairs": cointegrated_pairs,
                "significant_count": sum(1 for p in cointegrated_pairs if p['significant']),
                "pvalue_matrix": pvalue_matrix,
                "significance_level": significance_level,
                "lookback_period": lookback_period,
            }
            
        finally:
            await fmp_server.cleanup()
            
    except Exception as e:
        logger.error(f"Cointegration internal failed: {e}", exc_info=True)
        return {"error": str(e)}


# =============================================================================
# COINTEGRATION PAIR SCREENER
# =============================================================================

def _compute_composite_score(half_life: float, hurst: float, sharpe: float) -> float:
    """
    Compute composite ranking score for a cointegrated pair.
    
    Higher score = better pair. Favors:
    - Lower Hurst (more mean-reverting)
    - Higher Sharpe (better risk-adjusted return)
    - Moderate half-life (not too fast, not too slow)
    
    Formula: sharpe * (1 - hurst) / log(half_life + 1)
    """
    if half_life <= 0 or sharpe <= 0:
        return 0.0
    
    # Penalize extreme half-lives
    half_life_factor = 1.0 / np.log(half_life + 1)
    
    # Higher weight to mean-reversion strength
    mean_rev_factor = (1 - hurst) if hurst < 0.5 else 0.1
    
    return float(sharpe * mean_rev_factor * half_life_factor)


def _get_trading_signal(zscore: float, entry_threshold: float = 1.5) -> str:
    """
    Determine trading signal based on current z-score.
    """
    if zscore < -entry_threshold:
        return "BUY_SPREAD"
    elif zscore > entry_threshold:
        return "SELL_SPREAD"
    else:
        return "HOLD"


async def _fetch_universe_tickers(
    fmp_server: FMPMarketDataServer,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    max_tickers: int = 30
) -> List[str]:
    """
    Fetch tickers for a given sector or industry using FMP screener.
    Returns tickers sorted by market cap (largest first).
    
    Note: FMP uses specific sector/industry names. Common examples:
    - Sectors: "Technology", "Healthcare", "Financial Services", "Consumer Cyclical"
    - Industries: "Semiconductors", "Software - Application", "Biotechnology"
    """
    try:
        # Build screener filters - FMP expects these as direct params
        screener_filters = {
            "isActivelyTrading": True,
        }
        
        # FMP sector/industry names are case-sensitive, try common formats
        if sector:
            screener_filters["sector"] = sector.title()
        if industry:
            # Industry names in FMP are often hyphenated, e.g., "Software - Application"
            screener_filters["industry"] = industry
        
        # Call screener with proper argument structure
        result = await fmp_server.call_tool("run_stock_screener", {
            "filters": screener_filters,
            "limit": max_tickers * 2,  # Fetch extra to account for filtering
            "sort_by": "marketCap",
            "order": "desc",
            "include_raw": False
        })
        data = safe_parse_json(result)
        
        if not data:
            logger.warning(f"Screener returned no data for sector={sector}, industry={industry}")
            return []
        
        if isinstance(data, dict) and "error" in data:
            logger.warning(f"Screener error: {data}")
            return []
        
        # Extract results from response structure
        rows = []
        if isinstance(data, dict):
            rows = data.get("results", []) or data.get("data", []) or []
        elif isinstance(data, list):
            rows = data
        
        if not rows:
            logger.warning(f"No results from screener for sector={sector}, industry={industry}")
            return []
        
        # Extract tickers (already sorted by market cap from API)
        tickers = [
            item.get("symbol") 
            for item in rows 
            if item.get("symbol")
        ][:max_tickers]
        
        logger.info(f"[SCREENER] Fetched {len(tickers)} tickers for sector={sector}, industry={industry}")
        return tickers
        
    except Exception as e:
        logger.error(f"Failed to fetch universe tickers: {e}", exc_info=True)
        return []


async def _fetch_all_prices_batched(
    fmp_server: FMPMarketDataServer,
    tickers: List[str],
    lookback_days: int = 252
) -> Dict[str, pd.Series]:
    """
    Fetch historical prices for all tickers in a single batched operation.
    Returns dict mapping ticker -> price series.
    """
    import asyncio
    
    prices = {}
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(lookback_days * 1.5))
    
    async def fetch_single(ticker: str) -> Tuple[str, Optional[pd.Series]]:
        try:
            result = await fmp_server.call_tool("get_historical_data", {
                "symbol": ticker,
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            })
            data = safe_parse_json(result)
            
            if not data:
                logger.debug(f"No data returned for {ticker}")
                return ticker, None
            
            # Handle different response formats
            # Response could be: {"dates": [...], "close": [...]} or list of {date, close, ...}
            if isinstance(data, list) and len(data) > 0:
                # List of OHLCV records
                try:
                    df = pd.DataFrame(data)
                    # Find date and close columns
                    date_col = next((c for c in df.columns if c.lower() in ['date', 'timestamp']), None)
                    price_col = next((c for c in df.columns if c.lower() in ['close', 'adjclose', 'adj_close']), None)
                    
                    if date_col and price_col and len(df) >= 50:
                        df[date_col] = pd.to_datetime(df[date_col])
                        df = df.sort_values(date_col)
                        series = pd.Series(
                            df[price_col].values[-lookback_days:],
                            index=df[date_col].values[-lookback_days:],
                            name=ticker
                        )
                        return ticker, series
                except Exception as e:
                    logger.debug(f"Failed to parse list data for {ticker}: {e}")
            
            elif isinstance(data, dict):
                # Dict format: {"dates": [...], "close": [...]}
                price_field = _discover_price_field(data)
                date_field = _discover_date_field(data)
                
                if price_field and date_field:
                    prices_list = data.get(price_field, [])
                    dates_list = data.get(date_field, [])
                    
                    if len(prices_list) >= 50:
                        series = pd.Series(
                            prices_list[-lookback_days:],
                            index=pd.to_datetime(dates_list[-lookback_days:]),
                            name=ticker
                        )
                        return ticker, series
            
            logger.debug(f"Insufficient data for {ticker}")
            return ticker, None
            
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker}: {e}")
            return ticker, None
    
    # Fetch all tickers with rate limiting
    for i, ticker in enumerate(tickers):
        result_ticker, result_series = await fetch_single(ticker)
        if result_series is not None:
            prices[result_ticker] = result_series
        
        # Rate limiting
        if i < len(tickers) - 1:
            await asyncio.sleep(0.15)
    
    logger.info(f"[SCREENER] Fetched prices for {len(prices)}/{len(tickers)} tickers")
    return prices


_coint_sample_count = 0  # Global counter for debug sampling

def _test_pair_cointegration(
    prices_a: pd.Series,
    prices_b: pd.Series,
    significance_level: float = 0.05
) -> Optional[Dict[str, Any]]:
    """
    Test a single pair for cointegration and compute alpha metrics.
    Returns None if not cointegrated or insufficient data.
    """
    global _coint_sample_count
    
    try:
        # Align series
        combined = pd.concat([prices_a, prices_b], axis=1).dropna()
        if len(combined) < 50:
            return None
        
        x = combined.iloc[:, 0].values
        y = combined.iloc[:, 1].values
        
        # Engle-Granger test
        score, pvalue, _ = coint(x, y)
        
        # Log first few p-values for debugging
        _coint_sample_count += 1
        if _coint_sample_count <= 10:
            ticker_a = prices_a.name if hasattr(prices_a, 'name') else 'A'
            ticker_b = prices_b.name if hasattr(prices_b, 'name') else 'B'
            logger.info(f"[SCREENER DEBUG] {ticker_a}/{ticker_b}: p-value={pvalue:.4f}, sig_level={significance_level}")
        
        if pvalue > significance_level:
            return None
        
        # Calculate hedge ratio
        hedge_ratio = _calculate_hedge_ratio(
            pd.Series(x), pd.Series(y), method='ols'
        )
        
        # Calculate spread
        spread = y - hedge_ratio * x
        
        # Alpha metrics
        half_life = _calculate_spread_half_life(spread)
        hurst = _calculate_hurst_exponent(spread)
        sharpe = _calculate_spread_sharpe(spread)
        
        # Current z-score
        spread_mean = np.mean(spread)
        spread_std = np.std(spread)
        current_zscore = (spread[-1] - spread_mean) / spread_std if spread_std > 0 else 0
        
        return {
            "p_value": float(pvalue),
            "hedge_ratio": float(hedge_ratio),
            "half_life": float(half_life),
            "hurst": float(hurst),
            "spread_sharpe": float(sharpe),
            "current_zscore": float(current_zscore),
            "spread_mean": float(spread_mean),
            "spread_std": float(spread_std),
            "n_observations": len(spread)
        }
        
    except Exception as e:
        logger.debug(f"Pair test failed: {e}")
        return None


def _build_screener_spread_chart(
    prices_a: pd.Series,
    prices_b: pd.Series,
    hedge_ratio: float,
    ticker_a: str,
    ticker_b: str,
    current_zscore: float,
    chart_id: str
) -> Dict[str, Any]:
    """
    Build a spread chart for screener results with z-score bands.
    """
    # Align series
    combined = pd.concat([prices_a, prices_b], axis=1).dropna()
    x = combined.iloc[:, 0].values
    y = combined.iloc[:, 1].values
    dates = combined.index
    
    spread = y - hedge_ratio * x
    spread_mean = np.mean(spread)
    spread_std = np.std(spread)
    
    # Normalize to z-score
    zscore = (spread - spread_mean) / spread_std
    
    fig = go.Figure()
    
    # Z-score line
    fig.add_trace(go.Scatter(
        x=dates,
        y=zscore,
        mode='lines',
        name='Z-Score',
        line=dict(color='#3b82f6', width=1.5)
    ))
    
    # Entry/exit bands
    fig.add_hline(y=1.5, line_dash="dash", line_color="#f59e0b", 
                  annotation_text="Sell Entry (+1.5σ)")
    fig.add_hline(y=-1.5, line_dash="dash", line_color="#22c55e",
                  annotation_text="Buy Entry (-1.5σ)")
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    
    # Current position marker
    fig.add_trace(go.Scatter(
        x=[dates[-1]],
        y=[current_zscore],
        mode='markers',
        name=f'Current ({current_zscore:.2f})',
        marker=dict(
            size=12,
            color='#ef4444' if abs(current_zscore) > 1.5 else '#6b7280',
            symbol='diamond'
        )
    ))
    
    fig.update_layout(
        title=f"Spread Z-Score: {ticker_b} - {hedge_ratio:.2f}×{ticker_a}",
        xaxis_title="Date",
        yaxis_title="Z-Score (σ)",
        height=350,
        template="plotly_white",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return {
        'id': chart_id,
        'title': f"Spread: {ticker_b}/{ticker_a}",
        'plotly': fig.to_dict()
    }


@function_tool
async def screen_cointegrated_pairs(
    # Universe selection (pick one)
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    
    # Screening limits
    max_tickers: int = 30,
    max_pairs_to_test: int = 200,
    lookback_days: int = 252,
    
    # Quality filters (pairs must pass ALL) - defaults are permissive
    min_half_life: int = 1,
    max_half_life: int = 999,       # Effectively disabled
    max_hurst: float = 1.0,          # Effectively disabled
    min_spread_sharpe: float = -999, # Effectively disabled
    significance_level: float = 0.10,
    
    # Output control
    top_n: int = 10,
    include_charts: bool = True,
) -> Dict[str, Any]:
    """
    Screen a universe of stocks for tradeable cointegrated pairs.
    
    Takes a sector, industry, or custom ticker list, tests all possible pairs,
    and returns the best tradeable pairs ranked by a composite alpha score.
    
    **How to Use:**
    - By sector: screen_cointegrated_pairs(sector="Technology")
    - By industry: screen_cointegrated_pairs(industry="Semiconductors")
    - Custom list: screen_cointegrated_pairs(tickers=["NVDA", "AMD", "INTC", "MU"])
    
    **What It Returns:**
    - Ranked list of cointegrated pairs with trading signals
    - Alpha metrics: half-life, Hurst exponent, spread Sharpe
    - Current z-score and signal (BUY_SPREAD, SELL_SPREAD, HOLD)
    - Spread charts for top pairs
    
    **Quality Filters (all disabled by default - returns ALL cointegrated pairs):**
    - min_half_life: Minimum days for mean reversion (default: 1 = no filter)
    - max_half_life: Maximum days for mean reversion (default: 999 = no filter)
    - max_hurst: Maximum Hurst exponent (default: 1.0 = no filter)
    - min_spread_sharpe: Minimum Sharpe ratio (default: -999 = no filter)
    
    Args:
        sector: Sector name (e.g., "Technology", "Healthcare", "Financials")
        industry: Industry name (e.g., "Semiconductors", "Software")
        tickers: Custom list of tickers to screen
        max_tickers: Maximum tickers in universe (limits n^2 pairs)
        max_pairs_to_test: Cap on total pairs to test
        lookback_days: Historical data period (default: 252 = 1 year)
        min_half_life: Minimum half-life in days (default: 1 = no filter)
        max_half_life: Maximum half-life in days (default: 999 = no filter)
        max_hurst: Maximum Hurst exponent (default: 1.0 = no filter)
        min_spread_sharpe: Minimum spread Sharpe ratio (default: -999 = no filter)
        significance_level: Cointegration p-value threshold (default: 0.10)
        top_n: Number of top pairs to return (default: 10)
        include_charts: Generate spread charts for top pairs (default: True)
    
    Returns:
        Dict with:
        - universe_used: List of tickers screened
        - pairs_tested: Number of pairs tested
        - pairs_passed: Number passing all filters
        - top_pairs: Ranked list of best pairs with metrics and signals
        - charts: Spread charts for top pairs (if include_charts=True)
        - filters_applied: Filter settings used
    
    Example:
        # Screen semiconductors for pairs trades
        result = await screen_cointegrated_pairs(
            industry="Semiconductors",
            max_half_life=30,
            min_spread_sharpe=0.8
        )
        # Returns top pairs like NVDA/AMD with current z-scores and signals
    """
    import itertools
    import random
    
    logger.info(f"[SCREENER] Starting cointegration screening: sector={sector}, industry={industry}, tickers={len(tickers) if tickers else 0}")
    
    try:
        fmp_server = FMPMarketDataServer()
        await fmp_server.connect()
        
        try:
            # =====================================================================
            # STEP 1: Get Universe
            # =====================================================================
            universe = []
            
            if tickers:
                universe = tickers[:max_tickers]
                logger.info(f"[SCREENER] Using custom ticker list: {len(universe)} tickers")
            elif sector or industry:
                universe = await _fetch_universe_tickers(
                    fmp_server, sector=sector, industry=industry, max_tickers=max_tickers
                )
                if not universe:
                    return jsonify_results({
                        "error": f"No tickers found for sector={sector}, industry={industry}",
                        "suggestion": "Try a different sector/industry or provide custom tickers"
                    })
            else:
                return jsonify_results({
                    "error": "Must provide sector, industry, or tickers",
                    "usage": "screen_cointegrated_pairs(sector='Technology') or tickers=['AAPL','MSFT']"
                })
            
            if len(universe) < 2:
                return jsonify_results({
                    "error": f"Need at least 2 tickers, got {len(universe)}",
                    "universe": universe
                })
            
            # =====================================================================
            # STEP 2: Fetch All Prices (Batched)
            # =====================================================================
            logger.info(f"[SCREENER] Fetching prices for {len(universe)} tickers...")
            prices_dict = await _fetch_all_prices_batched(fmp_server, universe, lookback_days)
            
            valid_tickers = list(prices_dict.keys())
            if len(valid_tickers) < 2:
                return jsonify_results({
                    "error": f"Insufficient price data. Only {len(valid_tickers)} tickers have valid data.",
                    "valid_tickers": valid_tickers,
                    "failed_tickers": [t for t in universe if t not in valid_tickers]
                })
            
            # =====================================================================
            # STEP 3: Generate and Test Pairs
            # =====================================================================
            all_pairs = list(itertools.combinations(valid_tickers, 2))
            total_possible = len(all_pairs)
            
            # Cap pairs to test
            if len(all_pairs) > max_pairs_to_test:
                random.shuffle(all_pairs)
                all_pairs = all_pairs[:max_pairs_to_test]
            
            logger.info(f"[SCREENER] Testing {len(all_pairs)} pairs (of {total_possible} possible)...")
            
            # Reset debug counter
            global _coint_sample_count
            _coint_sample_count = 0
            
            # Test each pair
            passed_pairs = []
            
            # Debug counters
            fail_coint = 0
            fail_half_life_min = 0
            fail_half_life_max = 0
            fail_hurst = 0
            fail_sharpe = 0
            
            for ticker_a, ticker_b in all_pairs:
                result = _test_pair_cointegration(
                    prices_dict[ticker_a],
                    prices_dict[ticker_b],
                    significance_level=significance_level
                )
                
                if result is None:
                    fail_coint += 1
                    continue
                
                # Apply quality filters with debug
                if result["half_life"] < min_half_life:
                    fail_half_life_min += 1
                    continue
                if result["half_life"] > max_half_life:
                    fail_half_life_max += 1
                    logger.debug(f"[SCREENER] {ticker_a}/{ticker_b} failed: half_life={result['half_life']:.1f} > {max_half_life}")
                    continue
                if result["hurst"] > max_hurst:
                    fail_hurst += 1
                    logger.debug(f"[SCREENER] {ticker_a}/{ticker_b} failed: hurst={result['hurst']:.3f} > {max_hurst}")
                    continue
                if result["spread_sharpe"] < min_spread_sharpe:
                    fail_sharpe += 1
                    continue
                
                # Compute composite score
                score = _compute_composite_score(
                    result["half_life"],
                    result["hurst"],
                    result["spread_sharpe"]
                )
                
                # Get trading signal
                signal = _get_trading_signal(result["current_zscore"])
                
                passed_pairs.append({
                    "pair": [ticker_a, ticker_b],
                    "ticker_a": ticker_a,
                    "ticker_b": ticker_b,
                    "p_value": round(result["p_value"], 4),
                    "hedge_ratio": round(result["hedge_ratio"], 4),
                    "half_life": round(result["half_life"], 1),
                    "hurst": round(result["hurst"], 3),
                    "spread_sharpe": round(result["spread_sharpe"], 2),
                    "current_zscore": round(result["current_zscore"], 2),
                    "signal": signal,
                    "composite_score": round(score, 4),
                    "n_observations": result["n_observations"]
                })
            
            # =====================================================================
            # STEP 4: Rank and Select Top Pairs
            # =====================================================================
            passed_pairs.sort(key=lambda x: x["composite_score"], reverse=True)
            top_pairs = passed_pairs[:top_n]
            
            # Log failure breakdown
            logger.info(f"[SCREENER] Failure breakdown: coint_test={fail_coint}, half_life_min={fail_half_life_min}, half_life_max={fail_half_life_max}, hurst={fail_hurst}, sharpe={fail_sharpe}")
            logger.info(f"[SCREENER] Found {len(passed_pairs)} pairs passing filters, returning top {len(top_pairs)}")
            
            # =====================================================================
            # STEP 5: Generate Charts for Top Pairs
            # =====================================================================
            charts = []
            if include_charts and top_pairs:
                for i, pair_data in enumerate(top_pairs[:5]):  # Charts for top 5
                    ticker_a = pair_data["ticker_a"]
                    ticker_b = pair_data["ticker_b"]
                    
                    chart = _build_screener_spread_chart(
                        prices_dict[ticker_a],
                        prices_dict[ticker_b],
                        pair_data["hedge_ratio"],
                        ticker_a,
                        ticker_b,
                        pair_data["current_zscore"],
                        f"screener_spread_{i}"
                    )
                    charts.append(chart)
                
                charts = wrap_plotly_charts(charts, default_type="cointegration_screener")
            
            # =====================================================================
            # STEP 6: Build Response
            # =====================================================================
            # Count signals
            signal_counts = {
                "BUY_SPREAD": sum(1 for p in top_pairs if p["signal"] == "BUY_SPREAD"),
                "SELL_SPREAD": sum(1 for p in top_pairs if p["signal"] == "SELL_SPREAD"),
                "HOLD": sum(1 for p in top_pairs if p["signal"] == "HOLD")
            }
            
            response = {
                "status": "success",
                "universe_used": valid_tickers,
                "universe_size": len(valid_tickers),
                "pairs_tested": len(all_pairs),
                "pairs_passed": len(passed_pairs),
                "top_pairs": top_pairs,
                "signal_summary": signal_counts,
                "actionable_pairs": [p for p in top_pairs if p["signal"] != "HOLD"],
                "filters_applied": {
                    "significance_level": significance_level,
                    "min_half_life": min_half_life,
                    "max_half_life": max_half_life,
                    "max_hurst": max_hurst,
                    "min_spread_sharpe": min_spread_sharpe,
                },
                "charts": charts,
                "interpretation": (
                    f"Screened {len(valid_tickers)} stocks, tested {len(all_pairs)} pairs. "
                    f"{len(passed_pairs)} pairs passed quality filters. "
                    f"Top pair: {top_pairs[0]['pair'][0]}/{top_pairs[0]['pair'][1]} "
                    f"(Sharpe={top_pairs[0]['spread_sharpe']}, Half-life={top_pairs[0]['half_life']}d, "
                    f"Current z={top_pairs[0]['current_zscore']:.1f} → {top_pairs[0]['signal']})"
                    if top_pairs else "No pairs passed quality filters. Try relaxing constraints."
                )
            }
            
            return jsonify_results(response)
            
        finally:
            await fmp_server.cleanup()
            
    except Exception as e:
        logger.error(f"Cointegration screening failed: {e}", exc_info=True)
        return jsonify_results({
            "error": "Screening failed",
            "details": str(e)
        })
