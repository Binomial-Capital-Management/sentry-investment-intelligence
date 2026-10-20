"""
Canvas executor for Commodity Ratio.

Analyzes any commodity ratio for mean reversion trading opportunities.
Supports preset pairs (Gold/Silver, Gold/Oil, etc.) or custom symbols.
"""

import logging
from typing import Any, Dict, List, Optional

from .charts import build_ratio_history_chart, build_regime_chart, build_zscore_chart

logger = logging.getLogger(__name__)


async def execute_commodity_ratio(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute commodity ratio analysis for Canvas.
    """
    from core.agents.alternatives_tools.commodity_ratio_tool import (
        analyze_commodity_ratio_internal,
        PRESET_PAIRS,
    )
    
    # Extract parameters
    preset = params.get("preset", "gold_silver")
    numerator = params.get("numerator")
    denominator = params.get("denominator")
    lookback_days = int(params.get("lookback_days", 365))
    high_z = float(params.get("high_z_threshold", 1.5))
    low_z = float(params.get("low_z_threshold", -1.5))
    
    # Resolve pair name for logging
    if preset == "custom":
        pair_name = f"{numerator}/{denominator}" if numerator and denominator else "Custom"
    else:
        pair_config = PRESET_PAIRS.get(preset, {})
        pair_name = pair_config.get("name", preset)
    
    logger.info(f"Executing Commodity Ratio analysis: {pair_name}, {lookback_days} day lookback")
    
    try:
        # Call internal function - NO chart generation, we build our own
        result = await analyze_commodity_ratio_internal(
            preset=preset,
            numerator=numerator,
            denominator=denominator,
            lookback_days=lookback_days,
            high_z_threshold=high_z,
            low_z_threshold=low_z,
            generate_chart=False,
        )
        
        if "error" in result:
            return {
                "status": "error",
                "error": result.get("error", "Analysis failed"),
                "tool_id": "commodity_ratio",
            }
        
        # Extract key data
        current_ratio = result.get("current_ratio", 0)
        num_info = result.get("numerator", {})
        denom_info = result.get("denominator", {})
        regime = result.get("regime", {})
        analysis_period = result.get("analysis_period", {})
        pair_name = result.get("pair_name", "")
        historical_series = result.get("historical_series", {})
        
        # Regime details
        regime_name = regime.get("regime", "UNKNOWN")
        signal = regime.get("signal", "NO TRADE")
        confidence = regime.get("confidence", 0)
        z_score = regime.get("ratio_z_score", 0)
        percentile = regime.get("ratio_percentile", 50)
        trade_idea = regime.get("trade_idea", "")
        historical = regime.get("historical_context", {})
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            current_ratio, pair_name,
            num_info.get("name", "Num"), denom_info.get("name", "Denom"),
            regime_name, signal, confidence, z_score, percentile,
            lookback_days
        )
        
        # Build stats table
        stats_table = _build_stats_table(
            result, regime, historical, analysis_period, num_info, denom_info
        )
        
        # Build charts from historical_series data
        charts = {}
        
        # Main ratio history chart
        if historical_series:
            ratio_chart = build_ratio_history_chart(
                dates=historical_series.get("dates", []),
                num_prices=historical_series.get("num_prices", []),
                denom_prices=historical_series.get("denom_prices", []),
                ratio=historical_series.get("ratio", []),
                ratio_mean=historical_series.get("ratio_mean", current_ratio),
                ratio_std=historical_series.get("ratio_std", 1),
                high_z=high_z,
                low_z=low_z,
                num_name=num_info.get("name", "Num"),
                denom_name=denom_info.get("name", "Denom"),
            )
            if ratio_chart:
                charts["ratio_history"] = ratio_chart
        
        # Supplementary charts
        regime_chart = build_regime_chart(regime_name, confidence, z_score)
        if regime_chart:
            charts["regime"] = regime_chart
        
        zscore_chart = build_zscore_chart(
            z_score, 
            {"high": high_z, "low": low_z}, 
            num_info.get("name", "Num"), 
            denom_info.get("name", "Denom")
        )
        if zscore_chart:
            charts["zscore"] = zscore_chart
        
        # Build summary
        summary = (
            f"{pair_name} Ratio: {current_ratio:.2f} (z={z_score:+.2f}σ, {percentile:.0f}th percentile). "
            f"Regime: {regime_name}. Signal: {signal}. {trade_idea}"
        )
        
        return {
            "status": "success",
            "tool_id": "commodity_ratio",
            "tickers": [num_info.get("symbol", ""), denom_info.get("symbol", "")],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "current_ratio": current_ratio,
                "z_score": z_score,
                "percentile": percentile,
                "confidence": confidence,
                "num_price": num_info.get("price", 0),
                "denom_price": denom_info.get("price", 0),
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Commodity Ratio Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "commodity_ratio",
        }


def _build_metric_cards(
    current_ratio: float,
    pair_name: str,
    num_name: str,
    denom_name: str,
    regime_name: str,
    signal: str,
    confidence: float,
    z_score: float,
    percentile: float,
    lookback_days: int,
) -> List[Dict[str, Any]]:
    """Build displayable metric cards."""
    cards = []
    
    cards.append({
        "id": "ratio",
        "label": pair_name,
        "value": f"{current_ratio:.2f}",
        "description": f"{lookback_days}d lookback",
        "sentiment": "neutral",
    })
    
    if "NO TRADE" in signal:
        sentiment = "neutral"
    elif "CHEAP" in regime_name:
        sentiment = "positive"
    else:
        sentiment = "neutral"
    
    cards.append({
        "id": "signal",
        "label": "Signal",
        "value": signal,
        "description": regime_name,
        "sentiment": sentiment,
    })
    
    cards.append({
        "id": "zscore",
        "label": "Z-Score",
        "value": f"{z_score:+.2f}σ",
        "description": f"{percentile:.0f}th percentile",
        "sentiment": "positive" if abs(z_score) > 1.5 else "neutral",
    })
    
    cards.append({
        "id": "confidence",
        "label": "Confidence",
        "value": f"{confidence:.0%}",
        "description": "Signal strength",
        "sentiment": "positive" if confidence > 0.7 else "neutral",
    })
    
    return cards


def _build_stats_table(
    result: Dict[str, Any],
    regime: Dict[str, Any],
    historical: Dict[str, Any],
    analysis_period: Dict[str, Any],
    num_info: Dict[str, Any],
    denom_info: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build comprehensive stats table."""
    rows = []
    
    rows.append({"category": "Prices", "metric": num_info.get("name", "Numerator"), "value": f"${num_info.get('price', 0):,.2f}"})
    rows.append({"category": "Prices", "metric": denom_info.get("name", "Denominator"), "value": f"${denom_info.get('price', 0):,.2f}"})
    rows.append({"category": "Prices", "metric": "Ratio", "value": f"{result.get('current_ratio', 0):.4f}"})
    
    rows.append({"category": "Historical", "metric": "Mean", "value": f"{historical.get('ratio_mean', 0):.4f}"})
    rows.append({"category": "Historical", "metric": "Std Dev", "value": f"{historical.get('ratio_std', 0):.4f}"})
    rows.append({"category": "Historical", "metric": "Min", "value": f"{historical.get('ratio_min', 0):.4f}"})
    rows.append({"category": "Historical", "metric": "Max", "value": f"{historical.get('ratio_max', 0):.4f}"})
    rows.append({"category": "Historical", "metric": "vs Mean", "value": historical.get('current_vs_mean', 'N/A')})
    
    rows.append({"category": "Regime", "metric": "Classification", "value": regime.get('regime', 'N/A')})
    rows.append({"category": "Regime", "metric": "Signal", "value": regime.get('signal', 'N/A')})
    rows.append({"category": "Regime", "metric": "Z-Score", "value": f"{regime.get('ratio_z_score', 0):+.2f}σ"})
    rows.append({"category": "Regime", "metric": "Percentile", "value": f"{regime.get('ratio_percentile', 0):.0f}%"})
    rows.append({"category": "Regime", "metric": "Confidence", "value": f"{regime.get('confidence', 0):.0%}"})
    
    rows.append({"category": "Period", "metric": "Start", "value": analysis_period.get('start_date', 'N/A')})
    rows.append({"category": "Period", "metric": "End", "value": analysis_period.get('end_date', 'N/A')})
    rows.append({"category": "Period", "metric": "Trading Days", "value": str(analysis_period.get('trading_days', 0))})
    
    return rows
