"""
Chart builders for NOPE Divergence Scanner.

Builds divergence scatter, NOPE vs price trends, and signal breakdown.
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


def build_divergence_scatter(divergences: List[Dict]) -> Optional[Dict[str, Any]]:
    """Build scatter plot of z-score vs confidence for all divergences."""
    if not divergences:
        return None
    
    bullish = [d for d in divergences if d.get("divergence", {}).get("type") == "BULLISH"]
    bearish = [d for d in divergences if d.get("divergence", {}).get("type") == "BEARISH"]
    
    traces = []
    
    # Bullish points
    if bullish:
        traces.append({
            "x": [_safe_float(d.get("divergence", {}).get("z_score")) for d in bullish],
            "y": [_safe_float(d.get("divergence", {}).get("confidence")) * 100 for d in bullish],
            "text": [d.get("ticker", "") for d in bullish],
            "type": "scatter",
            "mode": "markers+text",
            "name": "Bullish",
            "marker": {"color": COLORS["green"], "size": 14, "symbol": "triangle-up"},
            "textposition": "top center",
            "textfont": {"size": 10},
        })
    
    # Bearish points
    if bearish:
        traces.append({
            "x": [_safe_float(d.get("divergence", {}).get("z_score")) for d in bearish],
            "y": [_safe_float(d.get("divergence", {}).get("confidence")) * 100 for d in bearish],
            "text": [d.get("ticker", "") for d in bearish],
            "type": "scatter",
            "mode": "markers+text",
            "name": "Bearish",
            "marker": {"color": COLORS["red"], "size": 14, "symbol": "triangle-down"},
            "textposition": "bottom center",
            "textfont": {"size": 10},
        })
    
    # Threshold line at z=-1.5
    traces.append({
        "x": [-1.5, -1.5],
        "y": [0, 100],
        "type": "scatter",
        "mode": "lines",
        "name": "Threshold (z=-1.5)",
        "line": {"color": COLORS["gray"], "width": 1, "dash": "dash"},
        "showlegend": False,
    })
    
    return {
        "plotly": {
            "data": traces,
            "layout": {
                "title": {"text": "<b>NOPE Divergences</b> (z-score vs Confidence)", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": "Z-Score (more negative = stronger divergence)", "zeroline": True},
                "yaxis": {"title": "Confidence (%)", "range": [0, 100]},
                "legend": {"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
                "height": 320,
                "margin": {"t": 50, "b": 60, "l": 60, "r": 30},
                "template": "plotly_white",
            },
        },
        "type": "scatter",
        "label": "Divergence Map",
    }


def build_nope_vs_price_chart(divergences: List[Dict]) -> Optional[Dict[str, Any]]:
    """Build bar chart showing NOPE change vs price change for top divergences."""
    if not divergences:
        return None
    
    tickers = []
    nope_changes = []
    price_changes = []
    colors = []
    
    for div in divergences[:8]:  # Top 8
        ticker = div.get("ticker", "")
        nope_change = _safe_float(div.get("nope_change"))
        price_change = _safe_float(div.get("price_change_pct"))
        div_type = div.get("divergence", {}).get("type", "")
        
        tickers.append(ticker)
        nope_changes.append(nope_change)
        price_changes.append(price_change)
        colors.append(COLORS["green"] if div_type == "BULLISH" else COLORS["red"])
    
    return {
        "plotly": {
            "data": [
                {
                    "x": tickers,
                    "y": nope_changes,
                    "type": "bar",
                    "name": "NOPE Change",
                    "marker": {"color": COLORS["blue"]},
                    "yaxis": "y",
                },
                {
                    "x": tickers,
                    "y": price_changes,
                    "type": "bar",
                    "name": "Price Change %",
                    "marker": {"color": colors},
                    "yaxis": "y2",
                },
            ],
            "layout": {
                "title": {"text": "<b>NOPE vs Price Change</b>", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": ""},
                "yaxis": {"title": "NOPE Δ", "side": "left"},
                "yaxis2": {"title": "Price Δ %", "side": "right", "overlaying": "y"},
                "barmode": "group",
                "legend": {"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
                "height": 280,
                "margin": {"t": 50, "b": 50, "l": 60, "r": 60},
                "template": "plotly_white",
            },
        },
        "type": "bar",
        "label": "NOPE vs Price",
    }


def build_signal_breakdown(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build pie chart of signal breakdown."""
    if not summary:
        return None
    
    bullish = summary.get("bullish", 0)
    bearish = summary.get("bearish", 0)
    no_div = summary.get("no_divergence", 0)
    no_data = summary.get("no_data", 0)
    
    values = []
    labels = []
    colors = []
    
    if bullish > 0:
        values.append(bullish)
        labels.append(f"Bullish ({bullish})")
        colors.append(COLORS["green"])
    
    if bearish > 0:
        values.append(bearish)
        labels.append(f"Bearish ({bearish})")
        colors.append(COLORS["red"])
    
    if no_div > 0:
        values.append(no_div)
        labels.append(f"No Signal ({no_div})")
        colors.append(COLORS["gray"])
    
    if no_data > 0:
        values.append(no_data)
        labels.append(f"No Data ({no_data})")
        colors.append("#d1d5db")
    
    if not values:
        return None
    
    return {
        "plotly": {
            "data": [{
                "values": values,
                "labels": labels,
                "type": "pie",
                "marker": {"colors": colors},
                "hole": 0.4,
                "textinfo": "percent",
                "textposition": "outside",
            }],
            "layout": {
                "title": {"text": "<b>Signal Breakdown</b>", "x": 0.5, "font": {"size": 14}},
                "showlegend": True,
                "legend": {"orientation": "h", "y": -0.1, "x": 0.5, "xanchor": "center"},
                "height": 280,
                "margin": {"t": 50, "b": 50, "l": 30, "r": 30},
            },
        },
        "type": "pie",
        "label": "Signal Breakdown",
    }
