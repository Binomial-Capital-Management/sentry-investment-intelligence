"""
Chart builders for ARIMAX Macro Forecast.

Builds forecast chart with confidence intervals and indicator correlations.
"""

import math
from typing import Any, Dict, List, Optional

COLORS = {
    "blue": "#1E3A5F",
    "green": "#22c55e",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "gray": "#6b7280",
    "teal": "#3D8B7A",
    "orange": "#E85D04",
    "purple": "#8b5cf6",
}


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, replacing NaN/Inf with default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def build_forecast_chart(
    target_name: str,
    historical_dates: List[str],
    historical_values: List[float],
    fitted_values: List[float],
    forecast_dates: List[str],
    forecast_values: List[float],
    conf_lower: List[float],
    conf_upper: List[float],
    selected_indicators: List[Dict[str, Any]],
    confidence_level: float = 0.95
) -> Optional[Dict[str, Any]]:
    """Build forecast chart with price history, forecast, confidence interval, and indicator correlations."""
    if not historical_dates or not historical_values:
        return None
    
    # Subsample historical data if too many points
    max_points = 200
    if len(historical_dates) > max_points:
        stride = len(historical_dates) // max_points
        plot_dates = historical_dates[::stride]
        plot_values = [historical_values[i] for i in range(0, len(historical_values), stride)]
        plot_fitted = [fitted_values[i] for i in range(0, len(fitted_values), stride)] if fitted_values else []
    else:
        plot_dates = historical_dates
        plot_values = historical_values
        plot_fitted = fitted_values if fitted_values else []
    
    # Key metrics
    current_value = _safe_float(historical_values[-1] if historical_values else 0)
    forecast_end = _safe_float(forecast_values[-1] if forecast_values else 0)
    pct_change = ((forecast_end / current_value) - 1) * 100 if current_value != 0 else 0
    conf_pct = int(confidence_level * 100)
    
    traces = []
    
    # Historical prices
    traces.append({
        "x": plot_dates,
        "y": plot_values,
        "mode": "lines",
        "name": "Historical",
        "line": {"color": COLORS["blue"], "width": 2},
        "hovertemplate": "%{x}<br>$%{y:,.2f}<extra></extra>",
    })
    
    # Model fit (subtle)
    if plot_fitted and len(plot_fitted) == len(plot_dates):
        traces.append({
            "x": plot_dates,
            "y": plot_fitted,
            "mode": "lines",
            "name": "Model Fit",
            "line": {"color": COLORS["teal"], "width": 1.2, "dash": "dash"},
            "opacity": 0.6,
            "hovertemplate": "%{x}<br>Fit: $%{y:,.2f}<extra></extra>",
        })
    
    # Confidence band (filled area)
    if conf_upper and conf_lower and len(conf_upper) == len(forecast_dates) and len(conf_lower) == len(forecast_dates):
        traces.append({
            "x": forecast_dates + forecast_dates[::-1],
            "y": list(conf_upper) + list(conf_lower)[::-1],
            "fill": "toself",
            "fillcolor": "rgba(232, 93, 4, 0.15)",
            "line": {"color": "rgba(0,0,0,0)"},
            "name": f"{conf_pct}% CI",
            "hoverinfo": "skip",
            "showlegend": True,
        })
    
    # Forecast line
    traces.append({
        "x": forecast_dates,
        "y": forecast_values,
        "mode": "lines",
        "name": "Forecast",
        "line": {"color": COLORS["orange"], "width": 2.5},
        "hovertemplate": "%{x}<br>Forecast: $%{y:,.2f}<extra></extra>",
    })
    
    # Annotations for endpoint
    annotations = []
    if forecast_dates and forecast_values:
        direction = "▲" if pct_change > 0 else "▼"
        color = "#22763F" if pct_change > 0 else "#B91C1C"
        annotations.append({
            "x": forecast_dates[-1],
            "y": forecast_end,
            "text": f"<b>{direction} {abs(pct_change):.1f}%</b>",
            "showarrow": True,
            "arrowhead": 2,
            "arrowcolor": color,
            "ax": 40,
            "ay": -20,
            "font": {"size": 11, "color": color},
            "bgcolor": "white",
            "bordercolor": color,
            "borderwidth": 1,
        })
    
    # Divider line between historical and forecast
    shapes = []
    if plot_dates:
        shapes.append({
            "type": "line",
            "x0": plot_dates[-1],
            "y0": 0,
            "x1": plot_dates[-1],
            "y1": 1,
            "yref": "paper",
            "line": {"color": COLORS["gray"], "width": 1, "dash": "dash"},
        })
    
    layout = {
        "title": {"text": f"<b>{target_name}</b> — ARIMAX Forecast", "x": 0.5, "font": {"size": 14}},
        "xaxis": {"title": "Date"},
        "yaxis": {"title": "Price", "tickprefix": "$"},
        "legend": {"orientation": "h", "y": 1.02, "x": 0.5, "xanchor": "center"},
        "height": 400,
        "margin": {"t": 80, "b": 60, "l": 60, "r": 30},
        "template": "plotly_white",
        "hovermode": "x unified",
        "annotations": annotations,
        "shapes": shapes,
    }
    
    return {
        "plotly": {"data": traces, "layout": layout},
        "type": "line",
        "label": "Forecast",
    }


def build_correlation_chart(selected_indicators: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build bar chart of indicator correlations."""
    if not selected_indicators:
        return None
    
    # Extract indicator names and correlations
    names = []
    corrs = []
    
    for ind in selected_indicators[:8]:  # Top 8
        series = ind.get("series", "")
        corr = _safe_float(ind.get("correlation", 0))
        lag = ind.get("lag", 0)
        
        # Truncate long names
        short_name = series[:20] + "..." if len(series) > 20 else series
        if lag > 0:
            short_name += f" (lag {lag})"
        
        names.append(short_name)
        corrs.append(corr)
    
    if not names:
        return None
    
    colors = [COLORS["green"] if c > 0 else COLORS["red"] for c in corrs]
    
    return {
        "plotly": {
            "data": [{
                "x": names,
                "y": corrs,
                "type": "bar",
                "marker": {"color": colors},
                "text": [f"{c:+.2f}" for c in corrs],
                "textposition": "outside",
                "textfont": {"size": 10},
                "hovertemplate": "%{x}<br>ρ = %{y:+.3f}<extra></extra>",
            }],
            "layout": {
                "title": {"text": "<b>Top Correlated Indicators</b>", "x": 0.5, "font": {"size": 14}},
                "xaxis": {"title": "", "tickangle": -30},
                "yaxis": {"title": "Correlation", "range": [-1.1, 1.1], "zeroline": True, "zerolinewidth": 1},
                "height": 280,
                "margin": {"t": 50, "b": 80, "l": 60, "r": 30},
                "template": "plotly_white",
            },
        },
        "type": "bar",
        "label": "Correlations",
    }
