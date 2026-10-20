"""
Chart builders for Option Pricing.

Builds payoff diagram, Greeks chart, price sensitivity, and Monte Carlo paths.
"""

import math
import random
from typing import Any, Dict, List, Optional

COLORS = {
    "blue": "#3b82f6",
    "green": "#22c55e",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "gray": "#6b7280",
    "teal": "#0891b2",
    "purple": "#8b5cf6",
}


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _black_scholes_price(S: float, K: float, T: float, r: float, sigma: float, q: float, option_type: str) -> float:
    """Quick Black-Scholes for sensitivity chart."""
    if T <= 0 or sigma <= 0:
        return max(0, S - K) if option_type == "call" else max(0, K - S)
    
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    def norm_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    
    if option_type == "call":
        return S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * math.exp(-q * T) * norm_cdf(-d1)


def build_payoff_chart(
    spot: float,
    strike: float,
    option_price: float,
    option_type: str,
) -> Optional[Dict[str, Any]]:
    """Build payoff diagram at expiration."""
    if spot <= 0 or strike <= 0:
        return None
    
    # Price range must encompass BOTH spot and strike with padding
    low_anchor = min(spot, strike)
    high_anchor = max(spot, strike)
    spread = high_anchor - low_anchor
    
    # If spot and strike are close, use percentage-based range
    # Otherwise, use the spread with padding
    if spread < low_anchor * 0.05:  # Within 5% of each other
        center = (spot + strike) / 2
        price_min = center * 0.80
        price_max = center * 1.20
    else:
        padding = spread * 0.3
        price_min = max(0.01, low_anchor - padding)
        price_max = high_anchor + padding
    
    num_points = 50
    step = (price_max - price_min) / num_points
    
    prices = [round(price_min + i * step, 2) for i in range(num_points + 1)]
    
    # Calculate P&L at expiry
    pnl = []
    for p in prices:
        if option_type == "call":
            payoff = max(p - strike, 0) - option_price
        else:
            payoff = max(strike - p, 0) - option_price
        pnl.append(round(payoff, 4))
    
    # Calculate P&L at spot for marker
    if option_type == "call":
        pnl_at_spot = max(spot - strike, 0) - option_price
    else:
        pnl_at_spot = max(strike - spot, 0) - option_price
    
    # Find min/max P&L for y-axis range
    min_pnl = min(pnl)
    max_pnl = max(pnl)
    
    return {
        "plotly": {
            "data": [
                {
                    "x": prices,
                    "y": pnl,
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"{option_type.title()} P&L",
                    "line": {"color": COLORS["blue"], "width": 2.5},
                    "fill": "tozeroy",
                    "fillcolor": "rgba(59, 130, 246, 0.1)",
                },
                {
                    "x": [price_min, price_max],
                    "y": [0, 0],
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Breakeven",
                    "line": {"color": COLORS["gray"], "width": 1, "dash": "dot"},
                    "showlegend": False,
                },
                {
                    "x": [spot, spot],
                    "y": [min_pnl, max_pnl],
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"Spot ${spot:.2f}",
                    "line": {"color": COLORS["green"], "width": 2, "dash": "dash"},
                },
                {
                    "x": [strike, strike],
                    "y": [min_pnl, max_pnl],
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"Strike ${strike:.2f}",
                    "line": {"color": COLORS["amber"], "width": 2, "dash": "dash"},
                },
                {
                    "x": [spot],
                    "y": [pnl_at_spot],
                    "type": "scatter",
                    "mode": "markers",
                    "name": f"Current P&L ${pnl_at_spot:.2f}",
                    "marker": {"color": COLORS["green"], "size": 12, "symbol": "diamond"},
                    "showlegend": False,
                },
            ],
            "layout": {
                "title": {"text": f"<b>{option_type.title()} Payoff at Expiry</b>", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": "Underlying Price ($)", "tickprefix": "$"},
                "yaxis": {"title": "P&L ($)", "tickprefix": "$", "zeroline": True, "zerolinewidth": 1},
                "legend": {"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
                "height": 320,
                "margin": {"t": 50, "b": 60, "l": 60, "r": 30},
                "template": "plotly_white",
                "hovermode": "x unified",
            },
        },
        "type": "line",
        "label": "Payoff Diagram",
    }


def build_greeks_chart(greeks: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart of Greeks."""
    if not greeks:
        return None
    
    greek_data = [
        ("Delta", _safe_float(greeks.get("delta"))),
        ("Gamma", _safe_float(greeks.get("gamma")) * 100),  # Scale for visibility
        ("Vega", _safe_float(greeks.get("vega"))),
        ("Theta", _safe_float(greeks.get("theta"))),
        ("Rho", _safe_float(greeks.get("rho"))),
    ]
    
    names = [g[0] for g in greek_data]
    values = [g[1] for g in greek_data]
    colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in values]
    
    return {
        "plotly": {
            "data": [{
                "y": names,
                "x": values,
                "type": "bar",
                "orientation": "h",
                "marker": {"color": colors},
                "text": [f"{v:+.4f}" for v in values],
                "textposition": "outside",
            }],
            "layout": {
                "title": {"text": "<b>Option Greeks</b>", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": "Value", "zeroline": True, "zerolinewidth": 1},
                "yaxis": {"title": ""},
                "height": 220,
                "margin": {"t": 45, "b": 40, "l": 60, "r": 80},
                "template": "plotly_white",
            },
        },
        "type": "bar",
        "label": "Greeks",
    }


def build_price_sensitivity_chart(
    spot: float,
    strike: float,
    tte: float,
    vol: float,
    rfr: float,
    div_yield: float,
    option_type: str,
) -> Optional[Dict[str, Any]]:
    """Build option price vs underlying price sensitivity chart."""
    if spot <= 0 or strike <= 0 or tte <= 0 or vol <= 0:
        return None
    
    # Price range must encompass BOTH spot and strike
    low_anchor = min(spot, strike)
    high_anchor = max(spot, strike)
    spread = high_anchor - low_anchor
    
    if spread < low_anchor * 0.05:  # Within 5% of each other
        center = (spot + strike) / 2
        price_min = center * 0.85
        price_max = center * 1.15
    else:
        padding = spread * 0.25
        price_min = max(0.01, low_anchor - padding)
        price_max = high_anchor + padding
    
    num_points = 40
    step = (price_max - price_min) / num_points
    
    prices = [price_min + i * step for i in range(num_points + 1)]
    
    # Calculate option prices at each underlying level
    option_prices = []
    for p in prices:
        opt_price = _black_scholes_price(p, strike, tte, rfr, vol, div_yield, option_type)
        option_prices.append(round(opt_price, 4))
    
    # Current price point
    current_opt = _black_scholes_price(spot, strike, tte, rfr, vol, div_yield, option_type)
    
    max_opt = max(option_prices)
    
    return {
        "plotly": {
            "data": [
                {
                    "x": prices,
                    "y": option_prices,
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"{option_type.title()} Value",
                    "line": {"color": COLORS["teal"], "width": 2.5},
                },
                {
                    "x": [strike, strike],
                    "y": [0, max_opt],
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"Strike ${strike:.2f}",
                    "line": {"color": COLORS["amber"], "width": 1.5, "dash": "dash"},
                },
                {
                    "x": [spot],
                    "y": [current_opt],
                    "type": "scatter",
                    "mode": "markers",
                    "name": f"Current (${current_opt:.2f})",
                    "marker": {"color": COLORS["green"], "size": 12, "symbol": "diamond"},
                },
            ],
            "layout": {
                "title": {"text": "<b>Price Sensitivity</b>", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": "Underlying Price ($)", "tickprefix": "$"},
                "yaxis": {"title": "Option Price ($)", "tickprefix": "$"},
                "legend": {"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
                "height": 300,
                "margin": {"t": 50, "b": 60, "l": 60, "r": 30},
                "template": "plotly_white",
                "hovermode": "x unified",
            },
        },
        "type": "line",
        "label": "Price Sensitivity",
    }


def build_monte_carlo_chart(
    spot: float,
    strike: float,
    tte: float,
    vol: float,
    rfr: float,
    div_yield: float,
    option_type: str,
    num_paths: int = 50,
    num_steps: int = 100,
    total_sims: int = 10000,
    seed: int = 42,
) -> Optional[Dict[str, Any]]:
    """Build Monte Carlo simulation paths chart."""
    if spot <= 0 or strike <= 0 or tte <= 0 or vol <= 0:
        return None
    
    random.seed(seed)
    dt = tte / num_steps
    
    # Time axis
    times = [i * dt for i in range(num_steps + 1)]
    
    # Generate paths
    traces = []
    itm_count = 0
    
    for i in range(num_paths):
        path = [spot]
        S = spot
        for _ in range(num_steps):
            Z = random.gauss(0, 1)
            S = S * math.exp((rfr - div_yield - 0.5 * vol ** 2) * dt + vol * math.sqrt(dt) * Z)
            path.append(S)
        
        # Check if ITM at expiry
        terminal = path[-1]
        if option_type == "call":
            itm = terminal > strike
        else:
            itm = terminal < strike
        
        if itm:
            itm_count += 1
        
        # Color: green if ITM, red if OTM, with low opacity
        color = "rgba(34, 197, 94, 0.3)" if itm else "rgba(239, 68, 68, 0.2)"
        
        traces.append({
            "x": times,
            "y": path,
            "type": "scatter",
            "mode": "lines",
            "line": {"color": color, "width": 1},
            "showlegend": False,
            "hoverinfo": "skip",
        })
    
    # Strike line
    traces.append({
        "x": [0, tte],
        "y": [strike, strike],
        "type": "scatter",
        "mode": "lines",
        "name": f"Strike ${strike:.2f}",
        "line": {"color": COLORS["amber"], "width": 2, "dash": "dash"},
    })
    
    # Spot marker
    traces.append({
        "x": [0],
        "y": [spot],
        "type": "scatter",
        "mode": "markers",
        "name": f"Spot ${spot:.2f}",
        "marker": {"color": COLORS["blue"], "size": 10},
    })
    
    itm_pct = (itm_count / num_paths) * 100
    
    # Format total sims for display
    if total_sims >= 1000:
        sims_str = f"{total_sims // 1000}K"
    else:
        sims_str = str(total_sims)
    
    return {
        "plotly": {
            "data": traces,
            "layout": {
                "title": {
                    "text": f"<b>Monte Carlo</b> ({sims_str} sims, showing {num_paths} paths, ~{itm_pct:.0f}% ITM)",
                    "x": 0.5,
                    "font": {"size": 14},
                },
                "xaxis": {"title": "Time to Expiry (Years)"},
                "yaxis": {"title": "Price ($)", "tickprefix": "$"},
                "legend": {"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
                "height": 320,
                "margin": {"t": 50, "b": 60, "l": 60, "r": 30},
                "template": "plotly_white",
                "annotations": [
                    {
                        "x": tte * 0.95,
                        "y": strike,
                        "text": "Strike",
                        "showarrow": False,
                        "yshift": 15,
                        "font": {"color": COLORS["amber"], "size": 11},
                    }
                ],
            },
        },
        "type": "line",
        "label": "Monte Carlo Paths",
    }
