"""
FX Carry Trade Charts for Canvas
"""
from typing import Dict, Any, Optional, List


def build_carry_ranking_chart(
    rankings: List[Dict[str, Any]],
    has_carry: bool
) -> Optional[Dict[str, Any]]:
    """
    Build FX carry trade ranking chart.
    
    Two modes:
    1. Carry mode: Horizontal bar chart showing risk-adjusted carry
    2. Volatility mode: Horizontal bar chart showing volatility
    """
    if not rankings:
        return None
    
    pairs = [r.get("pair", "") for r in rankings]
    
    if has_carry:
        # Risk-adjusted carry chart
        risk_adj_carries = [r.get("risk_adjusted_carry", 0) for r in rankings]
        carries = [r.get("carry_pct", 0) for r in rankings]
        vols = [r.get("volatility_pct", 0) for r in rankings]
        
        # Color: green for positive, red for negative
        colors = ['#22c55e' if c > 0 else '#ef4444' for c in risk_adj_carries]
        
        data = [{
            "type": "bar",
            "y": pairs,  # Pairs on y-axis (horizontal bars)
            "x": risk_adj_carries,  # Risk-adj carry on x-axis
            "orientation": "h",
            "marker": {"color": colors},
            "text": [f"{c:.3f}" for c in risk_adj_carries],
            "textposition": "outside",
            "hovertemplate": (
                "<b>%{y}</b><br>"
                "Risk-Adj Carry: %{x:.3f}<br>"
                "Carry: %{customdata[0]:.2f}%<br>"
                "Volatility: %{customdata[1]:.1f}%"
                "<extra></extra>"
            ),
            "customdata": [[c, v] for c, v in zip(carries, vols)]
        }]
        
        layout = {
            "title": {"text": "FX Carry Trade Rankings", "font": {"size": 14}, "x": 0.5, "xanchor": "center"},
            "xaxis": {"title": "Risk-Adjusted Carry (Higher = Better)", "zeroline": True, "zerolinewidth": 2, "zerolinecolor": "#999"},
            "yaxis": {"title": "", "autorange": "reversed"},  # Best at top
            "height": max(400, len(pairs) * 50),
            "margin": {"l": 100, "r": 40, "t": 60, "b": 60},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "white",
            "showlegend": False,
        }
    else:
        # Volatility-only chart
        vols = [r.get("volatility_pct", 0) for r in rankings]
        
        data = [{
            "type": "bar",
            "y": pairs,
            "x": vols,
            "orientation": "h",
            "marker": {"color": "#60a5fa"},
            "text": [f"{v:.1f}%" for v in vols],
            "textposition": "outside",
            "hovertemplate": "<b>%{y}</b><br>Volatility: %{x:.1f}%<extra></extra>"
        }]
        
        layout = {
            "title": {"text": "FX Pair Volatility Rankings", "font": {"size": 14}, "x": 0.5, "xanchor": "center"},
            "xaxis": {"title": "Annualized Volatility (%)"},
            "yaxis": {"title": "", "autorange": "reversed"},  # Lowest vol at top
            "height": max(400, len(pairs) * 50),
            "margin": {"l": 100, "r": 40, "t": 60, "b": 60},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "white",
            "showlegend": False,
        }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "bar",
        "label": "FX Rankings"
    }
