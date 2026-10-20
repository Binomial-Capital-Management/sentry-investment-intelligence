"""
Interest Rate Swap Canvas Executor
Prices vanilla IRS using FRED treasury data.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def execute_irs(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute IRS pricing for Canvas."""
    from core.agents.structuring_tools.interest_rate_swap_tool import price_interest_rate_swap_internal
    from .charts import build_cashflow_chart, build_pv_breakdown_chart
    
    try:
        # Extract parameters
        notional = float(params.get('notional', 10_000_000))
        fixed_rate = float(params.get('fixed_rate', 0.04))
        float_index = params.get('float_index', 'SOFR')
        tenor = params.get('tenor', '5Y')
        payment_freq = params.get('payment_freq', 'semiannual')
        pricing_date = params.get('pricing_date')  # Optional
        
        logger.info(f"Pricing IRS: {notional:,.0f} notional, {tenor}, fixed {fixed_rate:.2%} vs {float_index}")
        
        # Call internal pricing function
        result = await price_interest_rate_swap_internal(
            notional=notional,
            fixed_rate=fixed_rate,
            float_index=float_index,
            tenor=tenor,
            payment_freq=payment_freq,
            pricing_date=pricing_date
        )
        
        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error", "IRS pricing failed")}
        
        # Extract values
        swap_value = result.get("swap_value", 0)
        dv01 = result.get("dv01", 0)
        fixed_leg_pv = result.get("fixed_leg_pv", 0)
        float_leg_pv = result.get("float_leg_pv", 0)
        payment_schedule = result.get("payment_schedule", [])
        discount_factors = result.get("discount_factors", [])
        forward_rates = result.get("forward_rates", [])
        
        # Build charts
        charts = {}
        
        cf_chart = build_cashflow_chart(
            payment_schedule=payment_schedule,
            fixed_rate=fixed_rate,
            forward_rates=forward_rates,
            notional=notional,
            tenor=tenor
        )
        if cf_chart:
            charts["cashflows"] = cf_chart
        
        pv_chart = build_pv_breakdown_chart(
            fixed_leg_pv=fixed_leg_pv,
            float_leg_pv=float_leg_pv,
            swap_value=swap_value
        )
        if pv_chart:
            charts["pv_breakdown"] = pv_chart
        
        # Build metric cards
        direction = "Receive Fixed" if swap_value > 0 else "Pay Fixed"
        sentiment = "positive" if swap_value > 0 else "negative"
        
        metric_cards = [
            {
                "id": "swap_value",
                "label": "Swap Value",
                "value": f"${swap_value:,.2f}",
                "sentiment": sentiment,
                "description": f"{direction} is advantageous"
            },
            {
                "id": "dv01",
                "label": "DV01",
                "value": f"${dv01:,.2f}",
                "sentiment": "neutral",
                "description": "Sensitivity to 1bp yield shift"
            },
            {
                "id": "fixed_leg_pv",
                "label": "Fixed Leg PV",
                "value": f"${fixed_leg_pv:,.2f}",
                "sentiment": "neutral"
            },
            {
                "id": "float_leg_pv",
                "label": "Float Leg PV",
                "value": f"${float_leg_pv:,.2f}",
                "sentiment": "neutral"
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Swap", "metric": "Notional", "value": f"${notional:,.0f}"},
            {"category": "Swap", "metric": "Tenor", "value": tenor},
            {"category": "Swap", "metric": "Payment Frequency", "value": payment_freq.title()},
            {"category": "Valuation", "metric": "Swap Value", "value": f"${swap_value:,.2f}"},
            {"category": "Valuation", "metric": "DV01", "value": f"${dv01:,.2f}"},
            {"category": "Legs", "metric": "Fixed Leg PV", "value": f"${fixed_leg_pv:,.2f}"},
            {"category": "Legs", "metric": "Float Leg PV", "value": f"${float_leg_pv:,.2f}"},
            {"category": "Rates", "metric": "Fixed Rate", "value": f"{fixed_rate:.2%}"},
            {"category": "Rates", "metric": "Float Index", "value": float_index},
            {"category": "Schedule", "metric": "Number of Payments", "value": str(len(payment_schedule))},
        ]
        
        return {
            "status": "success",
            "tool_id": "irs",
            "tickers": [],
            "weights": [],
            "metrics": {
                "swap_value": swap_value,
                "dv01": dv01,
                "fixed_leg_pv": fixed_leg_pv,
                "float_leg_pv": float_leg_pv,
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"IRS execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}
