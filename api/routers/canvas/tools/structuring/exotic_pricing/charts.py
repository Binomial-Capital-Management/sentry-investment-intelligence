"""
Chart builders for Exotic Derivatives Pricing.

Clean, professional charts for exotic options.
"""

import math
from typing import Any, Dict, List, Optional

COLORS = {
    "blue": "#3b82f6",
    "green": "#22c55e",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "gray": "#6b7280",
    "teal": "#0891b2",
}


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


def build_payoff_chart(
    derivative_type: str,
    option_type: str,
    spot: float,
    strike: float,
    price: float,
    exotic_params: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build payoff diagram - P&L at expiration vs underlying price."""
    if spot <= 0 or strike <= 0:
        return None
    
    # Price range centered on strike
    center = strike
    range_pct = 0.25
    spot_min = center * (1 - range_pct)
    spot_max = center * (1 + range_pct)
    num_points = 50
    step = (spot_max - spot_min) / num_points
    
    spot_range = [round(spot_min + i * step, 2) for i in range(num_points + 1)]
    
    # Calculate vanilla payoffs for comparison
    vanilla_payoffs = []
    exotic_payoffs = []
    
    for s in spot_range:
        # Vanilla payoff
        if option_type == "call":
            vanilla = max(s - strike, 0) - price
        else:
            vanilla = max(strike - s, 0) - price
        vanilla_payoffs.append(round(vanilla, 4))
        
        # Exotic payoff (simplified at-expiry view)
        if derivative_type == "digital":
            digital_payout = exotic_params.get("payoff", 100)
            if option_type == "call":
                exotic = (digital_payout if s > strike else 0) - price
            else:
                exotic = (digital_payout if s < strike else 0) - price
        else:
            # For barrier/asian/lookback, show vanilla-like payoff at expiry
            exotic = vanilla
        exotic_payoffs.append(round(exotic, 4))
    
    # Title based on type
    type_labels = {
        "barrier": f"Barrier {option_type.title()}",
        "asian": f"Asian {option_type.title()}",
        "lookback": f"Lookback {option_type.title()}",
        "digital": f"Digital {option_type.title()}",
    }
    title = type_labels.get(derivative_type, f"{derivative_type.title()} {option_type.title()}")
    
    return {
        "plotly": {
            "data": [
                {
                    "x": spot_range,
                    "y": exotic_payoffs,
                    "type": "scatter",
                    "mode": "lines",
                    "name": title,
                    "line": {"color": COLORS["blue"], "width": 2.5},
                },
                {
                    "x": [spot_min, spot_max],
                    "y": [0, 0],
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Breakeven",
                    "line": {"color": COLORS["gray"], "width": 1, "dash": "dot"},
                    "showlegend": False,
                },
                {
                    "x": [spot, spot],
                    "y": [min(exotic_payoffs), max(exotic_payoffs)],
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"Spot ${spot:.2f}",
                    "line": {"color": COLORS["green"], "width": 1.5, "dash": "dash"},
                },
                {
                    "x": [strike, strike],
                    "y": [min(exotic_payoffs), max(exotic_payoffs)],
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"Strike ${strike:.2f}",
                    "line": {"color": COLORS["amber"], "width": 1.5, "dash": "dash"},
                },
            ],
            "layout": {
                "title": {"text": f"<b>{title} Payoff</b>", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": "Underlying Price ($)", "tickprefix": "$"},
                "yaxis": {"title": "P&L ($)", "tickprefix": "$", "zeroline": True, "zerolinewidth": 1},
                "legend": {"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
                "height": 350,
                "margin": {"t": 50, "b": 60, "l": 60, "r": 30},
                "template": "plotly_white",
                "hovermode": "x unified",
            },
        },
        "type": "line",
        "label": f"{title} Payoff",
    }


def build_greeks_chart(greeks: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart of Greeks."""
    if not greeks:
        return None
    
    # Only show non-zero Greeks
    greek_data = [
        ("Delta", _safe_float(greeks.get("delta"))),
        ("Vega", _safe_float(greeks.get("vega"))),
        ("Theta", _safe_float(greeks.get("theta"))),
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
                "height": 200,
                "margin": {"t": 45, "b": 40, "l": 60, "r": 80},
                "template": "plotly_white",
            },
        },
        "type": "bar",
        "label": "Greeks",
    }


def build_barrier_chart(
    spot: float,
    strike: float,
    barrier_level: float,
    barrier_type: str,
    option_type: str,
) -> Optional[Dict[str, Any]]:
    """Build price level visualization showing spot, strike, and barrier."""
    if spot <= 0 or barrier_level <= 0:
        return None
    
    # Determine levels and colors
    levels = sorted([
        ("Spot", spot, COLORS["green"]),
        ("Strike", strike, COLORS["amber"]),
        ("Barrier", barrier_level, COLORS["red"]),
    ], key=lambda x: x[1])
    
    names = [l[0] for l in levels]
    prices = [l[1] for l in levels]
    colors = [l[2] for l in levels]
    
    # Distance from spot to barrier
    barrier_dist = abs(spot - barrier_level) / spot * 100
    
    # Barrier type description
    is_up = "up" in barrier_type
    is_out = "out" in barrier_type
    
    if is_up and is_out:
        desc = f"Knocked OUT if price rises to ${barrier_level:.2f}"
    elif is_up and not is_out:
        desc = f"Knocked IN if price rises to ${barrier_level:.2f}"
    elif not is_up and is_out:
        desc = f"Knocked OUT if price falls to ${barrier_level:.2f}"
    else:
        desc = f"Knocked IN if price falls to ${barrier_level:.2f}"
    
    return {
        "plotly": {
            "data": [{
                "y": names,
                "x": prices,
                "type": "bar",
                "orientation": "h",
                "marker": {"color": colors},
                "text": [f"${p:.2f}" for p in prices],
                "textposition": "outside",
            }],
            "layout": {
                "title": {"text": f"<b>{barrier_type.replace('-', ' ').title()}</b>", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": "Price ($)", "tickprefix": "$"},
                "yaxis": {"title": ""},
                "height": 200,
                "margin": {"t": 45, "b": 40, "l": 60, "r": 80},
                "template": "plotly_white",
                "annotations": [{
                    "text": f"{desc} ({barrier_dist:.1f}% from spot)",
                    "x": 0.5,
                    "y": -0.25,
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 11, "color": COLORS["gray"]},
                }],
            },
        },
        "type": "bar",
        "label": "Barrier Levels",
    }
