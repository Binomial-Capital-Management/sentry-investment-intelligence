"""Chart builders for Sector Rotation Canvas tool."""
from typing import Any, Dict, Optional

# Color palette
COLORS = {
    "bullish": "#22c55e",
    "bearish": "#ef4444",
    "neutral": "#6b7280",
    "risk_on": "#22c55e",
    "risk_off": "#ef4444",
    "transition": "#f59e0b",
}


def build_sector_signals_chart(signal_scores: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """Build horizontal bar chart of sector signal scores.
    
    Args:
        signal_scores: Dict mapping sector name to composite z-score
        
    Returns:
        Plotly chart configuration or None
    """
    if not signal_scores:
        return None
    
    # Sort by score descending
    sorted_sectors = sorted(signal_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Prepare data (reverse for bottom-to-top display in horizontal bars)
    sectors = [s[0].title() for s in reversed(sorted_sectors)]
    scores = [s[1] for s in reversed(sorted_sectors)]
    
    # Color based on direction
    colors = [
        COLORS["bullish"] if s > 0.3 else (COLORS["bearish"] if s < -0.3 else COLORS["neutral"])
        for s in scores
    ]
    
    # Text labels
    text_labels = [f"{s:+.2f}σ" for s in scores]
    
    return {
        "plotly": {
            "data": [{
                "type": "bar",
                "y": sectors,
                "x": scores,
                "orientation": "h",
                "marker": {"color": colors},
                "text": text_labels,
                "textposition": "outside",
                "textfont": {"size": 10},
                "hovertemplate": "<b>%{y}</b><br>Signal: %{x:.2f}σ<extra></extra>",
            }],
            "layout": {
                "title": {"text": "Sector Rotation Signals", "font": {"size": 14}},
                "xaxis": {
                    "title": "Signal Strength (σ)",
                    "zeroline": True,
                    "zerolinecolor": "#374151",
                    "zerolinewidth": 2,
                },
                "yaxis": {"tickfont": {"size": 10}},
                "height": max(350, len(sectors) * 30 + 80),
                "margin": {"t": 50, "r": 60, "b": 50, "l": 120},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
            },
        },
        "type": "bar",
        "label": "Sector Signals",
    }


def build_factor_heatmap_chart(factor_matrix: Dict[str, Dict[str, float]]) -> Optional[Dict[str, Any]]:
    """Build heatmap of factor z-scores across sectors.
    
    Args:
        factor_matrix: Dict mapping sector -> factor -> z-score
        
    Returns:
        Plotly chart configuration or None
    """
    if not factor_matrix:
        return None
    
    # Get sectors and factors
    sectors = list(factor_matrix.keys())
    if not sectors:
        return None
    
    factors = list(factor_matrix[sectors[0]].keys())
    
    # Build z-value matrix
    z_values = [
        [factor_matrix[sector].get(factor, 0) for factor in factors]
        for sector in sectors
    ]
    
    # Format sector names
    sector_labels = [s.title() for s in sectors]
    
    # Text annotations
    text_values = [[f"{v:.1f}" for v in row] for row in z_values]
    
    return {
        "plotly": {
            "data": [{
                "type": "heatmap",
                "z": z_values,
                "x": factors,
                "y": sector_labels,
                "colorscale": [
                    [0, COLORS["bearish"]],
                    [0.5, "#f3f4f6"],
                    [1, COLORS["bullish"]],
                ],
                "zmid": 0,
                "text": text_values,
                "texttemplate": "%{text}",
                "textfont": {"size": 10},
                "hoverongaps": False,
                "hovertemplate": "<b>%{y}</b><br>%{x}: %{z:.2f}σ<extra></extra>",
                "colorbar": {"title": "Z-Score", "ticksuffix": "σ"},
            }],
            "layout": {
                "title": {"text": "Factor Z-Scores by Sector", "font": {"size": 14}},
                "xaxis": {"side": "bottom"},
                "yaxis": {"tickfont": {"size": 10}},
                "height": max(300, len(sectors) * 25 + 100),
                "margin": {"t": 50, "r": 80, "b": 50, "l": 130},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
            },
        },
        "type": "heatmap",
        "label": "Factor Heatmap",
    }


def build_regime_indicator_chart(regime: str, confidence: float) -> Optional[Dict[str, Any]]:
    """Build regime indicator showing current market state on a spectrum.
    
    Args:
        regime: Current regime (risk_on, risk_off, transition)
        confidence: Confidence level 0-1
        
    Returns:
        Plotly chart configuration or None
    """
    # Map regime to position on -1 to +1 scale
    if regime == "risk_on":
        position = 0.5 + (confidence * 0.5)  # 0.5 to 1.0
    elif regime == "risk_off":
        position = -0.5 - (confidence * 0.5)  # -0.5 to -1.0
    else:  # transition
        position = 0
    
    # Regime labels and colors
    regimes = ["Risk-Off", "Transition", "Risk-On"]
    regime_positions = [-0.75, 0, 0.75]
    regime_colors = [COLORS["risk_off"], COLORS["transition"], COLORS["risk_on"]]
    
    return {
        "plotly": {
            "data": [
                # Background spectrum bar
                {
                    "type": "bar",
                    "x": [2],
                    "y": ["Regime"],
                    "orientation": "h",
                    "marker": {
                        "color": [[0, COLORS["risk_off"]], [0.5, COLORS["transition"]], [1, COLORS["risk_on"]]],
                        "colorscale": [
                            [0, "#fecaca"],
                            [0.4, "#fef3c7"],
                            [0.6, "#fef3c7"],
                            [1, "#bbf7d0"],
                        ],
                    },
                    "width": 0.4,
                    "showlegend": False,
                    "hoverinfo": "skip",
                },
                # Current position marker
                {
                    "type": "scatter",
                    "x": [position + 1],  # Shift to 0-2 range
                    "y": ["Regime"],
                    "mode": "markers+text",
                    "marker": {
                        "size": 20,
                        "color": regime_colors[1] if regime == "transition" else (regime_colors[2] if regime == "risk_on" else regime_colors[0]),
                        "symbol": "diamond",
                        "line": {"width": 2, "color": "#1f2937"},
                    },
                    "text": [f"{confidence*100:.0f}%"],
                    "textposition": "top center",
                    "textfont": {"size": 11, "color": "#374151"},
                    "showlegend": False,
                    "hovertemplate": f"<b>{regime.replace('_', ' ').title()}</b><br>Confidence: {confidence*100:.0f}%<extra></extra>",
                },
            ],
            "layout": {
                "title": {"text": "Market Regime Indicator", "font": {"size": 14}},
                "xaxis": {
                    "range": [0, 2],
                    "tickvals": [0.25, 1, 1.75],
                    "ticktext": ["RISK-OFF", "TRANSITION", "RISK-ON"],
                    "tickfont": {"size": 10},
                    "showgrid": False,
                    "zeroline": False,
                },
                "yaxis": {
                    "visible": False,
                },
                "height": 140,
                "margin": {"t": 40, "r": 20, "b": 40, "l": 20},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "showlegend": False,
            },
        },
        "type": "bar",
        "label": "Regime Indicator",
    }
