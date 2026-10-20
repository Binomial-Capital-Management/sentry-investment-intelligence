"""
Canvas executor for Dispersion Trade.

Prices dispersion trades: long index vol, short constituent vols.
Profits when correlation decreases (constituents move independently).
"""

import logging
from typing import Any, Dict, List, Optional

from .charts import build_correlation_chart, build_position_chart, build_vega_chart

logger = logging.getLogger(__name__)


async def execute_dispersion(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute dispersion trade pricing for Canvas.
    """
    from core.agents.structuring_tools.dispersion_trade_tool import price_dispersion_trade_internal
    
    # Extract parameters
    index_ticker = params.get("index_ticker", "SPY").upper()
    num_constituents = int(params.get("num_constituents", 10))
    notional = float(params.get("notional", 1_000_000))
    tenor = params.get("tenor", "3M")
    
    logger.info(f"Executing Dispersion trade: {index_ticker}, top {num_constituents} constituents")
    
    try:
        # Call internal function - it auto-fetches ETF holdings
        result = await price_dispersion_trade_internal(
            index_ticker=index_ticker,
            notional=notional,
            num_constituents=num_constituents,
            tenor=tenor,
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Dispersion pricing failed"),
                "tool_id": "dispersion",
            }
        
        # Extract key data
        net_cost = result.get("net_cost", 0)
        correlation_beta = result.get("correlation_beta", 0)
        realized_corr = result.get("current_avg_correlation", 0)
        implied_corr = result.get("implied_correlation", 0)
        net_vega = result.get("net_vega", 0)
        net_delta = result.get("net_delta", 0)
        index_cost = result.get("index_straddle_cost", 0)
        constituent_cost = result.get("constituent_straddles_cost", 0)
        index_data = result.get("index_data", {})
        constituent_data = result.get("constituent_data", [])
        summary = result.get("summary", "")
        
        # Get tickers from constituent data
        constituent_tickers = [c.get("ticker", "") for c in constituent_data]
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            net_cost, correlation_beta, realized_corr, implied_corr, net_vega, index_ticker
        )
        
        # Build stats table
        stats_table = _build_stats_table(
            result, index_data, constituent_data, result.get("index_contracts", 0)
        )
        
        # Build charts
        charts = {}
        
        corr_chart = build_correlation_chart(realized_corr, implied_corr)
        if corr_chart:
            charts["correlation"] = corr_chart
        
        pos_chart = build_position_chart(index_cost, constituent_cost, net_cost)
        if pos_chart:
            charts["positions"] = pos_chart
        
        vega_chart = build_vega_chart(constituent_data)
        if vega_chart:
            charts["vega"] = vega_chart
        
        logger.info(f"Built {len(charts)} charts for dispersion trade")
        
        return {
            "status": "success",
            "tool_id": "dispersion",
            "tickers": [index_ticker] + constituent_tickers,
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "net_cost": net_cost,
                "correlation_beta": correlation_beta,
                "realized_correlation": realized_corr,
                "implied_correlation": implied_corr,
                "net_vega": net_vega,
                "net_delta": net_delta,
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Dispersion Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "dispersion",
        }


def _build_metric_cards(
    net_cost: float,
    correlation_beta: float,
    realized_corr: float,
    implied_corr: float,
    net_vega: float,
    index_ticker: str,
) -> List[Dict[str, Any]]:
    """Build displayable metric cards."""
    cards = []
    
    cards.append({
        "id": "net_cost",
        "label": "Net Cost",
        "value": f"${net_cost:,.0f}",
        "description": "Initial outlay",
        "sentiment": "neutral",
    })
    
    cards.append({
        "id": "corr_beta",
        "label": "Correlation Beta",
        "value": f"${correlation_beta:,.0f}",
        "description": "P&L per 1% corr move",
        "sentiment": "positive" if correlation_beta > 0 else "negative",
    })
    
    corr_diff = implied_corr - realized_corr
    cards.append({
        "id": "corr_spread",
        "label": "Correlation Spread",
        "value": f"{corr_diff:+.1%}",
        "description": "Implied - Realized",
        "sentiment": "positive" if corr_diff < 0 else "negative",
    })
    
    cards.append({
        "id": "net_vega",
        "label": "Net Vega",
        "value": f"${net_vega:,.0f}",
        "description": "Should be ~0",
        "sentiment": "positive" if abs(net_vega) < 1000 else "neutral",
    })
    
    return cards


def _build_stats_table(
    result: Dict[str, Any],
    index_data: Dict[str, Any],
    constituent_data: List[Dict[str, Any]],
    index_contracts: int,
) -> List[Dict[str, str]]:
    """Build comprehensive stats table."""
    rows = []
    inputs = result.get("inputs", {})
    
    rows.append({"category": "Trade", "metric": "Index", "value": inputs.get("index_ticker", "")})
    rows.append({"category": "Trade", "metric": "Notional", "value": f"${inputs.get('notional', 0):,.0f}"})
    rows.append({"category": "Trade", "metric": "Tenor", "value": inputs.get("tenor", "")})
    rows.append({"category": "Trade", "metric": "Constituents", "value": str(len(constituent_data))})
    
    if index_data:
        rows.append({"category": "Index", "metric": "Contracts", "value": str(index_contracts)})
        rows.append({"category": "Index", "metric": "IV", "value": f"{index_data.get('avg_iv', 0):.1%}"})
        rows.append({"category": "Index", "metric": "Straddle Price", "value": f"${index_data.get('straddle_price', 0):,.2f}"})
        rows.append({"category": "Index", "metric": "Vega", "value": f"{index_data.get('vega', 0):.4f}"})
    
    rows.append({"category": "Correlation", "metric": "Realized", "value": f"{result.get('current_avg_correlation', 0):.1%}"})
    rows.append({"category": "Correlation", "metric": "Implied", "value": f"{result.get('implied_correlation', 0):.1%}"})
    rows.append({"category": "Correlation", "metric": "Beta ($/1%)", "value": f"${result.get('correlation_beta', 0):,.0f}"})
    
    rows.append({"category": "Costs", "metric": "Index Cost", "value": f"${result.get('index_straddle_cost', 0):,.0f}"})
    rows.append({"category": "Costs", "metric": "Constituents Cost", "value": f"${result.get('constituent_straddles_cost', 0):,.0f}"})
    rows.append({"category": "Costs", "metric": "Net Cost", "value": f"${result.get('net_cost', 0):,.0f}"})
    
    rows.append({"category": "Greeks", "metric": "Net Vega", "value": f"${result.get('net_vega', 0):,.2f}"})
    rows.append({"category": "Greeks", "metric": "Net Delta", "value": f"{result.get('net_delta', 0):,.4f}"})
    
    return rows
