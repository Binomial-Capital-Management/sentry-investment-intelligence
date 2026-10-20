"""Monte Carlo Chart Builders for Canvas.

Builds Plotly chart configurations for price paths and distribution histograms.
"""

from typing import Dict, List, Any, Optional
import numpy as np

# Color palette for spaghetti paths
PATH_COLORS = [
    '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e', '#10b981', 
    '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7',
    '#d946ef', '#ec4899', '#f43f5e', '#fb7185', '#fda4af', '#fecdd3',
    '#c084fc', '#a78bfa', '#818cf8', '#60a5fa', '#38bdf8', '#22d3ee',
    '#2dd4bf', '#34d399', '#4ade80', '#a3e635', '#facc15', '#fbbf24',
]


def build_price_paths_chart(
    representative_paths: List[List[float]],
    time_horizon: int = 252,
) -> Optional[Dict[str, Any]]:
    """Build spaghetti-style price paths chart.
    
    Args:
        representative_paths: List of simulation paths (each path is list of values)
        time_horizon: Number of trading days
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not representative_paths:
        return None
    
    x_axis = list(range(len(representative_paths[0])))
    path_traces = []
    
    for i, path in enumerate(representative_paths):
        # Normalize to cumulative return from initial value
        if path[0] != 0:
            normalized = [(v / path[0] - 1) for v in path]
        else:
            normalized = path
            
        color = PATH_COLORS[i % len(PATH_COLORS)]
        path_traces.append({
            "type": "scatter",
            "x": x_axis,
            "y": normalized,
            "mode": "lines",
            "line": {"color": color, "width": 1},
            "showlegend": False,
            "hoverinfo": "skip",
        })
    
    return {
        "plotly": {
            "data": path_traces,
            "layout": {
                "title": {
                    "text": f"Monte Carlo Simulation ({len(representative_paths)} Paths)", 
                    "font": {"size": 14}
                },
                "xaxis": {
                    "title": "Trading Days", 
                    "gridcolor": "#e5e7eb", 
                    "zeroline": False
                },
                "yaxis": {
                    "title": "Cumulative Return", 
                    "gridcolor": "#e5e7eb", 
                    "tickformat": ".0%", 
                    "zeroline": True, 
                    "zerolinecolor": "#9ca3af"
                },
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
            }
        },
        "type": "price_paths",
        "label": "Price Paths",
    }


def build_histogram_chart(
    terminal_returns: List[float],
    bin_size: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """Build distribution histogram with percentile lines.
    
    Args:
        terminal_returns: List of terminal returns as decimals (e.g., 0.15 = 15%)
        bin_size: Width of histogram bins in percentage points
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not terminal_returns:
        return None
    
    # Convert to percentage
    rets_pct = [r * 100 for r in terminal_returns]
    
    # Calculate percentiles for vertical lines
    p5 = float(np.percentile(rets_pct, 5))
    p15 = float(np.percentile(rets_pct, 15))
    p30 = float(np.percentile(rets_pct, 30))
    p50 = float(np.percentile(rets_pct, 50))
    
    return {
        "plotly": {
            "data": [{
                "type": "histogram", 
                "x": rets_pct, 
                "xbins": {"size": bin_size},
                "marker": {
                    "color": "#3b82f6", 
                    "line": {"color": "#1d4ed8", "width": 0.5}
                },
                "name": "Terminal Returns"
            }],
            "layout": {
                "title": {
                    "text": f"Monte Carlo Distribution ({len(terminal_returns):,} Trials)", 
                    "font": {"size": 14}
                },
                "xaxis": {
                    "title": "Terminal Return (%)", 
                    "gridcolor": "#e5e7eb", 
                    "dtick": 10
                },
                "yaxis": {
                    "title": "Occurrences", 
                    "gridcolor": "#e5e7eb"
                },
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "bargap": 0.05,
                "shapes": [
                    _percentile_line(p5),
                    _percentile_line(p15),
                    _percentile_line(p30),
                    _percentile_line(p50),
                ],
                "annotations": [
                    _percentile_annotation(p5, "95%", "#dc2626"),
                    _percentile_annotation(p15, "85%", "#ea580c"),
                    _percentile_annotation(p30, "70%", "#ca8a04"),
                    _percentile_annotation(p50, "50%", "#16a34a"),
                ],
                "margin": {"t": 60, "r": 30, "b": 50, "l": 60},
            }
        },
        "type": "histogram",
        "label": "Distribution",
    }


def _percentile_line(x_val: float) -> Dict[str, Any]:
    """Create a vertical dashed line shape for percentile marker."""
    return {
        "type": "line", 
        "x0": x_val, 
        "x1": x_val, 
        "y0": 0, 
        "y1": 1, 
        "yref": "paper", 
        "line": {"color": "#6b7280", "width": 1.5, "dash": "dash"}
    }


def _percentile_annotation(x_val: float, label: str, color: str) -> Dict[str, Any]:
    """Create annotation for percentile label at top of chart."""
    return {
        "x": x_val, 
        "y": 1.02, 
        "yref": "paper", 
        "text": label, 
        "showarrow": False, 
        "font": {"color": color, "size": 11, "family": "Arial Black"}
    }
