"""
Cointegration Canvas Charts
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_pvalue_heatmap(
    tickers: List[str],
    pvalue_matrix: List[List[float]],
    significance_level: float = 0.05
) -> Optional[Dict[str, Any]]:
    """Build p-value heatmap for cointegration tests."""
    if not tickers or not pvalue_matrix:
        return None
    
    # Create heatmap with custom colorscale (green = significant, red = not)
    data = [{
        "type": "heatmap",
        "z": pvalue_matrix,
        "x": tickers,
        "y": tickers,
        "colorscale": [
            [0, "#22c55e"],      # Green (p=0, highly significant)
            [0.05, "#86efac"],   # Light green
            [0.1, "#fef08a"],    # Yellow
            [0.5, "#fca5a5"],    # Light red
            [1, "#ef4444"]       # Red (p=1, not significant)
        ],
        "zmin": 0,
        "zmax": 0.2,
        "colorbar": {"title": "P-Value", "tickformat": ".2f"},
        "hovertemplate": "%{y} vs %{x}<br>P-Value: %{z:.4f}<extra></extra>"
    }]
    
    layout = {
        "title": f"Cointegration P-Values (α={significance_level})",
        "xaxis": {"title": "Ticker", "side": "bottom"},
        "yaxis": {"title": "Ticker"},
        "template": "plotly_white",
        "height": 450,
        "margin": {"l": 80, "r": 40, "t": 60, "b": 80}
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "heatmap",
        "label": "P-Value Heatmap"
    }


def build_spread_chart(
    ticker_a: str,
    ticker_b: str,
    spread_data: Dict[str, Any],
    hedge_ratio: float,
    current_zscore: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Build spread chart with mean reversion bands."""
    if not spread_data:
        return None
    
    dates = spread_data.get('dates', [])
    spread = spread_data.get('spread', [])
    mean = spread_data.get('mean', 0)
    std = spread_data.get('std', 1)
    
    if not dates or not spread:
        return None
    
    # Normalize to z-score
    zscore = [(s - mean) / std if std > 0 else 0 for s in spread]
    
    data = [
        {
            "type": "scatter",
            "x": dates,
            "y": zscore,
            "mode": "lines",
            "name": "Z-Score",
            "line": {"color": "#3b82f6", "width": 2},
            "hovertemplate": "%{x}<br>Z-Score: %{y:.2f}<extra></extra>"
        }
    ]
    
    # Add bands
    shapes = [
        {"type": "line", "x0": dates[0], "x1": dates[-1], "y0": 0, "y1": 0,
         "line": {"color": "#6b7280", "width": 1, "dash": "dash"}},
        {"type": "line", "x0": dates[0], "x1": dates[-1], "y0": 2, "y1": 2,
         "line": {"color": "#ef4444", "width": 1, "dash": "dot"}},
        {"type": "line", "x0": dates[0], "x1": dates[-1], "y0": -2, "y1": -2,
         "line": {"color": "#22c55e", "width": 1, "dash": "dot"}},
    ]
    
    # Add current position marker
    if current_zscore is not None:
        data.append({
            "type": "scatter",
            "x": [dates[-1]],
            "y": [current_zscore],
            "mode": "markers",
            "name": f"Current ({current_zscore:.2f})",
            "marker": {
                "size": 12,
                "color": "#ef4444" if abs(current_zscore) > 2 else "#6b7280",
                "symbol": "diamond"
            }
        })
    
    layout = {
        "title": f"Spread Z-Score: {ticker_b} - {hedge_ratio:.2f}×{ticker_a}",
        "xaxis": {"title": "Date"},
        "yaxis": {"title": "Z-Score (σ)"},
        "shapes": shapes,
        "template": "plotly_white",
        "height": 350,
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02},
        "annotations": [
            {"x": dates[-1], "y": 2, "text": "+2σ", "showarrow": False, "xanchor": "left", "font": {"color": "#ef4444"}},
            {"x": dates[-1], "y": -2, "text": "-2σ", "showarrow": False, "xanchor": "left", "font": {"color": "#22c55e"}},
        ]
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "spread",
        "label": f"Spread: {ticker_b}/{ticker_a}"
    }


def build_pairs_ranking_chart(
    cointegrated_pairs: List[Dict[str, Any]],
    top_n: int = 10
) -> Optional[Dict[str, Any]]:
    """Build bar chart ranking pairs by p-value."""
    if not cointegrated_pairs:
        return None
    
    # Take top N by p-value (lowest first)
    sorted_pairs = sorted(cointegrated_pairs, key=lambda x: x['p_value'])[:top_n]
    
    labels = [f"{p['ticker_a']}/{p['ticker_b']}" for p in sorted_pairs]
    pvalues = [p['p_value'] for p in sorted_pairs]
    colors = ["#22c55e" if p['significant'] else "#ef4444" for p in sorted_pairs]
    
    data = [{
        "type": "bar",
        "x": labels,
        "y": pvalues,
        "marker": {"color": colors},
        "hovertemplate": "%{x}<br>P-Value: %{y:.4f}<extra></extra>"
    }]
    
    layout = {
        "title": f"Top {len(sorted_pairs)} Pairs by Cointegration Strength",
        "xaxis": {"title": "Pair", "tickangle": -45},
        "yaxis": {"title": "P-Value", "range": [0, max(pvalues) * 1.1]},
        "template": "plotly_white",
        "height": 350,
        "shapes": [{
            "type": "line", "x0": -0.5, "x1": len(labels) - 0.5, "y0": 0.05, "y1": 0.05,
            "line": {"color": "#f97316", "width": 2, "dash": "dash"}
        }],
        "annotations": [{
            "x": len(labels) - 1, "y": 0.05, "text": "α=0.05",
            "showarrow": False, "xanchor": "right", "font": {"color": "#f97316"}
        }]
    }
    
    return {
        "plotly": {"data": data, "layout": layout},
        "type": "ranking",
        "label": "Pairs Ranking"
    }
















