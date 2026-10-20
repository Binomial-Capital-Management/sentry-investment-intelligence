"""
Canvas executor for Variance Swap.

Prices variance swap contracts using replicating portfolio of options.
Calculates fair strike from options chain and mark-to-market value.
"""

import logging
from typing import Any, Dict, List, Optional
import math

from .charts import build_vol_comparison_chart, build_payoff_chart

logger = logging.getLogger(__name__)


async def execute_var_swap(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute variance swap pricing for Canvas.
    
    Args:
        user_id: User ID
        org_id: Organization ID
        params: Tool parameters from request
    
    Returns:
        Canvas-formatted response with charts, metrics, and summary
    """
    from core.agents.structuring_tools.variance_swap_tool import price_variance_swap_internal
    
    # Extract parameters
    underlying = params.get("underlying", "").upper().strip()
    notional = float(params.get("notional", 100_000))
    strike_variance = params.get("strike_variance")
    tenor = params.get("tenor", "3M")
    
    if not underlying:
        return {
            "status": "error",
            "error": "Please provide an underlying ticker (e.g., SPY, AAPL)",
            "tool_id": "var_swap",
        }
    
    # Convert strike_variance if provided as string
    if strike_variance is not None:
        try:
            strike_variance = float(strike_variance)
        except (ValueError, TypeError):
            strike_variance = None
    
    logger.info(f"Executing Variance Swap: {underlying}, notional={notional}, tenor={tenor}")
    
    try:
        # Call internal function
        result = await price_variance_swap_internal(
            underlying=underlying,
            notional_per_vega=notional,
            strike_variance=strike_variance,
            tenor=tenor,
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Variance swap pricing failed"),
                "tool_id": "var_swap",
            }
        
        # Extract key data
        swap_value = result.get("swap_value", 0)
        fair_strike = result.get("fair_strike", 0)
        strike_var = result.get("strike_variance", 0)
        implied_vol = result.get("implied_vol", 0)
        realized_var = result.get("realized_variance", 0)
        realized_vol = result.get("realized_vol", 0)
        vega = result.get("vega", 0)
        tenor_years = result.get("tenor_years", 0)
        days_to_maturity = result.get("days_to_maturity", 0)
        options_used = result.get("options_used", 0)
        estimation_method = result.get("estimation_method", "unknown")
        summary = result.get("summary", "")
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            swap_value, fair_strike, strike_var, implied_vol, realized_vol, vega
        )
        
        # Build stats table
        stats_table = _build_stats_table(result)
        
        # Build charts
        charts = {}
        
        # 1. Volatility comparison
        vol_chart = build_vol_comparison_chart(implied_vol, realized_vol, math.sqrt(strike_var) if strike_var else 0)
        if vol_chart:
            charts["vol_comparison"] = vol_chart
        
        # 2. Payoff diagram
        payoff_chart = build_payoff_chart(strike_var, fair_strike, notional)
        if payoff_chart:
            charts["payoff"] = payoff_chart
        
        logger.info(f"Built {len(charts)} charts for variance swap")
        
        # Build response
        return {
            "status": "success",
            "tool_id": "var_swap",
            "tickers": [underlying],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "swap_value": swap_value,
                "fair_strike": fair_strike,
                "strike_variance": strike_var,
                "implied_vol": implied_vol,
                "realized_vol": realized_vol,
                "vega": vega,
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Variance Swap Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "var_swap",
        }


def _build_metric_cards(
    swap_value: float,
    fair_strike: float,
    strike_var: float,
    implied_vol: float,
    realized_vol: float,
    vega: float,
) -> List[Dict[str, Any]]:
    """Build displayable metric cards."""
    cards = []
    
    # Swap Value
    cards.append({
        "id": "swap_value",
        "label": "Swap Value",
        "value": f"${swap_value:,.0f}",
        "description": "Mark-to-market",
        "sentiment": "positive" if swap_value > 0 else "negative" if swap_value < 0 else "neutral",
    })
    
    # Fair Strike (as vol)
    cards.append({
        "id": "fair_vol",
        "label": "Fair Vol",
        "value": f"{implied_vol:.1%}",
        "description": f"Strike: {fair_strike:.4f}",
        "sentiment": "neutral",
    })
    
    # Strike Vol
    strike_vol = math.sqrt(strike_var) if strike_var else 0
    cards.append({
        "id": "strike_vol",
        "label": "Strike Vol",
        "value": f"{strike_vol:.1%}",
        "description": f"Var: {strike_var:.4f}",
        "sentiment": "neutral",
    })
    
    # Realized Vol
    cards.append({
        "id": "realized_vol",
        "label": "Realized Vol",
        "value": f"{realized_vol:.1%}",
        "description": "Historical",
        "sentiment": "neutral",
    })
    
    # Vega
    cards.append({
        "id": "vega",
        "label": "Vega",
        "value": f"${vega:,.0f}",
        "description": "Per variance point",
        "sentiment": "neutral",
    })
    
    return cards


def _build_stats_table(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build comprehensive stats table."""
    rows = []
    inputs = result.get("inputs", {})
    
    # Trade Setup
    rows.append({"category": "Trade", "metric": "Underlying", "value": inputs.get("underlying", "")})
    rows.append({"category": "Trade", "metric": "Notional", "value": f"${inputs.get('notional_per_vega', 0):,.0f}"})
    rows.append({"category": "Trade", "metric": "Tenor", "value": inputs.get("tenor", "")})
    rows.append({"category": "Trade", "metric": "Days to Maturity", "value": str(result.get("days_to_maturity", 0))})
    
    # Variance
    rows.append({"category": "Variance", "metric": "Fair Strike", "value": f"{result.get('fair_strike', 0):.4f}"})
    rows.append({"category": "Variance", "metric": "Contract Strike", "value": f"{result.get('strike_variance', 0):.4f}"})
    rows.append({"category": "Variance", "metric": "Realized Var", "value": f"{result.get('realized_variance', 0):.4f}"})
    
    # Volatility
    rows.append({"category": "Volatility", "metric": "Implied Vol", "value": f"{result.get('implied_vol', 0):.2%}"})
    rows.append({"category": "Volatility", "metric": "Realized Vol", "value": f"{result.get('realized_vol', 0):.2%}"})
    strike_vol = math.sqrt(result.get("strike_variance", 0)) if result.get("strike_variance") else 0
    rows.append({"category": "Volatility", "metric": "Strike Vol", "value": f"{strike_vol:.2%}"})
    
    # Pricing
    rows.append({"category": "Pricing", "metric": "Swap Value", "value": f"${result.get('swap_value', 0):,.2f}"})
    rows.append({"category": "Pricing", "metric": "Vega", "value": f"${result.get('vega', 0):,.2f}"})
    rows.append({"category": "Pricing", "metric": "Options Used", "value": str(result.get("options_used", 0))})
    rows.append({"category": "Pricing", "metric": "Method", "value": result.get("estimation_method", "unknown")})
    
    return rows
