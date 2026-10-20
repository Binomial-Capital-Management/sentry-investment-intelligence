"""
Traditional DCF Canvas Executor
2-stage or 3-stage deterministic DCF valuation.
All logic self-contained in executor.
"""
from typing import Dict, Any, Optional
import logging
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.fmp.FMPAdvancedValuationServer import FMPAdvancedValuationServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


def _extract_scalar(value):
    """Extract scalar from FMP data."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list) and len(value) > 0:
        return _extract_scalar(value[0])
    if isinstance(value, dict):
        for key in ['value', 'v', 'amount']:
            if key in value:
                return _extract_scalar(value[key])
        if len(value) == 1:
            return _extract_scalar(list(value.values())[0])
    return None


def _calculate_dcf(base_metric, growth_rate, discount_rate, terminal_growth, stages, stage1_years, stage2_years):
    """Calculate DCF with breakdown. Stages can be 'stable', 2, or 3."""
    if not base_metric or base_metric <= 0:
        return {"error": "Invalid base metric"}
    if discount_rate <= terminal_growth:
        return {"error": "Discount rate must exceed terminal growth"}
    
    breakdown = {"stage1_cashflows": [], "stage2_cashflows": [], "stage1_pv": 0, "stage2_pv": 0}
    current_cf = base_metric
    total_pv = 0
    
    # Handle stable stage (single-stage perpetuity)
    if stages == "stable":
        # Pure perpetuity: next year's cash flow / (r - g)
        # Assumes company is already at terminal state
        next_cf = base_metric * (1 + terminal_growth)
        terminal_value = next_cf / (discount_rate - terminal_growth)
        
        breakdown["terminal_value"] = round(terminal_value, 2)
        breakdown["terminal_pv"] = round(terminal_value, 2)  # No discounting needed - value today
        
        return {"intrinsic_value": round(terminal_value, 2), "breakdown": breakdown}
    
    # Standard 2-stage or 3-stage
    stages = int(stages)
    
    # Stage 1
    for year in range(1, stage1_years + 1):
        current_cf *= (1 + growth_rate)
        pv = current_cf / ((1 + discount_rate) ** year)
        total_pv += pv
        breakdown["stage1_cashflows"].append({"year": year, "cf": round(current_cf, 2), "pv": round(pv, 2)})
    breakdown["stage1_pv"] = round(total_pv, 2)
    
    # Stage 2 (for 3-stage)
    if stages == 3 and stage2_years > 0:
        decrement = (growth_rate - terminal_growth) / stage2_years
        fade_growth = growth_rate
        for offset in range(stage2_years):
            year = stage1_years + offset + 1
            fade_growth -= decrement
            current_cf *= (1 + fade_growth)
            pv = current_cf / ((1 + discount_rate) ** year)
            total_pv += pv
            breakdown["stage2_cashflows"].append({"year": year, "cf": round(current_cf, 2), "pv": round(pv, 2)})
        breakdown["stage2_pv"] = round(total_pv - breakdown["stage1_pv"], 2)
    
    # Terminal
    years_elapsed = stage1_years + (stage2_years if stages == 3 else 0)
    terminal_cf = current_cf * (1 + terminal_growth)
    terminal_value = terminal_cf / (discount_rate - terminal_growth)
    terminal_pv = terminal_value / ((1 + discount_rate) ** years_elapsed)
    
    breakdown["terminal_value"] = round(terminal_value, 2)
    breakdown["terminal_pv"] = round(terminal_pv, 2)
    
    return {"intrinsic_value": round(total_pv + terminal_pv, 2), "breakdown": breakdown}


async def execute_dcf_traditional(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Traditional DCF for Canvas."""
    from .charts import build_cashflow_chart, build_value_breakdown_chart
    
    ticker = params.get('ticker') or params.get('underlying')
    if not ticker:
        return {"status": "error", "error": "Ticker is required"}
    
    ticker = ticker.upper()
    market_server = None
    valuation_server = None
    
    try:
        stages = params.get('stages', '2')
        if stages not in ['stable', 'Stable', 'STABLE']:
            stages = int(stages)
        else:
            stages = 'stable'
        
        # For stable stage: use 1 year (minimal runway before terminal)
        # For 2-stage/3-stage: use provided stage1_years
        if stages == 'stable':
            stage1_years = 1  # Stable stage = 1 year before perpetuity
        else:
            stage1_years = int(params.get('stage1_years', 5))
        stage2_years = int(params.get('stage2_years', 5)) if stages == 3 else 0
        terminal_growth = float(params.get('terminal_growth', 0.025))
        model_type = params.get('model_type', 'eps')
        
        # Optional overrides
        growth_rate = params.get('growth_rate')
        if growth_rate is not None:
            growth_rate = float(growth_rate)
        discount_rate = params.get('discount_rate')
        if discount_rate is not None:
            discount_rate = float(discount_rate)
        
        stage_label = "Stable-Stage" if stages == 'stable' else f"{stages}-Stage"
        logger.info(f"Traditional DCF for {ticker}: {stage_label}")
        
        # Fetch financial data
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Get TTM metrics from ratios-ttm endpoint (better for DCF)
        ttm_fields = ["netIncomePerShareTTM", "freeCashFlowPerShareTTM", "price"]
        current_result = await market_server.call_tool("get_fields", {
            "symbol": ticker,
            "fields": ttm_fields
        })
        
        raw_data = {}
        if current_result and hasattr(current_result, "content"):
            current_data = safe_parse_json(current_result)
            if current_data.get("status") != "missing_required_params":
                raw_data = current_data.get("data", current_data)
        
        if not raw_data:
            return {"status": "error", "error": f"No financial data found for {ticker}"}
        
        current_price = _extract_scalar(raw_data.get("price"))
        eps_ttm = _extract_scalar(raw_data.get("netIncomePerShareTTM"))
        fcf_per_share_ttm = _extract_scalar(raw_data.get("freeCashFlowPerShareTTM"))
        
        if not current_price:
            return {"status": "error", "error": f"Missing price data for {ticker}"}
        
        # Base metric (TTM)
        if model_type == "fcf" and fcf_per_share_ttm:
            base_metric = fcf_per_share_ttm
            metric_name = "FCF/Share (TTM)"
        elif eps_ttm:
            base_metric = eps_ttm
            metric_name = "EPS (TTM)"
        else:
            return {"status": "error", "error": f"No TTM EPS or FCF data for {ticker}"}
        
        # Auto-calculate growth if not provided (use 5-year historical EPS)
        if growth_rate is None:
            hist_result = await market_server.call_tool("get_fields", {
                "symbol": ticker,
                "fields": ["eps", "epsDiluted"]
            })
            
            eps_history = []
            if hist_result and hasattr(hist_result, "content"):
                hist_data = safe_parse_json(hist_result)
                if isinstance(hist_data, dict) and "data" in hist_data:
                    hist_data = hist_data["data"]
                if isinstance(hist_data, list):
                    for d in hist_data:
                        if isinstance(d, dict):
                            val = _extract_scalar(d.get("eps") or d.get("epsDiluted"))
                            if val:
                                eps_history.append(val)
            
            if len(eps_history) >= 2:
                oldest, newest = eps_history[-1], eps_history[0]
                if oldest > 0 and newest > 0:
                    years = len(eps_history) - 1
                    growth_rate = (newest / oldest) ** (1 / years) - 1
                    growth_rate = max(min(growth_rate, 0.30), -0.10)  # Cap at +30%/-10%
            growth_rate = growth_rate or 0.08
        
        await market_server.cleanup()
        market_server = None
        
        # Auto-calculate discount rate if not provided
        if discount_rate is None:
            discount_rate = 0.10
            try:
                valuation_server = FMPAdvancedValuationServer()
                await valuation_server.connect()
                wacc_result = await valuation_server.call_tool("calculate_wacc_inputs", {"symbol": ticker})
                if wacc_result and not wacc_result.isError:
                    wacc_data = safe_parse_json(wacc_result)
                    if "wacc_inputs" in wacc_data:
                        inputs = wacc_data["wacc_inputs"]
                        if inputs.get("costOfEquity"):
                            discount_rate = float(inputs["costOfEquity"])
                        elif inputs.get("wacc"):
                            discount_rate = float(inputs["wacc"])
                        elif inputs.get("beta"):
                            discount_rate = 0.04 + float(inputs["beta"]) * 0.05
                await valuation_server.cleanup()
                valuation_server = None
            except Exception:
                pass
        
        # Calculate DCF
        dcf_result = _calculate_dcf(base_metric, growth_rate, discount_rate, terminal_growth, stages, stage1_years, stage2_years)
        if "error" in dcf_result:
            return {"status": "error", "error": dcf_result["error"]}
        
        intrinsic_value = dcf_result["intrinsic_value"]
        breakdown = dcf_result["breakdown"]
        upside = ((intrinsic_value / current_price) - 1) * 100 if current_price else 0
        recommendation = "Undervalued" if upside > 10 else ("Overvalued" if upside < -10 else "Fair Value")
        
        # Package result
        result = {
            "intrinsic_value": intrinsic_value,
            "current_price": current_price,
            "upside_pct": round(upside, 2),
            "recommendation": recommendation,
            "model_config": {"base_metric": round(base_metric, 2), "metric_name": metric_name},
            "inputs": {
                "growth_rate_pct": f"{growth_rate:.1%}",
                "discount_rate_pct": f"{discount_rate:.1%}",
                "terminal_growth_pct": f"{terminal_growth:.1%}",
            },
            "breakdown": breakdown,
        }
        
        
        # Build charts
        charts = {}
        cf_chart = build_cashflow_chart(breakdown, ticker, stages)
        if cf_chart:
            charts["cashflows"] = cf_chart
        
        value_chart = build_value_breakdown_chart(breakdown, ticker)
        if value_chart:
            charts["breakdown"] = value_chart
        
        # Metric cards
        metric_cards = [
            {
                "id": "current_price",
                "label": "Current Price",
                "value": f"${current_price:.2f}",
                "sentiment": "neutral",
            },
            {
                "id": "intrinsic_value",
                "label": "Intrinsic Value",
                "value": f"${intrinsic_value:.2f}",
                "sentiment": "positive" if intrinsic_value > current_price else "negative",
            },
            {
                "id": "upside",
                "label": "Upside/Downside",
                "value": f"{upside:+.1f}%",
                "sentiment": "positive" if upside > 0 else "negative",
            },
            {
                "id": "recommendation",
                "label": "Verdict",
                "value": recommendation,
                "sentiment": "positive" if "Under" in recommendation else ("negative" if "Over" in recommendation else "neutral"),
            },
        ]
        
        # Stats table
        stats_table = [
            {"category": "Target", "metric": "Ticker", "value": ticker},
            {"category": "Valuation", "metric": "Current Price", "value": f"${current_price:.2f}"},
            {"category": "Valuation", "metric": "Intrinsic Value", "value": f"${intrinsic_value:.2f}"},
            {"category": "Valuation", "metric": "Upside/Downside", "value": f"{upside:+.1f}%"},
            {"category": "Model", "metric": "Stages", "value": f"{stage_label} DCF"},
            {"category": "Model", "metric": "Base Metric", "value": f"{metric_name}: ${base_metric:.2f}"},
        ]
        
        # Only show growth rate for multi-stage models
        if stages != 'stable':
            stats_table.append({"category": "Inputs", "metric": "Growth Rate (Stage 1)", "value": f"{growth_rate:.1%}"})
        
        stats_table.extend([
            {"category": "Inputs", "metric": "Terminal Growth", "value": f"{terminal_growth:.1%}"},
            {"category": "Inputs", "metric": "Discount Rate", "value": f"{discount_rate:.1%}"},
        ])
        
        # Duration info based on model type
        if stages == 'stable':
            stats_table.append({"category": "Duration", "metric": "Model Type", "value": "Single-stage perpetuity"})
        else:
            stats_table.append({"category": "Duration", "metric": "Stage 1 Years", "value": str(stage1_years)})
            if stages == 3:
                stats_table.append({"category": "Duration", "metric": "Stage 2 (Fade) Years", "value": str(stage2_years)})
        
        # Value breakdown
        stats_table.append({"category": "Breakdown", "metric": "─" * 20, "value": "─" * 15})
        if stages == 'stable':
            # Stable stage: terminal value dominates
            stats_table.append({"category": "PV", "metric": "Terminal PV", "value": f"${breakdown.get('terminal_pv', 0):.2f}"})
        else:
            stats_table.append({"category": "PV", "metric": "Stage 1 PV", "value": f"${breakdown.get('stage1_pv', 0):.2f}"})
            if stages == 3:
                stats_table.append({"category": "PV", "metric": "Stage 2 PV", "value": f"${breakdown.get('stage2_pv', 0):.2f}"})
            stats_table.append({"category": "PV", "metric": "Terminal PV", "value": f"${breakdown.get('terminal_pv', 0):.2f}"})
        
        return {
            "status": "success",
            "tool_id": "dcf_traditional",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "current_price": current_price,
                "intrinsic_value": intrinsic_value,
                "upside_pct": upside,
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
            "summary": (
                f"**{stage_label} DCF: {ticker}**\n\n"
                f"Intrinsic value: **${intrinsic_value:.2f}** vs current ${current_price:.2f}\n\n"
                f"**{recommendation}** ({upside:+.1f}%)\n\n"
                + (f"Perpetuity model with {terminal_growth:.1%} terminal growth, {discount_rate:.1%} discount rate.\n\n*Assumes company is already at steady-state terminal characteristics.*"
                   if stages == 'stable' else
                   f"Using {growth_rate:.1%} growth, {discount_rate:.1%} discount rate")
            ),
        }
    
    except Exception as e:
        logger.error(f"Traditional DCF failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}
    finally:
        if market_server:
            try:
                await market_server.cleanup()
            except:
                pass
        if valuation_server:
            try:
                await valuation_server.cleanup()
            except:
                pass
