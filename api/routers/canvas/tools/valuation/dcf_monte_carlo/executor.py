"""
Monte Carlo DCF Canvas Executor

Probabilistic DCF valuation with data-driven assumptions.
Wraps core/agents/valuation_tools/monte_carlo_dcf_tool.py
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def execute_dcf_monte_carlo(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Monte Carlo DCF analysis for Canvas.
    
    Runs N simulations with uncertainty in growth, discount rate, and terminal growth.
    Returns probability distribution of fair values.
    """
    from core.agents.valuation_tools.monte_carlo_dcf_tool import analyze_monte_carlo_dcf_internal
    
    ticker = params.get('ticker') or params.get('underlying')
    if not ticker:
        return {"status": "error", "error": "Ticker is required"}
    
    ticker = ticker.upper()
    
    try:
        # Extract parameters
        terminal_growth = float(params.get('terminal_growth', 0.025))
        stages = int(params.get('stages', 2))
        stage1_years = int(params.get('stage1_years', 5))
        stage2_years = int(params.get('stage2_years', 5))
        model_type = params.get('model_type', 'eps')
        iterations = int(params.get('iterations', 1000))
        
        logger.info(f"Running Monte Carlo DCF for {ticker}: {iterations} iterations, {stages}-stage")
        
        # Call the internal function
        result = await analyze_monte_carlo_dcf_internal(
            symbol=ticker,
            fields=None,  # Uses defaults
            terminal_growth=terminal_growth,
            stages=stages,
            stage1_years=stage1_years,
            stage2_years=stage2_years,
            model_type=model_type,
            iterations=iterations,
            seed=None,
            include_sensitivity=True,
            include_histogram=True,
        )
        
        if "error" in result:
            return {"status": "error", "error": result.get("error", "Monte Carlo DCF failed")}
        
        # Extract key values
        valuation = result.get("valuation_distribution", {})
        data_inputs = result.get("data_derived_inputs", {})
        financial_data = result.get("financial_data", {})
        
        mean_value = valuation.get("mean", 0)
        median_value = valuation.get("median", 0)
        std_value = valuation.get("std", 0)
        percentiles = valuation.get("percentiles", {})
        confidence = valuation.get("confidence_intervals", {})
        
        current_price = result.get("current_price", 0)
        prob_undervalued = result.get("probability_undervalued", 0)
        expected_upside = result.get("expected_upside", 0)
        
        # Build charts from histogram data
        from .charts import build_distribution_chart
        
        charts = {}
        histogram = result.get("histogram")
        if histogram:
            dist_chart = build_distribution_chart(
                histogram=histogram,
                current_price=current_price,
                median_value=median_value,
                percentiles=percentiles,
                symbol=ticker,
            )
            if dist_chart:
                charts["distribution"] = dist_chart
        
        # Build metric cards
        metric_cards = [
            {
                "id": "current_price",
                "label": "Current Price",
                "value": f"${current_price:.2f}" if current_price else "N/A",
                "sentiment": "neutral",
            },
            {
                "id": "median_value",
                "label": "Median Fair Value",
                "value": f"${median_value:.2f}" if median_value else "N/A",
                "sentiment": "positive" if median_value > current_price else "negative",
            },
            {
                "id": "prob_undervalued",
                "label": "P(Undervalued)",
                "value": f"{prob_undervalued:.1%}",
                "description": f"From {iterations} simulations",
                "sentiment": "positive" if prob_undervalued > 0.5 else "negative",
            },
            {
                "id": "expected_upside",
                "label": "Expected Upside",
                "value": f"{expected_upside:+.1%}",
                "sentiment": "positive" if expected_upside > 0 else "negative",
            },
            {
                "id": "value_range",
                "label": "80% Confidence",
                "value": f"${confidence.get('80%', [0, 0])[0]:.0f} - ${confidence.get('80%', [0, 0])[1]:.0f}",
                "sentiment": "neutral",
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Target", "metric": "Ticker", "value": ticker},
            {"category": "Valuation", "metric": "Current Price", "value": f"${current_price:.2f}"},
            {"category": "Valuation", "metric": "Mean Fair Value", "value": f"${mean_value:.2f}"},
            {"category": "Valuation", "metric": "Median Fair Value", "value": f"${median_value:.2f}"},
            {"category": "Valuation", "metric": "Std Dev", "value": f"${std_value:.2f}"},
            {"category": "Percentiles", "metric": "5th Percentile", "value": f"${percentiles.get('p5', 0):.2f}"},
            {"category": "Percentiles", "metric": "25th Percentile", "value": f"${percentiles.get('p25', 0):.2f}"},
            {"category": "Percentiles", "metric": "75th Percentile", "value": f"${percentiles.get('p75', 0):.2f}"},
            {"category": "Percentiles", "metric": "95th Percentile", "value": f"${percentiles.get('p95', 0):.2f}"},
            {"category": "Probability", "metric": "P(Undervalued)", "value": f"{prob_undervalued:.1%}"},
            {"category": "Probability", "metric": "Expected Upside", "value": f"{expected_upside:+.1%}"},
            {"category": "Inputs", "metric": "Growth Mean", "value": data_inputs.get("growth_mean_pct", "N/A")},
            {"category": "Inputs", "metric": "Growth Std", "value": data_inputs.get("growth_std_pct", "N/A")},
            {"category": "Inputs", "metric": "Discount Rate", "value": data_inputs.get("discount_rate_pct", "N/A")},
            {"category": "Inputs", "metric": "Terminal Growth", "value": data_inputs.get("terminal_growth_pct", "N/A")},
            {"category": "Model", "metric": "Stages", "value": str(stages)},
            {"category": "Model", "metric": "High-Growth Years", "value": str(stage1_years)},
            {"category": "Model", "metric": "Iterations", "value": f"{iterations:,}"},
        ]
        
        # Add sensitivity drivers if available
        sensitivity = result.get("sensitivity_drivers", [])
        if sensitivity and isinstance(sensitivity, list):
            stats_table.append({"category": "Sensitivity", "metric": "─" * 20, "value": "─" * 15})
            # sensitivity is a list of dicts: [{"param": "growth", "correlation": 0.85, ...}, ...]
            for item in sensitivity[:3]:
                param = item.get("param", "unknown").replace("_", " ").title()
                corr = item.get("correlation", 0)
                stats_table.append({
                    "category": "Sensitivity",
                    "metric": param,
                    "value": f"{corr:+.2f} correlation"
                })
        
        return {
            "status": "success",
            "tool_id": "dcf_monte_carlo",
            "tickers": [ticker],
            "weights": [],
            "metrics": {
                "current_price": current_price,
                "mean_value": mean_value,
                "median_value": median_value,
                "probability_undervalued": prob_undervalued,
                "expected_upside": expected_upside,
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
            "summary": (
                f"**Monte Carlo DCF: {ticker}**\n\n"
                f"Based on {iterations:,} simulations, the median fair value is **${median_value:.2f}** "
                f"vs current price of ${current_price:.2f}.\n\n"
                f"**Probability stock is undervalued: {prob_undervalued:.1%}**\n\n"
                f"80% confidence range: ${confidence.get('80%', [0, 0])[0]:.0f} - ${confidence.get('80%', [0, 0])[1]:.0f}"
            ),
        }
        
    except Exception as e:
        logger.error(f"Monte Carlo DCF failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}
