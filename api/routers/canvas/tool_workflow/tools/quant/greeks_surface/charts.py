"""Chart builders for Greeks Surface Canvas tool."""
from typing import Dict, List, Any, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


def build_greek_3d_surface(
    ticker: str,
    spot_price: float,
    greek_name: str,
    surface_grid: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build 3D surface chart for a specific Greek."""
    try:
        strike_grid = surface_grid['strike_grid']
        dte_grid = surface_grid['dte_grid']
        greek_grid = surface_grid['greek_grid']
        
        # Scale factors for display
        scale_factors = {'delta': 1.0, 'gamma': 100.0, 'theta': 1.0, 'vega': 1.0}
        scale = scale_factors.get(greek_name, 1.0)
        
        # Scale the grid
        greek_display = [[v * scale for v in row] for row in greek_grid]
        
        # Colorscales
        colorscales = {
            'delta': [[0, '#d32f2f'], [0.5, '#ffeb3b'], [1, '#1b5e20']],
            'gamma': [[0, '#e3f2fd'], [0.5, '#42a5f5'], [1, '#0d47a1']],
            'theta': [[0, '#1b5e20'], [0.5, '#ffeb3b'], [1, '#b71c1c']],
            'vega': [[0, '#fff3e0'], [0.5, '#ffa726'], [1, '#bf360c']],
        }
        
        units = {'delta': 'Δ', 'gamma': 'Γ (×100)', 'theta': 'Θ', 'vega': 'ν'}
        display_name = greek_name.capitalize()
        
        return {
            "plotly": {
                "data": [{
                    "type": "surface",
                    "x": strike_grid,
                    "y": dte_grid,
                    "z": greek_display,
                    "colorscale": colorscales.get(greek_name, colorscales['delta']),
                    "colorbar": {"title": {"text": units.get(greek_name, greek_name)}},
                    "hovertemplate": f"<b>Strike:</b> $%{{x:.2f}}<br><b>DTE:</b> %{{y:.0f}}<br><b>{display_name}:</b> %{{z:.4f}}<extra></extra>",
                }],
                "layout": {
                    "title": {"text": f"{ticker} {display_name} Surface", "x": 0.5},
                    "scene": {
                        "xaxis": {"title": "Strike ($)"},
                        "yaxis": {"title": "Days to Expiration"},
                        "zaxis": {"title": f"{display_name} ({units.get(greek_name, '')})"},
                        "camera": {"eye": {"x": 1.5, "y": -1.5, "z": 1.2}},
                    },
                    "height": 500,
                    "margin": {"l": 0, "r": 0, "t": 50, "b": 0},
                },
            },
            "type": f"{greek_name}_surface",
            "label": f"{ticker} {display_name} Surface",
        }
    except Exception as e:
        logger.error(f"Failed to build {greek_name} surface chart: {e}")
        return None


def build_greeks_smile(
    ticker: str,
    spot_price: float,
    greeks_points: Dict[str, Any],
    target_dte: int = 30,
) -> Optional[Dict[str, Any]]:
    """Build Greeks smile chart (all Greeks vs strike at a specific DTE)."""
    try:
        strikes = np.array(greeks_points['strikes'])
        dte = np.array(greeks_points['dte'])
        deltas = np.array(greeks_points['deltas'])
        gammas = np.array(greeks_points['gammas'])
        thetas = np.array(greeks_points['thetas'])
        vegas = np.array(greeks_points['vegas'])
        
        # Filter to target DTE (±5 days tolerance)
        mask = np.abs(dte - target_dte) <= 5
        if mask.sum() < 3:
            return None
        
        # Sort by strike
        sort_idx = np.argsort(strikes[mask])
        smile_strikes = strikes[mask][sort_idx].tolist()
        smile_deltas = deltas[mask][sort_idx].tolist()
        smile_gammas = gammas[mask][sort_idx].tolist()
        smile_thetas = thetas[mask][sort_idx].tolist()
        smile_vegas = vegas[mask][sort_idx].tolist()
        
        return {
            "plotly": {
                "data": [
                    {"type": "scatter", "x": smile_strikes, "y": smile_deltas, "name": "Delta", 
                     "mode": "lines+markers", "line": {"color": "#10b981"}, "yaxis": "y1"},
                    {"type": "scatter", "x": smile_strikes, "y": smile_gammas, "name": "Gamma",
                     "mode": "lines+markers", "line": {"color": "#3b82f6"}, "yaxis": "y2"},
                    {"type": "scatter", "x": smile_strikes, "y": smile_thetas, "name": "Theta",
                     "mode": "lines+markers", "line": {"color": "#f59e0b"}, "yaxis": "y3"},
                    {"type": "scatter", "x": smile_strikes, "y": smile_vegas, "name": "Vega",
                     "mode": "lines+markers", "line": {"color": "#8b5cf6"}, "yaxis": "y4"},
                ],
                "layout": {
                    "title": {"text": f"{ticker} Greeks Smile ({target_dte} DTE)", "x": 0.5},
                    "xaxis": {"title": "Strike ($)", "domain": [0.1, 0.9]},
                    "yaxis": {"title": "Delta", "titlefont": {"color": "#10b981"}, "side": "left", "position": 0},
                    "yaxis2": {"title": "Gamma", "titlefont": {"color": "#3b82f6"}, "overlaying": "y", "side": "left", "position": 0.05, "anchor": "free"},
                    "yaxis3": {"title": "Theta", "titlefont": {"color": "#f59e0b"}, "overlaying": "y", "side": "right", "position": 0.95, "anchor": "free"},
                    "yaxis4": {"title": "Vega", "titlefont": {"color": "#8b5cf6"}, "overlaying": "y", "side": "right"},
                    "legend": {"orientation": "h", "y": 1.1},
                    "height": 400,
                    "shapes": [{"type": "line", "x0": spot_price, "x1": spot_price, "y0": 0, "y1": 1, "yref": "paper", "line": {"dash": "dash", "color": "#9ca3af"}}],
                },
            },
            "type": "greeks_smile",
            "label": f"{ticker} Greeks Smile",
        }
    except Exception as e:
        logger.error(f"Failed to build Greeks smile chart: {e}")
        return None


def build_greeks_term_structure(
    ticker: str,
    spot_price: float,
    greeks_points: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build ATM Greeks term structure chart."""
    try:
        dte = np.array(greeks_points['dte'])
        moneyness = np.array(greeks_points['moneyness'])
        gammas = np.array(greeks_points['gammas'])
        thetas = np.array(greeks_points['thetas'])
        vegas = np.array(greeks_points['vegas'])
        
        # ATM mask
        atm_mask = (moneyness >= 0.97) & (moneyness <= 1.03)
        unique_dtes = np.unique(dte)
        
        term_dte = []
        term_gamma = []
        term_theta = []
        term_vega = []
        
        for d in sorted(unique_dtes):
            mask = (dte == d) & atm_mask
            if mask.sum() > 0:
                term_dte.append(int(d))
                term_gamma.append(float(np.median(gammas[mask]) * 100))
                term_theta.append(float(np.median(thetas[mask])))
                term_vega.append(float(np.median(vegas[mask])))
        
        if len(term_dte) < 2:
            return None
        
        return {
            "plotly": {
                "data": [
                    {"type": "scatter", "x": term_dte, "y": term_gamma, "name": "Gamma (×100)",
                     "mode": "lines+markers", "line": {"color": "#3b82f6", "width": 2}},
                    {"type": "scatter", "x": term_dte, "y": term_theta, "name": "Theta",
                     "mode": "lines+markers", "line": {"color": "#f59e0b", "width": 2}, "yaxis": "y2"},
                    {"type": "scatter", "x": term_dte, "y": term_vega, "name": "Vega",
                     "mode": "lines+markers", "line": {"color": "#8b5cf6", "width": 2}, "yaxis": "y3"},
                ],
                "layout": {
                    "title": {"text": f"{ticker} ATM Greeks Term Structure", "x": 0.5},
                    "xaxis": {"title": "Days to Expiration"},
                    "yaxis": {"title": "Gamma (×100)", "titlefont": {"color": "#3b82f6"}},
                    "yaxis2": {"title": "Theta", "titlefont": {"color": "#f59e0b"}, "overlaying": "y", "side": "right"},
                    "yaxis3": {"title": "Vega", "titlefont": {"color": "#8b5cf6"}, "overlaying": "y", "side": "right", "position": 0.95, "anchor": "free"},
                    "legend": {"orientation": "h", "y": 1.1},
                    "height": 350,
                },
            },
            "type": "greeks_term_structure",
            "label": f"{ticker} Term Structure",
        }
    except Exception as e:
        logger.error(f"Failed to build term structure chart: {e}")
        return None
