"""
Reverse DCF Canvas Executor

Back-solve for market-implied growth rate from current stock price.
"""
from typing import Dict, List, Any, Optional
import logging

from .charts import build_growth_waterfall_chart, build_sensitivity_heatmap

logger = logging.getLogger(__name__)


async def execute_reverse_dcf(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Reverse DCF analysis for Canvas.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including ticker, discount_rate, etc.
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
    from core.mcp_servers.fmp.FMPAdvancedValuationServer import FMPAdvancedValuationServer
    from core.utils.mcp_result_parser import safe_parse_json
    
    ticker = params.get('ticker') or params.get('underlying')
    if not ticker:
        return {"status": "error", "error": "Ticker is required"}
    
    ticker = ticker.upper()
    
    try:
        # Fetch financial data
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Fetch key metrics
        fields = [
            "price", "netIncomePerShareTTM", "freeCashFlowPerShareTTM",
            "marketCap", "beta", "outstandingShares"
        ]
        
        result = await market_server.call_tool("get_fields", {
            "symbol": ticker,
            "fields": fields,
            "params": {"period": "annual", "limit": 1}
        })
        
        raw_data = {}
        if result and hasattr(result, 'content'):
            data = safe_parse_json(result)
            if data.get("status") != "missing_required_params":
                raw_data = data.get("data", data)
        
        await market_server.cleanup()
        
        if not raw_data:
            return {"status": "error", "error": f"No financial data found for {ticker}"}
        
        # Extract values
        price = raw_data.get("price")
        eps = raw_data.get("netIncomePerShareTTM") or raw_data.get("eps")
        fcf_per_share = raw_data.get("freeCashFlowPerShareTTM")
        beta = raw_data.get("beta", 1.0)
        market_cap = raw_data.get("marketCap")
        shares = raw_data.get("outstandingShares")
        
        if price is None:
            return {"status": "error", "error": f"Missing price data for {ticker}"}
        
        # Model parameters
        model_type = params.get('model_type', 'eps')
        if model_type == 'eps':
            base_metric = eps
        elif model_type in ['fcf', 'fcfe']:
            base_metric = fcf_per_share
        else:
            base_metric = eps
        
        if base_metric is None or base_metric <= 0:
            return {"status": "error", "error": f"Invalid base metric ({model_type}): {base_metric}"}
        
        # Calculate discount rate from CAPM if not provided
        if 'discount_rate' in params:
            discount_rate = params['discount_rate']
        else:
            risk_free = params.get('risk_free_rate', 0.04)
            market_premium = params.get('market_risk_premium', 0.05)
            discount_rate = risk_free + (beta or 1.0) * market_premium
        
        # DCF parameters (ensure integers for range())
        stages = int(params.get('stages', 2))
        stage1_years = int(params.get('stage1_years', 5))
        stage2_years = int(params.get('stage2_years', 5))  # Fade period for 3-stage
        terminal_growth = float(params.get('terminal_growth', 0.025))
        growth_bounds = params.get('growth_bounds', (-0.05, 0.50))
        
        # Solve for implied growth
        result = _solve_implied_growth(
            target_price=price,
            base_metric=base_metric,
            discount_rate=discount_rate,
            stages=stages,
            stage1_years=stage1_years,
            stage2_years=stage2_years,
            terminal_growth=terminal_growth,
            growth_bounds=growth_bounds,
        )
        
        if "error" in result:
            return {"status": "error", "error": result["error"]}
        
        implied_growth = result["implied_growth_rate"]
        calculated_value = result["calculated_dcf_value"]
        
        # Sensitivity analysis
        sensitivity_grid = _build_sensitivity_grid(
            base_metric, discount_rate, stages, stage1_years,
            stage2_years, terminal_growth, growth_bounds, price  # Pass actual price
        )
        
        # Build charts
        charts = {}
        
        # Growth waterfall
        waterfall_chart = build_growth_waterfall_chart(
            ticker, implied_growth, terminal_growth, price, calculated_value
        )
        if waterfall_chart:
            charts["growth_waterfall"] = waterfall_chart
        
        # Sensitivity heatmap
        sensitivity_chart = build_sensitivity_heatmap(
            sensitivity_grid, implied_growth, discount_rate
        )
        if sensitivity_chart:
            charts["sensitivity_heatmap"] = sensitivity_chart
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            ticker, price, implied_growth, discount_rate, base_metric, model_type, calculated_value
        )
        
        # Build stats table
        stats_table = _build_stats_table(
            ticker, price, implied_growth, discount_rate, terminal_growth,
            base_metric, model_type, stages, stage1_years, beta, result
        )
        
        # Metrics for persistence
        metrics = {
            "implied_growth_rate": implied_growth,
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth,
            "current_price": price,
            "calculated_dcf_value": calculated_value,
            "base_metric": base_metric,
            "model_type": model_type,
            "stages": stages,
        }
        
        return {
            "status": "success",
            "tool_id": "reverse_dcf",
            "tickers": [ticker],
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Reverse DCF execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


def _solve_implied_growth(
    target_price: float,
    base_metric: float,
    discount_rate: float,
    stages: int,
    stage1_years: int,
    stage2_years: int,
    terminal_growth: float,
    growth_bounds: tuple,
    tolerance: float = 0.01,
    max_iterations: int = 100,
) -> Dict[str, Any]:
    """Use bisection to find implied growth rate."""
    low, high = growth_bounds
    
    # Check bounds
    dcf_low = _calculate_dcf_value(base_metric, low, discount_rate, stages, stage1_years, stage2_years, terminal_growth)
    dcf_high = _calculate_dcf_value(base_metric, high, discount_rate, stages, stage1_years, stage2_years, terminal_growth)
    
    if dcf_low > target_price and dcf_high > target_price:
        return {"error": "Stock appears overvalued vs any reasonable growth rate"}
    if dcf_low < target_price and dcf_high < target_price:
        return {"error": "Stock appears undervalued vs any reasonable growth rate"}
    
    iterations = 0
    while iterations < max_iterations:
        mid = (low + high) / 2
        dcf_mid = _calculate_dcf_value(base_metric, mid, discount_rate, stages, stage1_years, stage2_years, terminal_growth)
        
        if abs(dcf_mid - target_price) < tolerance:
            return {
                "implied_growth_rate": mid,
                "calculated_dcf_value": dcf_mid,
                "iterations": iterations + 1,
                "converged": True,
            }
        
        if dcf_mid < target_price:
            low = mid
        else:
            high = mid
        
        iterations += 1
    
    mid = (low + high) / 2
    dcf_mid = _calculate_dcf_value(base_metric, mid, discount_rate, stages, stage1_years, stage2_years, terminal_growth)
    return {
        "implied_growth_rate": mid,
        "calculated_dcf_value": dcf_mid,
        "iterations": iterations,
        "converged": False,
    }


def _calculate_dcf_value(
    base_metric: float,
    growth_rate: float,
    discount_rate: float,
    stages: int,
    stage1_years: int,
    stage2_years: int,
    terminal_growth: float,
) -> float:
    """Calculate DCF intrinsic value per share."""
    if base_metric is None or base_metric <= 0:
        return 0.0
    
    total_pv = 0.0
    current_cf = base_metric
    
    if stages == 1:
        if discount_rate <= terminal_growth:
            return float('inf')
        return current_cf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    
    elif stages == 2:
        # Stage 1: High growth
        for year in range(1, stage1_years + 1):
            current_cf = current_cf * (1 + growth_rate)
            pv = current_cf / ((1 + discount_rate) ** year)
            total_pv += pv
        
        # Terminal value
        if discount_rate <= terminal_growth:
            return float('inf')
        terminal_cf = current_cf * (1 + terminal_growth)
        terminal_value = terminal_cf / (discount_rate - terminal_growth)
        terminal_pv = terminal_value / ((1 + discount_rate) ** stage1_years)
        total_pv += terminal_pv
    
    elif stages == 3:
        # Stage 1
        for year in range(1, stage1_years + 1):
            current_cf = current_cf * (1 + growth_rate)
            pv = current_cf / ((1 + discount_rate) ** year)
            total_pv += pv
        
        # Stage 2: Fade
        if stage2_years > 0:
            growth_decrement = (growth_rate - terminal_growth) / stage2_years
            fade_growth = growth_rate
            for year in range(stage1_years + 1, stage1_years + stage2_years + 1):
                fade_growth -= growth_decrement
                current_cf = current_cf * (1 + fade_growth)
                pv = current_cf / ((1 + discount_rate) ** year)
                total_pv += pv
        
        # Terminal
        total_years = stage1_years + stage2_years
        if discount_rate <= terminal_growth:
            return float('inf')
        terminal_cf = current_cf * (1 + terminal_growth)
        terminal_value = terminal_cf / (discount_rate - terminal_growth)
        terminal_pv = terminal_value / ((1 + discount_rate) ** total_years)
        total_pv += terminal_pv
    
    return total_pv


def _build_sensitivity_grid(
    base_metric: float,
    discount_rate: float,
    stages: int,
    stage1_years: int,
    stage2_years: int,
    terminal_growth: float,
    growth_bounds: tuple,
    target_price: float = 50.0,  # Added: actual stock price
) -> Dict[str, Any]:
    """Build sensitivity grid for discount rate vs implied growth."""
    dr_offsets = [-0.02, -0.01, 0, 0.01, 0.02]
    terminal_offsets = [-0.01, -0.005, 0, 0.005, 0.01]
    
    grid = {}
    for dr_offset in dr_offsets:
        dr = discount_rate + dr_offset
        dr_key = f"{dr:.1%}"
        grid[dr_key] = {}
        
        for tg_offset in terminal_offsets:
            tg = terminal_growth + tg_offset
            tg_key = f"{tg:.2%}"
            
            # Solve for implied growth at this discount rate / terminal growth
            result = _solve_implied_growth(
                target_price=target_price,  # Use actual stock price
                base_metric=base_metric,
                discount_rate=dr,
                stages=stages,
                stage1_years=stage1_years,
                stage2_years=stage2_years,
                terminal_growth=tg,
                growth_bounds=growth_bounds,
                max_iterations=30,
            )
            
            if "implied_growth_rate" in result:
                grid[dr_key][tg_key] = result["implied_growth_rate"]
    
    return grid


def _build_metric_cards(
    ticker: str,
    price: float,
    implied_growth: float,
    discount_rate: float,
    base_metric: float,
    model_type: str,
    calculated_value: float,
) -> List[Dict[str, Any]]:
    """Build metric cards from Reverse DCF results."""
    cards = []
    
    # Implied growth rate
    sentiment = "positive" if implied_growth < 0.15 else ("neutral" if implied_growth < 0.25 else "negative")
    cards.append({
        "id": "implied_growth",
        "label": "Market-Implied Growth",
        "value": f"{implied_growth:.1%}",
        "sentiment": sentiment,
    })
    
    # Current price
    cards.append({
        "id": "current_price",
        "label": "Current Price",
        "value": f"${price:.2f}",
        "sentiment": "neutral",
    })
    
    # Base metric
    cards.append({
        "id": "base_metric",
        "label": f"TTM {model_type.upper()}",
        "value": f"${base_metric:.2f}",
        "sentiment": "neutral",
    })
    
    # Discount rate
    cards.append({
        "id": "discount_rate",
        "label": "Discount Rate",
        "value": f"{discount_rate:.1%}",
        "sentiment": "neutral",
    })
    
    # P/E multiple implied
    if base_metric > 0:
        pe_implied = price / base_metric
        cards.append({
            "id": "pe_implied",
            "label": "Implied P/E",
            "value": f"{pe_implied:.1f}x",
            "sentiment": "negative" if pe_implied > 30 else "neutral",
        })
    
    return cards


def _build_stats_table(
    ticker: str,
    price: float,
    implied_growth: float,
    discount_rate: float,
    terminal_growth: float,
    base_metric: float,
    model_type: str,
    stages: int,
    stage1_years: int,
    beta: Optional[float],
    solve_result: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build stats table from Reverse DCF results."""
    rows = []
    
    # Summary
    rows.append({"category": "Summary", "metric": "Ticker", "value": ticker})
    rows.append({"category": "Summary", "metric": "Current Price", "value": f"${price:.2f}"})
    rows.append({"category": "Summary", "metric": "Market-Implied Growth", "value": f"{implied_growth:.2%}"})
    
    # Interpretation
    if implied_growth < 0:
        interpretation = "Market expects negative growth (contraction)"
    elif implied_growth < 0.05:
        interpretation = "Low growth expectations (mature company)"
    elif implied_growth < 0.15:
        interpretation = "Moderate growth expectations"
    elif implied_growth < 0.25:
        interpretation = "High growth expectations"
    else:
        interpretation = "Very high growth expectations (speculative)"
    
    rows.append({"category": "Summary", "metric": "Interpretation", "value": interpretation})
    
    # Model inputs
    rows.append({"category": "Model", "metric": "Base Metric", "value": f"{model_type.upper()}: ${base_metric:.2f}"})
    rows.append({"category": "Model", "metric": "Discount Rate", "value": f"{discount_rate:.2%}"})
    rows.append({"category": "Model", "metric": "Terminal Growth", "value": f"{terminal_growth:.2%}"})
    rows.append({"category": "Model", "metric": "Stage 1 Years", "value": str(stage1_years)})
    rows.append({"category": "Model", "metric": "Number of Stages", "value": str(stages)})
    
    if beta:
        rows.append({"category": "Model", "metric": "Beta", "value": f"{beta:.2f}"})
    
    # Solver info
    rows.append({"category": "Solver", "metric": "Iterations", "value": str(solve_result.get("iterations", "N/A"))})
    rows.append({"category": "Solver", "metric": "Converged", "value": "Yes" if solve_result.get("converged") else "No"})
    rows.append({"category": "Solver", "metric": "Calculated DCF Value", "value": f"${solve_result.get('calculated_dcf_value', 0):.2f}"})
    
    # Valuation multiples
    if base_metric > 0:
        pe = price / base_metric
        rows.append({"category": "Valuation", "metric": "Current P/E", "value": f"{pe:.1f}x"})
        
        # Implied future P/E (after growth)
        future_earnings = base_metric * ((1 + implied_growth) ** stage1_years)
        future_pe = price / future_earnings if future_earnings > 0 else 0
        rows.append({"category": "Valuation", "metric": f"P/E in {stage1_years}yr (implied)", "value": f"{future_pe:.1f}x"})
    
    return rows

