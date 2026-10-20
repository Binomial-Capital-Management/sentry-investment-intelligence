"""
Canvas charts for Instanton Rare Event Analysis.

Visualizations:
- Instanton path with uncertainty cone
- Severity distribution (PDF + CDF)
- Scenario probability comparison
- Action surface heatmap
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Light theme colors (matching other Canvas tools)
COLORS = {
    "primary": "#3b82f6",     # Blue
    "secondary": "#22c55e",   # Green
    "danger": "#ef4444",      # Red
    "warning": "#f59e0b",     # Amber
    "neutral": "#6b7280",     # Gray
    "grid": "#e5e7eb",        # Light gray grid
}


def build_instanton_path_chart(
    instanton_data: Dict[str, Any],
    current_price: float,
    crash_pct: float,
    horizon_days: int,
) -> Dict[str, Any]:
    """
    Build instanton path visualization showing the most likely crash trajectory.
    """
    times = instanton_data.get("times", [])
    prices = instanton_data.get("prices", [])
    
    if not times or not prices:
        return None
    
    traces = []
    
    # Fluctuation band (uncertainty cone)
    if "fluctuation_band" in instanton_data:
        band = instanton_data["fluctuation_band"]
        upper = band.get("upper", prices)
        lower = band.get("lower", prices)
        
        # Upper boundary
        traces.append({
            "type": "scatter",
            "x": times,
            "y": upper,
            "mode": "lines",
            "line": {"width": 1, "color": "rgba(59, 130, 246, 0.3)"},
            "showlegend": False,
            "hoverinfo": "skip",
        })
        
        # Lower boundary with fill
        traces.append({
            "type": "scatter",
            "x": times,
            "y": lower,
            "mode": "lines",
            "line": {"width": 1, "color": "rgba(59, 130, 246, 0.3)"},
            "fill": "tonexty",
            "fillcolor": "rgba(59, 130, 246, 0.1)",
            "name": "±1σ Uncertainty",
        })
    
    # Main instanton path
    traces.append({
        "type": "scatter",
        "x": times,
        "y": prices,
        "mode": "lines",
        "name": "Instanton Path",
        "line": {"color": COLORS["danger"], "width": 3},
    })
    
    # Start marker
    traces.append({
        "type": "scatter",
        "x": [0],
        "y": [current_price],
        "mode": "markers",
        "name": "Current Price",
        "marker": {"color": COLORS["secondary"], "size": 12, "symbol": "circle"},
    })
    
    # End marker
    crash_price = current_price * (1 + crash_pct / 100)
    traces.append({
        "type": "scatter",
        "x": [horizon_days],
        "y": [crash_price],
        "mode": "markers",
        "name": f"Crash Target ({crash_pct:.0f}%)",
        "marker": {"color": COLORS["danger"], "size": 12, "symbol": "x"},
    })
    
    layout = {
        "title": {"text": f"Most Likely Path to {crash_pct:.0f}% Crash", "font": {"size": 14}},
        "xaxis": {
            "title": "Days",
            "gridcolor": COLORS["grid"],
        },
        "yaxis": {
            "title": "Price ($)",
            "gridcolor": COLORS["grid"],
            "tickformat": "$,.0f",
        },
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "showlegend": True,
        "legend": {"orientation": "h", "y": 1.12},
        "shapes": [
            {
                "type": "line",
                "x0": 0, "x1": horizon_days,
                "y0": crash_price, "y1": crash_price,
                "line": {"color": COLORS["warning"], "width": 2, "dash": "dash"},
            }
        ],
        "annotations": [
            {
                "x": horizon_days * 0.98,
                "y": crash_price,
                "text": f"Crash: ${crash_price:,.0f}",
                "showarrow": False,
                "xanchor": "right",
                "yanchor": "bottom",
                "font": {"size": 10, "color": COLORS["warning"]},
            }
        ],
        "height": 400,
        "margin": {"t": 60, "r": 30, "b": 50, "l": 60},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "line",
        "label": "Crash Path (Instanton)",
    }


def build_severity_distribution_chart(
    severity_data: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Build severity distribution chart showing crash probability across levels.
    """
    # Extract scenario data
    if not scenarios:
        return None
    
    # Sort scenarios by crash level
    sorted_scenarios = sorted(scenarios, key=lambda s: s.get("crash_pct", 0), reverse=True)
    
    crash_levels = [abs(s.get("crash_pct", 0)) for s in sorted_scenarios]
    probs = [s.get("probability", 0) * 100 for s in sorted_scenarios]
    names = [s.get("name", f"{s.get('crash_pct', 0):.0f}%") for s in sorted_scenarios]
    
    traces = [{
        "type": "bar",
        "x": names,
        "y": probs,
        "marker": {
            "color": [COLORS["danger"] if p > 1 else COLORS["warning"] if p > 0.1 else COLORS["primary"] for p in probs],
        },
        "text": [f"{p:.2f}%" for p in probs],
        "textposition": "outside",
        "hovertemplate": "<b>%{x}</b><br>Probability: %{y:.3f}%<extra></extra>",
    }]
    
    layout = {
        "title": {"text": "Crash Probability by Severity", "font": {"size": 14}},
        "xaxis": {
            "title": "Scenario",
            "gridcolor": COLORS["grid"],
        },
        "yaxis": {
            "title": "Probability (%)",
            "gridcolor": COLORS["grid"],
            "type": "log" if max(probs) / (min(probs) + 0.0001) > 100 else "linear",
        },
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "height": 350,
        "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "bar",
        "label": "Severity Distribution",
    }


