"""
Canvas executor for Vanna/Charm Flow Analysis.

Analyzes dealer vanna (∂Δ/∂σ) and charm (∂Δ/∂t) positioning.
- Vanna: Delta change when volatility changes
- Charm: Delta change as time passes

Generates regime signals and alpha strategies.
"""

import logging
from typing import Any, Dict, Optional

from core.agents.quant_tools.vanna_charm_flow_tool import analyze_vanna_charm_flow_internal
from .charts import build_vanna_profile_chart, build_scenario_chart, build_regime_gauge_chart

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


def _format_shares(val: float) -> str:
    """Format share count to human readable."""
    abs_val = abs(val)
    sign = "+" if val >= 0 else "-"
    if abs_val >= 1e6:
        return f"{sign}{abs_val/1e6:.1f}M"
    elif abs_val >= 1e3:
        return f"{sign}{abs_val/1e3:.0f}K"
    else:
        return f"{sign}{abs_val:.0f}"


async def execute_vanna_charm(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute vanna/charm flow analysis for Canvas.
    """
    # Extract parameters
    ticker = params.get("ticker", "").strip().upper()
    if not ticker:
        return {
            "status": "error",
            "error": "Ticker is required",
            "tool_id": "vanna_charm",
        }
    
    min_oi = int(params.get("min_oi", 100))
    max_dte = int(params.get("max_dte", 45))
    
    logger.info(f"Executing Vanna/Charm analysis for {ticker}")
    
    try:
        # Call internal function
        result = await analyze_vanna_charm_flow_internal(
            underlying=ticker,
            min_oi_threshold=min_oi,
            max_dte=max_dte,
        )
        
        if result.get("error"):
            return {
                "status": "error",
                "error": result.get("error"),
                "tool_id": "vanna_charm",
            }
        
        # Extract data
        spot_price = _safe_float(result.get("spot_price", 0))
        aggregate_vanna = _safe_float(result.get("aggregate_vanna", 0))
        aggregate_charm = _safe_float(result.get("aggregate_charm", 0))
        aggregate_gamma = _safe_float(result.get("aggregate_gamma", 0))
        
        regime = result.get("regime", {})
        key_levels = result.get("key_levels", {})
        scenarios = result.get("scenarios", [])
        alpha_strategies = result.get("alpha_strategies", [])
        data_quality = result.get("data_quality", {})
        
        vanna_regime = regime.get("vanna_regime", "neutral")
        charm_regime = regime.get("charm_regime", "neutral")
        
        # Build metric cards
        metric_cards = []
        
        # Vanna regime
        vanna_sentiment = "positive" if "short" in vanna_regime else ("negative" if "long" in vanna_regime else "neutral")
        metric_cards.append({
            "id": "vanna_regime",
            "label": "Vanna Regime",
            "value": vanna_regime.replace("_", " ").upper(),
            "sentiment": vanna_sentiment,
            "description": "Vol spike → dealer hedging direction",
        })
        
        # Charm regime
        charm_sentiment = "positive" if "positive" in charm_regime else ("negative" if "negative" in charm_regime else "neutral")
        metric_cards.append({
            "id": "charm_regime",
            "label": "Charm Regime",
            "value": charm_regime.replace("_", " ").upper(),
            "sentiment": charm_sentiment,
            "description": "Daily time decay hedging",
        })
        
        # Net vanna
        metric_cards.append({
            "id": "net_vanna",
            "label": "Net Vanna",
            "value": f"{_format_shares(aggregate_vanna)} / 1% IV",
            "sentiment": "positive" if aggregate_vanna < 0 else "negative",
            "description": "Shares per 1% vol change",
        })
        
        # Net charm
        metric_cards.append({
            "id": "net_charm",
            "label": "Net Charm",
            "value": f"{_format_shares(aggregate_charm)} / day",
            "sentiment": "positive" if aggregate_charm > 0 else "negative",
            "description": "Daily hedging flow",
        })
        
        # Vanna flip point
        vanna_flip = key_levels.get("vanna_flip_point")
        if vanna_flip:
            distance_pct = (vanna_flip - spot_price) / spot_price * 100
            metric_cards.append({
                "id": "vanna_flip",
                "label": "Vanna Flip",
                "value": f"${vanna_flip:.0f}",
                "sentiment": "neutral",
                "description": f"{distance_pct:+.1f}% from spot",
            })
        
        # Build stats table
        stats_table = [
            {"category": "Positioning", "metric": "Net Vanna", "value": f"{aggregate_vanna:,.0f} shares/1% IV"},
            {"category": "Positioning", "metric": "Net Charm", "value": f"{aggregate_charm:,.0f} shares/day"},
            {"category": "Positioning", "metric": "Net Gamma", "value": f"{aggregate_gamma:,.0f} shares/$1"},
            {"category": "Key Levels", "metric": "Spot Price", "value": f"${spot_price:.2f}"},
            {"category": "Key Levels", "metric": "Vanna Flip Point", "value": f"${vanna_flip:.0f}" if vanna_flip else "N/A"},
            {"category": "Key Levels", "metric": "Max Vanna Strike", "value": f"${key_levels.get('max_vanna_strike', 0):.0f}"},
            {"category": "Key Levels", "metric": "Max Charm Strike", "value": f"${key_levels.get('max_charm_strike', 0):.0f}"},
            {"category": "Data", "metric": "Contracts Analyzed", "value": f"{data_quality.get('contracts_analyzed', 0):,}"},
            {"category": "Data", "metric": "Total Call OI", "value": f"{data_quality.get('total_call_oi', 0):,}"},
            {"category": "Data", "metric": "Total Put OI", "value": f"{data_quality.get('total_put_oi', 0):,}"},
        ]
        
        # Build charts
        charts = {}
        
        # Chart 1: Vanna/Charm exposure profile
        try:
            vanna_chart = build_vanna_profile_chart(
                ticker, spot_price, aggregate_vanna, aggregate_charm,
                vanna_regime, vanna_flip, result.get("by_strike_data")
            )
            if vanna_chart:
                charts["vanna_profile"] = vanna_chart
        except Exception as e:
            logger.warning(f"Failed to build vanna profile chart: {e}")
        
        # Chart 2: Scenario waterfall
        try:
            scenario_chart = build_scenario_chart(ticker, scenarios)
            if scenario_chart:
                charts["scenarios"] = scenario_chart
        except Exception as e:
            logger.warning(f"Failed to build scenario chart: {e}")
        
        # Chart 3: Regime gauge
        try:
            gauge_chart = build_regime_gauge_chart(
                ticker, vanna_regime, charm_regime,
                aggregate_vanna, aggregate_charm
            )
            if gauge_chart:
                charts["regime_gauge"] = gauge_chart
        except Exception as e:
            logger.warning(f"Failed to build regime gauge chart: {e}")
        
        logger.info(f"Built {len(charts)} charts for {ticker} vanna/charm")
        
        # Build summary
        combined_signal = regime.get("combined_signal", "")
        summary = f"{ticker}: {vanna_regime.upper().replace('_', ' ')} + {charm_regime.upper().replace('_', ' ')}. {combined_signal}"
        
        # Format strategies for output
        strategy_summary = []
        for strat in alpha_strategies[:3]:  # Top 3
            strategy_summary.append({
                "name": strat.get("name"),
                "signal": strat.get("signal"),
                "timeframe": strat.get("timeframe"),
                "logic": strat.get("logic", "")[:200],
            })
        
        return {
            "status": "success",
            "tool_id": "vanna_charm",
            "tickers": [ticker],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "spot_price": spot_price,
                "aggregate_vanna": aggregate_vanna,
                "aggregate_charm": aggregate_charm,
                "aggregate_gamma": aggregate_gamma,
                "vanna_regime": vanna_regime,
                "charm_regime": charm_regime,
                "vanna_flip_point": vanna_flip,
            },
            "regime": regime,
            "alpha_strategies": strategy_summary,
            "scenarios": scenarios,
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Vanna/charm execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "vanna_charm",
        }
