"""
Canvas executor for Option Pricing.

Prices equity options using Black-Scholes, Binomial, or Monte Carlo.
"""

import logging
import math
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .charts import (
    build_price_sensitivity_chart,
    build_greeks_chart,
    build_payoff_chart,
    build_monte_carlo_chart,
)

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, replacing NaN/Inf with default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


async def execute_option_pricing(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute option pricing for Canvas.
    """
    from core.agents.quant_tools import price_equity_options_internal
    
    # Extract parameters
    ticker = params.get("ticker", "").upper().strip()
    strike = params.get("strike")
    expiry = params.get("expiry", "")
    option_type = params.get("option_type", "call").lower()
    pricing_model = params.get("pricing_model", "black_scholes").lower()
    american = params.get("american", False)
    num_simulations = int(params.get("num_simulations", 10000))
    num_simulations = max(100, min(100000, num_simulations))  # Clamp to valid range
    
    # Validate
    if not ticker:
        return {
            "status": "error",
            "error": "Please provide a ticker symbol (e.g., AAPL, SPY)",
            "tool_id": "option_pricing",
        }
    
    if not strike:
        return {
            "status": "error",
            "error": "Please provide a strike price",
            "tool_id": "option_pricing",
        }
    
    try:
        strike = float(strike)
    except (ValueError, TypeError):
        return {
            "status": "error",
            "error": "Strike must be a number",
            "tool_id": "option_pricing",
        }
    
    # Default expiry to 30 days out
    if not expiry:
        expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Build model params
    model_params = {}
    if pricing_model == "binomial":
        model_params["steps"] = 100
        model_params["american"] = american
    elif pricing_model == "monte_carlo":
        model_params["simulations"] = num_simulations
    
    logger.info(f"Executing Option Pricing: {ticker} strike={strike} (raw={params.get('strike')}) {option_type} {pricing_model}")
    
    try:
        result = await price_equity_options_internal(
            ticker=ticker,
            strike=strike,
            expiry=expiry,
            option_type=option_type,
            pricing_model=pricing_model,
            model_params=model_params,
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Option pricing failed"),
                "tool_id": "option_pricing",
            }
        
        # Extract data
        option_price = _safe_float(result.get("option_price"))
        greeks = result.get("greeks", {})
        model_inputs = result.get("model_inputs", {})
        breakdown = result.get("pricing_breakdown", {})
        implied_vol = result.get("implied_volatility")
        
        spot = _safe_float(model_inputs.get("underlying_price"))
        vol = _safe_float(model_inputs.get("volatility"))
        rfr = _safe_float(model_inputs.get("risk_free_rate"))
        div_yield = _safe_float(model_inputs.get("dividend_yield"))
        tte = _safe_float(model_inputs.get("time_to_expiry_years"))
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            option_price=option_price,
            spot=spot,
            strike=strike,
            option_type=option_type,
            greeks=greeks,
            vol=vol,
            tte=tte,
            pricing_model=pricing_model,
        )
        
        # Build stats table
        stats_table = _build_stats_table(result)
        
        # Build charts
        charts = {}
        
        # 1. Payoff diagram
        payoff_chart = build_payoff_chart(
            spot=spot,
            strike=strike,
            option_price=option_price,
            option_type=option_type,
        )
        if payoff_chart:
            charts["payoff"] = payoff_chart
        
        # 2. Greeks chart
        greeks_chart = build_greeks_chart(greeks)
        if greeks_chart:
            charts["greeks"] = greeks_chart
        
        # 3. Price sensitivity (spot vs option price)
        sensitivity_chart = build_price_sensitivity_chart(
            spot=spot,
            strike=strike,
            tte=tte,
            vol=vol,
            rfr=rfr,
            div_yield=div_yield,
            option_type=option_type,
        )
        if sensitivity_chart:
            charts["sensitivity"] = sensitivity_chart
        
        # 4. Monte Carlo paths (only for MC model)
        if pricing_model == "monte_carlo":
            # Show sample of paths (max 100 for performance)
            chart_paths = min(100, num_simulations)
            mc_chart = build_monte_carlo_chart(
                spot=spot,
                strike=strike,
                tte=tte,
                vol=vol,
                rfr=rfr,
                div_yield=div_yield,
                option_type=option_type,
                num_paths=chart_paths,
                num_steps=100,
                total_sims=num_simulations,
            )
            if mc_chart:
                charts["monte_carlo"] = mc_chart
        
        logger.info(f"Built {len(charts)} charts for option pricing")
        
        # Summary
        intrinsic = _safe_float(breakdown.get("intrinsic_value"))
        time_value = _safe_float(breakdown.get("time_value"))
        
        summary = (
            f"**{ticker} {strike} {option_type.title()}** @ ${option_price:.4f}\n\n"
            f"- Spot: ${spot:.2f}, Strike: ${strike:.2f}\n"
            f"- Intrinsic: ${intrinsic:.4f}, Time Value: ${time_value:.4f}\n"
            f"- Delta: {_safe_float(greeks.get('delta')):.4f}, "
            f"Vega: {_safe_float(greeks.get('vega')):.4f}\n"
            f"- Model: {pricing_model.replace('_', ' ').title()}, Vol: {vol:.1%}"
        )
        
        return {
            "status": "success",
            "tool_id": "option_pricing",
            "tickers": [ticker],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "option_price": option_price,
                "spot": spot,
                "strike": strike,
                "delta": _safe_float(greeks.get("delta")),
                "gamma": _safe_float(greeks.get("gamma")),
                "vega": _safe_float(greeks.get("vega")),
                "theta": _safe_float(greeks.get("theta")),
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Option Pricing Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "option_pricing",
        }


def _build_metric_cards(
    option_price: float,
    spot: float,
    strike: float,
    option_type: str,
    greeks: Dict[str, Any],
    vol: float,
    tte: float,
    pricing_model: str,
) -> List[Dict[str, Any]]:
    """Build metric cards."""
    cards = []
    
    # Option Price
    cards.append({
        "id": "price",
        "label": f"{option_type.title()} Price",
        "value": f"${option_price:.4f}",
        "description": pricing_model.replace("_", " ").title(),
        "sentiment": "neutral",
    })
    
    # Moneyness
    moneyness = spot / strike
    if option_type == "call":
        itm = moneyness > 1
    else:
        itm = moneyness < 1
    
    cards.append({
        "id": "moneyness",
        "label": "Spot / Strike",
        "value": f"${spot:.2f} / ${strike:.2f}",
        "description": f"{'ITM' if itm else 'OTM'} ({moneyness:.2%})",
        "sentiment": "positive" if itm else "neutral",
    })
    
    # Delta
    delta = _safe_float(greeks.get("delta"))
    cards.append({
        "id": "delta",
        "label": "Delta",
        "value": f"{delta:+.4f}",
        "description": f"{abs(delta)*100:.0f}% move probability",
        "sentiment": "neutral",
    })
    
    # Theta
    theta = _safe_float(greeks.get("theta"))
    cards.append({
        "id": "theta",
        "label": "Theta",
        "value": f"${theta:.4f}",
        "description": "Daily decay",
        "sentiment": "negative" if theta < 0 else "neutral",
    })
    
    # Volatility
    cards.append({
        "id": "vol",
        "label": "Volatility",
        "value": f"{vol:.1%}",
        "description": "Annualized",
        "sentiment": "neutral",
    })
    
    # Time to Expiry
    days = int(tte * 365)
    cards.append({
        "id": "tte",
        "label": "Days to Expiry",
        "value": str(days),
        "description": f"{tte:.3f} years",
        "sentiment": "warning" if days < 7 else "neutral",
    })
    
    return cards


def _build_stats_table(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build stats table."""
    rows = []
    
    model_inputs = result.get("model_inputs", {})
    greeks = result.get("greeks", {})
    breakdown = result.get("pricing_breakdown", {})
    
    # Inputs
    rows.append({"category": "Input", "metric": "Underlying", "value": model_inputs.get("ticker", "")})
    rows.append({"category": "Input", "metric": "Spot Price", "value": f"${model_inputs.get('underlying_price', 0):.2f}"})
    rows.append({"category": "Input", "metric": "Strike", "value": f"${model_inputs.get('strike', 0):.2f}"})
    rows.append({"category": "Input", "metric": "Expiry", "value": model_inputs.get("expiry", "")})
    rows.append({"category": "Input", "metric": "Type", "value": model_inputs.get("option_type", "").title()})
    rows.append({"category": "Input", "metric": "Model", "value": model_inputs.get("pricing_model", "").replace("_", " ").title()})
    
    # Market Data
    rows.append({"category": "Market", "metric": "Volatility", "value": f"{model_inputs.get('volatility', 0):.2%}"})
    rows.append({"category": "Market", "metric": "Risk-Free Rate", "value": f"{model_inputs.get('risk_free_rate', 0):.2%}"})
    rows.append({"category": "Market", "metric": "Div Yield", "value": f"{model_inputs.get('dividend_yield', 0):.2%}"})
    rows.append({"category": "Market", "metric": "Time to Expiry", "value": f"{model_inputs.get('time_to_expiry_years', 0):.4f} yrs"})
    
    # Result
    rows.append({"category": "Result", "metric": "Option Price", "value": f"${result.get('option_price', 0):.4f}"})
    rows.append({"category": "Result", "metric": "Intrinsic", "value": f"${breakdown.get('intrinsic_value', 0):.4f}"})
    rows.append({"category": "Result", "metric": "Time Value", "value": f"${breakdown.get('time_value', 0):.4f}"})
    
    # Greeks
    rows.append({"category": "Greeks", "metric": "Delta", "value": f"{_safe_float(greeks.get('delta')):+.4f}"})
    rows.append({"category": "Greeks", "metric": "Gamma", "value": f"{_safe_float(greeks.get('gamma')):.6f}"})
    rows.append({"category": "Greeks", "metric": "Vega", "value": f"{_safe_float(greeks.get('vega')):.4f}"})
    rows.append({"category": "Greeks", "metric": "Theta", "value": f"{_safe_float(greeks.get('theta')):.4f}"})
    rows.append({"category": "Greeks", "metric": "Rho", "value": f"{_safe_float(greeks.get('rho')):.4f}"})
    
    return rows
