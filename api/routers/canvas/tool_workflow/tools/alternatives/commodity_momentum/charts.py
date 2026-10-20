"""
Canvas chart builders for Commodity Momentum.

Compact visualizations for:
1. Momentum rankings bar chart
2. Market breadth gauge
3. Regime indicator
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Color palette
COLORS = {
    "green": "#22c55e",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "teal": "#0891b2",
    "gray": "#6b7280",
}


def build_momentum_rankings_chart(
    rankings: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart of momentum rankings."""
    if not rankings:
        return None
    
    try:
        # Sort by score
        sorted_rankings = sorted(rankings, key=lambda x: x.get("score", 0), reverse=True)
        
        symbols = [r.get("symbol", "?") for r in sorted_rankings]
        scores = [r.get("score", 0) for r in sorted_rankings]
        colors = [COLORS["green"] if s > 0 else COLORS["red"] for s in scores]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "y": symbols,
                    "x": scores,
                    "orientation": "h",
                    "marker": {"color": colors},
                    "text": [f"{s:+.1f}" for s in scores],
                    "textposition": "outside",
                    "hovertemplate": "<b>%{y}</b>: %{x:+.1f}<extra></extra>",
                }],
                "layout": {
                    "title": {"text": "Momentum Rankings", "font": {"size": 14}},
                    "xaxis": {"title": "Score", "zeroline": True, "zerolinecolor": COLORS["gray"]},
                    "yaxis": {"autorange": "reversed"},
                    "height": max(180, len(rankings) * 28),
                    "margin": {"t": 40, "r": 50, "b": 40, "l": 70},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Rankings",
        }
    except Exception as e:
        logger.warning(f"Failed to build momentum rankings chart: {e}")
        return None


def build_breadth_chart(
    breadth_pct: float,
    signal: str,
) -> Optional[Dict[str, Any]]:
    """Build gauge showing market breadth."""
    try:
        # Color based on breadth
        if breadth_pct > 70:
            color = COLORS["green"]
        elif breadth_pct > 50:
            color = COLORS["teal"]
        elif breadth_pct > 30:
            color = COLORS["amber"]
        else:
            color = COLORS["red"]
        
        return {
            "plotly": {
                "data": [{
                    "type": "indicator",
                    "mode": "gauge+number",
                    "value": breadth_pct,
                    "gauge": {
                        "axis": {"range": [0, 100]},
                        "bar": {"color": color},
                        "steps": [
                            {"range": [0, 30], "color": "rgba(239, 68, 68, 0.2)"},
                            {"range": [30, 50], "color": "rgba(245, 158, 11, 0.2)"},
                            {"range": [50, 70], "color": "rgba(8, 145, 178, 0.2)"},
                            {"range": [70, 100], "color": "rgba(34, 197, 94, 0.2)"},
                        ],
                    },
                    "title": {"text": f"Breadth: {signal}"},
                    "number": {"suffix": "%"},
                }],
                "layout": {
                    "height": 180,
                    "margin": {"t": 40, "r": 20, "b": 20, "l": 20},
                    "paper_bgcolor": "white",
                },
            },
            "type": "gauge",
            "label": "Market Breadth",
        }
    except Exception as e:
        logger.warning(f"Failed to build breadth chart: {e}")
        return None


def build_regime_chart(
    regime_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build chart showing HMM regime probabilities."""
    if not regime_data or not regime_data.get("enabled"):
        return None
    
    try:
        all_probs = regime_data.get("all_probabilities", {})
        current_regime = regime_data.get("market_regime", "UNKNOWN")
        
        if not all_probs:
            return None
        
        regimes = list(all_probs.keys())
        probs = [all_probs[r] * 100 for r in regimes]
        
        # Color the current regime differently
        colors = [
            COLORS["teal"] if r == current_regime else COLORS["gray"]
            for r in regimes
        ]
        
        return {
            "plotly": {
                "data": [{
                    "type": "bar",
                    "x": regimes,
                    "y": probs,
                    "marker": {"color": colors},
                    "text": [f"{p:.0f}%" for p in probs],
                    "textposition": "outside",
                }],
                "layout": {
                    "title": {"text": f"Regime: {current_regime}", "font": {"size": 13}},
                    "yaxis": {"title": "Probability (%)", "range": [0, 110]},
                    "height": 180,
                    "margin": {"t": 40, "r": 20, "b": 50, "l": 50},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                },
            },
            "type": "bar",
            "label": "Regime Probabilities",
        }
    except Exception as e:
        logger.warning(f"Failed to build regime chart: {e}")
        return None


def build_roc_comparison_chart(
    rankings: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build grouped bar chart comparing ROC across timeframes."""
    if not rankings or len(rankings) < 2:
        return None
    
    try:
        # Take top 6 for readability
        top_rankings = sorted(rankings, key=lambda x: abs(x.get("score", 0)), reverse=True)[:6]
        
        symbols = [r.get("symbol", "?") for r in top_rankings]
        roc_1w = [r.get("roc_1w", 0) for r in top_rankings]
        roc_1m = [r.get("roc_1m", 0) for r in top_rankings]
        roc_3m = [r.get("roc_3m", 0) for r in top_rankings]
        
        return {
            "plotly": {
                "data": [
                    {
                        "type": "bar",
                        "name": "1W",
                        "x": symbols,
                        "y": roc_1w,
                        "marker": {"color": COLORS["teal"]},
                    },
                    {
                        "type": "bar",
                        "name": "1M",
                        "x": symbols,
                        "y": roc_1m,
                        "marker": {"color": COLORS["amber"]},
                    },
                    {
                        "type": "bar",
                        "name": "3M",
                        "x": symbols,
                        "y": roc_3m,
                        "marker": {"color": COLORS["green"]},
                    },
                ],
                "layout": {
                    "title": {"text": "ROC by Timeframe", "font": {"size": 13}},
                    "barmode": "group",
                    "yaxis": {"title": "ROC (%)"},
                    "height": 200,
                    "margin": {"t": 40, "r": 20, "b": 50, "l": 50},
                    "paper_bgcolor": "white",
                    "plot_bgcolor": "white",
                    "legend": {"orientation": "h", "y": -0.2},
                },
            },
            "type": "bar",
            "label": "ROC Comparison",
        }
    except Exception as e:
        logger.warning(f"Failed to build ROC comparison chart: {e}")
        return None
