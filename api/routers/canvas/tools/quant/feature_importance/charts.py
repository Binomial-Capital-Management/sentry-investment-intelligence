"""Chart builders for Feature Importance Canvas tool."""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

COLORS = {
    "primary": "#1e3a5f",
    "positive": "#059669",
    "negative": "#dc2626",
    "warning": "#f59e0b",
    "accent": "#3b82f6",
    "purple": "#8b5cf6",
    "grid": "#e2e8f0",
}


def build_importance_bars_chart(
    gain_scores: Dict[str, float],
    top_n: int = 15
) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart for feature importance (gain method)."""
    try:
        if not gain_scores:
            return None
        
        # Sort by importance
        sorted_features = sorted(gain_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        features = [f[0] for f in sorted_features]
        scores = [f[1] for f in sorted_features]
        
        # Reverse for horizontal bar (top at top)
        features = features[::-1]
        scores = scores[::-1]
        
        # Normalize for color scale
        max_score = max(scores) if scores else 1
        normalized = [s / max_score for s in scores]
        
        return {
            "id": "importance_bars",
            "title": "Feature Importance (Gain)",
            "plotly": {
                "data": [{
                    "type": "bar",
                    "y": features,
                    "x": scores,
                    "orientation": "h",
                    "marker": {
                        "color": normalized,
                        "colorscale": "Blues",
                        "line": {"color": "white", "width": 0.5}
                    },
                    "text": [f"{s:.4f}" for s in scores],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{y}</b><br>Importance: %{x:.4f}<extra></extra>"
                }],
                "layout": {
                    "title": {"text": "XGBoost Feature Importance (Gain)", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"title": "Importance Score", "gridcolor": COLORS["grid"]},
                    "yaxis": {"title": ""},
                    "height": 400 + (len(features) * 18),
                    "margin": {"l": 180, "r": 60, "t": 60, "b": 60},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                }
            }
        }
    except Exception as e:
        logger.warning(f"Importance bars chart failed: {e}")
        return None


def build_permutation_scatter_chart(
    gain_scores: Dict[str, float],
    perm_scores: Dict[str, float]
) -> Optional[Dict[str, Any]]:
    """Build scatter plot comparing gain vs permutation importance."""
    try:
        if not gain_scores or not perm_scores:
            return None
        
        # Get common features
        common = set(gain_scores.keys()) & set(perm_scores.keys())
        if not common:
            return None
        
        features = list(common)
        gain_vals = [gain_scores[f] for f in features]
        perm_vals = [perm_scores[f] for f in features]
        
        max_val = max(max(gain_vals), max(perm_vals)) * 1.1
        
        return {
            "id": "permutation_scatter",
            "title": "Gain vs Permutation Importance",
            "plotly": {
                "data": [
                    # Scatter points
                    {
                        "type": "scatter",
                        "x": gain_vals,
                        "y": perm_vals,
                        "mode": "markers",
                        "marker": {
                            "size": 10,
                            "color": gain_vals,
                            "colorscale": "Viridis",
                            "showscale": True,
                            "colorbar": {"title": "Gain"}
                        },
                        "text": features,
                        "hovertemplate": "<b>%{text}</b><br>Gain: %{x:.4f}<br>Perm: %{y:.4f}<extra></extra>"
                    },
                    # Diagonal reference line
                    {
                        "type": "scatter",
                        "x": [0, max_val],
                        "y": [0, max_val],
                        "mode": "lines",
                        "line": {"color": COLORS["negative"], "dash": "dash", "width": 2},
                        "name": "Perfect Agreement",
                        "showlegend": True
                    }
                ],
                "layout": {
                    "title": {"text": "Gain vs Permutation Importance", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"title": "Gain Importance", "gridcolor": COLORS["grid"]},
                    "yaxis": {"title": "Permutation Importance", "gridcolor": COLORS["grid"]},
                    "height": 500,
                    "margin": {"l": 60, "r": 60, "t": 60, "b": 60},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "showlegend": True,
                    "legend": {"x": 0.02, "y": 0.98}
                }
            }
        }
    except Exception as e:
        logger.warning(f"Permutation scatter chart failed: {e}")
        return None


def build_shap_chart(
    shap_scores: Dict[str, float],
    top_n: int = 15
) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart for SHAP importance."""
    try:
        if not shap_scores:
            return None
        
        # Sort by importance
        sorted_features = sorted(shap_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        features = [f[0] for f in sorted_features]
        scores = [f[1] for f in sorted_features]
        
        # Reverse for horizontal bar
        features = features[::-1]
        scores = scores[::-1]
        
        return {
            "id": "shap_summary",
            "title": "SHAP Feature Importance",
            "plotly": {
                "data": [{
                    "type": "bar",
                    "y": features,
                    "x": scores,
                    "orientation": "h",
                    "marker": {
                        "color": scores,
                        "colorscale": "Reds",
                        "line": {"color": "white", "width": 0.5}
                    },
                    "text": [f"{s:.4f}" for s in scores],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{y}</b><br>Mean |SHAP|: %{x:.4f}<extra></extra>"
                }],
                "layout": {
                    "title": {"text": "SHAP Feature Importance (Mean |SHAP|)", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"title": "Mean Absolute SHAP Value", "gridcolor": COLORS["grid"]},
                    "yaxis": {"title": ""},
                    "height": 400 + (len(features) * 18),
                    "margin": {"l": 180, "r": 60, "t": 60, "b": 60},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                }
            }
        }
    except Exception as e:
        logger.warning(f"SHAP chart failed: {e}")
        return None


def build_correlation_heatmap(
    correlation_matrix: List[List[float]],
    feature_names: List[str]
) -> Optional[Dict[str, Any]]:
    """Build correlation heatmap for top features."""
    try:
        if not correlation_matrix or not feature_names:
            return None
        
        # Limit to top 12 for readability
        n = min(12, len(feature_names))
        matrix = [row[:n] for row in correlation_matrix[:n]]
        names = feature_names[:n]
        
        # Round values for text display
        text_matrix = [[f"{v:.2f}" for v in row] for row in matrix]
        
        return {
            "id": "correlation",
            "title": "Feature Correlation Matrix",
            "plotly": {
                "data": [{
                    "type": "heatmap",
                    "z": matrix,
                    "x": names,
                    "y": names,
                    "colorscale": "RdBu",
                    "zmid": 0,
                    "text": text_matrix,
                    "texttemplate": "%{text}",
                    "textfont": {"size": 9},
                    "colorbar": {"title": "Corr"},
                    "hovertemplate": "%{x} vs %{y}<br>Correlation: %{z:.3f}<extra></extra>"
                }],
                "layout": {
                    "title": {"text": "Top Features Correlation", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"tickangle": -45},
                    "yaxis": {"autorange": "reversed"},
                    "height": 500,
                    "width": 600,
                    "margin": {"l": 120, "r": 60, "t": 60, "b": 120},
                    "paper_bgcolor": "white",
                }
            }
        }
    except Exception as e:
        logger.warning(f"Correlation heatmap failed: {e}")
        return None
