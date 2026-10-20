"""Chart builders for Squeeze Detector Canvas tool - Institutional grade."""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Institutional color palette
COLORS = {
    "primary": "#1e3a5f",      # Dark blue
    "secondary": "#64748b",    # Slate
    "positive": "#059669",     # Green
    "negative": "#dc2626",     # Red
    "neutral": "#94a3b8",      # Light gray
    "accent": "#0ea5e9",       # Sky blue
    "grid": "#e2e8f0",         # Very light gray
}


def build_zscore_bar_chart(
    ticker: str,
    features: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Clean horizontal bar chart of z-scores."""
    try:
        z_scores = {}
        for key, val in features.items():
            if "zscore" in key.lower() and isinstance(val, (int, float)):
                label = key.replace("_zscore", "").replace("_", " ").upper()
                z_scores[label] = val
        
        if not z_scores:
            return None
        
        # Sort by value
        sorted_items = sorted(z_scores.items(), key=lambda x: x[1], reverse=True)
        labels = [x[0] for x in sorted_items]
        values = [x[1] for x in sorted_items]
        
        # Color by sign
        colors = [COLORS["negative"] if v > 1.5 else COLORS["positive"] if v < -1 else COLORS["secondary"] for v in values]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "y": labels,
                    "x": values,
                    "orientation": "h",
                    "marker": {"color": colors},
                    "text": [f"{v:+.1f}σ" for v in values],
                    "textposition": "outside",
                    "textfont": {"size": 11, "color": COLORS["primary"]},
                }],
                "layout": {
                    "title": {"text": f"{ticker} | Signal Z-Scores", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"title": "Standard Deviations", "zeroline": True, "zerolinecolor": COLORS["primary"], "zerolinewidth": 1, "gridcolor": COLORS["grid"]},
                    "yaxis": {"automargin": True, "tickfont": {"size": 10}},
                    "height": 350,
                    "margin": {"l": 120, "r": 60, "t": 40, "b": 40},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                },
            },
            "type": "zscore_bars",
            "label": f"{ticker} Z-Scores",
        }
    except Exception as e:
        logger.error(f"Failed to build z-score chart: {e}")
        return None


def build_probability_chart(
    ticker: str,
    trigger_prob_5d: float,
    trigger_prob_10d: float,
) -> Optional[Dict[str, Any]]:
    """Simple bar chart showing trigger probabilities."""
    try:
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": ["5-Day", "10-Day"],
                    "y": [trigger_prob_5d * 100, trigger_prob_10d * 100],
                    "marker": {"color": [COLORS["primary"], COLORS["secondary"]]},
                    "text": [f"{trigger_prob_5d*100:.0f}%", f"{trigger_prob_10d*100:.0f}%"],
                    "textposition": "outside",
                    "textfont": {"size": 14, "color": COLORS["primary"]},
                    "width": 0.5,
                }],
                "layout": {
                    "title": {"text": f"{ticker} | Trigger Probability", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "yaxis": {"title": "%", "range": [0, 100], "gridcolor": COLORS["grid"]},
                    "xaxis": {"title": ""},
                    "height": 280,
                    "margin": {"l": 50, "r": 30, "t": 40, "b": 40},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                },
            },
            "type": "probability",
            "label": f"{ticker} Trigger Probability",
        }
    except Exception as e:
        logger.error(f"Failed to build probability chart: {e}")
        return None


def build_levels_chart(
    ticker: str,
    spot_price: float,
    key_levels: Dict[str, float],
) -> Optional[Dict[str, Any]]:
    """Clean horizontal lines showing key price levels."""
    try:
        levels = []
        
        level_config = [
            ("put_wall", "Put Wall", COLORS["positive"]),
            ("zero_gamma", "Zero Gamma", COLORS["neutral"]),
            ("gamma_ramp", "Gamma Ramp", COLORS["accent"]),
            ("call_wall", "Call Wall", COLORS["negative"]),
        ]
        
        for key, label, color in level_config:
            val = key_levels.get(key)
            if val and val > 0:
                levels.append((label, val, color))
        
        if not levels:
            return None
        
        # Add spot
        levels.append(("Spot", spot_price, COLORS["primary"]))
        levels.sort(key=lambda x: x[1])
        
        labels = [l[0] for l in levels]
        prices = [l[1] for l in levels]
        colors = [l[2] for l in levels]
        
        return {
            "plotly": {
                "data": [{
                    "type": "scatter",
                    "x": prices,
                    "y": [0.5] * len(prices),
                    "mode": "markers+text",
                    "marker": {"size": 12, "color": colors},
                    "text": labels,
                    "textposition": "top center",
                    "textfont": {"size": 10, "color": COLORS["primary"]},
                    "hovertemplate": "%{text}: $%{x:.2f}<extra></extra>",
                }],
                "layout": {
                    "title": {"text": f"{ticker} | Key Levels", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"title": "Price ($)", "tickprefix": "$", "gridcolor": COLORS["grid"]},
                    "yaxis": {"visible": False, "range": [0, 1]},
                    "height": 200,
                    "margin": {"l": 50, "r": 30, "t": 40, "b": 40},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "shapes": [
                        {"type": "line", "x0": spot_price, "x1": spot_price, "y0": 0, "y1": 1,
                         "line": {"color": COLORS["primary"], "width": 2, "dash": "dot"}},
                    ],
                },
            },
            "type": "key_levels",
            "label": f"{ticker} Key Levels",
        }
    except Exception as e:
        logger.error(f"Failed to build levels chart: {e}")
        return None


def build_magnitude_chart(
    ticker: str,
    spot_price: float,
    expected_move: float,
    ci_90: List[float],
) -> Optional[Dict[str, Any]]:
    """Simple range chart showing expected move with CI."""
    try:
        low, high = ci_90 if len(ci_90) >= 2 else [expected_move * 0.5, expected_move * 1.5]
        
        low_price = spot_price * (1 + low)
        exp_price = spot_price * (1 + expected_move)
        high_price = spot_price * (1 + high)
        
        return {
            "plotly": {
                "data": [
                    # Range bar
                    {"type": "scatter", "x": [low_price, high_price], "y": [0.5, 0.5],
                     "mode": "lines", "line": {"color": COLORS["neutral"], "width": 8},
                     "hoverinfo": "skip", "showlegend": False},
                    # Expected point
                    {"type": "scatter", "x": [exp_price], "y": [0.5],
                     "mode": "markers", "marker": {"size": 14, "color": COLORS["primary"]},
                     "name": f"Expected: ${exp_price:.2f} (+{expected_move*100:.0f}%)",
                     "hovertemplate": "Expected: $%{x:.2f}<extra></extra>"},
                    # Spot reference
                    {"type": "scatter", "x": [spot_price], "y": [0.5],
                     "mode": "markers", "marker": {"size": 10, "color": COLORS["secondary"], "symbol": "line-ns"},
                     "name": f"Spot: ${spot_price:.2f}",
                     "hovertemplate": "Spot: $%{x:.2f}<extra></extra>"},
                ],
                "layout": {
                    "title": {"text": f"{ticker} | Expected Move", "x": 0, "font": {"size": 14, "color": COLORS["primary"]}},
                    "xaxis": {"title": "Price ($)", "tickprefix": "$", "gridcolor": COLORS["grid"]},
                    "yaxis": {"visible": False, "range": [0, 1]},
                    "height": 200,
                    "margin": {"l": 50, "r": 30, "t": 40, "b": 40},
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "legend": {"orientation": "h", "y": -0.3, "font": {"size": 10}},
                    "annotations": [
                        {"x": low_price, "y": 0.3, "text": f"+{low*100:.0f}%", "showarrow": False, "font": {"size": 9, "color": COLORS["secondary"]}},
                        {"x": high_price, "y": 0.3, "text": f"+{high*100:.0f}%", "showarrow": False, "font": {"size": 9, "color": COLORS["secondary"]}},
                    ],
                },
            },
            "type": "magnitude",
            "label": f"{ticker} Expected Move",
        }
    except Exception as e:
        logger.error(f"Failed to build magnitude chart: {e}")
        return None
