"""
Canvas chart builders for Variance Swap.

Compact visualizations for:
1. Volatility comparison (implied vs realized vs strike)
2. Payoff diagram at different volatility levels
"""

from typing import Any, Dict, Optional
import logging
import math

logger = logging.getLogger(__name__)

# Color palette
COLORS = {
    "teal": "#0891b2",
    "cyan": "#06b6d4",
    "green": "#22c55e",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "gray": "#6b7280",
    "blue": "#3b82f6",
}


def build_vol_comparison_chart(
    implied_vol: float,
    realized_vol: float,
    strike_vol: float,
) -> Optional[Dict[str, Any]]:
    """Build bar chart comparing implied, realized, and strike volatility."""
    try:
        labels = ["Implied", "Realized", "Strike"]
        values = [implied_vol * 100, realized_vol * 100, strike_vol * 100]
        colors = [COLORS["teal"], COLORS["blue"], COLORS["amber"]]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": labels,
                    "y": values,
                    "marker": {"color": colors},
                    "text": [f"{v:.1f}%" for v in values],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{x}</b>: %{y:.1f}%<extra></extra>",
                }],
                "layout": {
                    "title": {"text": "Volatility Comparison", "font": {"size": 14}},
                    "yaxis": {"title": "Volatility (%)", "range": [0, max(values) * 1.3 if values else 50]},
                    "height": 220,
                    "margin": {"t": 40, "r": 20, "b": 40, "l": 50},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Vol Comparison",
        }
    except Exception as e:
        logger.warning(f"Failed to build vol comparison chart: {e}")
        return None


def build_payoff_chart(
    strike_variance: float,
    fair_strike: float,
    notional: float,
) -> Optional[Dict[str, Any]]:
    """Build scatter chart showing payoff at different realized volatilities."""
    if not strike_variance or not notional:
        return None
    
    try:
        strike_vol = math.sqrt(strike_variance) * 100  # as percentage
        fair_vol = math.sqrt(fair_strike) * 100 if fair_strike else strike_vol
        
        # Generate volatility range
        vol_min = max(5, strike_vol - 15)
        vol_max = strike_vol + 20
        vol_range = [vol_min + i * (vol_max - vol_min) / 20 for i in range(21)]
        
        # Calculate payoff at each vol level
        # Payoff = Notional * (RealizedVar - StrikeVar)
        payoffs = []
        for vol_pct in vol_range:
            realized_var = (vol_pct / 100) ** 2
            payoff = notional * (realized_var - strike_variance)
            payoffs.append(payoff)
        
        # Find where payoff is positive/negative for coloring
        colors = [COLORS["green"] if p > 0 else COLORS["red"] for p in payoffs]
        
        return {
            "plotly": {
                "data": [
                    {
                        "type": "scatter",
                        "x": vol_range,
                        "y": payoffs,
                        "mode": "lines+markers",
                        "line": {"color": COLORS["teal"], "width": 2},
                        "marker": {"color": colors, "size": 6},
                        "hovertemplate": "Vol: %{x:.1f}%<br>Payoff: $%{y:,.0f}<extra></extra>",
                    },
                ],
                "layout": {
                    "title": {"text": "Variance Swap Payoff", "font": {"size": 14}},
                    "xaxis": {"title": "Realized Vol (%)"},
                    "yaxis": {"title": "Payoff ($)", "zeroline": True, "zerolinecolor": COLORS["gray"]},
                    "height": 220,
                    "margin": {"t": 40, "r": 20, "b": 50, "l": 70},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                    "shapes": [
                        # Strike vol line
                        {
                            "type": "line",
                            "x0": strike_vol,
                            "x1": strike_vol,
                            "y0": 0,
                            "y1": 1,
                            "yref": "paper",
                            "line": {"color": COLORS["amber"], "width": 2, "dash": "dash"},
                        },
                    ],
                    "annotations": [
                        {
                            "x": strike_vol,
                            "y": 1.05,
                            "yref": "paper",
                            "text": f"Strike {strike_vol:.1f}%",
                            "showarrow": False,
                            "font": {"size": 10, "color": COLORS["amber"]},
                        },
                    ],
                },
            },
            "type": "scatter",
            "label": "Payoff",
        }
    except Exception as e:
        logger.warning(f"Failed to build payoff chart: {e}")
        return None
