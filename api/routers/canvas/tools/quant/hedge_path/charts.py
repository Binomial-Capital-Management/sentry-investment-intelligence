"""
Canvas charts for Optimal Hedge Path Finder.

Visualizations:
- Hedge allocation by instrument
- Factor before/after comparison
- Path flow diagram
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Institutional color palette
COLORS = {
    "primary": "#3b82f6",
    "secondary": "#10b981",
    "before": "#64748b",
    "after": "#059669",
    "cost": "#f59e0b",
    "negative": "#ef4444",
}


def _safe_float(val, default=0.0) -> float:
    """Safely convert value to float."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    return default


def build_hedge_allocation_chart(
    instruments: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Build horizontal bar chart showing hedge notional by instrument.
    """
    if not instruments:
        return None
    
    # Sort by cost descending
    sorted_inst = sorted(instruments, key=lambda x: abs(_safe_float(x.get("cost", 0))), reverse=True)[:12]
    
    tickers = [inst.get("instrument", inst.get("ticker", "?")) for inst in sorted_inst]
    costs = [abs(_safe_float(inst.get("cost", 0))) for inst in sorted_inst]
    delta_impacts = [_safe_float(inst.get("delta_impact", 0)) for inst in sorted_inst]
    
    # Reverse for horizontal bar
    tickers = tickers[::-1]
    costs = costs[::-1]
    delta_impacts = delta_impacts[::-1]
    
    # Color by cost vs delta impact direction
    colors = [COLORS["cost"] if c > 0 else COLORS["negative"] for c in costs]
    
    traces = [{
        "type": "bar",
        "x": costs,
        "y": tickers,
        "orientation": "h",
        "marker": {"color": COLORS["primary"]},
        "text": [f"${c:,.0f}" for c in costs],
        "textposition": "outside",
        "hovertemplate": "<b>%{y}</b><br>Cost: $%{x:,.0f}<br>Delta Impact: $%{customdata:,.0f}<extra></extra>",
        "customdata": delta_impacts,
    }]
    
    layout = {
        "title": {
            "text": "<b>Hedge Instruments by Cost</b>",
            "font": {"size": 14, "family": "Inter, system-ui"},
        },
        "xaxis": {
            "title": "Cost ($)",
            "gridcolor": "#e5e7eb",
        },
        "yaxis": {
            "title": "",
            "tickfont": {"size": 10},
        },
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "showlegend": False,
        "height": 400,
        "margin": {"t": 50, "r": 80, "b": 50, "l": 120},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "bar",
        "label": "Hedge Allocation",
    }


def build_factor_comparison_chart(
    current_factors: Dict[str, Any],
    final_factors: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Build grouped bar chart comparing factors before and after hedge.
    """
    if not current_factors:
        return None
    
    if not final_factors:
        final_factors = current_factors
    
    # Key factors to compare
    metrics = ["delta", "beta", "var_1d_95"]
    labels = ["Delta ($)", "Beta", "VaR 95%"]
    
    before_vals = []
    after_vals = []
    
    for metric in metrics:
        before = _safe_float(current_factors.get(metric, 0))
        after = _safe_float(final_factors.get(metric, before))
        
        # Normalize for display (beta on different scale)
        if metric == "beta":
            before_vals.append(before * 100000)  # Scale up for visibility
            after_vals.append(after * 100000)
        else:
            before_vals.append(abs(before))
            after_vals.append(abs(after))
    
    traces = [
        {
            "type": "bar",
            "x": labels,
            "y": before_vals,
            "name": "Before",
            "marker": {"color": COLORS["before"]},
        },
        {
            "type": "bar",
            "x": labels,
            "y": after_vals,
            "name": "After Hedge",
            "marker": {"color": COLORS["after"]},
        },
    ]
    
    layout = {
        "title": {
            "text": "<b>Factor Comparison: Before vs After</b>",
            "font": {"size": 14, "family": "Inter, system-ui"},
        },
        "xaxis": {"title": ""},
        "yaxis": {
            "title": "Value",
            "gridcolor": "#e5e7eb",
        },
        "barmode": "group",
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "legend": {"orientation": "h", "y": 1.12},
        "annotations": [
            {
                "x": 0.5, "y": -0.15,
                "xref": "paper", "yref": "paper",
                "text": "Beta scaled ×100K for visibility",
                "showarrow": False,
                "font": {"size": 9, "color": "#94a3b8"},
            }
        ],
        "height": 350,
        "margin": {"t": 70, "r": 30, "b": 60, "l": 60},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "bar",
        "label": "Factor Comparison",
    }


def build_path_flow_chart(
    instruments: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Build waterfall chart showing cumulative delta reduction.
    """
    if not instruments or len(instruments) < 2:
        return None
    
    # Take top instruments by delta impact
    sorted_inst = sorted(instruments, key=lambda x: abs(_safe_float(x.get("delta_impact", 0))), reverse=True)[:8]
    
    labels = ["Start"]
    values = [0]  # Placeholder for initial state
    
    cumulative = 0
    for inst in sorted_inst:
        ticker = inst.get("instrument", inst.get("ticker", "?"))
        delta_impact = _safe_float(inst.get("delta_impact", 0))
        
        labels.append(ticker)
        values.append(delta_impact)
        cumulative += delta_impact
    
    labels.append("Final")
    values.append(cumulative)
    
    traces = [{
        "type": "waterfall",
        "orientation": "v",
        "x": labels,
        "y": values,
        "connector": {"line": {"color": "#cbd5e1"}},
        "increasing": {"marker": {"color": COLORS["secondary"]}},
        "decreasing": {"marker": {"color": COLORS["negative"]}},
        "totals": {"marker": {"color": COLORS["primary"]}},
        "text": [f"${v:+,.0f}" for v in values],
        "textposition": "outside",
        "textfont": {"size": 10},
        "hovertemplate": "<b>%{x}</b><br>Delta Impact: $%{y:+,.0f}<extra></extra>",
    }]
    
    layout = {
        "title": {
            "text": "<b>Dijkstra Path: Cumulative Delta Reduction</b>",
            "font": {"size": 14, "family": "Inter, system-ui"},
        },
        "xaxis": {
            "title": "",
            "tickangle": -45,
        },
        "yaxis": {
            "title": "Delta Impact ($)",
            "gridcolor": "#e5e7eb",
        },
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "showlegend": False,
        "height": 380,
        "margin": {"t": 60, "r": 30, "b": 80, "l": 70},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "waterfall",
        "label": "Dijkstra Path",
    }
