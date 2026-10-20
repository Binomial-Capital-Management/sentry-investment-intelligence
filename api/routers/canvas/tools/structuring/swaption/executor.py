"""
Executor for Swaption Pricing Canvas tool.
Prices interest rate swaptions using Black or Bachelier models.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from core.agents.structuring_tools import price_swaption_internal
from .charts import build_pricing_chart, build_greeks_chart

logger = logging.getLogger(__name__)


async def execute_swaption(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute Swaption Pricing for Canvas.
    
    Args:
        user_id: User ID
        org_id: Organization ID
        params: Tool parameters from frontend
        
    Returns:
        Canvas-formatted result with metrics, stats, and charts
    """
    try:
        # Extract parameters
        notional = float(params.get("notional", 10_000_000))
        tenor = params.get("tenor", "5Y")
        float_index = params.get("float_index", "SOFR")
        payment_freq = params.get("payment_freq", "semiannual")
        option_type = params.get("option_type", "payer")
        expiry = params.get("expiry", "")
        strike = float(params.get("strike", 0.045))
        pricing_model = params.get("pricing_model", "black")
        volatility = params.get("volatility", None)
        pricing_date = params.get("pricing_date", None)
        
        # Validate required fields
        if not expiry:
            # Default to 3 months from now
            default_expiry = datetime.now() + timedelta(days=90)
            expiry = default_expiry.strftime("%Y-%m-%d")
        
        if volatility is not None:
            volatility = float(volatility) if volatility != "" else None
        
        logger.info(
            f"Executing Swaption Pricing: {option_type} {tenor} swap, "
            f"expiry={expiry}, strike={strike:.2%}, model={pricing_model}"
        )
        
        # Call internal agent function
        result = await price_swaption_internal(
            notional=notional,
            tenor=tenor,
            float_index=float_index,
            payment_freq=payment_freq,
            option_type=option_type,
            expiry=expiry,
            strike=strike,
            pricing_model=pricing_model,
            volatility=volatility,
            pricing_date=pricing_date
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Unknown error"),
                "tool_id": "swaption"
            }
        
        # Extract data
        swaption_price = result.get("swaption_price", 0.0)
        forward_swap_rate = result.get("forward_swap_rate", 0.0)
        annuity_factor = result.get("annuity_factor", 0.0)
        delta = result.get("delta", 0.0)
        vega = result.get("vega", 0.0)
        time_to_expiry = result.get("time_to_expiry", 0.0)
        volatility_used = result.get("volatility_used", 0.0)
        inputs = result.get("inputs", {})
        
        logger.info(
            f"Swaption result: price=${swaption_price:,.2f}, fwd={forward_swap_rate:.4f}, "
            f"delta=${delta:,.2f}, vega=${vega:,.2f}, annuity={annuity_factor:.4f}"
        )
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            swaption_price,
            notional,
            forward_swap_rate,
            strike,
            option_type,
            volatility_used
        )
        
        # Build stats table
        stats_table = _build_stats_table(
            delta,
            vega,
            annuity_factor,
            time_to_expiry,
            pricing_model
        )
        
        # Build charts from raw data
        charts = {}
        
        # Pricing breakdown chart
        pricing_chart = build_pricing_chart(
            swaption_price,
            forward_swap_rate,
            strike,
            annuity_factor,
            option_type,
            tenor,
            notional
        )
        if pricing_chart:
            charts["pricing"] = pricing_chart
        
        # Greeks sensitivity chart
        greeks_chart = build_greeks_chart(
            delta,
            vega,
            forward_swap_rate,
            volatility_used,
            notional
        )
        if greeks_chart:
            charts["greeks"] = greeks_chart
        
        logger.info(
            f"Built {len(metric_cards)} metric cards, {len(stats_table)} stats rows, "
            f"{len(charts)} charts"
        )
        
        # Summary text
        summary = (
            f"**{option_type.upper()} Swaption on {tenor} {float_index} Swap**\n\n"
            f"Premium: ${swaption_price:,.2f} ({swaption_price/notional*10000:.2f} bps of notional)\n\n"
            f"Strike: {strike:.2%} | Forward: {forward_swap_rate:.2%} | "
            f"Volatility: {volatility_used:.1%} | Model: {pricing_model.upper()}"
        )
        
        return {
            "status": "success",
            "tool_id": "swaption",
            "tickers": [],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "swaption_price": swaption_price,
                "forward_swap_rate": forward_swap_rate,
                "delta": delta,
                "vega": vega,
                "annuity_factor": annuity_factor,
                "volatility": volatility_used,
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Swaption execution error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"Failed to price swaption: {str(e)}",
            "tool_id": "swaption"
        }


def _build_metric_cards(
    swaption_price: float,
    notional: float,
    forward_swap_rate: float,
    strike: float,
    option_type: str,
    volatility: float
) -> list:
    """Build metric cards for Canvas UI."""
    
    # Determine moneyness
    if option_type.lower() == "payer":
        moneyness = "ITM" if forward_swap_rate > strike else ("ATM" if abs(forward_swap_rate - strike) < 0.001 else "OTM")
        moneyness_color = "green" if forward_swap_rate > strike else ("blue" if abs(forward_swap_rate - strike) < 0.001 else "gray")
    else:  # receiver
        moneyness = "ITM" if strike > forward_swap_rate else ("ATM" if abs(forward_swap_rate - strike) < 0.001 else "OTM")
        moneyness_color = "green" if strike > forward_swap_rate else ("blue" if abs(forward_swap_rate - strike) < 0.001 else "gray")
    
    # Premium in basis points
    premium_bps = (swaption_price / notional) * 10000
    
    return [
        {
            "label": "Swaption Premium",
            "value": f"${swaption_price:,.0f}",
            "subtitle": f"{premium_bps:.2f} bps of notional",
            "color": "blue"
        },
        {
            "label": "Forward Swap Rate",
            "value": f"{forward_swap_rate:.2%}",
            "subtitle": f"Strike: {strike:.2%} ({moneyness})",
            "color": moneyness_color
        },
        {
            "label": "Implied Volatility",
            "value": f"{volatility:.1%}",
            "subtitle": "Annualized",
            "color": "purple"
        }
    ]


def _build_stats_table(
    delta: float,
    vega: float,
    annuity_factor: float,
    time_to_expiry: float,
    pricing_model: str
) -> list:
    """Build swaption details stats table."""
    
    rows = [
        {"category": "Greeks", "metric": "Delta", "value": f"${delta:,.2f}"},
        {"category": "Greeks", "metric": "Vega (per 1% vol)", "value": f"${vega:,.2f}"},
        {"category": "Pricing", "metric": "Annuity Factor", "value": f"{annuity_factor:.4f}"},
        {"category": "Pricing", "metric": "Time to Expiry", "value": f"{time_to_expiry:.2f} years"},
        {"category": "Model", "metric": "Pricing Model", "value": pricing_model.upper()},
    ]
    
    return rows
