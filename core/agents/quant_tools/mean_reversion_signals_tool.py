"""
Mean Reversion Signal Generation Tool
Generate trade signals based on z-score mean reversion of spread for pairs trading
Based on PCA analysis tool pattern
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from statsmodels.tsa.stattools import adfuller, kpss
from arch.unitroot import PhillipsPerron
from datetime import datetime, timedelta
from dotenv import load_dotenv
from scipy.stats import zscore

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

load_dotenv()
logger = logging.getLogger(__name__)


async def _build_spread_bands_chart(
    spread: np.ndarray,
    dates: List[str],
    rolling_mean: np.ndarray,
    rolling_std: np.ndarray,
    z_entry_long: float,
    z_entry_short: float,
    chart_id: str
) -> Dict[str, Any]:
    """
    Build spread time series with rolling mean and ±1σ, ±2σ bands.
    Shows mean reversion opportunities visually.
    """
    if len(spread) == 0 or len(dates) == 0:
        return None

    fig = go.Figure()

    # Spread line
    fig.add_trace(go.Scatter(
        x=dates,
        y=spread,
        mode='lines',
        name='Spread',
        line=dict(color='#2E86AB', width=2),
        hovertemplate='<b>%{x}</b><br>Spread: %{y:.4f}<extra></extra>'
    ))

    # Rolling mean (centerline)
    fig.add_trace(go.Scatter(
        x=dates,
        y=rolling_mean,
        mode='lines',
        name='μ (Rolling Mean)',
        line=dict(color='black', dash='dash', width=2)
    ))

    # ±1σ bands (standard deviation range)
    fig.add_trace(go.Scatter(
        x=dates,
        y=rolling_mean + rolling_std,
        mode='lines',
        name='+1σ',
        line=dict(color='orange', dash='dot', width=1.5),
        showlegend=True
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=rolling_mean - rolling_std,
        mode='lines',
        name='-1σ',
        line=dict(color='orange', dash='dot', width=1.5),
        fill='tonexty',
        fillcolor='rgba(255,165,0,0.1)',
        showlegend=True
    ))

    # Entry bands (use actual thresholds, not hardcoded 2σ)
    fig.add_trace(go.Scatter(
        x=dates,
        y=rolling_mean + z_entry_short*rolling_std,
        mode='lines',
        name=f'+{z_entry_short}σ (SHORT Entry)',
        line=dict(color='red', dash='dot', width=1.5)
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=rolling_mean + z_entry_long*rolling_std,
        mode='lines',
        name=f'{z_entry_long}σ (LONG Entry)',
        line=dict(color='green', dash='dot', width=1.5)
    ))

    fig.update_layout(
        title="Spread with Mean Reversion Bands",
        xaxis_title="Date",
        yaxis_title="Spread Value",
        template="plotly_white",
        height=500,
        hovermode='x unified',
        legend=dict(x=0.7, y=0.95)
    )

    return {
        'id': f"{chart_id}_spread_bands",
        'title': "Spread with Mean Reversion Bands",
        'plotly': fig.to_dict()
    }


async def _build_zscore_chart(
    z_scores: np.ndarray,
    dates: List[str],
    signals: np.ndarray,
    z_score_entry_long: float,
    z_score_entry_short: float,
    z_score_exit: float,
    chart_id: str
) -> Dict[str, Any]:
    """
    Build z-score time series colored by signal regime.
    Entry/exit thresholds shown as horizontal lines.
    """
    if len(z_scores) == 0 or len(dates) == 0:
        return None

    # Color mapping: green (long), red (short), gray (flat)
    colors = ['green' if s == 1 else 'red' if s == -1 else 'lightgray' for s in signals]

    fig = go.Figure()

    # Z-score line with colored markers
    fig.add_trace(go.Scatter(
        x=dates,
        y=z_scores,
        mode='markers+lines',
        marker=dict(size=4, color=colors),
        line=dict(color='#2E86AB', width=1),
        name='Z-Score',
        hovertemplate='<b>%{x}</b><br>Z: %{y:.3f}<extra></extra>'
    ))

    # Entry thresholds (asymmetric)
    fig.add_hline(
        y=z_score_entry_short, line_dash="dash", line_color="red", line_width=2,
        annotation_text=f"SHORT Entry (+{z_score_entry_short}σ)",
        annotation_position="right"
    )
    fig.add_hline(
        y=z_score_entry_long, line_dash="dash", line_color="green", line_width=2,
        annotation_text=f"LONG Entry ({z_score_entry_long}σ)",
        annotation_position="right"
    )

    # Exit thresholds
    fig.add_hline(
        y=z_score_exit, line_dash="dot", line_color="orange", line_width=1.5,
        annotation_text=f"Exit (+{z_score_exit}σ)"
    )
    fig.add_hline(
        y=-z_score_exit, line_dash="dot", line_color="orange", line_width=1.5,
        annotation_text=f"Exit (-{z_score_exit}σ)"
    )

    # Zero line (mean)
    fig.add_hline(y=0, line_color="black", line_width=1)

    fig.update_layout(
        title="Z-Score with Trading Thresholds",
        xaxis_title="Date",
        yaxis_title="Z-Score (Standard Deviations)",
        template="plotly_white",
        height=500,
        hovermode='x unified'
    )

    return {
        'id': f"{chart_id}_zscore",
        'title': "Z-Score with Trading Thresholds",
        'plotly': fig.to_dict()
    }


async def _build_signal_timeline_chart(
    signals: np.ndarray,
    dates: List[str],
    transitions: List[Dict],
    chart_id: str
) -> Dict[str, Any]:
    """
    Build signal timeline bar chart showing long/short/flat periods.
    Markers indicate signal transitions (entry/exit points).
    """
    if len(signals) == 0 or len(dates) == 0:
        return None

    # Map signals to colors
    colors = ['green' if s == 1 else 'red' if s == -1 else 'lightgray' for s in signals]

    fig = go.Figure()

    # Signal bars
    fig.add_trace(go.Bar(
        x=dates,
        y=signals,
        marker=dict(color=colors, line=dict(color='black', width=0.5)),
        name='Position',
        hovertemplate='<b>%{x}</b><br>Signal: %{y}<extra></extra>',
        showlegend=False
    ))

    # Add transition markers
    for transition in transitions:
        marker_symbol = "▲" if transition['to'] == 1 else "▼" if transition['to'] == -1 else "◆"
        fig.add_annotation(
            x=transition['date'],
            y=transition['to'],
            text=marker_symbol,
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-30,
            arrowcolor='black',
            font=dict(size=14, color='black')
        )

    fig.update_layout(
        title="Trading Signal Timeline",
        xaxis_title="Date",
        yaxis_title="Position",
        template="plotly_white",
        height=400,
        yaxis=dict(
            tickmode='array',
            tickvals=[-1, 0, 1],
            ticktext=['SHORT', 'FLAT', 'LONG'],
            range=[-1.5, 1.5]
        )
    )

    return {
        'id': f"{chart_id}_signal_timeline",
        'title': "Trading Signal Timeline",
        'plotly': fig.to_dict()
    }


def _detect_signal_transitions(
    signals: np.ndarray,
    dates: List[str],
    z_scores: np.ndarray
) -> List[Dict[str, Any]]:
    """
    Identify all signal transitions (entry/exit points).

    Returns list of dicts with transition details.
    """
    transitions = []
    for i in range(1, len(signals)):
        if signals[i] != signals[i-1]:
            transitions.append({
                'date': dates[i],
                'from': int(signals[i-1]),
                'to': int(signals[i]),
                'z_score': float(z_scores[i])
            })
    return transitions


async def _test_stationarity_comprehensive(
    spread: np.ndarray,
    method: str,
    significance_level: float
) -> Dict[str, Any]:
    """
    Test spread stationarity using ADF, KPSS, or Phillips-Perron.
    """
    try:
        if method == "adf":
            adf_stat, p_value, usedlag, nobs, critical_values, _ = adfuller(spread, autolag='AIC')
            is_stationary = p_value < significance_level

            return {
                'method': 'Augmented Dickey-Fuller',
                'test_statistic': float(adf_stat),
                'p_value': float(p_value),
                'used_lag': int(usedlag),
                'n_obs': int(nobs),
                'critical_values': {k: float(v) for k, v in critical_values.items()},
                'is_stationary': is_stationary,
                'significance_level': significance_level,
                'interpretation': (
                    f"Spread is stationary at {significance_level*100}% level"
                    if is_stationary else
                    f"Spread is non-stationary (p={p_value:.4f})"
                ),
                'recommendation': (
                    "✓ Mean reversion signals reliable"
                    if is_stationary else
                    "⚠️ Spread may not revert - use caution"
                )
            }

        elif method == "kpss":
            kpss_stat, p_value, lags, critical_values = kpss(spread, regression='c', nlags='auto')
            is_stationary = p_value > significance_level

            return {
                'method': 'KPSS',
                'test_statistic': float(kpss_stat),
                'p_value': float(p_value),
                'lags': int(lags),
                'critical_values': {k: float(v) for k, v in critical_values.items()},
                'is_stationary': is_stationary,
                'significance_level': significance_level,
                'interpretation': (
                    f"Spread is stationary at {significance_level*100}% level"
                    if is_stationary else
                    f"Spread is non-stationary (p={p_value:.4f})"
                ),
                'recommendation': (
                    "✓ Mean reversion signals reliable"
                    if is_stationary else
                    "⚠️ Spread may not revert - use caution"
                )
            }

        elif method == "pp":
            pp_test = PhillipsPerron(spread)
            is_stationary = pp_test.pvalue < significance_level

            return {
                'method': 'Phillips-Perron',
                'test_statistic': float(pp_test.stat),
                'p_value': float(pp_test.pvalue),
                'lags': int(pp_test.lags),
                'n_obs': int(pp_test.nobs),
                'critical_values': {k: float(v) for k, v in pp_test.critical_values.items()},
                'is_stationary': is_stationary,
                'significance_level': significance_level,
                'interpretation': (
                    f"Spread is stationary at {significance_level*100}% level"
                    if is_stationary else
                    f"Spread is non-stationary (p={pp_test.pvalue:.4f})"
                ),
                'recommendation': (
                    "✓ Mean reversion signals reliable"
                    if is_stationary else
                    "⚠️ Spread may not revert - use caution"
                )
            }

    except Exception as e:
        logger.warning(f"Stationarity test failed: {e}")
        return {
            'method': method,
            'error': str(e),
            'is_stationary': None,
            'recommendation': "⚠️ Test failed - proceed with caution"
        }


async def _run_backtest(
    signals: np.ndarray,
    spread: np.ndarray,
    dates: List[str],
    transaction_cost_bps: float,
    initial_capital: float,
    trading_days_per_year: int,
    max_leverage: float = 2.0,
    target_volatility: float = 0.10
) -> Dict[str, Any]:
    """
    Backtest mean reversion strategy with proper position sizing.

    Uses volatility-targeted position sizing to prevent unbounded exposure:
    - Target annualized volatility on capital (default 10%)
    - Scale spread returns by volatility
    - Apply leverage constraint (default max 2x)
    """
    try:
        # Calculate spread returns (dollar P&L approach for pairs trading)
        # For mean reversion strategies, we care about dollar changes in spread
        # normalized by initial capital, not percentage changes of spread itself
        # (since spread can be negative, abs() corrupts the calculation)
        spread_changes = np.diff(spread, prepend=spread[0])

        # Normalize by initial capital to get returns as fraction of portfolio
        # Assumes 1 unit of spread per dollar of capital (can be scaled by position_scaling later)
        spread_returns = spread_changes / initial_capital

        # Calculate spread volatility for position sizing
        # Now based on corrected dollar P&L returns, not corrupted percentage returns
        spread_vol = np.std(spread_returns[spread_returns != 0])
        if spread_vol == 0 or np.isnan(spread_vol):
            spread_vol = 0.01  # Default to 1% if no volatility

        # Target volatility on capital (annualized -> daily)
        # Scale positions to achieve target volatility (e.g., 10% annual = ~0.63% daily)
        daily_vol_target = target_volatility / np.sqrt(trading_days_per_year)
        position_scaling = min(daily_vol_target / spread_vol, max_leverage)

        # Calculate strategy returns with scaled positions
        positions = signals.astype(float) * position_scaling
        strategy_returns = positions[:-1] * spread_returns[1:]
        strategy_returns = np.insert(strategy_returns, 0, 0)

        # Apply transaction costs on position changes
        # Calculate notional traded (position changes in capital terms)
        # E.g., going from 0 to 1.5x leverage on $100k = $150k notional traded
        positions_capital = positions * initial_capital
        notional_traded = np.abs(np.diff(positions_capital, prepend=0))

        # Transaction costs as percentage of notional, then convert to return on capital
        # E.g., 10 bps on $150k notional = $150 cost = 0.15% of $100k capital
        transaction_costs = notional_traded * (transaction_cost_bps / 10000.0) / initial_capital

        # Net returns after costs
        net_returns = strategy_returns - transaction_costs

        # Build equity curve with compounding (vectorized for efficiency)
        # Start with initial capital and compound all returns
        equity_curve = initial_capital * np.cumprod(1 + net_returns)

        # Apply stop-loss floor: if equity drops below 10% of initial, floor it
        # (In reality, this would close the position, but we model as freeze for simplicity)
        equity_curve = np.maximum(equity_curve, initial_capital * 0.1)

        # Calculate performance metrics
        total_return = (equity_curve[-1] - initial_capital) / initial_capital

        # Annualized return (compound)
        if len(net_returns) > 0 and total_return > -1:
            annualized_return = (1 + total_return) ** (trading_days_per_year / len(net_returns)) - 1
        else:
            annualized_return = -1.0  # Total loss

        # Risk metrics
        returns_std = np.std(net_returns)
        sharpe_ratio = (np.mean(net_returns) / returns_std * np.sqrt(trading_days_per_year)) if returns_std > 0 else 0

        # Drawdown calculation
        cumulative_max = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - cumulative_max) / cumulative_max
        max_drawdown = np.min(drawdowns)

        # Trade statistics
        trade_count = int(np.sum(np.abs(np.diff(signals, prepend=0)) > 0))
        winning_days = int(np.sum(net_returns > 0))
        losing_days = int(np.sum(net_returns < 0))
        win_rate = winning_days / (winning_days + losing_days) if (winning_days + losing_days) > 0 else 0

        return {
            'performance': {
                'total_return': float(total_return),
                'annualized_return': float(annualized_return),
                'sharpe_ratio': float(sharpe_ratio),
                'max_drawdown': float(max_drawdown),
                'volatility': float(returns_std * np.sqrt(trading_days_per_year)),
                'position_scaling': float(position_scaling)  # Show leverage used
            },
            'trades': {
                'total_trades': trade_count,
                'winning_days': winning_days,
                'losing_days': losing_days,
                'win_rate': float(win_rate),
                'avg_daily_return': float(np.mean(net_returns))
            },
            # Removed: full equity_curve arrays (embedded in charts to prevent context overflow)
            'equity_curve_summary': {
                'start_date': dates[0] if dates else None,
                'end_date': dates[-1] if dates else None,
                'n_observations': len(equity_curve),
                'final_value': float(equity_curve[-1]) if len(equity_curve) > 0 else 0,
                'min_drawdown': float(np.min(drawdowns)) if len(drawdowns) > 0 else 0,
            },
            'final_capital': float(equity_curve[-1]),
            'total_costs': float(np.sum(transaction_costs) * initial_capital)
        }

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {'error': str(e)}


async def _build_backtest_chart(
    equity_curve: List[float],
    dates: List[str],
    drawdowns: List[float],
    chart_id: str
) -> Dict[str, Any]:
    """Build backtest performance chart."""
    if not equity_curve or not dates:
        return None

    try:
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=["Equity Curve", "Drawdown"],
            vertical_spacing=0.15,
            row_heights=[0.7, 0.3]
        )

        fig.add_trace(
            go.Scatter(
                x=dates, y=equity_curve, mode='lines', name='Equity',
                line=dict(color='#2E86AB', width=2),
                hovertemplate='<b>%{x}</b><br>$%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        drawdown_pct = [d * 100 for d in drawdowns]
        fig.add_trace(
            go.Scatter(
                x=dates, y=drawdown_pct, mode='lines', name='Drawdown',
                fill='tozeroy', line=dict(color='red', width=1),
                fillcolor='rgba(255,0,0,0.2)',
                hovertemplate='<b>%{x}</b><br>%{y:.2f}%<extra></extra>'
            ),
            row=2, col=1
        )

        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Portfolio Value ($)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)

        fig.update_layout(
            title="Backtest Performance",
            template="plotly_white",
            height=700,
            hovermode='x unified'
        )

        return {
            'id': f"{chart_id}_backtest",
            'title': "Backtest Performance",
            'plotly': fig.to_dict()
        }

    except Exception as e:
        logger.warning(f"Backtest chart failed: {e}")
        return None


async def _generate_mean_reversion_signals_impl(
    # Mode 1: Auto-fetch and calculate (NEW)
    asset_x: Optional[str] = None,
    asset_y: Optional[str] = None,
    hedge_ratio: Optional[float] = None,
    lookback_period: int = 252,

    # Mode 2: Manual spread (EXISTING - backward compatible)
    spread: Optional[List[float]] = None,
    dates: Optional[List[str]] = None,

    # Signal parameters
    z_score_entry_long: float = -2.0,
    z_score_entry_short: float = 2.0,
    z_score_exit: float = 0.5,
    lookback_window: int = 20,
    direction: str = "both",
    allow_short: bool = True,
    min_data_points: Optional[int] = None,

    # NEW: Stationarity testing (optional)
    test_stationarity: bool = False,
    stationarity_method: str = "adf",
    stationarity_significance: float = 0.05,

    # NEW: Backtesting (optional)
    run_backtest: bool = False,
    transaction_cost_bps: float = 10.0,
    initial_capital: float = 100000.0,
    trading_days_per_year: int = 252,
    max_leverage: float = 2.0,
    target_volatility: float = 0.10,

    # Canvas mode: skip chart wrapping, return raw data for Canvas to build charts
    _canvas_mode: bool = False
) -> dict:
    """
    Generate mean reversion trading signals based on spread z-scores.

    Supports two modes:
    MODE 1 (Auto): Fetch data from FMP and calculate spread
    MODE 2 (Manual): Use pre-calculated spread

    Args:
        **Mode 1 Parameters (Auto-fetch from FMP):**
        asset_x: Primary asset ticker (e.g., 'GLD')
        asset_y: Hedge asset ticker (e.g., 'GDX')
        hedge_ratio: Beta from hedge ratio tool (e.g., 0.45)
        lookback_period: Historical days for testing (default: 252 = ~1 year)

        **Mode 2 Parameters (Manual spread):**
        spread: Pre-calculated spread series (List[float])
        dates: Date strings matching spread (List[str])

        **Signal Parameters:**
        z_score_entry_long: Z-score threshold to enter LONG (default: -2.0, negative)
        z_score_entry_short: Z-score threshold to enter SHORT (default: 2.0, positive)
        z_score_exit: Z-score threshold to exit (default: 0.5)
        lookback_window: Rolling window for mean/std (default: 20 days)
        direction: "both" | "long_only" | "short_only" (default: "both")
        allow_short: Enable short selling (default: True)
        min_data_points: Minimum data points (default: max(30, lookback_window))

        **Optional Enhancements (NEW):**
        test_stationarity: Run comprehensive stationarity test (default: False)
        stationarity_method: "adf" | "kpss" | "pp" (default: "adf")
        stationarity_significance: P-value threshold (default: 0.05)
        run_backtest: Backtest strategy with realistic costs (default: False)
        transaction_cost_bps: Transaction cost in basis points (default: 10)
        initial_capital: Starting capital for backtest (default: 100,000)
        trading_days_per_year: Trading days for annualization (default: 252)

    Returns:
        Dict with signals, z-scores, spread statistics, 3+ charts
        If test_stationarity=True: adds stationarity_test results
        If run_backtest=True: adds backtest_results and equity curve chart

    Statistical Logic:
        - Rolling z-score: z_t = (spread_t - μ_t) / σ_t
        - LONG when z < z_entry_long (spread cheap)
        - SHORT when z > z_entry_short (spread expensive)
        - EXIT when |z| < z_exit
        - Hysteresis prevents flip-flopping
        - First lookback_window points use expanding window

    Examples:
        # Mode 1: Auto-fetch from FMP
        signals = await generate_mean_reversion_signals(
            asset_x='GLD',
            asset_y='GDX',
            hedge_ratio=0.45,  # From calculate_hedge_ratio tool
            lookback_period=252,  # 1 year of data
            z_score_entry_long=-2.0,
            z_score_entry_short=2.5  # More conservative on shorts
        )

        # Mode 2: Manual spread
        signals = await generate_mean_reversion_signals(
            spread=[0.15, 0.12, ...],
            dates=['2024-01-01', '2024-01-02', ...],
            z_score_entry_long=-2.0,
            z_score_entry_short=2.0
        )
    """
    try:
        # Set default min_data_points
        if min_data_points is None:
            min_data_points = max(30, lookback_window)

        # Determine mode and fetch data if needed
        if asset_x and asset_y and hedge_ratio is not None:
            # MODE 1: Fetch from FMP and calculate spread
            logger.info(f"Mode 1: Fetching data for {asset_x} and {asset_y} from FMP...")

            # Calculate exact date range (FMP doesn't recognize "252d" format)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_period)

            fmp_server = FMPMarketDataServer()

            try:
                await fmp_server.connect()

                # Fetch data for both assets
                result_x = await fmp_server.call_tool("get_historical_data", {
                    "symbol": asset_x,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })
                result_y = await fmp_server.call_tool("get_historical_data", {
                    "symbol": asset_y,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })

                # Validate results
                if not result_x or not hasattr(result_x, 'content'):
                    raise ValueError(f"No data returned for {asset_x}")
                if not result_y or not hasattr(result_y, 'content'):
                    raise ValueError(f"No data returned for {asset_y}")

                # Parse results
                data_x = safe_parse_json(result_x)
                data_y = safe_parse_json(result_y)

                if not data_x or "dates" not in data_x:
                    raise ValueError(f"No data for {asset_x}")
                if not data_y or "dates" not in data_y:
                    raise ValueError(f"No data for {asset_y}")

                # Create DataFrames
                df_x = pd.DataFrame({
                    "date": pd.to_datetime(data_x["dates"]),
                    "price": data_x.get("prices", []) or data_x.get("closes", [])
                })
                df_y = pd.DataFrame({
                    "date": pd.to_datetime(data_y["dates"]),
                    "price": data_y.get("prices", []) or data_y.get("closes", [])
                })

                # Merge on common dates
                merged = pd.merge(df_x, df_y, on="date", suffixes=('_x', '_y'))
                merged = merged.sort_values("date")

                if len(merged) < min_data_points:
                    raise ValueError(f"Insufficient common dates: {len(merged)} (need {min_data_points}+)")

                # Calculate spread: Y - beta * X
                spread = (merged['price_y'] - hedge_ratio * merged['price_x']).tolist()
                dates = merged['date'].dt.strftime('%Y-%m-%d').tolist()

                logger.info(f"Calculated spread from {len(spread)} data points")

            finally:
                await fmp_server.cleanup()

        elif spread is not None and dates is not None:
            # MODE 2: Use provided spread
            logger.info(f"Mode 2: Using provided spread with {len(spread)} data points")

        else:
            raise ValueError(
                "Must provide either:\n"
                "  MODE 1: asset_x, asset_y, hedge_ratio, lookback_period (auto-fetch from FMP)\n"
                "  MODE 2: spread, dates (manual spread)"
            )

        # Input validation
        if not spread or not dates:
            raise ValueError("Spread and dates must be provided or fetched")

        if len(spread) != len(dates):
            raise ValueError(f"Date/spread length mismatch: {len(dates)} dates vs {len(spread)} spread values")

        if len(spread) < min_data_points:
            raise ValueError(f"Insufficient data: {len(spread)} points (need {min_data_points}+)")

        # Direction validation
        if direction not in ["both", "long_only", "short_only"]:
            raise ValueError(f"Invalid direction: {direction}. Must be 'both', 'long_only', or 'short_only'")

        # Override direction if allow_short is False
        if not allow_short and direction == "both":
            direction = "long_only"
            logger.info("allow_short=False, overriding direction to 'long_only'")

        # Threshold validation
        if z_score_entry_long >= 0:
            raise ValueError(f"z_score_entry_long must be negative (got {z_score_entry_long})")

        if z_score_entry_short <= 0:
            raise ValueError(f"z_score_entry_short must be positive (got {z_score_entry_short})")

        if z_score_exit < 0:
            raise ValueError(f"z_score_exit must be non-negative (got {z_score_exit})")

        if abs(z_score_entry_long) <= z_score_exit:
            raise ValueError(f"Long entry threshold ({z_score_entry_long}) magnitude must be > exit ({z_score_exit})")

        if z_score_entry_short <= z_score_exit:
            raise ValueError(f"Short entry threshold ({z_score_entry_short}) must be > exit ({z_score_exit})")

        # Lookback window validation
        if lookback_window >= len(spread):
            raise ValueError(f"Lookback window ({lookback_window}) must be < data length ({len(spread)})")

        if lookback_window < 5:
            raise ValueError(f"Lookback window too small: {lookback_window}. Minimum 5 for stable statistics.")

        # Convert to numpy
        spread_array = np.array(spread, dtype=float)

        # Check for NaN/Inf
        if np.isnan(spread_array).any() or np.isinf(spread_array).any():
            logger.warning("NaN/Inf detected in spread, cleaning...")
            spread_array = np.nan_to_num(spread_array, nan=0.0, posinf=0.0, neginf=0.0)

        # Check for constant spread (σ = 0)
        if np.std(spread_array) < 1e-10:
            raise ValueError("Constant spread detected (σ ≈ 0). Cannot calculate z-scores.")

        # Calculate rolling statistics (expanding window for first lookback_window points)
        spread_series = pd.Series(spread_array)
        window_int = int(lookback_window)  # Ensure integer for pandas
        rolling_mean = spread_series.rolling(window=window_int, min_periods=1).mean().values
        rolling_std = spread_series.rolling(window=window_int, min_periods=1).std().values

        # Replace zero std with small value to avoid division by zero
        rolling_std = np.where(rolling_std < 1e-10, 1e-10, rolling_std)

        # Calculate z-scores
        z_scores = (spread_array - rolling_mean) / rolling_std

        # Generate signals with hysteresis and directional constraints
        signals = np.zeros(len(spread_array), dtype=int)
        current_signal = 0

        for i in range(len(z_scores)):
            z = z_scores[i]

            # Entry logic (respecting direction constraints)
            if z < z_score_entry_long and direction in ["both", "long_only"]:
                current_signal = 1  # LONG (spread is cheap, expect reversion up)
            elif z > z_score_entry_short and direction in ["both", "short_only"]:
                current_signal = -1  # SHORT (spread is expensive, expect reversion down)
            # Exit logic (only from existing position)
            elif abs(z) < z_score_exit:
                current_signal = 0  # FLAT (exit position)
            # Otherwise maintain current position (hysteresis)

            signals[i] = current_signal

        # Detect signal transitions
        transitions = _detect_signal_transitions(signals, dates, z_scores)

        # Signal summary statistics
        signal_counts = {
            'long': int(np.sum(signals == 1)),
            'short': int(np.sum(signals == -1)),
            'flat': int(np.sum(signals == 0))
        }

        # Spread statistics
        spread_stats = {
            'mean': float(np.mean(spread_array)),
            'std': float(np.std(spread_array)),
            'min': float(np.min(spread_array)),
            'max': float(np.max(spread_array)),
            'current': float(spread_array[-1])
        }

        # Z-score statistics
        zscore_stats = {
            'current': float(z_scores[-1]),
            'mean': float(np.mean(z_scores)),
            'std': float(np.std(z_scores)),
            'min': float(np.min(z_scores)),
            'max': float(np.max(z_scores))
        }

        # Optional: Comprehensive stationarity testing
        stationarity_result = None
        if test_stationarity:
            logger.info(f"Running {stationarity_method.upper()} stationarity test...")
            stationarity_result = await _test_stationarity_comprehensive(
                spread_array, stationarity_method, stationarity_significance
            )
            if stationarity_result and not stationarity_result.get('is_stationary'):
                logger.warning(f"⚠️ {stationarity_result.get('recommendation')}")

        # Generate charts
        chart_id = f"signals_{abs(hash(dates[0]))&0xFFFF:04x}"
        charts = []

        # Chart 1: Spread with bands
        spread_chart = await _build_spread_bands_chart(
            spread_array, dates, rolling_mean, rolling_std,
            z_score_entry_long, z_score_entry_short, chart_id
        )
        if spread_chart:
            charts.append(spread_chart)

        # Chart 2: Z-score
        zscore_chart = await _build_zscore_chart(
            z_scores, dates, signals,
            z_score_entry_long, z_score_entry_short, z_score_exit,
            chart_id
        )
        if zscore_chart:
            charts.append(zscore_chart)

        # Chart 3: Signal timeline
        timeline_chart = await _build_signal_timeline_chart(
            signals, dates, transitions, chart_id
        )
        if timeline_chart:
            charts.append(timeline_chart)

        # Optional: Backtest strategy
        backtest_result = None
        if run_backtest:
            logger.info(f"Running backtest with {transaction_cost_bps} bps transaction costs...")
            backtest_result = await _run_backtest(
                signals, spread_array, dates, transaction_cost_bps, initial_capital, trading_days_per_year,
                max_leverage, target_volatility
            )

            # Chart 4: Backtest performance
            if backtest_result and 'equity_curve' in backtest_result:
                backtest_chart = await _build_backtest_chart(
                    backtest_result['equity_curve']['values'],
                    backtest_result['equity_curve']['dates'],
                    backtest_result['equity_curve']['drawdowns'],
                    chart_id
                )
                if backtest_chart:
                    charts.append(backtest_chart)

        # Prepare results
        results = {
            'signals': {
                'time_series': signals.tolist(),
                'dates': dates,
                'current_signal': int(signals[-1]),
                'last_transition': transitions[-1] if transitions else None
            },
            'z_scores': {
                'time_series': z_scores.tolist(),
                **zscore_stats
            },
            'spread_statistics': spread_stats,
            'signal_summary': {
                'total_periods': len(signals),
                'long_periods': signal_counts['long'],
                'short_periods': signal_counts['short'],
                'flat_periods': signal_counts['flat'],
                'total_transitions': len(transitions),
                'long_percentage': round(100 * signal_counts['long'] / len(signals), 2),
                'short_percentage': round(100 * signal_counts['short'] / len(signals), 2),
                'flat_percentage': round(100 * signal_counts['flat'] / len(signals), 2)
            },
            'parameters': {
                'z_score_entry_long': z_score_entry_long,
                'z_score_entry_short': z_score_entry_short,
                'z_score_exit': z_score_exit,
                'lookback_window': lookback_window,
                'direction': direction,
                'allow_short': allow_short,
                'min_data_points': min_data_points
            },
            # Raw data for Canvas chart building
            'raw_data': {
                'spread': spread_array.tolist(),
                'dates': dates,
                'z_scores': z_scores.tolist(),
                'signals': signals.tolist(),
                'rolling_mean': rolling_mean.tolist(),
                'rolling_std': rolling_std.tolist(),
                'transitions': transitions,
            }
        }

        # Add optional enhancements to results
        if stationarity_result:
            results['stationarity_test'] = stationarity_result

        if backtest_result:
            results['backtest'] = backtest_result

        # Canvas mode: return raw data without chart wrapping
        if _canvas_mode:
            return jsonify_results({
                'status': 'success',
                'results': results,
                'charts': []  # Canvas builds its own charts
            })

        # Agent mode: wrap charts for storage
        charts = wrap_plotly_charts(charts, default_type="mean_reversion_chart")

        return jsonify_results({
            'status': 'success',
            'results': results,
            'charts': charts
        })

    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        error_type = 'data_error' if any(
            kw in str(e).lower() for kw in ['insufficient', 'mismatch', 'constant', 'zero']
        ) else 'calculation_error'

        return {
            'status': 'error',
            'error': str(e),
            'error_type': error_type,
            'calculation_type': 'mean_reversion_signals'
        }


# Canvas-friendly internal function (returns raw data for Canvas to build charts)
async def generate_mean_reversion_signals_internal(
    ticker: str,
    lookback_period: int = 120,
    z_score_entry_long: float = -2.0,
    z_score_entry_short: float = 2.0,
    z_score_exit: float = 0.5,
    lookback_window: int = 20,
    direction: str = "both",
    test_stationarity: bool = True,
    run_backtest: bool = True,
    transaction_cost_bps: float = 10.0,
) -> dict:
    """
    Canvas-friendly mean reversion signals for a SINGLE ticker.
    
    For single-ticker mean reversion, we use price z-score (deviation from rolling mean).
    This identifies overbought/oversold conditions relative to recent history.
    
    Args:
        ticker: Stock ticker symbol
        lookback_period: Days of historical data (default: 120 = ~6 months)
        z_score_entry_long: Z-score to go long (default: -2.0, price is cheap)
        z_score_entry_short: Z-score to go short (default: 2.0, price is expensive)
        z_score_exit: Z-score to exit position (default: 0.5)
        lookback_window: Rolling window for mean/std (default: 20 days)
        direction: "both" | "long_only" | "short_only"
        test_stationarity: Run ADF stationarity test
        run_backtest: Run strategy backtest
        transaction_cost_bps: Transaction costs in basis points
    
    Returns:
        Dict with signals, z-scores, statistics, and raw data for chart building.
    """
    try:
        logger.info(f"Generating mean reversion signals for {ticker}")
        
        # Fetch price data
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_period + 30)  # Extra buffer
        
        fmp_server = FMPMarketDataServer()
        
        try:
            await fmp_server.connect()
            
            result = await fmp_server.call_tool("get_historical_data", {
                "symbol": ticker,
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            })
            
            if not result or not hasattr(result, 'content'):
                raise ValueError(f"No data returned for {ticker}")
            
            data = safe_parse_json(result)
            
            if not data or "dates" not in data:
                raise ValueError(f"No price data for {ticker}")
            
            dates = data["dates"][-lookback_period:]
            prices = (data.get("prices", []) or data.get("closes", []))[-lookback_period:]
            
            if len(prices) < lookback_window + 10:
                raise ValueError(f"Insufficient data: {len(prices)} days")
            
        finally:
            await fmp_server.cleanup()
        
        # For single ticker, use price as the "spread" (deviation from rolling mean)
        # This is the classic Bollinger Band / z-score mean reversion approach
        return await _generate_mean_reversion_signals_impl(
            spread=prices,
            dates=dates,
            z_score_entry_long=z_score_entry_long,
            z_score_entry_short=z_score_entry_short,
            z_score_exit=z_score_exit,
            lookback_window=lookback_window,
            direction=direction,
            test_stationarity=test_stationarity,
            stationarity_method="adf",
            run_backtest=run_backtest,
            transaction_cost_bps=transaction_cost_bps,
            _canvas_mode=True  # Return raw data for Canvas
        )
        
    except Exception as e:
        logger.error(f"Mean reversion signals failed for {ticker}: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'ticker': ticker
        }


@function_tool
async def generate_mean_reversion_signals(
    # Mode 1: Auto-fetch and calculate (NEW)
    asset_x: Optional[str] = None,
    asset_y: Optional[str] = None,
    hedge_ratio: Optional[float] = None,
    lookback_period: int = 252,

    # Mode 2: Manual spread (EXISTING - backward compatible)
    spread: Optional[List[float]] = None,
    dates: Optional[List[str]] = None,

    # Signal parameters
    z_score_entry_long: float = -2.0,
    z_score_entry_short: float = 2.0,
    z_score_exit: float = 0.5,
    lookback_window: int = 20,
    direction: str = "both",
    allow_short: bool = True,
    min_data_points: Optional[int] = None,

    # NEW: Stationarity testing (optional)
    test_stationarity: bool = False,
    stationarity_method: str = "adf",
    stationarity_significance: float = 0.05,

    # NEW: Backtesting (optional)
    run_backtest: bool = False,
    transaction_cost_bps: float = 10.0,
    initial_capital: float = 100000.0,
    trading_days_per_year: int = 252,
    max_leverage: float = 2.0,
    target_volatility: float = 0.10
) -> dict:
    """
    Generate mean reversion trading signals based on spread z-scores.

    Supports two modes:
    MODE 1 (Auto): Fetch data from FMP and calculate spread
    MODE 2 (Manual): Use pre-calculated spread

    Args:
        **Mode 1 Parameters (Auto-fetch from FMP):**
        asset_x: Primary asset ticker (e.g., 'GLD')
        asset_y: Hedge asset ticker (e.g., 'GDX')
        hedge_ratio: Beta from hedge ratio tool (e.g., 0.45)
        lookback_period: Historical days for testing (default: 252 = ~1 year)

        **Mode 2 Parameters (Manual spread):**
        spread: Pre-calculated spread series (List[float])
        dates: Date strings matching spread (List[str])

        **Signal Parameters:**
        z_score_entry_long: Z-score threshold to enter LONG (default: -2.0, negative)
        z_score_entry_short: Z-score threshold to enter SHORT (default: 2.0, positive)
        z_score_exit: Z-score threshold to exit (default: 0.5)
        lookback_window: Rolling window for mean/std (default: 20 days)
        direction: "both" | "long_only" | "short_only" (default: "both")
        allow_short: Enable short selling (default: True)
        min_data_points: Minimum data points (default: max(30, lookback_window))

        **Optional Enhancements (NEW):**
        test_stationarity: Run comprehensive stationarity test (default: False)
        stationarity_method: "adf" | "kpss" | "pp" (default: "adf")
        stationarity_significance: P-value threshold (default: 0.05)
        run_backtest: Backtest strategy with realistic costs (default: False)
        transaction_cost_bps: Transaction cost in basis points (default: 10)
        initial_capital: Starting capital for backtest (default: 100,000)
        trading_days_per_year: Trading days for annualization (default: 252)

    Returns:
        Dict with signals, z-scores, spread statistics, 3+ charts
        If test_stationarity=True: adds stationarity_test results
        If run_backtest=True: adds backtest_results and equity curve chart

    Statistical Logic:
        - Rolling z-score: z_t = (spread_t - μ_t) / σ_t
        - LONG when z < z_entry_long (spread cheap)
        - SHORT when z > z_entry_short (spread expensive)
        - EXIT when |z| < z_exit
        - Hysteresis prevents flip-flopping
        - First lookback_window points use expanding window

    Examples:
        # Mode 1: Auto-fetch from FMP
        signals = await generate_mean_reversion_signals(
            asset_x='GLD',
            asset_y='GDX',
            hedge_ratio=0.45,  # From calculate_hedge_ratio tool
            lookback_period=252,  # 1 year of data
            z_score_entry_long=-2.0,
            z_score_entry_short=2.5  # More conservative on shorts
        )

        # Mode 2: Manual spread
        signals = await generate_mean_reversion_signals(
            spread=[0.15, 0.12, ...],
            dates=['2024-01-01', '2024-01-02', ...],
            z_score_entry_long=-2.0,
            z_score_entry_short=2.0
        )
    """
    return await _generate_mean_reversion_signals_impl(
        asset_x=asset_x,
        asset_y=asset_y,
        hedge_ratio=hedge_ratio,
        lookback_period=lookback_period,
        spread=spread,
        dates=dates,
        z_score_entry_long=z_score_entry_long,
        z_score_entry_short=z_score_entry_short,
        z_score_exit=z_score_exit,
        lookback_window=lookback_window,
        direction=direction,
        allow_short=allow_short,
        min_data_points=min_data_points,
        test_stationarity=test_stationarity,
        stationarity_method=stationarity_method,
        stationarity_significance=stationarity_significance,
        run_backtest=run_backtest,
        transaction_cost_bps=transaction_cost_bps,
        initial_capital=initial_capital,
        trading_days_per_year=trading_days_per_year,
        max_leverage=max_leverage,
        target_volatility=target_volatility,
        _canvas_mode=False  # Agent mode: wrap charts
    )
