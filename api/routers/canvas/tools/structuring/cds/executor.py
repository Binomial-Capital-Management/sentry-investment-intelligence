"""
Credit Default Swap Canvas Executor
Prices CDS using Merton model or generic assumptions.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def execute_cds(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute CDS pricing for Canvas."""
    from core.agents.structuring_tools.credit_default_swap_tool import price_credit_default_swap_internal
    from .charts import build_survival_curve_chart, build_pv_breakdown_chart
    
    ticker = params.get('ticker') or params.get('underlying')
    if not ticker:
        return {"status": "error", "error": "Ticker is required"}
    
    ticker = ticker.upper()
    
    try:
        # Extract parameters
        notional = float(params.get('notional', 10_000_000))
        tenor = params.get('tenor', '5Y')
        pricing_date = params.get('pricing_date')  # Optional
        
        logger.info(f"Pricing CDS: {ticker}, {notional:,.0f} notional, {tenor}")
        
        # Call internal pricing function (calculates fair spread and recovery rate)
        result = await price_credit_default_swap_internal(
            ticker=ticker,
            notional=notional,
            tenor=tenor,
            pricing_date=pricing_date
        )
        
        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error", "CDS pricing failed")}
        
        # Extract values
        fair_spread_bps = result.get("fair_spread_bps", 0)
        recovery_rate = result.get("recovery_rate", 0)
        cds_value = result.get("cds_value", 0)
        upfront_payment = result.get("upfront_payment", 0)
        premium_leg_pv = result.get("premium_leg_pv", 0)
        protection_leg_pv = result.get("protection_leg_pv", 0)
        default_probability = result.get("default_probability")
        distance_to_default = result.get("distance_to_default")
        survival_curve = result.get("survival_curve", {})
        estimation_method = result.get("estimation_method", "unknown")
        warnings = result.get("warnings", [])
        
        # Build charts
        charts = {}
        
        survival_chart = build_survival_curve_chart(
            survival_curve=survival_curve,
            ticker=ticker,
            tenor=tenor,
            distance_to_default=distance_to_default,
            default_probability=default_probability
        )
        if survival_chart:
            charts["credit_risk_timeline"] = survival_chart
        
        spread_sensitivity_chart = build_pv_breakdown_chart(
            premium_leg_pv=premium_leg_pv,
            protection_leg_pv=protection_leg_pv,
            cds_value=cds_value,
            fair_spread_bps=fair_spread_bps
        )
        if spread_sensitivity_chart:
            charts["spread_sensitivity"] = spread_sensitivity_chart
        
        # Build metric cards
        method_display = {
            "merton": "Merton Model",
            "generic": "Generic BBB",
            "user_provided": "User Curve"
        }.get(estimation_method, estimation_method)
        
        metric_cards = [
            {
                "id": "fair_spread",
                "label": "Fair CDS Spread",
                "value": f"{fair_spread_bps:.1f} bps",
                "sentiment": "neutral",
                "description": "Model-implied par spread"
            },
            {
                "id": "recovery_rate",
                "label": "Recovery Rate",
                "value": f"{recovery_rate:.0%}",
                "sentiment": "positive" if recovery_rate > 0.40 else "negative",
                "description": "From balance sheet assets"
            },
            {
                "id": "default_prob",
                "label": "Default Probability",
                "value": f"{default_probability:.2%}" if default_probability is not None else "N/A",
                "sentiment": "negative" if default_probability and default_probability > 0.05 else "neutral",
                "description": f"Over {tenor}"
            },
            {
                "id": "distance_to_default",
                "label": "Distance to Default",
                "value": f"{distance_to_default:.2f}" if distance_to_default is not None else "N/A",
                "sentiment": "positive" if distance_to_default and distance_to_default > 3 else "negative",
                "description": "Merton DD (higher = safer)"
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Reference", "metric": "Entity", "value": ticker},
            {"category": "CDS", "metric": "Notional", "value": f"${notional:,.0f}"},
            {"category": "CDS", "metric": "Tenor", "value": tenor},
            {"category": "Pricing", "metric": "Fair Spread", "value": f"{fair_spread_bps:.1f} bps"},
            {"category": "Pricing", "metric": "Recovery Rate", "value": f"{recovery_rate:.0%}"},
            {"category": "Credit", "metric": "Default Probability", "value": f"{default_probability:.2%}" if default_probability is not None else "N/A"},
            {"category": "Credit", "metric": "Distance to Default", "value": f"{distance_to_default:.2f}" if distance_to_default is not None else "N/A"},
            {"category": "Legs", "metric": "Premium Leg PV", "value": f"${premium_leg_pv:,.2f}"},
            {"category": "Legs", "metric": "Protection Leg PV", "value": f"${protection_leg_pv:,.2f}"},
            {"category": "Model", "metric": "Estimation Method", "value": method_display},
        ]
        
        # Add warnings if any
        if warnings:
            for warning in warnings[:3]:
                stats_table.append({"category": "Warnings", "metric": "⚠️", "value": warning[:80]})
        
        return {
            "status": "success",
            "tool_id": "cds",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "fair_spread_bps": fair_spread_bps,
                "recovery_rate": recovery_rate,
                "default_probability": default_probability,
                "distance_to_default": distance_to_default,
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"CDS execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}
