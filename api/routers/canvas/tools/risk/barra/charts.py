"""Barra Factor Analysis Chart Builders for Canvas.

Builds Plotly chart configurations for factor exposures heatmap and risk decomposition.
"""

from typing import Dict, List, Any, Optional
import numpy as np


# Color scale for factor heatmap (diverging: red-white-blue)
HEATMAP_COLORSCALE = [
    [0.0, '#dc2626'],    # Strong negative (red)
    [0.25, '#f87171'],   # Moderate negative
    [0.5, '#ffffff'],    # Neutral (white)
    [0.75, '#60a5fa'],   # Moderate positive
    [1.0, '#2563eb'],    # Strong positive (blue)
]

# Colors for risk decomposition pie
PIE_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#06b6d4']


def build_factor_heatmap(
    factor_exposures: Dict[str, Dict[str, float]],
    tickers: List[str],
) -> Optional[Dict[str, Any]]:
    """Build factor exposure heatmap.
    
    Args:
        factor_exposures: Dict mapping ticker -> {factor: beta}
        tickers: List of ticker symbols
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not factor_exposures or not tickers:
        return None
    
    # Get factor names from first ticker
    first_ticker = next((t for t in tickers if t in factor_exposures), None)
    if not first_ticker:
        return None
    
    factor_names = list(factor_exposures[first_ticker].keys())
    if not factor_names:
        return None
    
    # Build exposure matrix (tickers x factors)
    z_values = []
    text_values = []
    y_labels = []
    
    for ticker in tickers:
        if ticker in factor_exposures:
            row = [factor_exposures[ticker].get(f, 0.0) for f in factor_names]
            z_values.append(row)
            text_values.append([f"{v:.2f}" for v in row])
            y_labels.append(ticker)
    
    if not z_values:
        return None
    
    # Determine scale based on data
    flat_values = [v for row in z_values for v in row]
    max_abs = max(abs(min(flat_values)), abs(max(flat_values)), 0.5)
    vmax = min(2.0, max(1.0, np.ceil(max_abs * 10) / 10))
    
    return {
        "plotly": {
            "data": [{
                "type": "heatmap",
                "z": z_values,
                "x": factor_names,
                "y": y_labels,
                "colorscale": HEATMAP_COLORSCALE,
                "zmid": 0,
                "zmin": -vmax,
                "zmax": vmax,
                "text": text_values,
                "texttemplate": "%{text}",
                "textfont": {"size": 11},
                "hovertemplate": "Asset: %{y}<br>Factor: %{x}<br>Beta: %{z:.3f}<extra></extra>",
                "colorbar": {
                    "title": {"text": "Factor Beta", "side": "right"},
                    "thickness": 15,
                    "len": 0.9,
                }
            }],
            "layout": {
                "title": {
                    "text": f"Factor Exposures ({len(y_labels)} Assets × {len(factor_names)} Factors)",
                    "font": {"size": 14}
                },
                "xaxis": {
                    "title": "Market Factors",
                    "tickangle": 45,
                    "side": "bottom",
                    "showgrid": False,
                },
                "yaxis": {
                    "title": "Assets",
                    "showgrid": False,
                    "autorange": "reversed",  # First ticker at top
                },
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "margin": {"t": 50, "r": 80, "b": 100, "l": 80},
            }
        },
        "type": "factor_heatmap",
        "label": "Factor Exposures",
    }


def build_risk_decomposition(
    risk_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build risk decomposition pie chart.
    
    Args:
        risk_data: Dict containing factor_contributions and risk_decomposition
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not risk_data:
        return None
    
    factor_contributions = risk_data.get('factor_contributions', {})
    risk_decomp = risk_data.get('risk_decomposition', {})
    total_risk = risk_data.get('total_risk', 0)
    
    if not factor_contributions and not risk_decomp:
        return None
    
    # Build pie chart data
    labels = []
    values = []
    colors = []
    
    # Add factor contributions
    for i, (factor, contrib) in enumerate(factor_contributions.items()):
        if contrib > 0.01:  # Only show factors > 1%
            labels.append(factor)
            values.append(contrib * 100)
            colors.append(PIE_COLORS[i % len(PIE_COLORS)])
    
    # Add idiosyncratic if available
    idio_pct = risk_decomp.get('idiosyncratic', 0)
    if idio_pct > 0.01:
        labels.append("Idiosyncratic")
        values.append(idio_pct * 100)
        colors.append('#9ca3af')  # Gray for idiosyncratic
    
    if not values:
        return None
    
    return {
        "plotly": {
            "data": [{
                "type": "pie",
                "labels": labels,
                "values": values,
                "marker": {"colors": colors},
                "textinfo": "label+percent",
                "textposition": "outside",
                "textfont": {"size": 11},
                "hovertemplate": "%{label}<br>%{value:.1f}% of variance<extra></extra>",
                "hole": 0.4,  # Donut style
            }],
            "layout": {
                "title": {
                    "text": f"Portfolio Risk Decomposition (Total: {total_risk*100:.1f}%)",
                    "font": {"size": 14}
                },
                "showlegend": True,
                "legend": {
                    "orientation": "h",
                    "yanchor": "bottom",
                    "y": -0.2,
                    "xanchor": "center",
                    "x": 0.5,
                },
                "annotations": [{
                    "text": f"{total_risk*100:.1f}%<br>Total",
                    "x": 0.5,
                    "y": 0.5,
                    "font": {"size": 16, "color": "#374151"},
                    "showarrow": False,
                }],
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "margin": {"t": 50, "r": 30, "b": 80, "l": 30},
            }
        },
        "type": "risk_decomposition",
        "label": "Risk Breakdown",
    }


def build_r_squared_bar(
    r_squared: Dict[str, float],
    tickers: List[str],
) -> Optional[Dict[str, Any]]:
    """Build R-squared bar chart showing model fit per asset.
    
    Args:
        r_squared: Dict mapping ticker -> R² value
        tickers: List of ticker symbols
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not r_squared or not tickers:
        return None
    
    # Filter to tickers with R² values
    labels = []
    values = []
    colors = []
    
    for ticker in tickers:
        if ticker in r_squared:
            r2 = r_squared[ticker]
            labels.append(ticker)
            values.append(r2 * 100)
            # Color based on fit quality
            if r2 >= 0.7:
                colors.append('#10b981')  # Green - good fit
            elif r2 >= 0.4:
                colors.append('#f59e0b')  # Yellow - moderate
            else:
                colors.append('#ef4444')  # Red - poor fit
    
    if not values:
        return None
    
    mean_r2 = sum(values) / len(values)
    
    return {
        "plotly": {
            "data": [{
                "type": "bar",
                "x": labels,
                "y": values,
                "marker": {"color": colors},
                "text": [f"{v:.0f}%" for v in values],
                "textposition": "outside",
                "hovertemplate": "%{x}<br>R²: %{y:.1f}%<extra></extra>",
            }],
            "layout": {
                "title": {
                    "text": f"Model Fit by Asset (Mean R² = {mean_r2:.0f}%)",
                    "font": {"size": 14}
                },
                "xaxis": {
                    "title": "Asset",
                    "tickangle": 45,
                },
                "yaxis": {
                    "title": "R² (%)",
                    "range": [0, 100],
                    "gridcolor": "#e5e7eb",
                },
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "margin": {"t": 50, "r": 30, "b": 80, "l": 60},
                "shapes": [{
                    "type": "line",
                    "x0": -0.5,
                    "x1": len(labels) - 0.5,
                    "y0": mean_r2,
                    "y1": mean_r2,
                    "line": {"color": "#6b7280", "width": 2, "dash": "dash"},
                }],
            }
        },
        "type": "r_squared",
        "label": "Model Fit",
    }

















