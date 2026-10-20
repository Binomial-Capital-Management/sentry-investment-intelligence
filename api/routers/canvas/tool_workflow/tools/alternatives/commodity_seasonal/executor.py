"""
Commodity Seasonality Canvas Executor
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def execute_commodity_seasonal(
    user_id: str,
    org_id: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute commodity seasonality analysis for Canvas."""
    from core.agents.alternatives_tools.commodity_seasonality_tool import analyze_commodity_seasonality_internal
    from .charts import build_seasonality_chart
    
    symbol = params.get('symbol')
    if not symbol:
        return {"status": "error", "error": "Commodity symbol is required"}
    
    # Extract ticker from "Name (TICKER)" format
    if '(' in symbol and ')' in symbol:
        symbol = symbol.split('(')[1].split(')')[0].strip()
    
    symbol = symbol.upper()
    
    try:
        # Extract parameters
        years_history = int(params.get('years_history', 2))
        years_history = min(max(years_history, 1), 5)  # Clamp 1-5 years
        
        logger.info(f"Analyzing seasonality for {symbol} over {years_history} years")
        
        # Call internal function (without chart generation - we'll rebuild)
        result = await analyze_commodity_seasonality_internal(
            symbol=symbol,
            years_history=years_history,
            generate_chart=False  # We'll build our own chart
        )
        
        if result.get("error"):
            return {"status": "error", "error": result["error"]}
        
        # Extract values
        current_context = result.get("current_context", {})
        signal = result.get("signal", {})
        best_months = result.get("best_months", [])
        worst_months = result.get("worst_months", [])
        
        ytd_return = current_context.get("ytd_return_pct", 0)
        ytd_z = current_context.get("ytd_z_score", 0)
        expected_ytd = current_context.get("expected_ytd_pct", 0)
        current_month = current_context.get("current_month", "")
        
        bias = signal.get("bias", "NEUTRAL")
        strength = signal.get("strength", "WEAK")
        expected_3m = signal.get("3m_expected_return", 0)
        avg_win_rate = signal.get("3m_avg_win_rate", 50)
        deviation_signal = signal.get("deviation_signal", "")
        
        # Build metric cards
        metric_cards = [
            {
                "id": "ytd_performance",
                "label": f"YTD Performance ({current_month})",
                "value": f"{ytd_return:+.2f}%",
                "sentiment": "positive" if ytd_return > 0 else "negative" if ytd_return < 0 else "neutral",
                "description": f"Expected: {expected_ytd:+.1f}%"
            },
            {
                "id": "ytd_z_score",
                "label": "YTD Z-Score",
                "value": f"{ytd_z:.2f}σ",
                "sentiment": "positive" if abs(ytd_z) < 1 else "negative" if abs(ytd_z) > 2 else "neutral",
                "description": deviation_signal
            },
            {
                "id": "seasonal_bias",
                "label": "3M Seasonal Bias",
                "value": f"{bias} ({strength})",
                "sentiment": "positive" if bias == "BULLISH" else "negative" if bias == "BEARISH" else "neutral",
                "description": f"Expected: {expected_3m:+.1f}%"
            },
            {
                "id": "win_rate",
                "label": "3M Avg Win Rate",
                "value": f"{avg_win_rate:.0f}%",
                "sentiment": "positive" if avg_win_rate > 60 else "negative" if avg_win_rate < 40 else "neutral",
                "description": "Historical success rate"
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Symbol", "metric": "Commodity", "value": symbol},
            {"category": "Analysis", "metric": "History Period", "value": f"{years_history} years"},
            {"category": "Analysis", "metric": "Data Points", "value": f"{result.get('data_points', 0):,} days"},
            {"category": "Current", "metric": "YTD Return", "value": f"{ytd_return:+.2f}%"},
            {"category": "Current", "metric": "YTD Z-Score", "value": f"{ytd_z:.2f}σ"},
            {"category": "Current", "metric": "vs Expected", "value": f"{ytd_return - expected_ytd:+.2f}%"},
            {"category": "Forecast", "metric": "3M Bias", "value": f"{bias} ({strength})"},
            {"category": "Forecast", "metric": "3M Expected Return", "value": f"{expected_3m:+.2f}%"},
            {"category": "Forecast", "metric": "3M Win Rate", "value": f"{avg_win_rate:.0f}%"},
        ]
        
        # Add best/worst months
        if best_months:
            for i, m in enumerate(best_months[:3], 1):
                stats_table.append({
                    "category": "Best Months",
                    "metric": m['month'],
                    "value": f"{m['return']:+.1f}%"
                })
        
        if worst_months:
            for i, m in enumerate(worst_months[:3], 1):
                stats_table.append({
                    "category": "Worst Months",
                    "metric": m['month'],
                    "value": f"{m['return']:+.1f}%"
                })
        
        # Build charts
        charts = {}
        
        # We need to reconstruct seasonal_stats from the result
        # The internal function doesn't return it directly, but we can infer from monthly_table
        # For now, let's pass the result dict which contains everything needed
        seasonality_chart = build_seasonality_chart(
            symbol=symbol,
            result=result,
            current_context=current_context
        )
        if seasonality_chart:
            charts["seasonality"] = seasonality_chart
        
        # Format summary
        summary = (
            f"{symbol} Seasonality Analysis ({years_history}Y): "
            f"YTD {ytd_return:+.1f}% (Z={ytd_z:.2f}), "
            f"3M outlook: {bias} ({expected_3m:+.1f}% expected, {avg_win_rate:.0f}% win rate). "
            f"Best months: {', '.join(m['month'] for m in best_months[:3])}. "
            f"Worst months: {', '.join(m['month'] for m in worst_months[:3])}."
        )
        
        return {
            "status": "success",
            "tool_id": "commodity_seasonal",
            "tickers": [symbol],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "symbol": symbol,
                "years_history": years_history,
                "ytd_return": ytd_return,
                "ytd_z_score": ytd_z,
                "bias": bias,
                "expected_3m": expected_3m
            },
            "summary": summary,
        }
    
    except Exception as e:
        logger.error(f"Commodity seasonality analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