def build_scenario_comparison_chart(
    scenarios: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build bar chart comparing fat-tail vs Gaussian crash probabilities.
    """
    names = [s.get("name", f"{s.get('crash_pct', 0):.0f}%") for s in scenarios]
    probs = [s.get("probability", 0) * 100 for s in scenarios]
    gaussian = [s.get("gaussian_estimate", s.get("probability", 0)) * 100 for s in scenarios]
    tail_mults = [s.get("tail_multiplier", 1.0) for s in scenarios]
    
    traces = [
        {
            "type": "bar",
            "x": names,
            "y": gaussian,
            "name": "Gaussian",
            "marker": {"color": COLORS["neutral"], "opacity": 0.6},
        },
        {
            "type": "bar",
            "x": names,
            "y": probs,
            "name": "Fat-Tail",
            "marker": {"color": COLORS["danger"]},
            "text": [f"{m:.1f}x" if m > 1.2 else "" for m in tail_mults],
            "textposition": "outside",
            "textfont": {"color": COLORS["warning"], "size": 10},
        },
    ]
    
    layout = {
        "title": {"text": "Fat-Tail vs Gaussian Estimates", "font": {"size": 14}},
        "xaxis": {
            "title": "Scenario",
            "gridcolor": COLORS["grid"],
        },
        "yaxis": {
            "title": "Probability (%)",
            "gridcolor": COLORS["grid"],
        },
        "barmode": "group",
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "showlegend": True,
        "legend": {"orientation": "h", "y": 1.12},
        "height": 350,
        "margin": {"t": 60, "r": 30, "b": 50, "l": 60},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "bar",
        "label": "Tail Risk Comparison",
    }


def build_action_surface_chart(
    current_price: float,
    sigma: float,
    horizon_days: int,
    mu: float = 0.0,
) -> Dict[str, Any]:
    """
    Build heatmap of crash probability vs horizon and severity.
    """
    horizons = np.linspace(5, max(60, horizon_days * 2), 20).astype(int)
    crashes = np.linspace(-40, -5, 20)
    
    # Compute probability matrix
    prob_matrix = np.zeros((len(crashes), len(horizons)))
    
    for i, crash_pct in enumerate(crashes):
        for j, horizon in enumerate(horizons):
            log_return = np.log(1 + crash_pct / 100)
            daily_return = log_return / horizon
            
            deviation = daily_return - mu
            action = horizon * deviation**2 / (2 * sigma**2)
            prob_matrix[i, j] = np.exp(-action)
    
    # Clip for visualization
    prob_matrix = np.clip(prob_matrix, 1e-8, 1)
    log_probs = np.log10(prob_matrix)
    
    traces = [{
        "type": "heatmap",
        "x": horizons.tolist(),
        "y": crashes.tolist(),
        "z": log_probs.tolist(),
        "colorscale": "RdYlGn_r",
        "colorbar": {
            "title": {"text": "Probability"},
            "tickvals": [-6, -4, -2, 0],
            "ticktext": ["0.0001%", "0.01%", "1%", "100%"],
        },
        "hovertemplate": "Horizon: %{x}d<br>Crash: %{y:.0f}%<br>Prob: %{customdata:.2e}<extra></extra>",
        "customdata": prob_matrix.tolist(),
    }]
    
    layout = {
        "title": {"text": "Crash Probability Landscape", "font": {"size": 14}},
        "xaxis": {
            "title": "Horizon (Days)",
        },
        "yaxis": {
            "title": "Crash Level (%)",
        },
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "shapes": [
            {
                "type": "line",
                "x0": horizon_days, "x1": horizon_days,
                "y0": -40, "y1": -5,
                "line": {"color": "#1f2937", "width": 2, "dash": "dash"},
            }
        ],
        "annotations": [
            {
                "x": horizon_days,
                "y": -4,
                "text": f"Current: {horizon_days}d",
                "showarrow": False,
                "font": {"size": 10, "color": "#1f2937"},
            }
        ],
        "height": 400,
        "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "heatmap",
        "label": "Probability Landscape",
    }
