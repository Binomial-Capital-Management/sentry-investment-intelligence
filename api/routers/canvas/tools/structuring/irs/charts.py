"""
Interest Rate Swap Charts for Canvas
"""
from typing import List, Dict, Any, Optional


def build_cashflow_chart(
    payment_schedule: List[str],
    fixed_rate: float,
    forward_rates: List[float],
    notional: float,
    tenor: str,
) -> Optional[Dict[str, Any]]:
    """Build chart showing fixed vs floating rate payments."""
    if not payment_schedule or not forward_rates:
        return None
    
    # Convert rates to percentages
    fixed_rates_pct = [fixed_rate * 100] * len(payment_schedule)
    forward_rates_pct = [r * 100 for r in forward_rates]
    
    data = [
        {
            "type": "scatter",
            "x": payment_schedule,
            "y": fixed_rates_pct,
            "mode": "lines+markers",
            "name": "Fixed Rate",
            "line": {"color": "rgba(59, 130, 246, 0.8)", "width": 3},
            "marker": {"size": 8},
            "hovertemplate": "Date: %{x}<br>Fixed: %{y:.2f}%<extra></extra>",
        },
        {
            "type": "scatter",
            "x": payment_schedule,
            "y": forward_rates_pct,
            "mode": "lines+markers",
            "name": "Forward Rate (Float)",
            "line": {"color": "rgba(251, 146, 60, 0.8)", "width": 3, "dash": "dash"},
            "marker": {"size": 8},
            "hovertemplate": "Date: %{x}<br>Float: %{y:.2f}%<extra></extra>",
        },
    ]
    
    layout = {
        "title": {"text": f"IRS Rate Schedule - {tenor}", "font": {"size": 14}},
        "xaxis": {"title": "Payment Date", "tickangle": -45},
        "yaxis": {"title": "Rate (%)", "tickformat": ".2f"},
        "showlegend": True,
        "legend": {"x": 0.02, "y": 0.98},
        "height": 400,
        "margin": {"l": 60, "r": 40, "t": 50, "b": 80},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "hovermode": "x unified",
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "line",
        "label": "Rate Schedule",
    }


def build_pv_breakdown_chart(
    fixed_leg_pv: float,
    float_leg_pv: float,
    swap_value: float,
) -> Optional[Dict[str, Any]]:
    """Build waterfall chart showing PV breakdown."""
    if not (fixed_leg_pv or float_leg_pv):
        return None
    
    # Waterfall: Fixed Leg → - Float Leg → = Swap Value
    x = ["Fixed Leg<br>PV", "Float Leg<br>PV", "Net Swap<br>Value"]
    y = [fixed_leg_pv, -float_leg_pv, swap_value]
    measure = ["absolute", "relative", "total"]
    text = [f"${fixed_leg_pv:,.0f}", f"-${float_leg_pv:,.0f}", f"${swap_value:,.0f}"]
    
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
        "totals": {"marker": {"color": "rgba(34, 197, 94, 0.8)" if swap_value > 0 else "rgba(239, 68, 68, 0.8)"}},
        "hovertemplate": "%{x}: %{text}<extra></extra>",
    }]
    
    layout = {
        "title": {"text": "IRS Present Value Breakdown", "font": {"size": 14}},
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
        "label": "PV Breakdown",
    }
