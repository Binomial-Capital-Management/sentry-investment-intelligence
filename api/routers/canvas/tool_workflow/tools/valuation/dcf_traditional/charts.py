"""
Traditional DCF Charts for Canvas
"""
from typing import Dict, Any, Optional


def build_cashflow_chart(
    breakdown: Dict[str, Any],
    symbol: str,
    stages: int,
) -> Optional[Dict[str, Any]]:
    """Build year-by-year cashflow chart."""
    stage1_cfs = breakdown.get("stage1_cashflows", [])
    stage2_cfs = breakdown.get("stage2_cashflows", [])
    
    if not stage1_cfs:
        return None
    
    # Combine all cashflows
    all_cfs = stage1_cfs + stage2_cfs
    
    years = [cf["year"] for cf in all_cfs]
    cashflows = [cf["cf"] for cf in all_cfs]
    pvs = [cf["pv"] for cf in all_cfs]
    
    data = [
        {
            "type": "bar",
            "x": years,
            "y": cashflows,
            "name": "Projected Cash Flow",
            "marker": {"color": "rgba(59, 130, 246, 0.7)"},
            "hovertemplate": "Year %{x}: $%{y:,.2f}<extra></extra>",
        },
        {
            "type": "scatter",
            "x": years,
            "y": pvs,
            "name": "Present Value",
            "mode": "lines+markers",
            "line": {"color": "green", "width": 2},
            "marker": {"size": 6},
            "hovertemplate": "Year %{x} PV: $%{y:,.2f}<extra></extra>",
        },
    ]
    
    layout = {
        "title": {"text": f"{symbol} - Projected Cash Flows", "font": {"size": 14}},
        "xaxis": {"title": "Year", "dtick": 1},
        "yaxis": {"title": "Cash Flow ($)", "tickformat": "$,.0f"},
        "showlegend": True,
        "legend": {"x": 0.02, "y": 0.98},
        "height": 400,
        "margin": {"l": 60, "r": 40, "t": 50, "b": 50},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "bar",
        "label": "Projected Cash Flows",
    }


def build_value_breakdown_chart(
    breakdown: Dict[str, Any],
    symbol: str,
) -> Optional[Dict[str, Any]]:
    """Build waterfall chart showing PV accumulation."""
    stage1_pv = breakdown.get("stage1_pv", 0)
    stage2_pv = breakdown.get("stage2_pv", 0)
    terminal_pv = breakdown.get("terminal_pv", 0)
    
    if not (stage1_pv or stage2_pv or terminal_pv):
        return None
    
    # Build waterfall: Stage 1 → (+Stage 2 if exists) → +Terminal → Total
    x = []
    y = []
    measure = []
    text = []
    
    # Stage 1 PV (absolute)
    x.append("Stage 1<br>PV")
    y.append(stage1_pv)
    measure.append("absolute")
    text.append(f"${stage1_pv:,.0f}")
    
    # Stage 2 PV (relative, if exists)
    if stage2_pv > 0:
        x.append("Stage 2<br>PV")
        y.append(stage2_pv)
        measure.append("relative")
        text.append(f"+${stage2_pv:,.0f}")
    
    # Terminal PV (relative)
    x.append("Terminal<br>PV")
    y.append(terminal_pv)
    measure.append("relative")
    text.append(f"+${terminal_pv:,.0f}")
    
    # Total (total)
    total = stage1_pv + stage2_pv + terminal_pv
    x.append("Total<br>Value")
    y.append(total)
    measure.append("total")
    text.append(f"${total:,.0f}")
    
    data = [{
        "type": "waterfall",
        "orientation": "v",
        "x": x,
        "y": y,
        "measure": measure,
        "text": text,
        "textposition": "outside",
        "connector": {
            "line": {"color": "rgba(128,128,128,0.5)", "width": 2, "dash": "dot"}
        },
        "increasing": {"marker": {"color": "rgba(59, 130, 246, 0.8)"}},
        "decreasing": {"marker": {"color": "rgba(239, 68, 68, 0.8)"}},
        "totals": {"marker": {"color": "rgba(34, 197, 94, 0.8)"}},
        "hovertemplate": "%{x}: %{text}<extra></extra>",
    }]
    
    layout = {
        "title": {"text": f"{symbol} - Value Waterfall", "font": {"size": 14}},
        "xaxis": {"title": ""},
        "yaxis": {"title": "Present Value ($)", "tickformat": "$,.0f"},
        "showlegend": False,
        "height": 400,
        "margin": {"l": 60, "r": 40, "t": 50, "b": 60},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "waterfall",
        "label": "Value Breakdown",
    }
