"""
Canvas executor for Signal Confluence Detector tool.
"""
import logging
from typing import Dict, Any
from core.agents.quant_tools import detect_signal_confluence_internal
from .charts import build_confluence_chart, build_z_score_distribution_chart

logger = logging.getLogger(__name__)


async def execute_confluence(user_id: str, org_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute signal confluence detection for Canvas.
    
    Detects when multiple independent signals align simultaneously - the Rentec approach.
    """
    try:
        # Extract parameters
        ticker = params.get("ticker", "").upper().strip()
        z_threshold = params.get("z_threshold", 1.5)
        min_signals = params.get("min_signals", 3)
        categories = params.get("categories", None)  # None = all categories
        
        if not ticker:
            return {
                "status": "error",
                "error": "Ticker is required",
                "tool_id": "confluence",
                "tickers": [],
                "weights": []
            }
        
        logger.info(f"Detecting signal confluence for {ticker}: z_threshold={z_threshold}, min_signals={min_signals}")
        
        # Call internal function
        result = await detect_signal_confluence_internal(
            ticker=ticker,
            z_threshold=z_threshold,
            min_signals=min_signals,
            categories=categories
        )
        
        # Check for errors
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Confluence detection failed"),
                "tool_id": "confluence",
                "tickers": [ticker],
                "weights": [],
                "hint": result.get("hint", "")
            }
        
        # Extract key data
        confluence_data = result.get("confluence", {})
        extreme_signals = result.get("extreme_signals", [])
        interpretation = result.get("interpretation", "")
        all_signals = result.get("all_signals", {})
        config = result.get("config", {})
        
        # Debug logging
        logger.info(f"Confluence data for {ticker}: {len(extreme_signals)} extreme, {len(all_signals)} total signals")
        if extreme_signals:
            logger.info(f"Extreme signals: {[s.get('signal') for s in extreme_signals[:5]]}")
        if all_signals:
            logger.info(f"All signals (first 5): {list(all_signals.keys())[:5]}")
        
        detected = confluence_data.get("detected", False)
        score = confluence_data.get("score", 0)
        bias = confluence_data.get("bias", "MIXED")
        bullish_count = confluence_data.get("bullish_signals", 0)
        bearish_count = confluence_data.get("bearish_signals", 0)
        
        # Build metric cards
        metric_cards = [
            {
                "label": "Confluence Detected",
                "value": "YES" if detected else "NO",
                "subtext": f"{score} signals aligned"
            },
            {
                "label": "Confluence Score",
                "value": f"{score}",
                "subtext": f"Threshold: {z_threshold:.1f}σ"
            },
            {
                "label": "Bias",
                "value": bias,
                "subtext": f"↑{bullish_count} / ↓{bearish_count}"
            },
            {
                "label": "Signal Coverage",
                "value": f"{len(extreme_signals)} extreme",
                "subtext": f"{len(all_signals)} total signals"
            }
        ]
        
        # Build stats table - show all extreme signals
        stats_table = []
        
        for sig in extreme_signals:
            signal_name = sig.get("signal", "")
            z_score = sig.get("z_score", 0)
            direction = sig.get("direction", "")
            category = sig.get("category", "")
            
            stats_table.append({
                "category": category.title(),
                "metric": signal_name.replace("_", " ").title(),
                "value": f"{z_score:+.2f}σ ({direction})"
            })
        
        # Add config info
        stats_table.append({"category": "Config", "metric": "Z Threshold", "value": f"{z_threshold:.1f}"})
        stats_table.append({"category": "Config", "metric": "Min Signals", "value": f"{min_signals}"})
        stats_table.append({"category": "Config", "metric": "Categories", "value": ", ".join(config.get("categories", []))})
        
        # Build charts - ALWAYS show both charts even with minimal data
        charts = {}
        
        # Chart 1: Extreme signals (if any)
        if extreme_signals:
            logger.info(f"Building confluence chart with {len(extreme_signals)} extreme signals")
            confluence_chart = build_confluence_chart(
                ticker=ticker,
                extreme_signals=extreme_signals,
                z_threshold=z_threshold,
                bias=bias
            )
            if confluence_chart:
                charts["confluence"] = confluence_chart
        else:
            logger.warning(f"No extreme signals to chart for {ticker}")
        
        # Chart 2: ALL signals distribution (should always have data)
        if all_signals:
            logger.info(f"Building distribution chart with {len(all_signals)} total signals")
            dist_chart = build_z_score_distribution_chart(
                ticker=ticker,
                all_signals=all_signals,
                z_threshold=z_threshold
            )
            if dist_chart:
                charts["distribution"] = dist_chart
        else:
            logger.warning(f"No signals at all returned for {ticker}")
        
        # Summary
        summary = (
            f"**{ticker} Signal Confluence Analysis**\n\n"
            f"**Confluence Detected:** {'YES' if detected else 'NO'}\n"
            f"**Confluence Score:** {score} signals (threshold: {min_signals})\n"
            f"**Bias:** {bias}\n\n"
            f"**Extreme Signals ({len(extreme_signals)}):**\n"
        )
        
        for sig in extreme_signals[:10]:  # Top 10
            summary += f"- {sig.get('signal', '').replace('_', ' ').title()}: {sig.get('z_score', 0):+.2f}σ ({sig.get('direction', '')})\n"
        
        if len(extreme_signals) > 10:
            summary += f"... and {len(extreme_signals) - 10} more\n"
        
        summary += f"\n**Interpretation:** {interpretation}\n"
        
        return {
            "status": "success",
            "tool_id": "confluence",
            "tickers": [ticker],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "confluence_detected": detected,
                "confluence_score": score,
                "bias": bias,
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "extreme_signals_count": len(extreme_signals),
                "total_signals_count": len(all_signals),
                "z_threshold": z_threshold
            },
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Confluence execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "tool_id": "confluence",
            "tickers": [params.get("ticker", "")],
            "weights": []
        }
