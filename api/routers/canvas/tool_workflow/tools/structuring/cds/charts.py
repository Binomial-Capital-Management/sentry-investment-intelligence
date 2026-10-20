"""
Credit Default Swap Charts for Canvas - Enhanced visualizations
"""
from typing import Dict, Any, Optional


def build_survival_curve_chart(
    survival_curve: Dict[str, float],
    ticker: str,
    tenor: str,
    distance_to_default: Optional[float] = None,
    default_probability: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build credit risk timeline with dual axis: survival vs default probability.
    
    Instead of a boring flat line, show:
    - Survival probability (left axis)
    - Cumulative default probability (right axis, inverted color)
    - Distance to default annotation
    """
    if not survival_curve:
        return None
    
    # Convert dict to sorted lists
    times = []
    survival_probs = []
    for time_str, prob in sorted(survival_curve.items(), key=lambda x: float(x[0])):
        times.append(float(time_str))
        survival_probs.append(prob * 100)  # Convert to %
    
    if not times:
        return None
    
    # Calculate cumulative default probability
    default_probs = [100 - sp for sp in survival_probs]
    
    # Determine if we should zoom in (for high-quality credits with low default prob)
    max_default = max(default_probs)
    survival_range = [95, 100] if min(survival_probs) > 95 else [0, 100]
    default_range = [0, 5] if max_default < 5 else [0, max(10, max_default * 1.2)]
    
    data = [
        {
            "type": "scatter",
            "x": times,
            "y": survival_probs,
            "mode": "lines",
            "name": "Survival Probability",
            "line": {"color": "#10AC84", "width": 3},
            "fill": "tozeroy",
            "fillcolor": "rgba(16, 172, 132, 0.15)",
            "yaxis": "y",
            "hovertemplate": "Year %{x:.1f}<br>Survival: %{y:.3f}%<extra></extra>",
        },
        {
            "type": "scatter",
            "x": times,
            "y": default_probs,
            "mode": "lines",
            "name": "Cumulative Default",
            "line": {"color": "#EE5A6F", "width": 2, "dash": "dash"},
            "yaxis": "y2",
            "hovertemplate": "Year %{x:.1f}<br>Default: %{y:.3f}%<extra></extra>",
        }
    ]
    
    # Add subtitle with distance to default if available
    title_text = f"{ticker} Credit Risk Timeline - {tenor}"
    if distance_to_default is not None:
        title_text += f"<br><sub style='color:#666'>Distance to Default: {distance_to_default:.2f}σ</sub>"
    
    layout = {
        "title": {"text": title_text, "font": {"size": 14}, "x": 0.5, "xanchor": "center"},
        "xaxis": {"title": "Time (Years)", "rangemode": "tozero", "gridcolor": "#E8E8E8"},
        "yaxis": {
            "title": "Survival Probability (%)",
            "range": survival_range,
            "tickformat": ".2f",
            "side": "left",
            "gridcolor": "#E8E8E8"
        },
        "yaxis2": {
            "title": "Cumulative Default (%)",
            "range": default_range,
            "tickformat": ".3f",
            "side": "right",
            "overlaying": "y",
            "showgrid": False
        },
        "hovermode": "x unified",
        "showlegend": True,
        "legend": {"x": 0.02, "y": 0.98, "bgcolor": "rgba(255,255,255,0.9)", "bordercolor": "#E0E0E0", "borderwidth": 1},
        "height": 400,
        "margin": {"l": 60, "r": 60, "t": 80, "b": 50},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "white",
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "line",
        "label": "Credit Risk Timeline",
    }


def build_pv_breakdown_chart(
    premium_leg_pv: float,
    protection_leg_pv: float,
    cds_value: float,
    fair_spread_bps: float,
) -> Optional[Dict[str, Any]]:
    """
    Build spread sensitivity ladder instead of boring waterfall.
    
    Shows how CDS value changes with different spread assumptions.
    More actionable than just showing PV breakdown.
    """
    if not fair_spread_bps:
        return None
    
    # Create spread ladder: -50%, -25%, fair, +25%, +50%
    spreads = [
        fair_spread_bps * 0.5,
        fair_spread_bps * 0.75,
        fair_spread_bps,
        fair_spread_bps * 1.25,
        fair_spread_bps * 1.5
    ]
    
    # Approximate CDS value change (linear approximation using DV01 concept)
    # CDS value changes roughly proportionally to spread change
    spread_changes = [s - fair_spread_bps for s in spreads]
    
    # For fair spread, CDS value = 0. Value changes linearly with spread.
    # Protection buyer benefits from spread widening (positive value)
    base_dv01 = premium_leg_pv / fair_spread_bps if fair_spread_bps > 0 else 0
    cds_values = [base_dv01 * sc for sc in spread_changes]
    
    # Labels with spread values
    labels = [
        f"{spreads[0]:.0f} bps<br>(-50%)", 
        f"{spreads[1]:.0f} bps<br>(-25%)", 
        f"{spreads[2]:.0f} bps<br>(Fair)", 
        f"{spreads[3]:.0f} bps<br>(+25%)", 
        f"{spreads[4]:.0f} bps<br>(+50%)"
    ]
    
    colors = ["#EE5A6F" if v < 0 else "#10AC84" if v > 0 else "#6C757D" for v in cds_values]
    
    data = [{
        "type": "bar",
        "x": labels,
        "y": cds_values,
        "marker": {"color": colors},
        "text": [f"${v:,.0f}" for v in cds_values],
        "textposition": "outside",
        "hovertemplate": "%{x}<br>CDS Value: %{text}<extra></extra>",
    }]
    
    layout = {
        "title": {"text": "CDS Spread Sensitivity", "font": {"size": 14}},
        "xaxis": {"title": "Spread Scenario"},
        "yaxis": {"title": "CDS Value ($)", "tickformat": "$,.0f", "zeroline": True, "zerolinewidth": 2, "zerolinecolor": "#999"},
        "showlegend": False,
        "height": 400,
        "margin": {"l": 60, "r": 40, "t": 50, "b": 60},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "annotations": [{
            "text": "Protection Buyer's Perspective: Positive value means spread widened (credit deteriorated)",
            "xref": "paper",
            "yref": "paper",
            "x": 0.5,
            "y": -0.18,
            "showarrow": False,
            "font": {"size": 10, "color": "#666"},
            "xanchor": "center"
        }]
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "bar",
        "label": "Spread Sensitivity",
    }
