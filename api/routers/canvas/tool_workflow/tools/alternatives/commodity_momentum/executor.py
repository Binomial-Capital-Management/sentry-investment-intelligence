"""
Canvas executor for Commodity Momentum.

Screens and ranks commodities by momentum with optional HMM regime detection.
"""

import logging
from typing import Any, Dict, List, Optional

from .charts import (
    build_momentum_rankings_chart,
    build_breadth_chart,
    build_regime_chart,
    build_roc_comparison_chart,
)

logger = logging.getLogger(__name__)

# Default commodity symbols for screening
DEFAULT_SYMBOLS = ["GCUSD", "SIUSD", "CLUSD", "NGUSD", "HGUSD", "BZUSD"]


async def execute_commodity_momentum(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute commodity momentum screening for Canvas.
    """
    from core.agents.alternatives_tools.commodity_momentum_tool import screen_commodity_momentum_internal
    
    # Extract parameters - handle both array (multiselect) and string formats
    symbols_param = params.get("symbols", DEFAULT_SYMBOLS)
    if isinstance(symbols_param, list):
        # Parse "Name (TICKER)" format to extract tickers
        parsed_symbols = []
        for sym in symbols_param:
            if '(' in sym and ')' in sym:
                # Extract ticker from "Name (TICKER)"
                ticker = sym.split('(')[1].split(')')[0].strip()
                parsed_symbols.append(ticker)
            else:
                parsed_symbols.append(sym)
        symbols_csv = ",".join(parsed_symbols)
    else:
        symbols_csv = symbols_param
    
    lookback_days = int(params.get("lookback_days", 120))
    detect_regime = params.get("detect_regime", True)
    
    # Ensure boolean
    if isinstance(detect_regime, str):
        detect_regime = detect_regime.lower() in ("true", "1", "yes")
    
    logger.info(f"Executing Commodity Momentum: {symbols_csv}, {lookback_days} days")
    
    try:
        # Call internal function
        result = await screen_commodity_momentum_internal(
            symbols_csv=symbols_csv,
            lookback_days=lookback_days,
            generate_chart=False,  # We build our own Canvas charts
            detect_regime=detect_regime,
        )
        
        if "error" in result:
            return {
                "status": "error",
                "error": result.get("error", "Screening failed"),
                "tool_id": "commodity_momentum",
            }
        
        # Extract key data
        rankings = result.get("rankings", [])
        leaders = result.get("leaders", [])
        laggards = result.get("laggards", [])
        market_breadth = result.get("market_breadth", {})
        regime_analysis = result.get("regime_analysis", {})
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            rankings, market_breadth, regime_analysis
        )
        
        # Build stats table
        stats_table = _build_stats_table(rankings, regime_analysis)
        
        # Build charts
        charts = {}
        
        rankings_chart = build_momentum_rankings_chart(rankings)
        if rankings_chart:
            charts["rankings"] = rankings_chart
        
        breadth_chart = build_breadth_chart(
            market_breadth.get("breadth_pct", 50),
            market_breadth.get("signal", "NEUTRAL"),
        )
        if breadth_chart:
            charts["breadth"] = breadth_chart
        
        regime_chart = build_regime_chart(regime_analysis)
        if regime_chart:
            charts["regime"] = regime_chart
        
        roc_chart = build_roc_comparison_chart(rankings)
        if roc_chart:
            charts["roc"] = roc_chart
        
        # Build summary
        leader_names = ", ".join([l.get("symbol", "?") for l in leaders[:3]])
        laggard_names = ", ".join([l.get("symbol", "?") for l in laggards[-3:]])
        regime_str = regime_analysis.get("market_regime", "N/A") if regime_analysis.get("enabled") else "Disabled"
        
        summary = (
            f"Screened {len(rankings)} commodities. "
            f"Leaders: {leader_names}. Laggards: {laggard_names}. "
            f"Breadth: {market_breadth.get('breadth_pct', 0):.0f}% ({market_breadth.get('signal', 'N/A')}). "
            f"Regime: {regime_str}."
        )
        
        return {
            "status": "success",
            "tool_id": "commodity_momentum",
            "tickers": [r.get("symbol", "") for r in rankings],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "symbols_screened": len(rankings),
                "breadth_pct": market_breadth.get("breadth_pct", 0),
                "regime": regime_analysis.get("market_regime") if regime_analysis.get("enabled") else None,
                "signal_multiplier": regime_analysis.get("signal_multiplier", 1.0),
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Commodity Momentum Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "commodity_momentum",
        }


def _build_metric_cards(
    rankings: List[Dict[str, Any]],
    market_breadth: Dict[str, Any],
    regime_analysis: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build displayable metric cards."""
    cards = []
    
    # Top performer
    if rankings:
        top = rankings[0]
        cards.append({
            "id": "leader",
            "label": "Top Performer",
            "value": top.get("symbol", "N/A"),
            "description": f"Score: {top.get('score', 0):+.1f}",
            "sentiment": "positive" if top.get("score", 0) > 0 else "negative",
        })
    
    # Market breadth
    breadth_pct = market_breadth.get("breadth_pct", 50)
    breadth_signal = market_breadth.get("signal", "NEUTRAL")
    cards.append({
        "id": "breadth",
        "label": "Market Breadth",
        "value": f"{breadth_pct:.0f}%",
        "description": breadth_signal,
        "sentiment": "positive" if breadth_pct > 50 else "negative" if breadth_pct < 50 else "neutral",
    })
    
    # Regime
    if regime_analysis.get("enabled") and regime_analysis.get("market_regime"):
        regime = regime_analysis.get("market_regime", "N/A")
        multiplier = regime_analysis.get("signal_multiplier", 1.0)
        cards.append({
            "id": "regime",
            "label": "HMM Regime",
            "value": regime,
            "description": f"Multiplier: {multiplier:.2f}x",
            "sentiment": "positive" if regime == "TRENDING" else "neutral",
        })
    
    # Symbols screened
    cards.append({
        "id": "count",
        "label": "Screened",
        "value": str(len(rankings)),
        "description": "commodities",
        "sentiment": "neutral",
    })
    
    return cards


def _build_stats_table(
    rankings: List[Dict[str, Any]],
    regime_analysis: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build stats table with ranking details."""
    rows = []
    
    # Add each commodity's stats
    for r in rankings:
        symbol = r.get("symbol", "?")
        rows.append({
            "category": symbol,
            "metric": "Score",
            "value": f"{r.get('score', 0):+.1f}",
        })
        rows.append({
            "category": symbol,
            "metric": "1W ROC",
            "value": f"{r.get('roc_1w', 0):+.1f}%",
        })
        rows.append({
            "category": symbol,
            "metric": "1M ROC",
            "value": f"{r.get('roc_1m', 0):+.1f}%",
        })
        rows.append({
            "category": symbol,
            "metric": "3M ROC",
            "value": f"{r.get('roc_3m', 0):+.1f}%",
        })
        rows.append({
            "category": symbol,
            "metric": "Regime",
            "value": r.get("relative_regime", r.get("regime", "N/A")),
        })
    
    # Add HMM regime info
    if regime_analysis.get("enabled") and regime_analysis.get("market_regime"):
        rows.append({
            "category": "HMM",
            "metric": "Regime",
            "value": regime_analysis.get("market_regime", "N/A"),
        })
        rows.append({
            "category": "HMM",
            "metric": "Probability",
            "value": f"{regime_analysis.get('regime_probability', 0):.1%}",
        })
        rows.append({
            "category": "HMM",
            "metric": "Persistence",
            "value": f"{regime_analysis.get('regime_persistence', 0):.1%}",
        })
        rows.append({
            "category": "HMM",
            "metric": "Multiplier",
            "value": f"{regime_analysis.get('signal_multiplier', 1.0):.2f}x",
        })
    
    return rows
