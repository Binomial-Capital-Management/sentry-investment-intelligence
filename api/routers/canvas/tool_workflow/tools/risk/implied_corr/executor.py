"""
Executor for Implied Correlation Canvas tool.
Calculates market-implied correlation from index options using the variance-decomposition method.
"""

import logging
from typing import Dict, Any, Optional

from core.agents.risk_tools import calculate_implied_correlation_internal
from .charts import build_weights_chart, build_volatility_chart, build_breakdown_chart

logger = logging.getLogger(__name__)


async def execute_implied_corr(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute Implied Correlation calculation for Canvas.
    
    Args:
        user_id: User ID
        org_id: Organization ID
        params: Tool parameters from frontend
        
    Returns:
        Canvas-formatted result with metrics, stats, and charts
    """
    try:
        # Extract parameters
        index_ticker = params.get("index_ticker", "").strip().upper()
        if not index_ticker:
            return {
                "status": "error",
                "error": "Please provide an index ticker (e.g., SPY, QQQ, IWM)",
                "tool_id": "implied_corr"
            }
        
        tenor = params.get("tenor", "3m")
        strike_reference = params.get("strike_reference", "ATM")
        top_n = int(params.get("top_n_constituents", 20))
        
        # Advanced parameters (optional)
        expiry_tolerance_days = int(params.get("expiry_tolerance_days", 7))
        atm_strike_tolerance = float(params.get("atm_strike_tolerance", 0.05))
        delta_call_target = float(params.get("delta_call_target", 0.50))
        delta_put_target = float(params.get("delta_put_target", -0.50))
        delta_tolerance = float(params.get("delta_tolerance", 0.10))
        
        logger.info(
            f"Executing Implied Correlation: {index_ticker}, "
            f"tenor={tenor}, strike={strike_reference}, top_n={top_n}"
        )
        
        # Call internal agent function
        result = await calculate_implied_correlation_internal(
            index_ticker=index_ticker,
            tenor=tenor,
            strike_reference=strike_reference,
            top_n_constituents=top_n,
            expiry_tolerance_days=expiry_tolerance_days,
            atm_strike_tolerance=atm_strike_tolerance,
            delta_call_target=delta_call_target,
            delta_put_target=delta_put_target,
            delta_tolerance=delta_tolerance,
            zero_tolerance=1e-10
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Unknown error"),
                "tool_id": "implied_corr"
            }
        
        # Extract data
        correlation_pct = result.get("correlation_pct", 0.0)
        index_iv = result.get("index_iv", 0.0)
        n_constituents = result.get("n_constituents", 0)
        constituent_data = result.get("constituent_data", [])
        calculation_details = result.get("calculation_details", {})
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            correlation_pct,
            index_iv,
            n_constituents,
            tenor,
            index_ticker
        )
        
        # Build stats table
        stats_table = _build_stats_table(constituent_data, index_ticker)
        
        # Build charts from raw data (not from agent's chart handles)
        charts = []
        
        if constituent_data:
            weights_chart = build_weights_chart(constituent_data, index_ticker)
            if weights_chart:
                charts.append(weights_chart)
            
            volatility_chart = build_volatility_chart(
                index_ticker,
                index_iv,
                constituent_data
            )
            if volatility_chart:
                charts.append(volatility_chart)
        
        if calculation_details:
            breakdown_chart = build_breakdown_chart(calculation_details)
            if breakdown_chart:
                charts.append(breakdown_chart)
        
        return {
            "status": "success",
            "tool_id": "implied_corr",
            "result": {
                "summary": (
                    f"**{index_ticker} Implied Correlation ({tenor.upper()}):** "
                    f"{correlation_pct:.1f}%\n\n"
                    f"Market-implied correlation between {n_constituents} constituents "
                    f"using {strike_reference} options. "
                    f"Index IV: {index_iv*100:.1f}%."
                ),
                "metric_cards": metric_cards,
                "stats_table": stats_table,
                "charts": charts,
                "raw_data": {
                    "correlation_pct": correlation_pct,
                    "index_iv": index_iv,
                    "index_ticker": index_ticker,
                    "tenor": tenor,
                    "strike_reference": strike_reference,
                    "n_constituents": n_constituents,
                    "constituent_data": constituent_data,
                    "calculation_details": calculation_details
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Implied Correlation execution error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"Failed to calculate implied correlation: {str(e)}",
            "tool_id": "implied_corr"
        }


def _build_metric_cards(
    correlation_pct: float,
    index_iv: float,
    n_constituents: int,
    tenor: str,
    index_ticker: str
) -> list:
    """Build metric cards for Canvas UI."""
    
    # Interpret correlation level
    if correlation_pct >= 75:
        corr_level = "Very High"
        corr_color = "red"
    elif correlation_pct >= 50:
        corr_level = "High"
        corr_color = "orange"
    elif correlation_pct >= 25:
        corr_level = "Moderate"
        corr_color = "blue"
    else:
        corr_level = "Low"
        corr_color = "green"
    
    return [
        {
            "label": "Implied Correlation",
            "value": f"{correlation_pct:.1f}%",
            "subtitle": f"{corr_level} ({tenor.upper()})",
            "color": corr_color
        },
        {
            "label": f"{index_ticker} Index IV",
            "value": f"{index_iv*100:.1f}%",
            "subtitle": "Implied Volatility",
            "color": "purple"
        },
        {
            "label": "Constituents Analyzed",
            "value": str(n_constituents),
            "subtitle": f"Top holdings of {index_ticker}",
            "color": "gray"
        }
    ]


def _build_stats_table(constituent_data: list, index_ticker: str) -> Dict[str, Any]:
    """Build constituent details stats table."""
    if not constituent_data:
        return {"columns": [], "rows": []}
    
    # Sort by weight descending
    sorted_data = sorted(constituent_data, key=lambda x: x['weight'], reverse=True)
    
    rows = []
    for item in sorted_data:
        rows.append({
            "Ticker": item['ticker'],
            "Weight": f"{item['weight']*100:.2f}%",
            "Implied Vol": f"{item['iv']*100:.1f}%",
            "Contribution": f"{item['weight'] * item['iv'] * 100:.2f}%"  # Weight * IV
        })
    
    return {
        "columns": ["Ticker", "Weight", "Implied Vol", "Contribution"],
        "rows": rows,
        "title": f"{index_ticker} Constituent Breakdown"
    }
