"""
RIM (Residual Income Model) Canvas Executor

Bank/financial institution valuation - wraps existing rim_tool.py
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def execute_rim(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute RIM analysis for Canvas.
    
    Wraps core/agents/valuation_tools/rim_tool.py
    Best for banks, insurance, REITs, and financials.
    """
    from core.agents.valuation_tools.rim_tool import analyze_rim_internal
    
    ticker = params.get('ticker') or params.get('underlying')
    if not ticker:
        return {"status": "error", "error": "Ticker is required"}
    
    ticker = ticker.upper()
    
    try:
        import json
        # Build params JSON for the internal function
        rim_params = {
            "terminal_roe": params.get('terminal_roe', 0.10),
            "book_value_growth": params.get('terminal_growth', 0.02),
            "forecast_years": int(params.get('projection_years', 5)),
            "use_tangible_book": params.get('use_tangible_book', False),
            "include_sensitivity": True,
            "monte_carlo": params.get('monte_carlo', False),
            "iterations": int(params.get('iterations', 1000)),
        }
        if params.get('cost_of_equity'):
            rim_params["cost_of_equity"] = params.get('cost_of_equity')
        
        # Call the internal RIM function
        result = await analyze_rim_internal(
            symbol=ticker,
            rim_params=json.dumps(rim_params),
            fields=None
        )
        
        if "error" in result:
            return {"status": "error", "error": result.get("error", "RIM calculation failed")}
        
        # Extract key values
        rim_data = result.get("rim_valuation", {})
        pb_analysis = result.get("price_to_book_analysis", {})
        
        intrinsic_value = rim_data.get("intrinsic_value_per_share", 0)
        current_price = rim_data.get("current_price", 0)
        upside = ((intrinsic_value / current_price) - 1) * 100 if current_price else 0
        
        book_value = rim_data.get("book_value_per_share", 0)
        current_pb = current_price / book_value if book_value else 0
        implied_pb = intrinsic_value / book_value if book_value else 0
        
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
                "id": "intrinsic_value",
                "label": "RIM Value",
                "value": f"${intrinsic_value:.2f}" if intrinsic_value else "N/A",
                "sentiment": "positive" if intrinsic_value > current_price else "negative",
            },
            {
                "id": "upside",
                "label": "Upside/Downside",
                "value": f"{upside:+.1f}%",
                "sentiment": "positive" if upside > 0 else "negative",
            },
            {
                "id": "current_pb",
                "label": "Current P/B",
                "value": f"{current_pb:.2f}x",
                "sentiment": "neutral",
            },
            {
                "id": "current_roe",
                "label": "Current ROE",
                "value": f"{rim_data.get('current_roe', 0)*100:.1f}%",
                "sentiment": "positive" if rim_data.get('current_roe', 0) > 0.10 else "neutral",
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Target", "metric": "Ticker", "value": ticker},
            {"category": "RIM", "metric": "Intrinsic Value", "value": f"${intrinsic_value:.2f}"},
            {"category": "RIM", "metric": "Current Price", "value": f"${current_price:.2f}"},
            {"category": "RIM", "metric": "Upside/Downside", "value": f"{upside:+.1f}%"},
            {"category": "Book Value", "metric": "Book Value/Share", "value": f"${book_value:.2f}"},
            {"category": "Book Value", "metric": "Current P/B", "value": f"{current_pb:.2f}x"},
            {"category": "Book Value", "metric": "Implied P/B", "value": f"{implied_pb:.2f}x"},
            {"category": "ROE", "metric": "Current ROE", "value": f"{rim_data.get('current_roe', 0)*100:.1f}%"},
            {"category": "ROE", "metric": "Terminal ROE", "value": f"{rim_data.get('terminal_roe', 0)*100:.1f}%"},
            {"category": "Inputs", "metric": "Cost of Equity", "value": f"{rim_data.get('cost_of_equity', 0)*100:.1f}%"},
            {"category": "Inputs", "metric": "Terminal Growth", "value": f"{rim_data.get('terminal_growth', 0)*100:.1f}%"},
        ]
        
        # Add P/B analysis if available
        if pb_analysis:
            stats_table.append({"category": "P/B Analysis", "metric": "─" * 20, "value": "─" * 15})
            justified_pb = pb_analysis.get("justified_pb", 0)
            stats_table.append({
                "category": "P/B",
                "metric": "Justified P/B (Gordon)",
                "value": f"{justified_pb:.2f}x"
            })
        
        return {
            "status": "success",
            "tool_id": "rim",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "intrinsic_value": intrinsic_value,
                "current_price": current_price,
                "upside_pct": upside,
                "current_pb": current_pb,
                "current_roe": rim_data.get("current_roe", 0),
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"RIM analysis failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}

