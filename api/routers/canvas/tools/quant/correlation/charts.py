"""Correlation Matrix Chart Builders for Canvas.

Builds Plotly chart configurations for correlation heatmap and eigenvalue analysis.
"""

from typing import Dict, List, Any, Optional
import numpy as np


def build_correlation_heatmap(
    tickers: List[str],
    correlation_matrix: List[List[float]],
    method: str = "pearson",
) -> Optional[Dict[str, Any]]:
    """Build correlation matrix heatmap.
    
    Args:
        tickers: List of ticker symbols
        correlation_matrix: 2D array of correlation values
        method: Correlation method used
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not tickers or not correlation_matrix:
        return None
    
    n = len(tickers)
    if len(correlation_matrix) != n:
        return None
    
    # Create text annotations for heatmap
    text = [[f"{correlation_matrix[i][j]:.2f}" for j in range(n)] for i in range(n)]
    
    # Colorscale: blue (negative) -> white (0) -> red (positive)
    colorscale = [
        [0.0, '#2563eb'],   # Blue (negative)
        [0.5, '#ffffff'],   # White (zero)
        [1.0, '#dc2626'],   # Red (positive)
    ]
    
    return {
        "plotly": {
            "data": [{
                "type": "heatmap",
                "z": correlation_matrix,
                "x": tickers,
                "y": tickers,
                "colorscale": colorscale,
                "zmin": -1,
                "zmax": 1,
                "text": text,
                "texttemplate": "%{text}",
                "textfont": {"size": 10},
                "hovertemplate": "<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.3f}<extra></extra>",
                "colorbar": {
                    "title": {"text": "Correlation", "font": {"size": 12}},
                    "thickness": 15,
                    "len": 0.8,
                },
            }],
            "layout": {
                "title": {"text": f"Correlation Matrix ({method.capitalize()})", "font": {"size": 14}},
                "xaxis": {"tickangle": -45, "tickfont": {"size": 10}},
                "yaxis": {"tickfont": {"size": 10}},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "margin": {"t": 50, "r": 80, "b": 80, "l": 80},
            }
        },
        "type": "correlation_heatmap",
        "label": "Correlation Heatmap",
    }


def build_eigenvalue_chart(
    eigenvalues: List[float],
    tickers: List[str],
) -> Optional[Dict[str, Any]]:
    """Build eigenvalue bar chart for matrix diagnostics.
    
    Args:
        eigenvalues: List of eigenvalues in descending order
        tickers: List of ticker symbols (for count)
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not eigenvalues:
        return None
    
    n = len(eigenvalues)
    x_labels = [f"PC{i+1}" for i in range(n)]
    
    # Calculate explained variance ratio
    total = sum(eigenvalues)
    explained_var = [ev / total * 100 for ev in eigenvalues] if total > 0 else eigenvalues
    cumulative = []
    running = 0
    for ev in explained_var:
        running += ev
        cumulative.append(running)
    
    return {
        "plotly": {
            "data": [
                {
                    "type": "bar",
                    "x": x_labels,
                    "y": explained_var,
                    "name": "Individual",
                    "marker": {"color": "#3b82f6"},
                    "hovertemplate": "<b>%{x}</b><br>Variance: %{y:.1f}%<extra></extra>",
                },
                {
                    "type": "scatter",
                    "x": x_labels,
                    "y": cumulative,
                    "name": "Cumulative",
                    "mode": "lines+markers",
                    "line": {"color": "#ef4444", "width": 2},
                    "marker": {"size": 6},
                    "yaxis": "y2",
                    "hovertemplate": "<b>%{x}</b><br>Cumulative: %{y:.1f}%<extra></extra>",
                },
            ],
            "layout": {
                "title": {"text": "Eigenvalue Analysis (Variance Explained)", "font": {"size": 14}},
                "xaxis": {"title": "Principal Component", "tickfont": {"size": 10}},
                "yaxis": {"title": "Explained Variance (%)", "gridcolor": "#e5e7eb"},
                "yaxis2": {
                    "title": "Cumulative (%)",
                    "overlaying": "y",
                    "side": "right",
                    "range": [0, 105],
                },
                "legend": {"x": 0.7, "y": 0.95},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "margin": {"t": 50, "r": 60, "b": 50, "l": 60},
                "shapes": [
                    # 80% threshold line
                    {"type": "line", "x0": -0.5, "x1": n - 0.5, "y0": 80, "y1": 80, 
                     "yref": "y2", "line": {"color": "#22c55e", "width": 1, "dash": "dash"}},
                ],
                "annotations": [
                    {"x": n - 1, "y": 80, "yref": "y2", "text": "80%", "showarrow": False,
                     "font": {"color": "#22c55e", "size": 10}},
                ],
            }
        },
        "type": "eigenvalues",
        "label": "Eigenvalues",
    }


def build_cluster_chart(
    tickers: List[str],
    clusters: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build cluster visualization chart.
    
    Args:
        tickers: List of ticker symbols
        clusters: Hierarchical clustering results
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not clusters or 'assignments' not in clusters:
        return None
    
    assignments = clusters.get('assignments', {})
    cluster_count = clusters.get('cluster_count', 0)
    
    if not assignments:
        return None
    
    # Group tickers by cluster
    cluster_groups = {}
    for ticker, cluster_id in assignments.items():
        if cluster_id not in cluster_groups:
            cluster_groups[cluster_id] = []
        cluster_groups[cluster_id].append(ticker)
    
    # Build bar chart showing cluster membership
    colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16']
    
    data = []
    for cluster_id in sorted(cluster_groups.keys()):
        members = cluster_groups[cluster_id]
        color = colors[int(cluster_id) % len(colors)]
        data.append({
            "type": "bar",
            "x": members,
            "y": [1] * len(members),
            "name": f"Cluster {cluster_id}",
            "marker": {"color": color},
            "hovertemplate": "<b>%{x}</b><br>Cluster %{data.name}<extra></extra>",
        })
    
    return {
        "plotly": {
            "data": data,
            "layout": {
                "title": {"text": f"Cluster Assignments ({cluster_count} clusters)", "font": {"size": 14}},
                "xaxis": {"title": "Ticker", "tickangle": -45},
                "yaxis": {"visible": False},
                "barmode": "stack",
                "showlegend": True,
                "legend": {"orientation": "h", "y": -0.2},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "margin": {"t": 50, "r": 30, "b": 80, "l": 30},
            }
        },
        "type": "clusters",
        "label": "Clusters",
    }
















