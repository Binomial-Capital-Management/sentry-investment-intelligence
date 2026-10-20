"""
Canvas charts for Vanna/Charm Flow Analysis.

Institutional-grade visualizations:
- Vanna exposure profile by strike with regime overlay
- Flow scenario waterfall
- Charm drift timeline
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Institutional color palette
COLORS = {
    "long": "#dc2626",       # Red - dealers long (sell pressure)
    "short": "#059669",      # Emerald - dealers short (buy pressure)
    "neutral": "#64748b",    # Slate gray
    "charm": "#7c3aed",      # Violet for charm
    "spot": "#0f172a",       # Near black for spot
    "grid": "#e2e8f0",       # Light gray grid
    "bg": "#fafafa",         # Off-white background
    "annotation_bg": "rgba(255,255,255,0.95)",
}


def build_vanna_profile_chart(
    ticker: str,
    spot_price: float,
    aggregate_vanna: float,
    aggregate_charm: float,
    vanna_regime: str,
    vanna_flip: Optional[float],
    by_strike_data: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build institutional vanna exposure profile.
    
    Shows:
    - Net vanna by strike zone (bucketed)
    - Regime indicator with signal
    - Key levels (spot, flip point)
    - Flow magnitude annotation
    """
    # Determine regime styling
    if "short" in vanna_regime:
        regime_color = COLORS["short"]
        regime_label = "SHORT VANNA"
        regime_signal = "Vol Spike → Dealers BUY"
        signal_icon = "▲"
    elif "long" in vanna_regime:
        regime_color = COLORS["long"]
        regime_label = "LONG VANNA"
        regime_signal = "Vol Spike → Dealers SELL"
        signal_icon = "▼"
    else:
        regime_color = COLORS["neutral"]
        regime_label = "NEUTRAL"
        regime_signal = "Balanced Positioning"
        signal_icon = "◆"
    
    # Format values
    vanna_millions = aggregate_vanna / 1e6
    charm_thousands = aggregate_charm / 1e3
    
    # Create exposure gauge visualization
    # Shows positioning on a scale from -10M to +10M
    max_scale = max(abs(vanna_millions) * 1.5, 5)  # Dynamic scale
    
    traces = []
    
    # Background range bar (full scale)
    traces.append({
        "type": "bar",
        "x": [max_scale * 2],
        "y": ["Vanna"],
        "orientation": "h",
        "marker": {"color": "#f1f5f9"},
        "hoverinfo": "skip",
        "showlegend": False,
    })
    
    # Actual vanna position bar
    traces.append({
        "type": "bar",
        "x": [abs(vanna_millions)],
        "y": ["Vanna"],
        "orientation": "h",
        "base": [0 if vanna_millions >= 0 else vanna_millions],
        "marker": {
            "color": regime_color,
            "line": {"width": 0},
        },
        "text": [f"{vanna_millions:+.1f}M"],
        "textposition": "outside",
        "textfont": {"size": 14, "color": regime_color, "family": "Inter, monospace"},
        "hovertemplate": f"<b>Net Vanna</b><br>{vanna_millions:+.2f}M shares per 1% IV<extra></extra>",
        "showlegend": False,
    })
    
    # Charm position bar
    charm_color = COLORS["short"] if charm_thousands > 0 else COLORS["long"]
    charm_scaled = charm_thousands / 100  # Scale to fit
    
    traces.append({
        "type": "bar",
        "x": [max_scale * 2],
        "y": ["Charm"],
        "orientation": "h",
        "marker": {"color": "#f1f5f9"},
        "hoverinfo": "skip",
        "showlegend": False,
    })
    
    traces.append({
        "type": "bar",
        "x": [abs(charm_scaled)],
        "y": ["Charm"],
        "orientation": "h",
        "base": [0 if charm_scaled >= 0 else charm_scaled],
        "marker": {
            "color": charm_color,
            "line": {"width": 0},
        },
        "text": [f"{charm_thousands:+.0f}K/day"],
        "textposition": "outside",
        "textfont": {"size": 14, "color": charm_color, "family": "Inter, monospace"},
        "hovertemplate": f"<b>Net Charm</b><br>{charm_thousands:+,.0f} shares per day<extra></extra>",
        "showlegend": False,
    })
    
    # Zero line
    shapes = [{
        "type": "line",
        "x0": 0, "x1": 0,
        "y0": -0.5, "y1": 1.5,
        "line": {"color": COLORS["spot"], "width": 2},
    }]
    
    layout = {
        "title": {
            "text": f"<b>{ticker}</b> Dealer Greek Exposure",
            "font": {"size": 16, "family": "Inter, system-ui", "color": "#0f172a"},
            "x": 0.5,
            "xanchor": "center",
        },
        "xaxis": {
            "title": "",
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "range": [-max_scale, max_scale],
        },
        "yaxis": {
            "title": "",
            "tickfont": {"size": 13, "color": "#475569", "family": "Inter"},
        },
        "barmode": "overlay",
        "paper_bgcolor": "white",
        "plot_bgcolor": COLORS["bg"],
        "shapes": shapes,
        "annotations": [
            # Regime box (top right)
            {
                "x": 0.98, "y": 0.98,
                "xref": "paper", "yref": "paper",
                "xanchor": "right", "yanchor": "top",
                "text": f"<b>{signal_icon} {regime_label}</b><br><span style='font-size:11px'>{regime_signal}</span>",
                "showarrow": False,
                "font": {"size": 13, "color": regime_color, "family": "Inter"},
                "bgcolor": COLORS["annotation_bg"],
                "bordercolor": regime_color,
                "borderwidth": 2,
                "borderpad": 8,
            },
            # Scale labels
            {
                "x": -max_scale * 0.9, "y": -0.35,
                "xref": "x", "yref": "paper",
                "text": "← LONG (sell pressure)",
                "showarrow": False,
                "font": {"size": 10, "color": COLORS["long"]},
            },
            {
                "x": max_scale * 0.9, "y": -0.35,
                "xref": "x", "yref": "paper",
                "text": "SHORT (buy pressure) →",
                "showarrow": False,
                "font": {"size": 10, "color": COLORS["short"]},
            },
        ],
        "height": 280,
        "margin": {"t": 60, "r": 140, "b": 50, "l": 80},
    }
    
    # Add vanna flip annotation if exists
    if vanna_flip and spot_price:
        distance_pct = (vanna_flip - spot_price) / spot_price * 100
        layout["annotations"].append({
            "x": 0.02, "y": 0.02,
            "xref": "paper", "yref": "paper",
            "xanchor": "left", "yanchor": "bottom",
            "text": f"Vanna Flip: <b>${vanna_flip:.0f}</b> ({distance_pct:+.1f}% from ${spot_price:.0f})",
            "showarrow": False,
            "font": {"size": 11, "color": COLORS["charm"]},
            "bgcolor": COLORS["annotation_bg"],
            "borderpad": 4,
        })
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "bar",
        "label": "Greek Exposure",
    }


