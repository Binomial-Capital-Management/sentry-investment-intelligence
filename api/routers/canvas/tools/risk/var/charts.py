"""
VaR Canvas Charts
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_returns_histogram(
    portfolio_returns: List[float],
    var_summary: Dict[str, Dict[str, float]],
    tickers: List[str],
    method: str
) -> Optional[Dict[str, Any]]:
    """Build returns histogram with VaR lines."""
    if not portfolio_returns:
        return None
    
    import numpy as np
    
    returns = np.array(portfolio_returns)
    
    # Create histogram bins
    hist, bin_edges = np.histogram(returns, bins=50)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Base histogram trace
    data = [{
        "type": "bar",
        "x": bin_centers.tolist(),
        "y": hist.tolist(),
        "marker": {"color": "#3b82f6", "opacity": 0.7},
        "name": "Returns",
        "hovertemplate": "Return: %{x:.2%}<br>Frequency: %{y}<extra></extra>"
    }]
    
    # Add VaR lines
    colors = ["#ef4444", "#f97316", "#eab308", "#22c55e"]
    shapes = []
    annotations = []
    
    for i, (var_name, var_data) in enumerate(var_summary.items()):
        var_pct = var_data.get("percentage", 0)
        if var_pct:
            color = colors[i % len(colors)]
            shapes.append({
                "type": "line",
                "x0": -var_pct,
                "x1": -var_pct,
                "y0": 0,
                "y1": max(hist) * 1.1,
                "line": {"color": color, "width": 2, "dash": "dash"}
            })
            annotations.append({
                "x": -var_pct,
                "y": max(hist) * (0.9 - i * 0.1),
                "text": f"{var_name}: {var_pct:.2%}",
                "showarrow": False,
                "font": {"color": color, "size": 10},
                "xanchor": "left"
            })
    
    ticker_display = ", ".join(tickers[:3])
    if len(tickers) > 3:
        ticker_display += f" +{len(tickers) - 3}"
    
    layout = {
        "title": f"Returns Distribution with VaR - {ticker_display}",
        "xaxis": {
            "title": "Daily Return",
            "tickformat": ".1%",
            "gridcolor": "#e5e7eb"
        },
        "yaxis": {
            "title": "Frequency",
            "gridcolor": "#e5e7eb"
        },
        "shapes": shapes,
        "annotations": annotations,
        "template": "plotly_white",
        "height": 400,
        "margin": {"l": 60, "r": 40, "t": 60, "b": 60}
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "histogram",
        "label": "Returns Distribution"
    }


def build_var_comparison_chart(
    var_summary: Dict[str, Dict[str, float]],
    portfolio_value: float
) -> Optional[Dict[str, Any]]:
    """Build bar chart comparing VaR across methods."""
    if not var_summary:
        return None
    
    # Organize by confidence level
    by_confidence = {}
    for var_name, var_data in var_summary.items():
        # Parse name like "Historical 95%"
        parts = var_name.split()
        if len(parts) >= 2:
            method = parts[0]
            conf = parts[1]
            if conf not in by_confidence:
                by_confidence[conf] = {}
            by_confidence[conf][method] = var_data.get("dollar", 0)
    
    data = []
    colors = {"Historical": "#3b82f6", "Parametric": "#8b5cf6", "Monte_carlo": "#22c55e", "Monte": "#22c55e"}
    
    for conf, methods in by_confidence.items():
        for method, dollar_var in methods.items():
            data.append({
                "type": "bar",
                "x": [f"{conf}"],
                "y": [dollar_var],
                "name": method,
                "marker": {"color": colors.get(method, "#6b7280")},
                "hovertemplate": f"{method} VaR<br>%{{y:$,.0f}}<extra></extra>"
            })
    
    layout = {
        "title": f"VaR Comparison (Portfolio: ${portfolio_value:,.0f})",
        "xaxis": {"title": "Confidence Level"},
        "yaxis": {"title": "VaR ($)", "tickprefix": "$", "tickformat": ",.0f"},
        "barmode": "group",
        "template": "plotly_white",
        "height": 350,
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02}
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "bar",
        "label": "VaR Comparison"
    }
















