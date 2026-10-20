"""
EPV (Earnings Power Value) Canvas Executor

Graham/Dodd normalized earnings valuation - wraps existing epv_tool.py
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def execute_epv(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute EPV analysis for Canvas.
    
    Wraps core/agents/valuation_tools/epv_tool.py
    """
    from core.agents.valuation_tools.epv_tool import analyze_epv_internal
    
    ticker = params.get('ticker') or params.get('underlying')
    if not ticker:
        return {"status": "error", "error": "Ticker is required"}
    
    ticker = ticker.upper()
    
    try:
        import json
        # Build params JSON for the internal function
        epv_params = {
            "normalization_years": int(params.get('normalization_years', 5)),
            "normalization_method": params.get('normalization_method', 'weighted'),
            "include_sensitivity": True,
            "include_multiples_comparison": True,
        }
        if params.get('wacc'):
            epv_params["wacc"] = params.get('wacc')
        if params.get('tax_rate'):
            epv_params["tax_rate"] = params.get('tax_rate')
        
        # Call the internal EPV function
        result = await analyze_epv_internal(
            symbol=ticker,
            epv_params=json.dumps(epv_params),
            fields=["operatingIncome", "ebit", "price", "marketCap", "beta"]
        )
        
        if "error" in result:
            return {"status": "error", "error": result.get("error", "EPV calculation failed")}
        
        # Extract key values
        epv_data = result.get("epv_valuation", {})
        sensitivity = result.get("sensitivity_analysis", {})
        multiples = result.get("multiples_comparison", {})
        
        epv_per_share = epv_data.get("epv_per_share", 0)
        current_price = epv_data.get("current_price", 0)
        upside = ((epv_per_share / current_price) - 1) * 100 if current_price else 0
        
        # Build charts from tool result
        charts = {}
        if "charts" in result:
            for chart_id, chart_data in result["charts"].items():
                charts[chart_id] = chart_data
        
        # Build metric cards
        metric_cards = [
            {
                "id": "current_price",
                "label": "Current Price",
                "value": f"${current_price:.2f}" if current_price else "N/A",
                "sentiment": "neutral",
            },
            {
                "id": "epv_per_share",
                "label": "EPV / Share",
                "value": f"${epv_per_share:.2f}" if epv_per_share else "N/A",
                "sentiment": "positive" if epv_per_share > current_price else "negative",
            },
            {
                "id": "upside",
                "label": "Margin of Safety",
                "value": f"{upside:+.1f}%",
                "sentiment": "positive" if upside > 0 else "negative",
            },
            {
                "id": "wacc",
                "label": "WACC Used",
                "value": f"{epv_data.get('wacc_used', 0)*100:.1f}%",
                "sentiment": "neutral",
            },
            {
                "id": "norm_nopat",
                "label": "Normalized NOPAT",
                "value": f"${epv_data.get('normalized_nopat', 0)/1e9:.2f}B",
                "sentiment": "neutral",
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Target", "metric": "Ticker", "value": ticker},
            {"category": "EPV", "metric": "EPV Per Share", "value": f"${epv_per_share:.2f}"},
            {"category": "EPV", "metric": "Current Price", "value": f"${current_price:.2f}"},
            {"category": "EPV", "metric": "Upside/Downside", "value": f"{upside:+.1f}%"},
            {"category": "Inputs", "metric": "WACC", "value": f"{epv_data.get('wacc_used', 0)*100:.2f}%"},
            {"category": "Inputs", "metric": "Tax Rate", "value": f"{epv_data.get('tax_rate', 0)*100:.1f}%"},
            {"category": "Inputs", "metric": "Normalization Years", "value": str(epv_data.get('normalization_years', 5))},
            {"category": "Calc", "metric": "Normalized EBIT", "value": f"${epv_data.get('normalized_ebit', 0)/1e9:.2f}B"},
            {"category": "Calc", "metric": "Normalized NOPAT", "value": f"${epv_data.get('normalized_nopat', 0)/1e9:.2f}B"},
            {"category": "Calc", "metric": "Enterprise EPV", "value": f"${epv_data.get('epv_enterprise', 0)/1e9:.2f}B"},
            {"category": "Calc", "metric": "Net Debt", "value": f"${epv_data.get('net_debt', 0)/1e9:.2f}B"},
        ]
        
        # Add multiples comparison if available
        if multiples:
            stats_table.append({"category": "Multiples", "metric": "─" * 20, "value": "─" * 15})
            for mult_name, mult_val in multiples.items():
                if isinstance(mult_val, (int, float)):
                    stats_table.append({
                        "category": "Multiples",
                        "metric": mult_name,
                        "value": f"{mult_val:.2f}x" if "EV" in mult_name or "P/" in mult_name else f"{mult_val:.2f}"
                    })
        
        return {
            "status": "success",
            "tool_id": "epv",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "epv_per_share": epv_per_share,
                "current_price": current_price,
                "upside_pct": upside,
                "wacc": epv_data.get("wacc_used", 0),
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"EPV analysis failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}

