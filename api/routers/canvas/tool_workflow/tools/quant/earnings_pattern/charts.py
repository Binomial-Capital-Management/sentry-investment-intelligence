"""
Canvas charts for Earnings Pattern Analyzer.

Visualizations:
- Expected vs Actual earnings move comparison
- Short straddle returns by quarter
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Color palette
COLORS = {
    "expected": "#8b5cf6",   # Purple
    "beat": "#22c55e",       # Green
    "miss": "#ef4444",       # Red
    "neutral": "#6b7280",    # Gray
}


def build_move_comparison_chart(
    ticker: str,
    historical_detail: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Build bar chart comparing expected vs actual moves around earnings.
    """
    # Filter to records with move data
    valid_records = [
        r for r in historical_detail
        if r.get("date") and r.get("expected_move_pct") is not None and r.get("actual_move_pct") is not None
    ]
    
    if len(valid_records) < 2:
        return None
    
    # Sort by date
    valid_records = sorted(valid_records, key=lambda x: x["date"])
    
    dates = [r["date"][:7] for r in valid_records]  # YYYY-MM format
    expected = [r.get("expected_move_pct", 0) for r in valid_records]
    actual = [r.get("actual_move_pct", 0) for r in valid_records]
    
    # Color actual bars based on vol crush
    actual_colors = [
        COLORS["beat"] if a < e else COLORS["miss"]
        for a, e in zip(actual, expected)
    ]
    
    # Calculate vol crush rate
    vol_crush_pct = sum(1 for a, e in zip(actual, expected) if a < e) / len(actual) * 100
    
    traces = [
        {
            "type": "bar",
            "x": dates,
            "y": expected,
            "name": "Expected (IV)",
            "marker": {"color": COLORS["expected"], "opacity": 0.7},
            "hovertemplate": "Expected: %{y:.1f}%<extra></extra>",
        },
        {
            "type": "bar",
            "x": dates,
            "y": actual,
            "name": "Actual Move",
            "marker": {"color": actual_colors},
            "hovertemplate": "Actual: %{y:.1f}%<extra></extra>",
        },
    ]
    
    layout = {
        "title": {"text": f"{ticker} Expected vs Actual Earnings Move", "font": {"size": 14}},
        "xaxis": {
            "title": "Earnings Date",
            "tickangle": -45,
        },
        "yaxis": {
            "title": "Move %",
            "gridcolor": "#e5e7eb",
        },
        "barmode": "group",
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "showlegend": True,
        "legend": {"orientation": "h", "y": 1.12},
        "annotations": [
            {
                "x": 0.02, "y": 0.98,
                "xref": "paper", "yref": "paper",
                "text": f"Vol Crush Rate: {vol_crush_pct:.0f}%",
                "showarrow": False,
                "font": {"size": 11, "color": COLORS["beat"] if vol_crush_pct > 50 else COLORS["miss"]},
                "bgcolor": "white",
                "bordercolor": COLORS["beat"] if vol_crush_pct > 50 else COLORS["miss"],
                "borderwidth": 1,
            }
        ],
        "height": 400,
        "margin": {"t": 60, "r": 30, "b": 80, "l": 60},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "bar",
        "label": "Expected vs Actual Move",
    }


def build_straddle_returns_chart(
    ticker: str,
    historical_detail: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Build bar chart of short straddle returns by quarter.
    """
    # Filter to records with straddle return data
    valid_records = [
        r for r in historical_detail
        if r.get("date") and r.get("short_straddle_return") is not None
    ]
    
    if len(valid_records) < 2:
        return None
    
    # Sort by date
    valid_records = sorted(valid_records, key=lambda x: x["date"])
    
    dates = [r["date"][:7] for r in valid_records]
    returns = [r.get("short_straddle_return", 0) for r in valid_records]
    
    # Color based on positive/negative
    colors = [COLORS["beat"] if r > 0 else COLORS["miss"] for r in returns]
    
    # Calculate stats
    win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
    avg_return = sum(returns) / len(returns)
    
    traces = [{
        "type": "bar",
        "x": dates,
        "y": returns,
        "marker": {"color": colors},
        "hovertemplate": "Return: %{y:+.1f}%<extra></extra>",
    }]
    
    layout = {
        "title": {"text": f"{ticker} Short Straddle Returns", "font": {"size": 14}},
        "xaxis": {
            "title": "Earnings Date",
            "tickangle": -45,
        },
        "yaxis": {
            "title": "Return %",
            "gridcolor": "#e5e7eb",
            "zeroline": True,
            "zerolinecolor": "#9ca3af",
            "zerolinewidth": 2,
        },
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "showlegend": False,
        "annotations": [
            {
                "x": 0.02, "y": 0.98,
                "xref": "paper", "yref": "paper",
                "text": f"Win Rate: {win_rate:.0f}% | Avg: {avg_return:+.1f}%",
                "showarrow": False,
                "font": {"size": 11, "color": COLORS["beat"] if avg_return > 0 else COLORS["miss"]},
                "bgcolor": "white",
                "bordercolor": COLORS["beat"] if avg_return > 0 else COLORS["miss"],
                "borderwidth": 1,
            }
        ],
        "height": 350,
        "margin": {"t": 60, "r": 30, "b": 80, "l": 60},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "bar",
        "label": "Straddle Returns",
    }
