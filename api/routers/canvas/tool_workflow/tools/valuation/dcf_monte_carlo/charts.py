"""
Monte Carlo DCF Charts for Canvas
Rebuilds distribution chart from histogram data.
"""
from typing import Dict, Any, List, Optional


def build_distribution_chart(
    histogram: Dict[str, Any],
    current_price: float,
    median_value: float,
    percentiles: Dict[str, float],
    symbol: str,
) -> Dict[str, Any]:
    """Build valuation distribution histogram with price markers."""
    buckets = histogram.get("buckets", [])
    if not buckets:
        return None
    
    x_vals = [(b["min"] + b["max"]) / 2 for b in buckets]
    y_vals = [b["count"] for b in buckets]
    
    data = [{
        "type": "bar",
        "x": x_vals,
        "y": y_vals,
        "name": "Fair Value Distribution",
        "marker": {
            "color": "rgba(59, 130, 246, 0.7)",
            "line": {"color": "rgba(59, 130, 246, 1)", "width": 1}
        },
        "hovertemplate": "Value: $%{x:,.0f}<br>Simulations: %{y}<extra></extra>",
        "width": histogram.get("bucket_width", 5),
    }]
    
    shapes = [
        {"type": "line", "x0": current_price, "x1": current_price,
         "y0": 0, "y1": 1, "yref": "paper",
         "line": {"color": "red", "width": 2}},
        {"type": "line", "x0": median_value, "x1": median_value,
         "y0": 0, "y1": 1, "yref": "paper",
         "line": {"color": "green", "width": 2, "dash": "dash"}},
    ]
    
    annotations = [
        {"x": current_price, "y": 1.02, "yref": "paper",
         "text": f"Current: ${current_price:,.0f}", "showarrow": False,
         "font": {"color": "red", "size": 11}},
        {"x": median_value, "y": 0.95, "yref": "paper",
         "text": f"Median: ${median_value:,.0f}", "showarrow": False,
         "font": {"color": "green", "size": 11}},
    ]
    
    layout = {
        "title": {"text": f"{symbol} Monte Carlo DCF", "font": {"size": 14}},
        "xaxis": {"title": "Fair Value ($)", "tickformat": "$,.0f"},
        "yaxis": {"title": "Simulations"},
        "shapes": shapes,
        "annotations": annotations,
        "showlegend": False,
        "height": 400,
        "margin": {"l": 60, "r": 40, "t": 50, "b": 50},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "histogram",
        "label": "Fair Value Distribution",
    }
