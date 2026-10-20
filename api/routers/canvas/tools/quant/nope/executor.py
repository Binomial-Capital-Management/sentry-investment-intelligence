"""
Canvas executor for NOPE Divergence Scanner.

Scans for NOPE (Net Options Pricing Effect) vs price divergences.
"""

import logging
import math
from typing import Any, Dict, List, Optional

from .charts import build_divergence_scatter, build_nope_vs_price_chart, build_signal_breakdown

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, replacing NaN/Inf with default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


async def execute_nope(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute NOPE divergence scan for Canvas.
    """
    from core.agents.quant_tools import scan_nope_divergences_internal
    
    # Extract parameters
    screener = params.get("screener", "custom")
    tickers_raw = params.get("tickers", "")
    etf_ticker = params.get("etf_ticker", "")
    sector = params.get("sector", "")
    z_threshold = float(params.get("z_threshold", 1.5))
    lookback_days = int(params.get("lookback_days", 5))
    top_n = int(params.get("top_n", 10))
    top_n = max(1, min(50, top_n))  # Clamp to 1-50
    
    # Parse tickers
    tickers = None
    if screener == "custom":
        if isinstance(tickers_raw, list):
            tickers = [t.strip().upper() for t in tickers_raw if t.strip()]
        elif isinstance(tickers_raw, str) and tickers_raw.strip():
            tickers = [t.strip().upper() for t in tickers_raw.replace(",", " ").split() if t.strip()]
        
        if not tickers:
            return {
                "status": "error",
                "error": "Please provide ticker(s) for custom screener",
                "tool_id": "nope",
            }
    
    # Limit tickers for custom screener
    if tickers and len(tickers) > top_n:
        tickers = tickers[:top_n]
    
    logger.info(f"Executing NOPE: screener={screener}, tickers={tickers}, etf={etf_ticker}, sector={sector}, top_n={top_n}")
    
    try:
        result = await scan_nope_divergences_internal(
            screener=screener,
            tickers=tickers,
            etf_ticker=etf_ticker if etf_ticker else None,
            sector=sector if sector else None,
            z_threshold=z_threshold,
            lookback_days=lookback_days,
            include_interpretation=True,
            max_results=top_n,
            max_etf_holdings=top_n,
            max_universe=top_n,  # Enforce universe limit for all screeners
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "NOPE scan failed"),
                "tool_id": "nope",
            }
        
        # Extract data
        summary = result.get("summary", {})
        divergences = result.get("divergences", [])
        no_divergence_tickers = result.get("no_divergence_tickers", [])
        no_data_tickers = result.get("no_data_tickers", [])
        
        # Build metric cards
        metric_cards = _build_metric_cards(summary, divergences)
        
        # Build stats table (all scanned tickers)
        stats_table = _build_stats_table(divergences, no_divergence_tickers, no_data_tickers)
        
        # Build charts
        charts = {}
        
        # 1. Divergence scatter (z-score vs confidence)
        scatter = build_divergence_scatter(divergences)
        if scatter:
            charts["scatter"] = scatter
        
        # 2. NOPE vs Price trends for top divergences
        if divergences:
            trend_chart = build_nope_vs_price_chart(divergences[:5])
            if trend_chart:
                charts["trends"] = trend_chart
        
        # 3. Signal breakdown (bullish vs bearish)
        breakdown = build_signal_breakdown(summary)
        if breakdown:
            charts["breakdown"] = breakdown
        
        logger.info(f"Built {len(charts)} charts for NOPE")
        
        # Get all scanned tickers
        div_tickers = [d.get("ticker", "") for d in divergences]
        all_tickers = div_tickers + no_divergence_tickers + no_data_tickers
        
        # Build summary text
        bullish_count = summary.get("bullish", 0)
        bearish_count = summary.get("bearish", 0)
        
        summary_text = f"**NOPE Divergence Scan** ({screener})\n\n"
        summary_text += f"- Scanned: {summary.get('universe_size', 0)} tickers\n"
        summary_text += f"- Divergences: {summary.get('divergences_found', 0)} ({bullish_count} bullish, {bearish_count} bearish)\n"
        
        if divergences:
            top = divergences[0]
            summary_text += f"\n**Top Signal:** {top.get('ticker')} - {top.get('divergence', {}).get('type', 'N/A')}"
            summary_text += f" (z={top.get('divergence', {}).get('z_score', 0):.2f})"
        
        return {
            "status": "success",
            "tool_id": "nope",
            "tickers": all_tickers,
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "universe_size": summary.get("universe_size", 0),
                "divergences_found": summary.get("divergences_found", 0),
                "bullish": bullish_count,
                "bearish": bearish_count,
            },
            "summary": summary_text,
        }
        
    except Exception as e:
        logger.error(f"NOPE Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "nope",
        }


def _build_metric_cards(summary: Dict[str, Any], divergences: List[Dict]) -> List[Dict[str, Any]]:
    """Build metric cards."""
    cards = []
    
    # Universe size
    cards.append({
        "id": "universe",
        "label": "Tickers Scanned",
        "value": str(summary.get("universe_size", 0)),
        "description": "Total universe",
        "sentiment": "neutral",
    })
    
    # Divergences found
    div_count = summary.get("divergences_found", 0)
    cards.append({
        "id": "divergences",
        "label": "Divergences",
        "value": str(div_count),
        "description": f"{summary.get('bullish', 0)} bullish, {summary.get('bearish', 0)} bearish",
        "sentiment": "positive" if div_count > 0 else "neutral",
    })
    
    # Bullish signals
    bullish = summary.get("bullish", 0)
    cards.append({
        "id": "bullish",
        "label": "Bullish",
        "value": str(bullish),
        "description": "NOPE ↑ Price ↓ → Expect bounce",
        "sentiment": "positive" if bullish > 0 else "neutral",
    })
    
    # Bearish signals
    bearish = summary.get("bearish", 0)
    cards.append({
        "id": "bearish",
        "label": "Bearish",
        "value": str(bearish),
        "description": "NOPE ↓ Price ↑ → Expect pullback",
        "sentiment": "negative" if bearish > 0 else "neutral",
    })
    
    # Top signal
    if divergences:
        top = divergences[0]
        div = top.get("divergence", {})
        z_score = _safe_float(div.get("z_score"))
        cards.append({
            "id": "top_signal",
            "label": f"Top: {top.get('ticker', 'N/A')}",
            "value": div.get("type", "N/A"),
            "description": f"z={z_score:.2f}, conf={div.get('confidence', 0):.0%}",
            "sentiment": "positive" if div.get("type") == "BULLISH" else "negative",
        })
    
    # No data count
    no_data = summary.get("no_data", 0)
    if no_data > 0:
        cards.append({
            "id": "no_data",
            "label": "No Data",
            "value": str(no_data),
            "description": "Tickers without NOPE data",
            "sentiment": "warning",
        })
    
    return cards


def _build_stats_table(
    divergences: List[Dict],
    no_divergence_tickers: List[str],
    no_data_tickers: List[str]
) -> List[Dict[str, str]]:
    """Build stats table showing ALL scanned tickers."""
    rows = []
    
    # Divergences first (with details)
    for div in divergences:
        ticker = div.get("ticker", "")
        divergence = div.get("divergence", {})
        
        div_type = divergence.get("type", "N/A")
        z_score = _safe_float(divergence.get("z_score"))
        confidence = _safe_float(divergence.get("confidence"))
        
        rows.append({
            "category": div_type,
            "metric": ticker,
            "value": f"z={z_score:+.2f}",
            "extra": f"{confidence:.0%} conf",
        })
    
    # No divergence tickers
    for ticker in no_divergence_tickers:
        rows.append({
            "category": "NO SIGNAL",
            "metric": ticker,
            "value": "—",
            "extra": "No divergence",
        })
    
    # No data tickers
    for ticker in no_data_tickers:
        rows.append({
            "category": "NO DATA",
            "metric": ticker,
            "value": "—",
            "extra": "Missing NOPE data",
        })
    
    return rows
