"""Canvas executor for Mean Reversion Signals tool."""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def execute_mean_reversion(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute mean reversion signal generation for Canvas.
    
    Returns z-score based trading signals with stationarity testing and backtesting.
    """
    from core.agents.quant_tools.mean_reversion_signals_tool import generate_mean_reversion_signals_internal
    from .charts import (
        build_spread_bands_chart,
        build_zscore_chart,
        build_signal_timeline_chart,
        build_backtest_chart,
    )
    
    # Extract parameters (ensure integers for window params)
    ticker = params.get("ticker", "SPY")
    lookback_period = int(params.get("lookback_period", 120))
    z_entry_long = float(params.get("z_score_entry_long", -2.0))
    z_entry_short = float(params.get("z_score_entry_short", 2.0))
    z_exit = float(params.get("z_score_exit", 0.5))
    lookback_window = int(params.get("lookback_window", 20))
    direction = params.get("direction", "both")
    test_stationarity = params.get("test_stationarity", True)
    run_backtest = params.get("run_backtest", True)
    transaction_cost_bps = float(params.get("transaction_cost_bps", 10.0))
    
    logger.info(f"Executing mean reversion signals for {ticker}")
    
    try:
        # Call internal function
        result = await generate_mean_reversion_signals_internal(
            ticker=ticker,
            lookback_period=lookback_period,
            z_score_entry_long=z_entry_long,
            z_score_entry_short=z_entry_short,
            z_score_exit=z_exit,
            lookback_window=lookback_window,
            direction=direction,
            test_stationarity=test_stationarity,
            run_backtest=run_backtest,
            transaction_cost_bps=transaction_cost_bps,
        )
        
        if result.get('status') == 'error':
            return {
                "status": "error",
                "error": result.get('error', 'Mean reversion analysis failed'),
                "charts": {},
                "metric_cards": [],
                "stats_table": {"headers": [], "rows": []},
            }
        
        results_data = result.get('results', {})
        raw_data = results_data.get('raw_data', {})
        
        # Extract raw data for chart building
        spread = raw_data.get('spread', [])
        dates = raw_data.get('dates', [])
        z_scores = raw_data.get('z_scores', [])
        signals = raw_data.get('signals', [])
        rolling_mean = raw_data.get('rolling_mean', [])
        rolling_std = raw_data.get('rolling_std', [])
        transitions = raw_data.get('transitions', [])
        
        # Build charts
        charts = {}
        
        # Chart 1: Spread with bands
        spread_chart = build_spread_bands_chart(
            ticker, spread, dates, rolling_mean, rolling_std, z_entry_long, z_entry_short
        )
        if spread_chart:
            charts["spread_bands"] = spread_chart
        
        # Chart 2: Z-score with thresholds
        zscore_chart = build_zscore_chart(
            ticker, z_scores, dates, signals, z_entry_long, z_entry_short, z_exit
        )
        if zscore_chart:
            charts["zscore"] = zscore_chart
        
        # Chart 3: Signal timeline
        timeline_chart = build_signal_timeline_chart(ticker, signals, dates, transitions)
        if timeline_chart:
            charts["signal_timeline"] = timeline_chart
        
        # Chart 4: Backtest (if available)
        backtest = results_data.get('backtest', {})
        if backtest and 'equity_curve' in backtest:
            eq_curve = backtest['equity_curve']
            bt_chart = build_backtest_chart(
                ticker, eq_curve.get('values', []), eq_curve.get('dates', []), eq_curve.get('drawdowns', [])
            )
            if bt_chart:
                charts["backtest"] = bt_chart
        
        logger.info(f"Built {len(charts)} charts for {ticker}")
        
        # Build metric cards - use `or 0` pattern to handle None values
        zscore_stats = results_data.get('z_scores', {}) or {}
        signal_summary = results_data.get('signal_summary', {}) or {}
        stationarity = results_data.get('stationarity_test', {}) or {}
        backtest_perf = (backtest.get('performance', {}) or {}) if backtest else {}
        
        current_signal = (results_data.get('signals', {}) or {}).get('current_signal', 0) or 0
        signal_label = "LONG" if current_signal == 1 else "SHORT" if current_signal == -1 else "FLAT"
        signal_sentiment = "positive" if current_signal == 1 else ("negative" if current_signal == -1 else "neutral")
        
        # Helper to safely format numbers
        def safe_fmt(val, fmt=".2f"):
            if val is None:
                return "N/A"
            try:
                return f"{float(val):{fmt}}"
            except (ValueError, TypeError):
                return str(val)
        
        current_z = zscore_stats.get('current') or 0
        metric_cards = [
            {"id": "current_signal", "label": "Current Signal", "value": signal_label, "sentiment": signal_sentiment},
            {"id": "current_zscore", "label": "Current Z-Score", "value": f"{safe_fmt(current_z)}σ", "sentiment": "neutral"},
            {"id": "is_stationary", "label": "Is Stationary", "value": "Yes ✓" if stationarity.get('is_stationary') else "No ⚠️",
             "sentiment": "positive" if stationarity.get('is_stationary') else "neutral"},
        ]
        
        if backtest_perf:
            sharpe = backtest_perf.get('sharpe_ratio') or 0
            total_ret = backtest_perf.get('total_return') or 0
            max_dd = backtest_perf.get('max_drawdown') or 0
            metric_cards.extend([
                {"id": "backtest_return", "label": "Backtest Return", "value": f"{safe_fmt(total_ret * 100, '.1f')}%",
                 "sentiment": "positive" if total_ret > 0 else "negative"},
                {"id": "sharpe_ratio", "label": "Sharpe Ratio", "value": safe_fmt(sharpe),
                 "sentiment": "positive" if sharpe > 1 else ("neutral" if sharpe > 0 else "negative")},
                {"id": "max_drawdown", "label": "Max Drawdown", "value": f"{safe_fmt(max_dd * 100, '.1f')}%", "sentiment": "negative"},
            ])
        
        # Build stats table as List[Dict] format
        stats_table = [
            {"category": "Signal Stats", "metric": "Long Periods", "value": f"{signal_summary.get('long_periods') or 0} ({safe_fmt((signal_summary.get('long_percentage') or 0), '.1f')}%)"},
            {"category": "Signal Stats", "metric": "Short Periods", "value": f"{signal_summary.get('short_periods') or 0} ({safe_fmt((signal_summary.get('short_percentage') or 0), '.1f')}%)"},
            {"category": "Signal Stats", "metric": "Flat Periods", "value": f"{signal_summary.get('flat_periods') or 0} ({safe_fmt((signal_summary.get('flat_percentage') or 0), '.1f')}%)"},
            {"category": "Signal Stats", "metric": "Total Transitions", "value": str(signal_summary.get('total_transitions') or 0)},
            {"category": "Z-Score", "metric": "Current Z", "value": safe_fmt(zscore_stats.get('current'), '.3f')},
            {"category": "Z-Score", "metric": "Mean", "value": safe_fmt(zscore_stats.get('mean'), '.3f')},
            {"category": "Z-Score", "metric": "Std Dev", "value": safe_fmt(zscore_stats.get('std'), '.3f')},
            {"category": "Z-Score", "metric": "Range", "value": f"{safe_fmt(zscore_stats.get('min'))} to {safe_fmt(zscore_stats.get('max'))}"},
        ]
        
        if stationarity:
            stats_table.extend([
                {"category": "Stationarity", "metric": "Test", "value": "ADF"},
                {"category": "Stationarity", "metric": "Statistic", "value": safe_fmt(stationarity.get('test_statistic'), '.3f')},
                {"category": "Stationarity", "metric": "P-Value", "value": safe_fmt(stationarity.get('p_value'), '.4f')},
                {"category": "Stationarity", "metric": "Result", "value": "Stationary ✓" if stationarity.get('is_stationary') else "Non-stationary ⚠️"},
            ])
        
        if backtest_perf:
            trades = backtest.get('trades', {}) or {}
            stats_table.extend([
                {"category": "Backtest", "metric": "Total Return", "value": f"{safe_fmt((backtest_perf.get('total_return') or 0) * 100)}%"},
                {"category": "Backtest", "metric": "Annual Return", "value": f"{safe_fmt((backtest_perf.get('annualized_return') or 0) * 100)}%"},
                {"category": "Backtest", "metric": "Sharpe Ratio", "value": safe_fmt(backtest_perf.get('sharpe_ratio'))},
                {"category": "Backtest", "metric": "Max Drawdown", "value": f"{safe_fmt((backtest_perf.get('max_drawdown') or 0) * 100)}%"},
                {"category": "Backtest", "metric": "Win Rate", "value": f"{safe_fmt((trades.get('win_rate') or 0) * 100, '.1f')}%"},
                {"category": "Backtest", "metric": "Total Trades", "value": str(trades.get('total_trades') or 0)},
            ])
        
        return {
            "status": "success",
            "tool_id": "mean_reversion",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "current_signal": signal_label,
                "current_zscore": current_z,
                "is_stationary": stationarity.get('is_stationary', False),
            },
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "summary": f"Mean reversion analysis for {ticker}: Current signal is {signal_label} (z={safe_fmt(current_z)}). "
                       f"{'Spread is stationary ✓' if stationarity.get('is_stationary') else 'Warning: Spread may not be stationary ⚠️'}",
        }
        
    except Exception as e:
        logger.error(f"Mean reversion execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "charts": {},
            "metric_cards": [],
            "stats_table": {"headers": [], "rows": []},
        }
