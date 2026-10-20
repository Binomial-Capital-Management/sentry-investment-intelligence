"""PCA Analysis Chart Builders for Canvas.

Builds Plotly chart configurations for scree plot, loadings heatmap, and eigen-portfolios.
"""

from typing import Dict, List, Any, Optional
import numpy as np


def build_scree_chart(
    explained_variance: List[float],
    cumulative_variance: List[float],
) -> Optional[Dict[str, Any]]:
    """Build scree plot showing explained variance by component.
    
    Args:
        explained_variance: List of variance ratios per component
        cumulative_variance: List of cumulative variance ratios
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not explained_variance:
        return None
    
    n = len(explained_variance)
    x_labels = [f"PC{i+1}" for i in range(n)]
    
    # Convert to percentages
    var_pct = [v * 100 for v in explained_variance]
    cum_pct = [v * 100 for v in cumulative_variance]
    
    return {
        "plotly": {
            "data": [
                {
                    "type": "bar",
                    "x": x_labels,
                    "y": var_pct,
                    "name": "Individual",
                    "marker": {"color": "#3b82f6"},
                    "hovertemplate": "<b>%{x}</b><br>Variance: %{y:.1f}%<extra></extra>",
                },
                {
                    "type": "scatter",
                    "x": x_labels,
                    "y": cum_pct,
                    "name": "Cumulative",
                    "mode": "lines+markers",
                    "line": {"color": "#ef4444", "width": 2},
                    "marker": {"size": 6},
                    "yaxis": "y2",
                    "hovertemplate": "<b>%{x}</b><br>Cumulative: %{y:.1f}%<extra></extra>",
                },
            ],
            "layout": {
                "title": {"text": "PCA Scree Plot - Explained Variance", "font": {"size": 14}},
                "xaxis": {"title": "Principal Component", "tickfont": {"size": 10}},
                "yaxis": {"title": "Explained Variance (%)", "gridcolor": "#e5e7eb"},
                "yaxis2": {
                    "title": "Cumulative (%)",
                    "overlaying": "y",
                    "side": "right",
                    "range": [0, 105],
                },
                "legend": {"x": 0.7, "y": 0.3},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "margin": {"t": 50, "r": 60, "b": 50, "l": 60},
                "shapes": [
                    {"type": "line", "x0": -0.5, "x1": n - 0.5, "y0": 80, "y1": 80, 
                     "yref": "y2", "line": {"color": "#22c55e", "width": 1, "dash": "dash"}},
                ],
            }
        },
        "type": "scree_plot",
        "label": "Scree Plot",
    }


def build_loadings_heatmap(
    tickers: List[str],
    loadings_matrix: List[List[float]],
) -> Optional[Dict[str, Any]]:
    """Build loadings heatmap showing stock contributions to PCs.
    
    Args:
        tickers: List of ticker symbols
        loadings_matrix: 2D array of loadings (n_components x n_tickers)
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not tickers or not loadings_matrix:
        return None
    
    n_components = len(loadings_matrix)
    n_tickers = len(tickers)
    
    # Transpose for heatmap (tickers on Y, PCs on X)
    loadings_t = np.array(loadings_matrix).T.tolist()
    
    # Create text annotations
    text = [[f"{loadings_t[i][j]:.2f}" for j in range(n_components)] for i in range(n_tickers)]
    
    pc_labels = [f"PC{i+1}" for i in range(n_components)]
    
    return {
        "plotly": {
            "data": [{
                "type": "heatmap",
                "z": loadings_t,
                "x": pc_labels,
                "y": tickers,
                "colorscale": "RdBu",
                "zmid": 0,
                "text": text,
                "texttemplate": "%{text}",
                "textfont": {"size": 9},
                "colorbar": {
                    "title": {"text": "Loading", "font": {"size": 12}},
                    "thickness": 15,
                    "len": 0.7,
                },
                "hovertemplate": "<b>%{y}</b> on %{x}<br>Loading: %{z:.3f}<extra></extra>",
            }],
            "layout": {
                "title": {"text": "Factor Loadings Heatmap", "font": {"size": 14}},
                "xaxis": {"title": "Principal Component", "tickfont": {"size": 10}},
                "yaxis": {"title": "Ticker", "tickfont": {"size": 10}, "autorange": "reversed"},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "margin": {"t": 50, "r": 80, "b": 50, "l": 80},
            }
        },
        "type": "loadings_heatmap",
        "label": "Factor Loadings",
    }


def build_eigen_portfolio_chart(
    tickers: List[str],
    eigen_portfolios: Dict[str, List[float]],
) -> Optional[Dict[str, Any]]:
    """Build eigen-portfolio weights bar chart.
    
    Args:
        tickers: List of ticker symbols
        eigen_portfolios: Dict mapping PC names to weight lists
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not tickers or not eigen_portfolios:
        return None
    
    # Just show PC1 weights as a bar chart
    pc1_weights = eigen_portfolios.get("PC1", [])
    if not pc1_weights:
        return None
    
    # Color based on long/short
    colors = ["#22c55e" if w > 0 else "#ef4444" for w in pc1_weights]
    
    return {
        "plotly": {
            "data": [{
                "type": "bar",
                "x": tickers,
                "y": pc1_weights,
                "marker": {"color": colors},
                "hovertemplate": "<b>%{x}</b><br>Weight: %{y:.3f}<extra></extra>",
            }],
            "layout": {
                "title": {"text": "PC1 Eigen-Portfolio Weights (Long/Short)", "font": {"size": 14}},
                "xaxis": {"title": "Ticker", "tickangle": -45, "tickfont": {"size": 10}},
                "yaxis": {"title": "Weight", "gridcolor": "#e5e7eb", "zeroline": True, "zerolinecolor": "#000"},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "margin": {"t": 50, "r": 30, "b": 80, "l": 60},
            }
        },
        "type": "eigen_portfolio",
        "label": "Eigen-Portfolio",
    }
















