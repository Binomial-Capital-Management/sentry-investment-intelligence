"""Volatility Surface Chart Builders for Canvas.

Builds Plotly chart configurations for 3D surface, IV smile, and term structure.
"""

from typing import Dict, List, Any, Optional
import numpy as np


def build_3d_surface_chart(
    underlying: str,
    spot_price: float,
    surface_grid: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build 3D volatility surface chart.
    
    Args:
        underlying: Ticker symbol
        spot_price: Current stock price
        surface_grid: Dict with strike_grid, dte_grid, iv_grid arrays
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not surface_grid:
        return None
    
    strike_grid = surface_grid.get('strike_grid')
    dte_grid = surface_grid.get('dte_grid')
    iv_grid = surface_grid.get('iv_grid')
    
    if strike_grid is None or dte_grid is None or iv_grid is None:
        return None
    
    # Convert to numpy if needed
    if not isinstance(strike_grid, np.ndarray):
        strike_grid = np.array(strike_grid)
    if not isinstance(dte_grid, np.ndarray):
        dte_grid = np.array(dte_grid)
    if not isinstance(iv_grid, np.ndarray):
        iv_grid = np.array(iv_grid)
    
    # Convert IV to percentage
    iv_pct = iv_grid * 100 if iv_grid.max() <= 1 else iv_grid
    
    # Convert to lists for JSON serialization
    strike_list = strike_grid.tolist()
    dte_list = dte_grid.tolist()
    iv_list = iv_pct.tolist()
    
    # Colorscale
    colorscale = [
        [0.0, '#0d47a1'],
        [0.2, '#1976d2'],
        [0.4, '#42a5f5'],
        [0.5, '#4fc3f7'],
        [0.6, '#fdd835'],
        [0.8, '#fb8c00'],
        [1.0, '#d32f2f']
    ]
    
    return {
        "plotly": {
            "data": [{
                "type": "surface",
                "x": strike_list,
                "y": dte_list,
                "z": iv_list,
                "colorscale": colorscale,
                "colorbar": {
                    "title": {"text": "IV (%)", "font": {"size": 12}},
                    "thickness": 15,
                    "len": 0.6,
                },
                "hovertemplate": "<b>Strike:</b> $%{x:.0f}<br><b>DTE:</b> %{y:.0f}<br><b>IV:</b> %{z:.1f}%<extra></extra>",
            }],
            "layout": {
                "title": {"text": f"{underlying} Volatility Surface", "font": {"size": 14}},
                "scene": {
                    "xaxis": {"title": "Strike ($)", "gridcolor": "#e5e7eb"},
                    "yaxis": {"title": "Days to Expiry", "gridcolor": "#e5e7eb"},
                    "zaxis": {"title": "IV (%)", "gridcolor": "#e5e7eb"},
                    "camera": {"eye": {"x": 1.5, "y": -1.5, "z": 1.2}},
                    "bgcolor": "white",
                },
                "paper_bgcolor": "white",
                "margin": {"t": 50, "r": 30, "b": 30, "l": 30},
            }
        },
        "type": "3d_surface",
        "label": "3D Surface",
    }


def build_iv_smile_chart(
    underlying: str,
    spot_price: float,
    iv_points: Dict[str, Any],
    target_dte: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Build IV smile chart (IV vs strike for a specific expiration).
    
    Args:
        underlying: Ticker symbol
        spot_price: Current stock price
        iv_points: Dict with strikes, dtes, ivs arrays
        target_dte: Target DTE to show, defaults to nearest
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not iv_points:
        return None
    
    strikes = iv_points.get('strikes', [])
    dtes = iv_points.get('dtes', [])
    ivs = iv_points.get('ivs', [])
    
    if not strikes or not dtes or not ivs:
        return None
    
    # Convert to numpy
    strikes = np.array(strikes)
    dtes = np.array(dtes)
    ivs = np.array(ivs)
    
    # Find unique DTEs and pick target
    unique_dtes = np.unique(dtes)
    if target_dte is None:
        target_dte = unique_dtes[len(unique_dtes) // 4] if len(unique_dtes) > 4 else unique_dtes[0]
    else:
        target_dte = unique_dtes[np.argmin(np.abs(unique_dtes - target_dte))]
    
    # Filter to target DTE
    mask = dtes == target_dte
    smile_strikes = strikes[mask]
    smile_ivs = ivs[mask] * 100 if ivs[mask].max() <= 1 else ivs[mask]
    
    # Sort by strike
    sort_idx = np.argsort(smile_strikes)
    smile_strikes = smile_strikes[sort_idx]
    smile_ivs = smile_ivs[sort_idx]
    
    return {
        "plotly": {
            "data": [{
                "type": "scatter",
                "x": smile_strikes.tolist(),
                "y": smile_ivs.tolist(),
                "mode": "lines+markers",
                "line": {"color": "#3b82f6", "width": 2},
                "marker": {"size": 6, "color": "#3b82f6"},
                "name": f"{int(target_dte)}D",
                "hovertemplate": "<b>Strike:</b> $%{x:.0f}<br><b>IV:</b> %{y:.1f}%<extra></extra>",
            }, {
                "type": "scatter",
                "x": [spot_price],
                "y": [float(np.interp(spot_price, smile_strikes, smile_ivs))],
                "mode": "markers",
                "marker": {"size": 12, "color": "#ef4444", "symbol": "diamond"},
                "name": "ATM",
                "hovertemplate": f"<b>Spot:</b> ${spot_price:.2f}<extra></extra>",
            }],
            "layout": {
                "title": {"text": f"{underlying} IV Smile ({int(target_dte)}D)", "font": {"size": 14}},
                "xaxis": {"title": "Strike ($)", "gridcolor": "#e5e7eb", "zeroline": False},
                "yaxis": {"title": "Implied Volatility (%)", "gridcolor": "#e5e7eb"},
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "showlegend": False,
                "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
            }
        },
        "type": "iv_smile",
        "label": "IV Smile",
    }


def build_term_structure_chart(
    underlying: str,
    spot_price: float,
    iv_points: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build term structure chart (ATM IV vs DTE).
    
    Args:
        underlying: Ticker symbol
        spot_price: Current stock price
        iv_points: Dict with strikes, dtes, ivs arrays
        
    Returns:
        Plotly chart configuration dict or None if no data
    """
    if not iv_points:
        return None
    
    strikes = iv_points.get('strikes', [])
    dtes = iv_points.get('dtes', [])
    ivs = iv_points.get('ivs', [])
    
    if not strikes or not dtes or not ivs:
        return None
    
    # Convert to numpy
    strikes = np.array(strikes)
    dtes = np.array(dtes)
    ivs = np.array(ivs)
    
    # For each unique DTE, find ATM IV (closest to spot)
    unique_dtes = np.unique(dtes)
    atm_ivs = []
    valid_dtes = []
    
    for dte in unique_dtes:
        mask = dtes == dte
        dte_strikes = strikes[mask]
        dte_ivs = ivs[mask]
        
        if len(dte_strikes) == 0:
            continue
            
        # Find closest to ATM
        atm_idx = np.argmin(np.abs(dte_strikes - spot_price))
        atm_iv = dte_ivs[atm_idx] * 100 if dte_ivs[atm_idx] <= 1 else dte_ivs[atm_idx]
        
        atm_ivs.append(float(atm_iv))
        valid_dtes.append(float(dte))
    
    if not valid_dtes:
        return None
    
    return {
        "plotly": {
            "data": [{
                "type": "scatter",
                "x": valid_dtes,
                "y": atm_ivs,
                "mode": "lines+markers",
                "line": {"color": "#8b5cf6", "width": 2},
                "marker": {"size": 8, "color": "#8b5cf6"},
                "name": "ATM IV",
                "hovertemplate": "<b>DTE:</b> %{x:.0f}<br><b>IV:</b> %{y:.1f}%<extra></extra>",
            }],
            "layout": {
                "title": {"text": f"{underlying} Term Structure", "font": {"size": 14}},
                "xaxis": {"title": "Days to Expiration", "gridcolor": "#e5e7eb", "zeroline": False},
                "yaxis": {"title": "ATM Implied Volatility (%)", "gridcolor": "#e5e7eb"},
                "plot_bgcolor": "white",
                "paper_bgcolor": "white",
                "showlegend": False,
                "margin": {"t": 50, "r": 30, "b": 50, "l": 60},
            }
        },
        "type": "term_structure",
        "label": "Term Structure",
    }
