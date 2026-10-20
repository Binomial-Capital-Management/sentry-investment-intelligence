"""
Canvas chart builders for Dispersion Trade.

Compact visualizations for:
1. Correlation comparison (realized vs implied)
2. Position breakdown (index vs constituents)
3. Vega profile per constituent
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Color palette
COLORS = {
    "teal": "#0891b2",
    "cyan": "#06b6d4",
    "green": "#22c55e",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "gray": "#6b7280",
}


def build_correlation_chart(realized: float, implied: float) -> Optional[Dict[str, Any]]:
    """Build bar chart comparing realized vs implied correlation."""
    try:
        labels = ["Realized", "Implied"]
        values = [realized * 100, implied * 100]
        
        # Color: green if implied < realized (cheap dispersion), red otherwise
        colors = [COLORS["gray"], COLORS["green"] if implied < realized else COLORS["red"]]
        
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
                    "title": {"text": "Correlation: Realized vs Implied", "font": {"size": 14}},
                    "yaxis": {"title": "Correlation (%)", "range": [0, max(values) * 1.2]},
                    "height": 220,
                    "margin": {"t": 40, "r": 20, "b": 40, "l": 50},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Correlation",
        }
    except Exception as e:
        logger.warning(f"Failed to build correlation chart: {e}")
        return None


def build_position_chart(
    index_cost: float,
    constituent_cost: float,
    net_cost: float,
) -> Optional[Dict[str, Any]]:
    """Build bar chart showing position costs breakdown."""
    try:
        labels = ["Index (Long)", "Constituents (Short)", "Net Cost"]
        values = [index_cost, -constituent_cost, net_cost]
        colors = [COLORS["teal"], COLORS["amber"], COLORS["green"] if net_cost < 0 else COLORS["red"]]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": labels,
                    "y": values,
                    "marker": {"color": colors},
                    "text": [f"${v:,.0f}" for v in values],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{x}</b>: $%{y:,.0f}<extra></extra>",
                }],
                "layout": {
                    "title": {"text": "Position Costs", "font": {"size": 14}},
                    "yaxis": {"title": "Cost ($)"},
                    "height": 220,
                    "margin": {"t": 40, "r": 20, "b": 40, "l": 60},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Positions",
        }
    except Exception as e:
        logger.warning(f"Failed to build position chart: {e}")
        return None


def build_vega_chart(constituent_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build bar chart of vega per constituent."""
    if not constituent_data:
        return None
    
    try:
        # Sort by vega descending
        sorted_data = sorted(constituent_data, key=lambda x: x.get("vega", 0), reverse=True)
        
        tickers = [d.get("ticker", "?") for d in sorted_data]
        vegas = [d.get("vega", 0) * d.get("contracts", 0) for d in sorted_data]
        ivs = [d.get("avg_iv", 0) * 100 for d in sorted_data]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": tickers,
                    "y": vegas,
                    "marker": {"color": COLORS["teal"]},
                    "text": [f"{v:.2f}" for v in vegas],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{x}</b><br>Vega: %{y:.2f}<br>IV: %{customdata:.1f}%<extra></extra>",
                    "customdata": ivs,
                }],
                "layout": {
                    "title": {"text": "Constituent Vega Exposure", "font": {"size": 14}},
                    "xaxis": {"title": "Ticker"},
                    "yaxis": {"title": "Vega ($)"},
                    "height": 220,
                    "margin": {"t": 40, "r": 20, "b": 50, "l": 50},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Vega Profile",
        }
    except Exception as e:
        logger.warning(f"Failed to build vega chart: {e}")
        return None