def build_scenario_chart(
    ticker: str,
    scenarios: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Build institutional scenario waterfall chart.
    
    Shows expected dealer flows at different vol levels.
    """
    if not scenarios:
        return None
    
    # Filter to vol-based scenarios
    vol_scenarios = [s for s in scenarios if "VIX" in s.get("vol_change_description", "")]
    
    if len(vol_scenarios) < 3:
        return None
    
    # Sort by vol change
    vol_scenarios = sorted(vol_scenarios, key=lambda x: x.get("iv_change_pct", 0))
    
    labels = []
    flows = []
    colors = []
    
    for s in vol_scenarios:
        desc = s.get("vol_change_description", "")
        flow = s.get("vanna_flow_shares", 0) / 1e6
        
        labels.append(desc)
        flows.append(flow)
        colors.append(COLORS["short"] if flow > 0 else COLORS["long"])
    
    traces = [{
        "type": "waterfall",
        "orientation": "v",
        "x": labels,
        "y": flows,
        "connector": {"line": {"color": "#cbd5e1", "width": 1}},
        "increasing": {"marker": {"color": COLORS["short"]}},
        "decreasing": {"marker": {"color": COLORS["long"]}},
        "totals": {"marker": {"color": COLORS["neutral"]}},
        "textposition": "outside",
        "text": [f"{f:+.1f}M" for f in flows],
        "textfont": {"size": 11, "family": "Inter, monospace"},
        "hovertemplate": "<b>%{x}</b><br>Dealer Flow: %{y:+.2f}M shares<extra></extra>",
    }]
    
    # Add overnight charm if present
    overnight = next((s for s in scenarios if "charm" in s.get("vol_change_description", "").lower()), None)
    if overnight:
        charm_flow = overnight.get("vanna_flow_shares", 0) / 1e6
        traces[0]["x"] = list(traces[0]["x"]) + ["Overnight"]
        traces[0]["y"] = list(traces[0]["y"]) + [charm_flow]
        traces[0]["text"] = list(traces[0]["text"]) + [f"{charm_flow:+.1f}M"]
    
    layout = {
        "title": {
            "text": f"<b>{ticker}</b> Vol Scenario Flows",
            "font": {"size": 16, "family": "Inter, system-ui", "color": "#0f172a"},
            "x": 0.5,
            "xanchor": "center",
        },
        "xaxis": {
            "title": "",
            "tickfont": {"size": 11, "color": "#475569"},
        },
        "yaxis": {
            "title": "Dealer Flow (M shares)",
            "titlefont": {"size": 12, "color": "#475569"},
            "tickfont": {"size": 11, "color": "#64748b"},
            "gridcolor": COLORS["grid"],
            "zeroline": True,
            "zerolinecolor": COLORS["spot"],
            "zerolinewidth": 2,
        },
        "paper_bgcolor": "white",
        "plot_bgcolor": COLORS["bg"],
        "showlegend": False,
        "annotations": [
            {
                "x": 0.5, "y": 1.08,
                "xref": "paper", "yref": "paper",
                "text": "<span style='color:#059669'>▲ Green = BUY pressure</span>  |  <span style='color:#dc2626'>▼ Red = SELL pressure</span>",
                "showarrow": False,
                "font": {"size": 10, "family": "Inter"},
            },
        ],
        "height": 380,
        "margin": {"t": 80, "r": 30, "b": 60, "l": 70},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "waterfall",
        "label": "Vol Scenario Flows",
    }


def build_regime_gauge_chart(
    ticker: str,
    vanna_regime: str,
    charm_regime: str,
    aggregate_vanna: float,
    aggregate_charm: float,
) -> Optional[Dict[str, Any]]:
    """
    Build a combined regime indicator with directional gauges.
    """
    # Normalize to -1 to +1 scale
    vanna_norm = max(-1, min(1, aggregate_vanna / 5e6))  # ±5M as full scale
    charm_norm = max(-1, min(1, aggregate_charm / 500e3))  # ±500K as full scale
    
    # Combined score
    combined = (vanna_norm * 0.6 + charm_norm * 0.4)  # Weight vanna more
    
    if combined > 0.3:
        signal = "BULLISH FLOW"
        signal_color = COLORS["short"]
    elif combined < -0.3:
        signal = "BEARISH FLOW"
        signal_color = COLORS["long"]
    else:
        signal = "NEUTRAL FLOW"
        signal_color = COLORS["neutral"]
    
    # Create indicator trace
    traces = [{
        "type": "indicator",
        "mode": "gauge+number+delta",
        "value": combined * 100,
        "number": {
            "suffix": "",
            "font": {"size": 32, "color": signal_color, "family": "Inter"},
        },
        "title": {
            "text": f"<b>{ticker}</b> Flow Regime<br><span style='font-size:14px;color:{signal_color}'>{signal}</span>",
            "font": {"size": 16, "family": "Inter"},
        },
        "gauge": {
            "axis": {
                "range": [-100, 100],
                "tickwidth": 1,
                "tickcolor": "#94a3b8",
                "tickvals": [-100, -50, 0, 50, 100],
                "ticktext": ["Strong Sell", "Sell", "Neutral", "Buy", "Strong Buy"],
            },
            "bar": {"color": signal_color, "thickness": 0.3},
            "bgcolor": "#f1f5f9",
            "borderwidth": 0,
            "steps": [
                {"range": [-100, -30], "color": "#fecaca"},
                {"range": [-30, 30], "color": "#e2e8f0"},
                {"range": [30, 100], "color": "#bbf7d0"},
            ],
            "threshold": {
                "line": {"color": COLORS["spot"], "width": 3},
                "thickness": 0.8,
                "value": combined * 100,
            },
        },
    }]
    
    layout = {
        "paper_bgcolor": "white",
        "font": {"family": "Inter, system-ui"},
        "height": 280,
        "margin": {"t": 80, "r": 30, "b": 30, "l": 30},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "gauge",
        "label": "Flow Regime",
    }
