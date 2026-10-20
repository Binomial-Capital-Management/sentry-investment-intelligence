"""
Canvas executor for Exotic Derivatives Pricing.

Prices exotic options: barrier, Asian, lookback, digital.
Uses Monte Carlo simulation with variance reduction.
"""

import logging
import math
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .charts import build_payoff_chart, build_greeks_chart, build_barrier_chart

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


async def execute_exotic_pricing(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute exotic derivatives pricing for Canvas.
    
    Args:
        user_id: User ID
        org_id: Organization ID
        params: Tool parameters from request
    
    Returns:
        Canvas-formatted response with charts, metrics, and summary
    """
    from core.agents.structuring_tools import price_exotic_derivatives_internal
    
    # Extract parameters
    derivative_type = params.get("derivative_type", "barrier")
    underlying = params.get("underlying", "").upper().strip()
    strike = params.get("strike")
    expiry = params.get("expiry", "")
    option_type = params.get("option_type", "call")
    num_simulations = int(params.get("num_simulations", 5000))
    
    # Barrier params
    barrier_type = params.get("barrier_type", "up-and-out")
    barrier_level = params.get("barrier_level")
    
    # Asian params
    averaging_type = params.get("averaging_type", "arithmetic")
    averaging_frequency = params.get("averaging_frequency", "daily")
    
    # Lookback params
    lookback_type = params.get("lookback_type", "fixed")
    
    # Digital params
    digital_payoff = float(params.get("digital_payoff", 100))
    
    # Validate required params
    if not underlying:
        return {
            "status": "error",
            "error": "Please provide an underlying ticker (e.g., SPY, AAPL)",
            "tool_id": "exotic_pricing",
        }
    
    if not expiry:
        # Default to 3M expiry
        expiry = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    
    # Convert strike
    try:
        strike = float(strike) if strike else None
    except (ValueError, TypeError):
        strike = None
    
    # Build exotic_params based on derivative type
    exotic_params: Dict[str, Any] = {}
    
    if derivative_type == "barrier":
        if barrier_level is None or barrier_level <= 0:
            return {
                "status": "error",
                "error": "Barrier options require a barrier_level price (e.g., 120 for a knock-out at $120)",
                "tool_id": "exotic_pricing",
            }
        exotic_params = {
            "barrier_type": barrier_type,
            "barrier_level": float(barrier_level),
        }
    elif derivative_type == "asian":
        exotic_params = {
            "averaging_type": averaging_type,
            "averaging_frequency": averaging_frequency,
        }
    elif derivative_type == "lookback":
        exotic_params = {
            "lookback_type": lookback_type,
        }
    elif derivative_type == "digital":
        exotic_params = {
            "payoff": digital_payoff,
        }
    else:
        return {
            "status": "error",
            "error": f"Unknown derivative type: {derivative_type}. Use: barrier, asian, lookback, digital",
            "tool_id": "exotic_pricing",
        }
    
    logger.info(f"Executing Exotic Pricing: {derivative_type} {option_type} on {underlying}")
    
    try:
        # Call internal function (strike=None triggers ATM)
        result = await price_exotic_derivatives_internal(
            derivative_type=derivative_type,
            underlying=underlying,
            strike=strike,  # None/0 = ATM (handled in internal)
            expiry=expiry,
            option_type=option_type,
            exotic_params=exotic_params,
            num_simulations=num_simulations,
        )
        
        logger.info(f"Exotic pricing result status: {result.get('status')}, price: {result.get('price')}")
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Exotic pricing failed"),
                "tool_id": "exotic_pricing",
            }
        
        # Extract key data
        price = _safe_float(result.get("price"))
        spot = _safe_float(result.get("spot_price"))
        strike_used = _safe_float(result.get("strike")) or spot  # ATM fallback
        vol = _safe_float(result.get("volatility"))
        rate = _safe_float(result.get("risk_free_rate"))
        time_to_expiry = _safe_float(result.get("time_to_expiry"))
        greeks = result.get("greeks", {})
        pricing_method = result.get("pricing_method", "unknown")
        conf_interval = _safe_float(result.get("confidence_interval_95"))
        
        # Build metric cards
        metric_cards = _build_metric_cards(
            derivative_type=derivative_type,
            option_type=option_type,
            price=price,
            spot=spot,
            strike=strike_used,
            vol=vol,
            greeks=greeks,
            exotic_params=exotic_params,
            conf_interval=conf_interval,
        )
        
        # Build stats table
        stats_table = _build_stats_table(result, exotic_params)
        
        # Build charts
        charts = {}
        
        logger.info(f"Building charts: spot={spot}, strike={strike_used}, price={price}")
        
        # 1. Payoff diagram
        payoff_chart = build_payoff_chart(
            derivative_type=derivative_type,
            option_type=option_type,
            spot=spot,
            strike=strike_used,
            price=price,
            exotic_params=exotic_params,
        )
        if payoff_chart:
            charts["payoff"] = payoff_chart
            logger.info("Built payoff chart")
        else:
            logger.warning(f"Payoff chart returned None (spot={spot}, strike={strike_used})")
        
        # 2. Greeks chart
        greeks_chart = build_greeks_chart(greeks)
        if greeks_chart:
            charts["greeks"] = greeks_chart
            logger.info("Built Greeks chart")
        else:
            logger.warning(f"Greeks chart returned None (greeks={greeks})")
        
        # 3. Barrier visualization (for barrier options only)
        if derivative_type == "barrier":
            barrier_level = exotic_params.get("barrier_level", 0)
            barrier_chart = build_barrier_chart(
                spot=spot,
                strike=strike_used,
                barrier_level=barrier_level,
                barrier_type=exotic_params.get("barrier_type", "up-and-out"),
                option_type=option_type,
            )
            if barrier_chart:
                charts["barrier"] = barrier_chart
                logger.info("Built barrier chart")
            else:
                logger.warning(f"Barrier chart returned None (barrier_level={barrier_level})")
        
        logger.info(f"Built {len(charts)} charts for exotic pricing: {list(charts.keys())}")
        
        # Build summary
        summary = _build_summary(result, exotic_params)
        
        return {
            "status": "success",
            "tool_id": "exotic_pricing",
            "tickers": [underlying],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "price": price,
                "spot": spot,
                "strike": strike_used,
                "volatility": vol,
                "delta": _safe_float(greeks.get("delta")),
                "vega": _safe_float(greeks.get("vega")),
                "theta": _safe_float(greeks.get("theta")),
            },
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Exotic Pricing Canvas execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "tool_id": "exotic_pricing",
        }


def _build_metric_cards(
    derivative_type: str,
    option_type: str,
    price: float,
    spot: float,
    strike: float,
    vol: float,
    greeks: Dict[str, Any],
    exotic_params: Dict[str, Any],
    conf_interval: float,
) -> List[Dict[str, Any]]:
    """Build displayable metric cards."""
    cards = []
    
    # Type label
    type_labels = {
        "barrier": "Barrier",
        "asian": "Asian",
        "lookback": "Lookback",
        "digital": "Digital",
    }
    type_label = type_labels.get(derivative_type, derivative_type.title())
    
    # Price
    cards.append({
        "id": "price",
        "label": f"{type_label} {option_type.title()} Price",
        "value": f"${price:.4f}",
        "description": f"±${conf_interval:.4f}" if conf_interval else "Closed-form",
        "sentiment": "neutral",
    })
    
    # Spot / Strike
    moneyness = spot / strike if strike else 1
    moneyness_label = "ITM" if (option_type == "call" and moneyness > 1) or (option_type == "put" and moneyness < 1) else "OTM" if (option_type == "call" and moneyness < 1) or (option_type == "put" and moneyness > 1) else "ATM"
    cards.append({
        "id": "spot_strike",
        "label": "Spot / Strike",
        "value": f"${spot:.2f} / ${strike:.2f}",
        "description": f"{moneyness_label} ({moneyness:.2%})",
        "sentiment": "positive" if moneyness_label == "ITM" else "neutral",
    })
    
    # Volatility
    cards.append({
        "id": "volatility",
        "label": "Volatility",
        "value": f"{vol:.1%}",
        "description": "Implied or realized",
        "sentiment": "neutral",
    })
    
    # Delta
    delta = _safe_float(greeks.get("delta"))
    cards.append({
        "id": "delta",
        "label": "Delta",
        "value": f"{delta:.4f}",
        "description": "Price sensitivity",
        "sentiment": "neutral",
    })
    
    # Derivative-specific card
    if derivative_type == "barrier":
        barrier = exotic_params.get("barrier_level", 0)
        barrier_type = exotic_params.get("barrier_type", "")
        distance = abs(spot - barrier) / spot * 100
        cards.append({
            "id": "barrier",
            "label": "Barrier",
            "value": f"${barrier:.2f}",
            "description": f"{barrier_type} ({distance:.1f}% away)",
            "sentiment": "warning" if distance < 5 else "neutral",
        })
    elif derivative_type == "asian":
        avg_type = exotic_params.get("averaging_type", "arithmetic")
        avg_freq = exotic_params.get("averaging_frequency", "daily")
        cards.append({
            "id": "averaging",
            "label": "Averaging",
            "value": avg_type.title(),
            "description": avg_freq.title(),
            "sentiment": "neutral",
        })
    elif derivative_type == "lookback":
        lb_type = exotic_params.get("lookback_type", "fixed")
        cards.append({
            "id": "lookback",
            "label": "Lookback",
            "value": lb_type.title(),
            "description": "Strike type",
            "sentiment": "neutral",
        })
    elif derivative_type == "digital":
        payoff = exotic_params.get("payoff", 100)
        cards.append({
            "id": "payoff",
            "label": "Digital Payoff",
            "value": f"${payoff:.2f}",
            "description": "If exercised",
            "sentiment": "neutral",
        })
    
    return cards


def _build_stats_table(
    result: Dict[str, Any],
    exotic_params: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build comprehensive stats table."""
    rows = []
    
    derivative_type = result.get("derivative_type", "")
    greeks = result.get("greeks", {})
    
    # Trade Setup
    rows.append({"category": "Trade", "metric": "Underlying", "value": result.get("underlying", "")})
    rows.append({"category": "Trade", "metric": "Type", "value": f"{derivative_type.title()} {result.get('option_type', '').title()}"})
    rows.append({"category": "Trade", "metric": "Strike", "value": f"${result.get('strike', 0):.2f}"})
    rows.append({"category": "Trade", "metric": "Expiry", "value": result.get("expiry", "")})
    rows.append({"category": "Trade", "metric": "Time to Expiry", "value": f"{result.get('time_to_expiry', 0):.3f} yrs"})
    
    # Market Data
    rows.append({"category": "Market", "metric": "Spot Price", "value": f"${result.get('spot_price', 0):.2f}"})
    rows.append({"category": "Market", "metric": "Volatility", "value": f"{result.get('volatility', 0):.2%}"})
    rows.append({"category": "Market", "metric": "Risk-Free Rate", "value": f"{result.get('risk_free_rate', 0):.2%}"})
    
    # Pricing
    rows.append({"category": "Pricing", "metric": "Price", "value": f"${result.get('price', 0):.4f}"})
    rows.append({"category": "Pricing", "metric": "Method", "value": result.get("pricing_method", "unknown")})
    if result.get("confidence_interval_95"):
        rows.append({"category": "Pricing", "metric": "95% CI", "value": f"±${result.get('confidence_interval_95', 0):.4f}"})
    rows.append({"category": "Pricing", "metric": "Num Steps", "value": str(result.get("num_steps", 0))})
    
    # Greeks
    rows.append({"category": "Greeks", "metric": "Delta", "value": f"{_safe_float(greeks.get('delta')):.4f}"})
    rows.append({"category": "Greeks", "metric": "Gamma", "value": f"{_safe_float(greeks.get('gamma')):.4f}"})
    rows.append({"category": "Greeks", "metric": "Vega", "value": f"{_safe_float(greeks.get('vega')):.4f}"})
    rows.append({"category": "Greeks", "metric": "Theta", "value": f"{_safe_float(greeks.get('theta')):.4f}"})
    rows.append({"category": "Greeks", "metric": "Rho", "value": f"{_safe_float(greeks.get('rho')):.4f}"})
    
    # Exotic-specific
    if derivative_type == "barrier":
        rows.append({"category": "Exotic", "metric": "Barrier Level", "value": f"${exotic_params.get('barrier_level', 0):.2f}"})
        rows.append({"category": "Exotic", "metric": "Barrier Type", "value": exotic_params.get("barrier_type", "")})
    elif derivative_type == "asian":
        rows.append({"category": "Exotic", "metric": "Averaging Type", "value": exotic_params.get("averaging_type", "")})
        rows.append({"category": "Exotic", "metric": "Averaging Freq", "value": exotic_params.get("averaging_frequency", "")})
    elif derivative_type == "lookback":
        rows.append({"category": "Exotic", "metric": "Lookback Type", "value": exotic_params.get("lookback_type", "")})
    elif derivative_type == "digital":
        rows.append({"category": "Exotic", "metric": "Payoff", "value": f"${exotic_params.get('payoff', 100):.2f}"})
    
    return rows


def _build_summary(result: Dict[str, Any], exotic_params: Dict[str, Any]) -> str:
    """Build human-readable summary."""
    derivative_type = result.get("derivative_type", "exotic")
    option_type = result.get("option_type", "")
    underlying = result.get("underlying", "")
    price = result.get("price", 0)
    spot = result.get("spot_price", 0)
    strike = result.get("strike", 0)
    expiry = result.get("expiry", "")
    vol = result.get("volatility", 0)
    
    summary = f"**{derivative_type.title()} {option_type.title()} on {underlying}**\n\n"
    summary += f"- **Price**: ${price:.4f}\n"
    summary += f"- **Spot**: ${spot:.2f}, **Strike**: ${strike:.2f}\n"
    summary += f"- **Expiry**: {expiry}, **Vol**: {vol:.1%}\n"
    
    if derivative_type == "barrier":
        barrier = exotic_params.get("barrier_level", 0)
        barrier_type = exotic_params.get("barrier_type", "")
        distance_pct = abs(spot - barrier) / spot * 100
        summary += f"- **Barrier**: ${barrier:.2f} ({barrier_type}), {distance_pct:.1f}% from spot\n"
    elif derivative_type == "asian":
        summary += f"- **Averaging**: {exotic_params.get('averaging_type', '')} {exotic_params.get('averaging_frequency', '')}\n"
    elif derivative_type == "lookback":
        summary += f"- **Lookback Type**: {exotic_params.get('lookback_type', 'fixed')}\n"
    elif derivative_type == "digital":
        summary += f"- **Digital Payoff**: ${exotic_params.get('payoff', 100):.2f}\n"
    
    return summary
