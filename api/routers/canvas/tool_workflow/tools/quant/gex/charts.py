"""Chart builders for Gamma Exposure (GEX) Canvas tool."""
from typing import Any, Dict, List, Optional

# Color palette
COLORS = {
    "gamma_bar": "#6366f1",  # Indigo
    "spot": "#ef4444",       # Red
    "max_gamma": "#f59e0b",  # Amber
    "put_wall": "#22c55e",   # Green
    "call_wall": "#ef4444",  # Red
    "short_gamma": "#ef4444",
    "long_gamma": "#22c55e",
    "neutral": "#6b7280",
}


def build_gamma_profile_chart(
    ticker: str,
    spot_price: float,
    gamma_profile: List[Dict[str, Any]],
    key_levels: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build bar chart of gamma exposure by strike.
    
    Args:
        ticker: Underlying symbol
        spot_price: Current spot price
        gamma_profile: List of strike-level gamma data
        key_levels: Dict with max_gamma_strike, put_wall, call_wall
        
    Returns:
        Plotly chart configuration or None
    """
    if not gamma_profile:
        return None
    
    # Extract data
    strikes = [p["strike"] for p in gamma_profile]
    gex_values = [p.get("gross_gex_millions", 0) for p in gamma_profile]
    
    max_gamma = key_levels.get("max_gamma_strike", 0)
    put_wall = key_levels.get("put_wall", 0)
    call_wall = key_levels.get("call_wall", 0)
    
    # Color bars - highlight near spot
    colors = []
    for strike in strikes:
        if abs(strike - spot_price) / spot_price < 0.01:
            colors.append("#ef4444")  # Red for ATM
        else:
            colors.append(COLORS["gamma_bar"])
    
    # Build shapes for key levels
    shapes = [
        # Spot price line
        {
            "type": "line",
            "x0": spot_price,
            "x1": spot_price,
            "y0": 0,
            "y1": 1,
            "yref": "paper",
            "line": {"color": COLORS["spot"], "width": 2, "dash": "solid"},
        },
    ]
    
    annotations = [
        {
            "x": spot_price,
            "y": 1.02,
            "yref": "paper",
            "text": f"Spot ${spot_price:.0f}",
            "showarrow": False,
            "font": {"size": 10, "color": COLORS["spot"]},
        },
    ]
    
    # Max gamma strike
    if max_gamma and max_gamma != spot_price:
        shapes.append({
            "type": "line",
            "x0": max_gamma,
            "x1": max_gamma,
            "y0": 0,
            "y1": 1,
            "yref": "paper",
            "line": {"color": COLORS["max_gamma"], "width": 2, "dash": "dot"},
        })
        annotations.append({
            "x": max_gamma,
            "y": 0.95,
            "yref": "paper",
            "text": f"Max γ",
            "showarrow": False,
            "font": {"size": 9, "color": COLORS["max_gamma"]},
        })
    
    # Put wall
    if put_wall and put_wall < spot_price:
        shapes.append({
            "type": "line",
            "x0": put_wall,
            "x1": put_wall,
            "y0": 0,
            "y1": 1,
            "yref": "paper",
            "line": {"color": COLORS["put_wall"], "width": 1.5, "dash": "dash"},
        })
        annotations.append({
            "x": put_wall,
            "y": 0.88,
            "yref": "paper",
            "text": "Put Wall",
            "showarrow": False,
            "font": {"size": 9, "color": COLORS["put_wall"]},
        })
    
    # Call wall
    if call_wall and call_wall > spot_price:
        shapes.append({
            "type": "line",
            "x0": call_wall,
            "x1": call_wall,
            "y0": 0,
            "y1": 1,
            "yref": "paper",
            "line": {"color": COLORS["call_wall"], "width": 1.5, "dash": "dash"},
        })
        annotations.append({
            "x": call_wall,
            "y": 0.88,
            "yref": "paper",
            "text": "Call Wall",
            "showarrow": False,
            "font": {"size": 9, "color": COLORS["call_wall"]},
        })
    
    return {
        "plotly": {
            "data": [{
                "type": "bar",
                "x": strikes,
                "y": gex_values,
                "marker": {"color": colors, "line": {"width": 0}},
                "hovertemplate": "<b>Strike:</b> $%{x:,.0f}<br><b>GEX:</b> $%{y:.2f}M<extra></extra>",
            }],
            "layout": {
                "title": {"text": f"{ticker} Gamma Exposure by Strike", "font": {"size": 14}},
                "xaxis": {
                    "title": "Strike Price ($)",
                    "tickformat": "$,.0f",
                    "gridcolor": "#e5e7eb",
                },
                "yaxis": {
                    "title": "Gross Gamma ($M)",
                    "gridcolor": "#e5e7eb",
                },
                "shapes": shapes,
                "annotations": annotations,
                "height": 400,
                "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
                "paper_bgcolor": "white",
                "plot_bgcolor": "#fafafa",
            },
        },
        "type": "bar",
        "label": "Gamma Profile",
    }


def build_key_levels_chart(
    ticker: str,
    spot_price: float,
    key_levels: Dict[str, Any],
    regime: str,
    confidence: float,
) -> Optional[Dict[str, Any]]:
    """Build vertical bar chart showing distance to key levels.
    
    Args:
        ticker: Underlying symbol
        spot_price: Current spot price
        key_levels: Dict with put_wall, call_wall, max_gamma_strike
        regime: Current dealer regime
        confidence: Regime confidence 0-1
        
    Returns:
        Plotly chart configuration or None
    """
    put_wall = key_levels.get("put_wall", 0)
    call_wall = key_levels.get("call_wall", 0)
    max_gamma = key_levels.get("max_gamma_strike", 0)
    
    if not put_wall or not call_wall or not spot_price:
        return None
    
    # Calculate distances from spot (as percentage)
    put_dist = (spot_price - put_wall) / spot_price * 100  # Positive = above put wall (good)
    call_dist = (call_wall - spot_price) / spot_price * 100  # Positive = below call wall (good)
    gamma_dist = (max_gamma - spot_price) / spot_price * 100  # Can be pos or neg
    
    # Build data for horizontal bars showing distance
    levels = ["Put Wall (Support)", "Max Gamma", "Call Wall (Resistance)"]
    prices = [put_wall, max_gamma, call_wall]
    distances = [put_dist, gamma_dist, call_dist]
    
    # Colors: green for support below, red for resistance above, amber for max gamma
    colors = [COLORS["put_wall"], COLORS["max_gamma"], COLORS["call_wall"]]
    
    # Text labels
    labels = [
        f"${put_wall:,.0f} ({put_dist:+.1f}%)",
        f"${max_gamma:,.0f} ({gamma_dist:+.1f}%)",
        f"${call_wall:,.0f} ({call_dist:+.1f}%)",
    ]
    
    # Determine regime info
    if regime in ("short_gamma", "SHORT_GAMMA"):
        regime_label = "SHORT γ (Trending)"
        regime_color = COLORS["short_gamma"]
    elif regime in ("long_gamma", "LONG_GAMMA"):
        regime_label = "LONG γ (Mean-Reverting)"
        regime_color = COLORS["long_gamma"]
    else:
        regime_label = "Neutral"
        regime_color = COLORS["neutral"]
    
    return {
        "plotly": {
            "data": [{
                "type": "bar",
                "y": levels,
                "x": prices,
                "orientation": "h",
                "marker": {"color": colors},
                "text": labels,
                "textposition": "outside",
                "textfont": {"size": 11},
                "hovertemplate": "<b>%{y}</b><br>Price: $%{x:,.0f}<extra></extra>",
            }],
            "layout": {
                "title": {"text": f"{ticker} Key Gamma Levels", "font": {"size": 14}},
                "xaxis": {
                    "title": "Strike Price ($)",
                    "tickformat": "$,.0f",
                    "zeroline": False,
                },
                "yaxis": {
                    "tickfont": {"size": 11},
                },
                "height": 200,
                "margin": {"t": 50, "r": 100, "b": 50, "l": 140},
                "paper_bgcolor": "white",
                "plot_bgcolor": "white",
                "shapes": [
                    # Spot price vertical line
                    {
                        "type": "line",
                        "x0": spot_price,
                        "x1": spot_price,
                        "y0": -0.5,
                        "y1": 2.5,
                        "line": {"color": "#1f2937", "width": 2, "dash": "dash"},
                    },
                ],
                "annotations": [
                    {
                        "x": spot_price,
                        "y": 2.7,
                        "text": f"Spot ${spot_price:,.0f}",
                        "showarrow": False,
                        "font": {"size": 10, "color": "#1f2937"},
                    },
                    {
                        "x": 0.02,
                        "y": 1.12,
                        "xref": "paper",
                        "yref": "paper",
                        "text": f"Regime: {regime_label} ({confidence*100:.0f}%)",
                        "showarrow": False,
                        "font": {"size": 10, "color": regime_color, "weight": "bold"},
                        "align": "left",
                    },
                ],
            },
        },
        "type": "bar",
        "label": "Key Levels",
    }
