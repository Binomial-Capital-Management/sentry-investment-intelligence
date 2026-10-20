"""
Canvas executor for Earnings Pattern Analyzer.

Analyzes historical earnings patterns to identify vol trading opportunities.
Compares expected vs actual moves, tracks vol crush rates, and generates
strategy signals (SELL_VOL/BUY_VOL/NEUTRAL).
"""

import logging
from typing import Any, Dict, Optional

from core.agents.quant_tools.earnings_pattern_analyzer import analyze_earnings_patterns_internal
from .charts import build_move_comparison_chart, build_straddle_returns_chart

logger = logging.getLogger(__name__)


def _safe_float(val, default=0.0) -> float:
    """Safely convert value to float."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace('%', '').replace('x', '').replace('$', '').replace(',', '').strip()
        try:
            return float(cleaned) if cleaned else default
        except ValueError:
            return default
    return default


async def execute_earnings_pattern(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute earnings pattern analysis for Canvas.
    
    Args:
        user_id: User ID
        org_id: Organization ID
        params: Tool parameters
    
    Returns:
        Canvas-formatted response
    """
    # Extract parameters
    ticker = params.get("ticker", "").strip().upper()
    if not ticker:
        return {
            "status": "error",
            "error": "Ticker is required",
            "tool_id": "earnings_pattern",
        }
    
    lookback_quarters = int(params.get("lookback_quarters", 8))
    
    logger.info(f"Executing Earnings Pattern analysis for {ticker}")
    
    try:
        # Call internal function
        result = await analyze_earnings_patterns_internal(
            ticker=ticker,
            lookback_quarters=lookback_quarters,
            include_chart=False,  # We'll build Canvas charts
            include_historical_detail=True,
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Analysis failed"),
                "tool_id": "earnings_pattern",
            }
        
        # Extract data
        historical_stats = result.get("historical_stats", {})
        vol_analysis = result.get("vol_analysis", {})
        strategy = result.get("strategy", {})
        next_earnings = result.get("next_earnings", {})
        historical_detail = result.get("historical_detail", [])
        current_vol = result.get("current_vol_snapshot", {})
        
        # Build metric cards
        metric_cards = []
        
        # Strategy signal
        signal = strategy.get("signal", "NEUTRAL")
        confidence = strategy.get("confidence", "LOW")
        signal_color = "positive" if signal == "SELL_VOL" else ("negative" if signal == "BUY_VOL" else "neutral")
        
        metric_cards.append({
            "id": "signal",
            "label": "Vol Signal",
            "value": signal.replace("_", " "),
            "sentiment": signal_color,
            "description": f"{confidence} confidence",
        })
        
        # Vol crush rate
        vol_crush_rate = _safe_float(historical_stats.get("vol_crush_rate", 0))
        metric_cards.append({
            "id": "vol_crush_rate",
            "label": "Vol Crush Rate",
            "value": f"{vol_crush_rate * 100:.0f}%",
            "sentiment": "positive" if vol_crush_rate > 0.6 else ("negative" if vol_crush_rate < 0.4 else "neutral"),
            "description": "Actual < Expected move",
        })
        
        # Beat rate
        beat_rate = _safe_float(historical_stats.get("eps_beat_rate", 0))
        metric_cards.append({
            "id": "beat_rate",
            "label": "EPS Beat Rate",
            "value": f"{beat_rate * 100:.0f}%",
            "sentiment": "positive" if beat_rate > 0.7 else ("negative" if beat_rate < 0.5 else "neutral"),
            "description": f"{historical_stats.get('eps_beat_count', 0)}/{historical_stats.get('quarters_with_eps_data', 0)} quarters",
        })
        
        # Avg short straddle return
        avg_straddle = _safe_float(historical_stats.get("avg_short_straddle_return", 0))
        metric_cards.append({
            "id": "straddle_return",
            "label": "Avg Straddle Return",
            "value": f"{avg_straddle:+.1f}%",
            "sentiment": "positive" if avg_straddle > 10 else ("negative" if avg_straddle < -10 else "neutral"),
            "description": "Historical short straddle",
        })
        
        # Next earnings
        if next_earnings and next_earnings.get("date"):
            expected_move = _safe_float(next_earnings.get("expected_move_pct", 0))
            metric_cards.append({
                "id": "next_earnings",
                "label": "Next Earnings",
                "value": next_earnings.get("date", "")[:10],
                "sentiment": "neutral",
                "description": f"Expected move: ±{expected_move:.1f}%" if expected_move else "",
            })
        
        # Build stats table
        avg_expected = _safe_float(historical_stats.get("avg_expected_move_pct", 0))
        avg_actual = _safe_float(historical_stats.get("avg_actual_move_pct", 0))
        move_ratio = _safe_float(historical_stats.get("move_ratio", 0))
        avg_surprise = _safe_float(historical_stats.get("avg_eps_surprise_pct", 0))
        iv_percentile = _safe_float(vol_analysis.get("current_percentile", 0))
        z_score = _safe_float(vol_analysis.get("current_z_score", 0))
        
        stats_table = [
            {"category": "Vol Pattern", "metric": "Vol Crush Rate", "value": f"{vol_crush_rate * 100:.0f}%"},
            {"category": "Vol Pattern", "metric": "Avg Expected Move", "value": f"±{avg_expected:.1f}%"},
            {"category": "Vol Pattern", "metric": "Avg Actual Move", "value": f"±{avg_actual:.1f}%"},
            {"category": "Vol Pattern", "metric": "Move Ratio", "value": f"{move_ratio:.2f}x"},
            {"category": "EPS History", "metric": "Beat Rate", "value": f"{beat_rate * 100:.0f}%"},
            {"category": "EPS History", "metric": "Avg EPS Surprise", "value": f"{avg_surprise:+.1f}%"},
            {"category": "Current IV", "metric": "IV Percentile", "value": f"{iv_percentile:.0f}th"},
            {"category": "Current IV", "metric": "Z-Score", "value": f"{z_score:+.2f}σ"},
            {"category": "Straddle", "metric": "Avg Return", "value": f"{avg_straddle:+.1f}%"},
            {"category": "Straddle", "metric": "Win Rate", "value": f"{_safe_float(historical_stats.get('short_straddle_win_rate', 0)) * 100:.0f}%"},
        ]
        
        # Build charts
        charts = {}
        
        # Chart 1: Expected vs Actual Move comparison
        try:
            move_chart = build_move_comparison_chart(ticker, historical_detail)
            if move_chart:
                charts["move_comparison"] = move_chart
        except Exception as e:
            logger.warning(f"Failed to build move comparison chart: {e}")
        
        # Chart 2: Short straddle returns
        try:
            straddle_chart = build_straddle_returns_chart(ticker, historical_detail)
            if straddle_chart:
                charts["straddle_returns"] = straddle_chart
        except Exception as e:
            logger.warning(f"Failed to build straddle returns chart: {e}")
        
        logger.info(f"Built {len(charts)} charts for {ticker} earnings pattern")
        
        # Build strategy ideas
        ideas = strategy.get("ideas", [])
        rationale = strategy.get("rationale", [])
        
        summary_parts = [f"{ticker}: {signal.replace('_', ' ')} signal ({confidence} confidence)."]
        if rationale:
            summary_parts.append(rationale[0])
        if ideas:
            summary_parts.append(f"Ideas: {ideas[0]}")
        
        return {
            "status": "success",
            "tool_id": "earnings_pattern",
            "tickers": [ticker],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "signal": signal,
                "confidence": confidence,
                "vol_crush_rate": vol_crush_rate,
                "beat_rate": beat_rate,
                "avg_expected_move": avg_expected,
                "avg_actual_move": avg_actual,
                "avg_straddle_return": avg_straddle,
                "iv_percentile": iv_percentile,
                "z_score": z_score,
            },
            "strategy": {
                "signal": signal,
                "confidence": confidence,
                "rationale": rationale,
                "ideas": ideas,
            },
            "next_earnings": next_earnings,
            "summary": " ".join(summary_parts),
        }
        
    except Exception as e:
        logger.error(f"Earnings pattern execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "earnings_pattern",
        }
