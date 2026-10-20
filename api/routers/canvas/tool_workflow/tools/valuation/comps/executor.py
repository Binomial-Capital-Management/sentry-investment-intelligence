"""
Comparable Companies Analysis Canvas Executor

Wraps the existing comps_tool.py for Canvas visualization.
"""
from typing import Dict, List, Any, Optional
import logging

from .charts import build_football_field_chart, build_multiples_comparison_chart

logger = logging.getLogger(__name__)

async def execute_comps(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Comparable Companies analysis for Canvas.
    
    Wraps core/agents/valuation_tools/comps_tool.py
    """
    from core.agents.valuation_tools.comps_tool import analyze_comparable_companies_internal
    
    target = params.get('ticker') or params.get('target')
    if not target:
        return {"status": "error", "error": "Target ticker is required"}
    
    target = target.upper()
    
    # Get peers from user input
    peers = params.get('peers', '')
    if isinstance(peers, str):
        peers = [p.strip().upper() for p in peers.split(',') if p.strip()]
    
    if not peers:
        return {"status": "error", "error": "Peers are required (comma-separated tickers)"}
    
    # Get selected multiples from user or use defaults - only ratios
    multiples = params.get('multiples', [
        "priceToEarningsRatioTTM",  # P/E
        "priceToBookRatioTTM",       # P/B  
        "priceToSalesRatioTTM",      # P/S
        "evToEBITDATTM",             # EV/EBITDA
        "priceToFreeCashFlowRatioTTM"  # P/FCF
    ])
    if isinstance(multiples, str):
        multiples = [m.strip() for m in multiples.split(',') if m.strip()]
    
    # Filter out non-ratio fields that user might have included
    non_ratio_fields = {"price", "marketCap", "market_cap", "stockPrice"}
    multiples = [m for m in multiples if m.lower() not in {f.lower() for f in non_ratio_fields}]
    
    # Include price internally for fair value calculations (but won't be displayed as a multiple)
    fields = ["price"] + multiples
    
    try:
        # Call the existing comps tool's internal function
        result = await analyze_comparable_companies_internal(
            target_ticker=target,
            peer_tickers=peers,
            fields=fields,
            include_football_field=True,
        )
        
        if "error" in result:
            return {"status": "error", "error": result.get("error", "Analysis failed")}
        
        # Extract data from tool result - data is nested inside comp_results
        comp_results = result.get("comp_results", {})
        fair_value = comp_results.get("fair_value", {})
        football_field = comp_results.get("football_field", {})
        comparison_table = comp_results.get("comparison_table", {})
        
        # Fair value keys from comps_tool: fair_value_median, upside_pct_median
        current_price = fair_value.get("current_price", 0)
        implied_value = fair_value.get("fair_value_median") or fair_value.get("fair_value_mean", 0)
        upside = fair_value.get("upside_pct_median") or fair_value.get("upside_pct_mean", 0)
        
        # Build valuation ranges from football field (uses low/high, not bear/bull)
        valuation_ranges = []
        for method_data in football_field.get("methods", []):
            low = method_data.get("low", 0)
            high = method_data.get("high", 0)
            mid = (low + high) / 2 if low and high else 0
            valuation_ranges.append({
                "method": method_data.get("method", "Unknown"),
                "bear_case": low,
                "base_case": mid,
                "bull_case": high,
            })
        
        # Build peer stats from field_statistics (not comparison_table)
        # Filter out non-ratio fields
        skip_fields = {"price", "marketCap", "market_cap", "stockPrice", "marketCapitalization"}
        field_statistics = comp_results.get("field_statistics", {})
        peer_stats = {}
        for field_name, stats in field_statistics.items():
            # Skip non-ratio fields
            if field_name.lower() in {f.lower() for f in skip_fields}:
                continue
            if isinstance(stats, dict) and stats.get("target_value") is not None:
                peer_stats[field_name] = {
                    "target_value": stats.get("target_value", 0),
                    "peer_median": stats.get("median", 0),
                    "peer_mean": stats.get("mean", 0),
                    "peer_min": stats.get("min", 0),
                    "peer_max": stats.get("max", 0),
                    "premium_discount": stats.get("target_vs_median_pct", 0),
                }
        
        # Build charts
        charts = {}
        
        if valuation_ranges:
            football_chart = build_football_field_chart(target, current_price, valuation_ranges)
            if football_chart:
                charts["football_field"] = football_chart
        
        if peer_stats:
            multiples_chart = build_multiples_comparison_chart(target, peer_stats)
            if multiples_chart:
                charts["multiples_comparison"] = multiples_chart
        
        # Also include any charts from the tool result
        if "charts" in result:
            result_charts = result["charts"]
            # Handle both dict and list formats
            if isinstance(result_charts, dict):
                for chart_id, chart_data in result_charts.items():
                    if chart_id not in charts:
                        charts[chart_id] = chart_data
            elif isinstance(result_charts, list):
                for i, chart_data in enumerate(result_charts):
                    chart_id = chart_data.get("id", f"chart_{i}") if isinstance(chart_data, dict) else f"chart_{i}"
                    if chart_id not in charts:
                        charts[chart_id] = chart_data
        
        # Use successful peers from result (fallback to input peers)
        successful_peers = result.get("peers", peers)
        
        # Get comparison table for display
        comparison_table_formatted = comp_results.get("comparison_table_formatted", [])
        
        # Build metric cards
        metric_cards = _build_metric_cards(target, current_price, implied_value, upside, successful_peers, peer_stats)
        
        # Build stats table with comparison data
        stats_table = _build_stats_table(
            target, peer_stats, valuation_ranges, successful_peers, fair_value,
            comparison_table=comparison_table_formatted
        )
        
        return {
            "status": "success",
            "tool_id": "comps",
            "tickers": [target] + successful_peers,
            "weights": [],
            "metrics": {
                "current_price": current_price,
                "implied_value": implied_value,
                "upside_pct": upside,
                "peers_count": len(successful_peers),
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Comps analysis failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


def _format_ratio_name(field_name: str) -> str:
    """Convert FMP field names to readable ratio labels."""
    name_map = {
        # P/E variants
        "priceToEarningsRatioTTM": "P/E",
        "priceToEarningsRatio": "P/E",
        "peRatioTTM": "P/E",
        "peRatio": "P/E",
        "pe": "P/E",
        # P/B variants
        "priceToBookRatioTTM": "P/B",
        "priceToBookRatio": "P/B",
        # P/S variants
        "priceToSalesRatioTTM": "P/S",
        "priceToSalesRatio": "P/S",
        # EV/EBITDA variants
        "evToEBITDATTM": "EV/EBITDA",
        "evToEBITDA": "EV/EBITDA",
        "enterpriseValueMultipleTTM": "EV/EBITDA",
        "enterpriseValueMultiple": "EV/EBITDA",
        # P/FCF variants
        "priceToFreeCashFlowRatioTTM": "P/FCF",
        "priceToFreeCashFlowRatio": "P/FCF",
        # P/OCF variants
        "priceToOperatingCashFlowRatioTTM": "P/OCF",
        "priceToOperatingCashFlowRatio": "P/OCF",
        # EV/Sales variants
        "evToSalesTTM": "EV/Sales",
        "evToSales": "EV/Sales",
        # EV/FCF variants
        "evToFreeCashFlowTTM": "EV/FCF",
        "evToFreeCashFlow": "EV/FCF",
        # PEG variants
        "priceToEarningsGrowthRatioTTM": "PEG",
        "priceToEarningsGrowthRatio": "PEG",
        "pegRatioTTM": "PEG",
        "pegRatio": "PEG",
        # Dividend
        "dividendYieldTTM": "Div Yield",
        "dividendYield": "Div Yield",
    }
    return name_map.get(field_name, field_name)


def _build_metric_cards(
    target: str,
    current_price: float,
    implied_value: float,
    upside: float,
    peers: List[str],
    peer_stats: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build metric cards from comps analysis."""
    cards = []
    
    # Current price
    cards.append({
        "id": "current_price",
        "label": "Current Price",
        "value": f"${current_price:.2f}" if current_price else "N/A",
        "sentiment": "neutral",
    })
    
    # Implied value
    cards.append({
        "id": "implied_value",
        "label": "Fair Value",
        "value": f"${implied_value:.2f}" if implied_value else "N/A",
        "sentiment": "positive" if implied_value and current_price and implied_value > current_price else "negative",
    })
    
    # Upside/Downside
    cards.append({
        "id": "upside",
        "label": "Upside/Downside",
        "value": f"{upside:+.1f}%" if upside else "N/A",
        "sentiment": "positive" if upside and upside > 0 else "negative",
    })
    
    # Peer count
    cards.append({
        "id": "peers",
        "label": "Peer Group",
        "value": f"{len(peers)} companies",
        "sentiment": "neutral",
    })
    
    # P/E premium/discount - check multiple key formats
    pe_stats = peer_stats.get("peRatio") or peer_stats.get("P/E") or peer_stats.get("pe_ratio")
    if pe_stats:
        pe_premium = pe_stats.get("premium_discount", 0)
        cards.append({
            "id": "pe_premium",
            "label": "P/E vs Peers",
            "value": f"{pe_premium:+.1f}%",
            "sentiment": "negative" if pe_premium > 20 else ("positive" if pe_premium < -10 else "neutral"),
        })
    
    return cards


def _build_stats_table(
    target: str,
    peer_stats: Dict[str, Any],
    valuation_ranges: List[Dict[str, Any]],
    peers: List[str],
    fair_value: Dict[str, Any],
    comparison_table: List[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Build stats table from comps analysis."""
    rows = []
    
    # Target info
    rows.append({"category": "Target", "metric": "Ticker", "value": target})
    rows.append({"category": "Target", "metric": "Peers Analyzed", "value": str(len(peers))})
    
    current_price = fair_value.get("current_price", 0)
    composite_fv = fair_value.get("composite_fair_value", 0)
    upside = fair_value.get("upside_percent", 0)
    if current_price:
        rows.append({"category": "Target", "metric": "Current Price", "value": f"${current_price:.2f}"})
    if composite_fv:
        rows.append({"category": "Target", "metric": "Composite Fair Value", "value": f"${composite_fv:.2f}"})
    if upside:
        rows.append({"category": "Target", "metric": "Upside/Downside", "value": f"{upside:+.1f}%"})
    
    # Comparison table - show each company's multiples (ratios only)
    # Fields to exclude from display (not ratios)
    exclude_fields = {"Company", "index", "price", "marketCap", "market_cap", "stockPrice"}
    
    if comparison_table:
        rows.append({"category": "Comparison", "metric": "─" * 20, "value": "─" * 15})
        for company_data in comparison_table:
            company = company_data.get("Company", "Unknown")
            # Add each ratio for this company
            for key, value in company_data.items():
                if key in exclude_fields:
                    continue
                # Format the value
                if isinstance(value, (int, float)):
                    formatted = f"{value:.2f}x"
                elif value == "N/A" or value is None:
                    formatted = "N/A"
                else:
                    formatted = str(value)
                rows.append({
                    "category": company,
                    "metric": _format_ratio_name(key),
                    "value": formatted
                })
    
    # Valuation ranges (football field data)
    if valuation_ranges:
        rows.append({"category": "Valuation Ranges", "metric": "─" * 20, "value": "─" * 15})
        for vr in valuation_ranges:
            bear = vr.get('bear_case', 0)
            base = vr.get('base_case', 0)
            bull = vr.get('bull_case', 0)
            if bear or base or bull:  # Only show if we have data
                rows.append({
                    "category": vr.get("method", "Unknown"),
                    "metric": "Low / Mid / High",
                    "value": f"${bear:.0f} / ${base:.0f} / ${bull:.0f}"
                })
    
    # Peer stats summary - only ratios
    skip_fields = {"price", "marketCap", "market_cap", "stockPrice"}
    if peer_stats:
        rows.append({"category": "Multiple Analysis", "metric": "─" * 20, "value": "─" * 15})
        for mult_name, stats in peer_stats.items():
            if mult_name.lower() in {f.lower() for f in skip_fields}:
                continue
            target_val = stats.get('target_value', 0)
            peer_med = stats.get('peer_median', 0)
            prem_disc = stats.get('premium_discount', 0)
            if target_val or peer_med:  # Only show if we have data
                display_name = _format_ratio_name(mult_name)
                rows.append({
                    "category": display_name,
                    "metric": f"{target} vs Median",
                    "value": f"{target_val:.2f}x vs {peer_med:.2f}x ({prem_disc:+.1f}%)"
                })
    
    return rows
