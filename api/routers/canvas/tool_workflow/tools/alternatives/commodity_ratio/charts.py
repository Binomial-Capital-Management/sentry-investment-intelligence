"""
Canvas chart builders for Commodity Ratio.

Builds proper historical ratio line chart with z-score bands.
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

COLORS = {
    "teal": "#0891b2",
    "amber": "#d97706",
    "gray": "#6b7280",
    "green": "#22c55e",
}


def build_ratio_history_chart(
    dates: List[str],
    num_prices: List[float],
    denom_prices: List[float],
    ratio: List[float],
    ratio_mean: float,
    ratio_std: float,
    high_z: float,
    low_z: float,
    num_name: str,
    denom_name: str,
) -> Optional[Dict[str, Any]]:
    """Build two-panel chart: normalized prices + ratio with z-score bands."""
    try:
        if not dates or not ratio:
            return None
        
        # Calculate thresholds
        upper_threshold = ratio_mean + high_z * ratio_std
        lower_threshold = ratio_mean + low_z * ratio_std
        
        # Normalize prices to 100
        num_base = num_prices[0] if num_prices[0] != 0 else 1
        denom_base = denom_prices[0] if denom_prices[0] != 0 else 1
        norm_num = [p / num_base * 100 for p in num_prices]
        norm_denom = [p / denom_base * 100 for p in denom_prices]
        
        pair_name = f"{num_name}/{denom_name}"
        
        return {
            "plotly": {
                "data": [
                    # Panel 1: Normalized prices
                    {
                        "type": "scatter",
                        "x": dates,
                        "y": norm_num,
                        "name": num_name,
                        "line": {"color": COLORS["teal"], "width": 2},
                        "xaxis": "x",
                        "yaxis": "y",
                    },
                    {
                        "type": "scatter",
                        "x": dates,
                        "y": norm_denom,
                        "name": denom_name,
                        "line": {"color": COLORS["amber"], "width": 2},
                        "xaxis": "x",
                        "yaxis": "y",
                    },
                    # Panel 2: Ratio
                    {
                        "type": "scatter",
                        "x": dates,
                        "y": ratio,
                        "name": pair_name,
                        "line": {"color": COLORS["gray"], "width": 2.5},
                        "xaxis": "x2",
                        "yaxis": "y2",
                    },
                    # Mean line
                    {
                        "type": "scatter",
                        "x": [dates[0], dates[-1]],
                        "y": [ratio_mean, ratio_mean],
                        "name": "Mean",
                        "line": {"color": "#555", "width": 1.5, "dash": "solid"},
                        "xaxis": "x2",
                        "yaxis": "y2",
                        "showlegend": False,
                    },
                    # Upper threshold
                    {
                        "type": "scatter",
                        "x": [dates[0], dates[-1]],
                        "y": [upper_threshold, upper_threshold],
                        "name": f"+{high_z}σ",
                        "line": {"color": COLORS["amber"], "width": 1, "dash": "dash"},
                        "xaxis": "x2",
                        "yaxis": "y2",
                        "showlegend": False,
                    },
                    # Lower threshold
                    {
                        "type": "scatter",
                        "x": [dates[0], dates[-1]],
                        "y": [lower_threshold, lower_threshold],
                        "name": f"{low_z}σ",
                        "line": {"color": COLORS["teal"], "width": 1, "dash": "dash"},
                        "xaxis": "x2",
                        "yaxis": "y2",
                        "showlegend": False,
                    },
                ],
                "layout": {
                    "title": {"text": f"<b>{pair_name} Ratio Analysis</b>", "x": 0.5},
                    "height": 500,
                    "grid": {"rows": 2, "columns": 1, "pattern": "independent", "roworder": "top to bottom"},
                    "xaxis": {"domain": [0, 1], "showticklabels": False},
                    "yaxis": {"domain": [0.55, 1], "title": "Normalized (100)"},
                    "xaxis2": {"domain": [0, 1], "anchor": "y2"},
                    "yaxis2": {"domain": [0, 0.45], "title": "Ratio"},
                    "legend": {"orientation": "h", "y": 1.12, "x": 0.5, "xanchor": "center"},
                    "margin": {"t": 60, "b": 40, "l": 60, "r": 40},
                    "template": "plotly_white",
                    "annotations": [
                        {"text": f"<b>Prices</b> (Normalized)", "x": 0.5, "y": 1.02, "xref": "paper", "yref": "paper", "showarrow": False, "font": {"size": 12}},
                        {"text": f"<b>Ratio</b> (Mean: {ratio_mean:.2f})", "x": 0.5, "y": 0.48, "xref": "paper", "yref": "paper", "showarrow": False, "font": {"size": 12}},
                    ],
                },
            },
            "type": "line",
            "label": f"{pair_name} Ratio History",
        }
    except Exception as e:
        logger.warning(f"Failed to build ratio history chart: {e}")
        return None


def build_regime_chart(
    regime: str,
    confidence: float,
    z_score: float,
) -> Optional[Dict[str, Any]]:
    """Build bar chart showing regime confidence."""
    try:
        if "CHEAP" in regime:
            color = COLORS["green"]
        elif "SLIGHTLY" in regime:
            color = COLORS["amber"]
        else:
            color = COLORS["gray"]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": ["Confidence"],
                    "y": [confidence * 100],
                    "marker": {"color": color},
                    "text": [f"{confidence:.0%}"],
                    "textposition": "outside",
                }],
                "layout": {
                    "title": {"text": f"Regime: {regime}", "font": {"size": 13}},
                    "yaxis": {"range": [0, 110], "title": "Confidence (%)"},
                    "height": 180,
                    "margin": {"t": 40, "r": 20, "b": 30, "l": 50},
                    "template": "plotly_white",
                },
            },
            "type": "bar",
            "label": "Regime Confidence",
        }
    except Exception as e:
        logger.warning(f"Failed to build regime chart: {e}")
        return None


def build_zscore_chart(
    z_score: float,
    thresholds: Dict[str, float],
    num_name: str,
    denom_name: str,
) -> Optional[Dict[str, Any]]:
    """Build horizontal indicator showing z-score position."""
    try:
        high_z = thresholds.get("high", 1.5)
        low_z = thresholds.get("low", -1.5)
        
        if z_score > high_z:
            color = COLORS["amber"]
        elif z_score < low_z:
            color = COLORS["teal"]
        else:
            color = COLORS["gray"]
        
        return {
            "plotly": {
                "data": [{
                    "type": "scatter",
                    "y": ["Z-Score"],
                    "x": [z_score],
                    "mode": "markers+text",
                    "marker": {"size": 20, "color": color, "symbol": "diamond"},
                    "text": [f"{z_score:+.2f}σ"],
                    "textposition": "top center",
                }],
                "layout": {
                    "title": {"text": "Z-Score Position", "font": {"size": 13}},
                    "xaxis": {"range": [-3, 3], "zeroline": True, "zerolinewidth": 2},
                    "height": 120,
                    "margin": {"t": 35, "r": 20, "b": 30, "l": 60},
                    "template": "plotly_white",
                    "shapes": [
                        {"type": "rect", "x0": high_z, "x1": 3, "y0": -0.5, "y1": 0.5, "fillcolor": "rgba(217, 119, 6, 0.2)", "line": {"width": 0}},
                        {"type": "rect", "x0": -3, "x1": low_z, "y0": -0.5, "y1": 0.5, "fillcolor": "rgba(8, 145, 178, 0.2)", "line": {"width": 0}},
                    ],
                },
            },
            "type": "scatter",
            "label": "Z-Score",
        }
    except Exception as e:
        logger.warning(f"Failed to build z-score chart: {e}")
        return None
