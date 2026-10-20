"""
Greeks Surface Tool - 3D Greeks Surface Modeling for Options Analysis

Fetches options chain data from Polygon and models the Greeks surfaces (delta, gamma,
theta, vega) across strikes and expirations. Generates 3D interactive charts for visualization.

Key Features:
- Polygon options chain fetching with full Greeks data
- 3D surface interpolation using scipy griddata for each Greek
- Interactive Plotly 3D surface charts (one per Greek)
- Strike cross-section charts (Greeks smile)
- Term structure charts (Greeks vs DTE)
- Comparative multi-Greek analysis

Analytics (when compute_analytics=True):
- ATM Greeks values for each metric
- Greeks term structure slopes
- Greeks ratios (gamma/delta, theta/gamma)
- Moneyness bucketing analysis
- Delta-neutral strike identification

Pattern: Follows exact patterns from volatility_surface_tool.py
"""
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict  # Required for Pydantic on Python < 3.12
from datetime import datetime, timedelta
import math
import logging
import numpy as np
from scipy.interpolate import griddata
from scipy import stats
from agents import function_tool

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)

# Supported Greeks for surface modeling
SUPPORTED_GREEKS = ['delta', 'gamma', 'theta', 'vega']


class PriceOverride(TypedDict):
    ticker: str
    price: float


async def _fetch_underlying_price(fmp_server, ticker: str) -> Optional[float]:
    """Fetch current price for underlying. Pattern from volatility_surface_tool.py:50"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)

        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)
        prices = data.get("prices") or data.get("closes") or data.get("close") or []

        if prices:
            return float(prices[-1])

        return None

    except Exception as e:
        logger.warning(f"Failed to fetch price for {ticker}: {e}")
        return None


async def _fetch_options_chain(polygon_server, underlying: str, max_dte: int = 120) -> List[Dict[str, Any]]:
    """
    Fetch complete options chain from Polygon with pagination.

    Uses shared helper to handle pagination and filter out 0-DTE options.
    Requires Greeks to be present for surface modeling.

    CRITICAL: Polygon MCP wraps responses as data["data"]["results"], not data["results"]
    """
    from core.agents.quant_tools.options_chain_helpers import fetch_options_chain_paginated
    return await fetch_options_chain_paginated(
        polygon_server, 
        underlying, 
        min_dte=1, 
        max_dte=max_dte,
        max_pages=8,  # More pages for full surface coverage
        limit_per_page=250,
        require_greeks=True  # Must have Greeks for surface modeling
    )


def _extract_greeks_points(chain_data: List[Dict[str, Any]], spot_price: float) -> Dict[str, Any]:
    """
    Extract Greeks surface data points from options chain.

    Uses Polygon structured data:
    - Delta: option["greeks"]["delta"]
    - Gamma: option["greeks"]["gamma"]
    - Theta: option["greeks"]["theta"]
    - Vega: option["greeks"]["vega"]
    - Strike: option["details"]["strike_price"]
    - Expiration: option["details"]["expiration_date"]
    - Type: option["details"]["contract_type"]
    - IV: option["implied_volatility"]
    - Volume: option["day"]["volume"]

    Returns:
        {
            'strikes': List[float],
            'expirations': List[datetime],
            'moneyness': List[float],  # strike/spot
            'dte': List[int],  # days to expiration
            'option_types': List[str],
            'deltas': List[float],
            'gammas': List[float],
            'thetas': List[float],
            'vegas': List[float],
            'ivs': List[float],
            'volumes': List[int],
            'count': int
        }
    """
    strikes = []
    expirations = []
    moneyness = []
    dte = []
    option_types = []
    deltas = []
    gammas = []
    thetas = []
    vegas = []
    ivs = []
    volumes = []
    open_interests = []

    for contract in chain_data:
        # Extract details (nested structure)
        details = contract.get('details', {})
        strike = details.get('strike_price')
        expiration_str = details.get('expiration_date')
        contract_type = details.get('contract_type')

        if not strike or not expiration_str or not contract_type:
            continue

        # Extract Greeks (required for this tool)
        greeks = contract.get('greeks', {})
        delta = greeks.get('delta')
        gamma = greeks.get('gamma')
        theta = greeks.get('theta')
        vega = greeks.get('vega')

        # Skip if missing critical Greeks
        if delta is None or gamma is None:
            continue

        # Parse expiration date
        try:
            expiry = datetime.strptime(expiration_str, '%Y-%m-%d')
        except ValueError:
            logger.debug(f"Failed to parse expiration date: {expiration_str}")
            continue

        days_to_expiry = (expiry - datetime.now()).days

        # Skip expired options
        if days_to_expiry < 0:
            continue

        # Extract IV for reference
        iv = contract.get('implied_volatility')

        # Extract volume for liquidity context
        day_data = contract.get('day', {})
        volume = day_data.get('volume', 0) or 0
        open_interest = contract.get('open_interest', 0) or 0

        # Store data point
        strikes.append(float(strike))
        expirations.append(expiry)
        moneyness.append(float(strike) / spot_price)
        dte.append(days_to_expiry)
        option_types.append(contract_type)
        deltas.append(float(delta))
        gammas.append(float(gamma) if gamma is not None else 0.0)
        thetas.append(float(theta) if theta is not None else 0.0)
        vegas.append(float(vega) if vega is not None else 0.0)
        ivs.append(float(iv) if iv is not None else 0.0)
        volumes.append(int(volume))
        open_interests.append(int(open_interest))

    if not strikes:
        return {
            'strikes': [],
            'expirations': [],
            'moneyness': [],
            'dte': [],
            'option_types': [],
            'deltas': [],
            'gammas': [],
            'thetas': [],
            'vegas': [],
            'ivs': [],
            'volumes': [],
            'open_interests': [],
            'count': 0
        }

    raw_count = len(strikes)
    iv_array = np.array(ivs, dtype=float)
    moneyness_array = np.array(moneyness, dtype=float)
    volume_array = np.array(volumes, dtype=int)
    oi_array = np.array(open_interests, dtype=int)

    near_atm_mask = (moneyness_array >= 0.7) & (moneyness_array <= 1.3)
    liquid_mask = (volume_array > 0) | (oi_array > 0)

    valid_iv = iv_array[np.isfinite(iv_array) & (iv_array > 0)]
    if valid_iv.size >= 12:
        q1, q3 = np.percentile(valid_iv, [25, 75])
        iqr = q3 - q1
        iv_lower = max(0.01, q1 - (1.5 * iqr))
        iv_upper = q3 + (1.5 * iqr)
        iv_mask = (iv_array >= iv_lower) & (iv_array <= iv_upper)
    else:
        iv_mask = np.ones_like(iv_array, dtype=bool)

    preferred_mask = near_atm_mask & liquid_mask & iv_mask
    fallback_mask = near_atm_mask & iv_mask

    if int(preferred_mask.sum()) >= 12:
        final_mask = preferred_mask
        filter_label = "near_atm_liquid"
    elif int(fallback_mask.sum()) >= 12:
        final_mask = fallback_mask
        filter_label = "near_atm"
    else:
        final_mask = iv_mask
        filter_label = "iv_outlier_only"

    if int(final_mask.sum()) < raw_count:
        logger.info(
            "Greek surface point filter kept %s/%s contracts (%s)",
            int(final_mask.sum()),
            raw_count,
            filter_label,
        )

        strikes = [value for value, keep in zip(strikes, final_mask) if keep]
        expirations = [value for value, keep in zip(expirations, final_mask) if keep]
        moneyness = [value for value, keep in zip(moneyness, final_mask) if keep]
        dte = [value for value, keep in zip(dte, final_mask) if keep]
        option_types = [value for value, keep in zip(option_types, final_mask) if keep]
        deltas = [value for value, keep in zip(deltas, final_mask) if keep]
        gammas = [value for value, keep in zip(gammas, final_mask) if keep]
        thetas = [value for value, keep in zip(thetas, final_mask) if keep]
        vegas = [value for value, keep in zip(vegas, final_mask) if keep]
        ivs = [value for value, keep in zip(ivs, final_mask) if keep]
        volumes = [value for value, keep in zip(volumes, final_mask) if keep]
        open_interests = [value for value, keep in zip(open_interests, final_mask) if keep]

    return {
        'strikes': strikes,
        'expirations': expirations,
        'moneyness': moneyness,
        'dte': dte,
        'option_types': option_types,
        'deltas': deltas,
        'gammas': gammas,
        'thetas': thetas,
        'vegas': vegas,
        'ivs': ivs,
        'volumes': volumes,
        'open_interests': open_interests,
        'count': len(strikes)
    }


def _build_greek_surface_grid(
    greeks_points: Dict[str, Any],
    greek_name: str,
    grid_resolution: int = 30
) -> Optional[Dict[str, Any]]:
    """
    Build interpolated 3D surface grid for a specific Greek using scipy griddata.

    Args:
        greeks_points: Dictionary with strikes, dte, and greek values
        greek_name: Which Greek to build surface for ('delta', 'gamma', 'theta', 'vega')
        grid_resolution: Number of points in each dimension

    Returns:
        {
            'strike_grid': 2D array,
            'dte_grid': 2D array,
            'greek_grid': 2D array (interpolated),
            'strike_range': [min, max],
            'dte_range': [min, max]
        }
    """
    strikes = np.array(greeks_points['strikes'])
    dte = np.array(greeks_points['dte'])
    
    # Map Greek name to data array
    greek_map = {
        'delta': 'deltas',
        'gamma': 'gammas',
        'theta': 'thetas',
        'vega': 'vegas'
    }
    
    if greek_name not in greek_map:
        logger.error(f"Unsupported Greek: {greek_name}")
        return None
    
    greek_values = np.array(greeks_points[greek_map[greek_name]])

    if len(strikes) < 4:
        logger.warning(f"Not enough data points for {greek_name} surface interpolation")
        return None

    # Filter out invalid values
    valid_mask = np.isfinite(greek_values)
    if valid_mask.sum() < 4:
        logger.warning(f"Not enough valid {greek_name} values for interpolation")
        return None
    
    strikes_valid = strikes[valid_mask]
    dte_valid = dte[valid_mask]
    greek_valid = greek_values[valid_mask]

    point_buckets: Dict[tuple[float, float], List[float]] = {}
    for strike, days, greek_value in zip(strikes_valid, dte_valid, greek_valid):
        point_buckets.setdefault((float(strike), float(days)), []).append(float(greek_value))

    unique_points = np.array(list(point_buckets.keys()), dtype=float)
    unique_greeks = np.array(
        [float(np.mean(bucket)) for bucket in point_buckets.values()],
        dtype=float,
    )

    if len(unique_points) < 4:
        logger.warning(f"Not enough unique {greek_name} strike/DTE points for interpolation")
        return None

    # Create grid
    strike_min, strike_max = unique_points[:, 0].min(), unique_points[:, 0].max()
    dte_min, dte_max = unique_points[:, 1].min(), unique_points[:, 1].max()

    strike_range = np.linspace(strike_min, strike_max, grid_resolution)
    dte_range = np.linspace(dte_min, dte_max, grid_resolution)

    strike_grid, dte_grid = np.meshgrid(strike_range, dte_range)

    greek_grid = None
    interpolation_methods = ("linear", "cubic", "nearest")
    for method in interpolation_methods:
        try:
            candidate = griddata(unique_points, unique_greeks, (strike_grid, dte_grid), method=method)
        except Exception as exc:
            logger.warning("%s surface interpolation failed with %s method: %s", greek_name, method, exc)
            continue

        if candidate is None or np.isnan(candidate).all():
            continue

        greek_grid = candidate
        break

    if greek_grid is None:
        logger.warning("Failed to build %s surface grid with all interpolation methods", greek_name)
        return None

    # Fill NaN values with nearest neighbor interpolation
    if np.isnan(greek_grid).any():
        mask = np.isnan(greek_grid)
        greek_grid[mask] = griddata(
            unique_points,
            unique_greeks,
            (strike_grid[mask], dte_grid[mask]),
            method='nearest'
        )

    return {
        'strike_grid': strike_grid,
        'dte_grid': dte_grid,
        'greek_grid': greek_grid,
        'strike_range': [float(strike_min), float(strike_max)],
        'dte_range': [int(dte_min), int(dte_max)]
    }


# =============================================================================
# ANALYTICS HELPERS
# =============================================================================

def _compute_greeks_analytics(
    greeks_points: Dict[str, Any],
    spot_price: float
) -> Dict[str, Any]:
    """
    Compute Greeks analytics: ATM values, term slopes, ratios.

    Args:
        greeks_points: Extracted Greeks data
        spot_price: Current underlying price

    Returns:
        {
            'atm_delta': float,
            'atm_gamma': float,
            'atm_theta': float,
            'atm_vega': float,
            'gamma_delta_ratio': float,
            'theta_gamma_ratio': float,
            'vega_theta_ratio': float,
            'delta_term_slope': float,
            'gamma_term_slope': float,
            'max_gamma_strike': float,  # Strike with highest gamma
            'delta_neutral_strike': float,  # Strike closest to delta=0.5
        }
    """
    moneyness = np.array(greeks_points['moneyness'])
    dte = np.array(greeks_points['dte'])
    deltas = np.array(greeks_points['deltas'])
    gammas = np.array(greeks_points['gammas'])
    thetas = np.array(greeks_points['thetas'])
    vegas = np.array(greeks_points['vegas'])
    strikes = np.array(greeks_points['strikes'])
    option_types = np.array(greeks_points['option_types'])

    analytics = {}

    # --- ATM Greeks (moneyness closest to 1.0) ---
    atm_mask = (moneyness >= 0.97) & (moneyness <= 1.03)
    
    if atm_mask.sum() > 0:
        # For calls, ATM delta should be ~0.5
        call_atm_mask = atm_mask & (option_types == 'call')
        if call_atm_mask.sum() > 0:
            analytics['atm_delta'] = float(np.median(deltas[call_atm_mask]))
        else:
            analytics['atm_delta'] = float(np.median(np.abs(deltas[atm_mask])))
        
        analytics['atm_gamma'] = float(np.median(gammas[atm_mask]))
        analytics['atm_theta'] = float(np.median(thetas[atm_mask]))
        analytics['atm_vega'] = float(np.median(vegas[atm_mask]))
    else:
        # Fallback to median of all
        analytics['atm_delta'] = float(np.median(np.abs(deltas)))
        analytics['atm_gamma'] = float(np.median(gammas))
        analytics['atm_theta'] = float(np.median(thetas))
        analytics['atm_vega'] = float(np.median(vegas))

    # --- Greeks Ratios ---
    if analytics['atm_delta'] != 0:
        analytics['gamma_delta_ratio'] = analytics['atm_gamma'] / abs(analytics['atm_delta'])
    else:
        analytics['gamma_delta_ratio'] = None

    if analytics['atm_gamma'] != 0:
        analytics['theta_gamma_ratio'] = abs(analytics['atm_theta']) / analytics['atm_gamma']
    else:
        analytics['theta_gamma_ratio'] = None

    if analytics['atm_theta'] != 0:
        analytics['vega_theta_ratio'] = analytics['atm_vega'] / abs(analytics['atm_theta'])
    else:
        analytics['vega_theta_ratio'] = None

    # --- Term Structure Slopes ---
    unique_dte = np.unique(dte)
    if len(unique_dte) >= 2:
        dte_gamma_pairs = []
        for d in unique_dte:
            dte_mask = (dte == d) & atm_mask
            if dte_mask.sum() > 0:
                dte_gamma_pairs.append((d, float(np.median(gammas[dte_mask]))))

        if len(dte_gamma_pairs) >= 2:
            dte_gamma_pairs.sort(key=lambda x: x[0])
            x = np.array([p[0] for p in dte_gamma_pairs])
            y = np.array([p[1] for p in dte_gamma_pairs])
            if len(x) >= 2:
                slope, _, _, _, _ = stats.linregress(x, y)
                analytics['gamma_term_slope'] = float(slope)
        else:
            analytics['gamma_term_slope'] = None
    else:
        analytics['gamma_term_slope'] = None

    # --- Max Gamma Strike ---
    if len(gammas) > 0:
        max_gamma_idx = np.argmax(gammas)
        analytics['max_gamma_strike'] = float(strikes[max_gamma_idx])
        analytics['max_gamma_value'] = float(gammas[max_gamma_idx])
    else:
        analytics['max_gamma_strike'] = None
        analytics['max_gamma_value'] = None

    # --- Delta Neutral Strike (for calls, find strike where delta ≈ 0.5) ---
    call_mask = option_types == 'call'
    if call_mask.sum() > 0:
        call_deltas = deltas[call_mask]
        call_strikes = strikes[call_mask]
        # Find closest to 0.5
        delta_diff = np.abs(call_deltas - 0.5)
        closest_idx = np.argmin(delta_diff)
        analytics['delta_neutral_strike'] = float(call_strikes[closest_idx])
        analytics['delta_neutral_value'] = float(call_deltas[closest_idx])
    else:
        analytics['delta_neutral_strike'] = None
        analytics['delta_neutral_value'] = None

    return analytics


# =============================================================================
# CHART BUILDERS
# =============================================================================

def _get_greek_colorscale(greek_name: str) -> List[List]:
    """Get premium colorscale for each Greek type."""
    colorscales = {
        'delta': [
            [0.0, '#d32f2f'],   # Deep red (negative/put delta)
            [0.25, '#f44336'],  # Red
            [0.45, '#ffeb3b'],  # Yellow (near zero)
            [0.55, '#ffeb3b'],  # Yellow (near zero)
            [0.75, '#4caf50'],  # Green
            [1.0, '#1b5e20']    # Deep green (positive/call delta)
        ],
        'gamma': [
            [0.0, '#e3f2fd'],   # Very light blue (low gamma)
            [0.2, '#90caf9'],   # Light blue
            [0.4, '#42a5f5'],   # Medium blue
            [0.6, '#1e88e5'],   # Blue
            [0.8, '#1565c0'],   # Dark blue
            [1.0, '#0d47a1']    # Deep blue (high gamma)
        ],
        'theta': [
            [0.0, '#1b5e20'],   # Deep green (less negative = good)
            [0.2, '#4caf50'],   # Green
            [0.4, '#ffeb3b'],   # Yellow
            [0.6, '#ff9800'],   # Orange
            [0.8, '#f44336'],   # Red
            [1.0, '#b71c1c']    # Deep red (more negative = bad)
        ],
        'vega': [
            [0.0, '#fff3e0'],   # Light orange (low vega)
            [0.2, '#ffcc80'],   # Pale orange
            [0.4, '#ffa726'],   # Orange
            [0.6, '#fb8c00'],   # Medium orange
            [0.8, '#e65100'],   # Dark orange
            [1.0, '#bf360c']    # Deep orange (high vega)
        ]
    }
    return colorscales.get(greek_name, colorscales['delta'])


def _get_greek_display_name(greek_name: str) -> str:
    """Get display name for Greek."""
    return greek_name.capitalize()


def _get_greek_units(greek_name: str) -> str:
    """Get units description for Greek."""
    units = {
        'delta': 'Δ',
        'gamma': 'Γ',
        'theta': 'Θ ($/day)',
        'vega': 'ν ($/1% IV)'
    }
    return units.get(greek_name, greek_name)


async def _build_greek_3d_surface_chart(
    underlying: str,
    spot_price: float,
    surface_grid: Dict[str, Any],
    greek_name: str,
    chart_id: str
) -> Optional[Dict[str, Any]]:
    """Build 3D Greek surface chart. Pattern from volatility_surface_tool.py"""
    try:
        import plotly.graph_objects as go

        strike_grid = surface_grid['strike_grid']
        dte_grid = surface_grid['dte_grid']
        greek_grid = surface_grid['greek_grid']

        # Scale factors for display
        scale_factors = {
            'delta': 1.0,      # Show as-is (-1 to 1)
            'gamma': 100.0,    # Scale up for visibility
            'theta': 1.0,      # Show as-is (negative values)
            'vega': 1.0        # Show as-is
        }
        scale = scale_factors.get(greek_name, 1.0)
        greek_display = greek_grid * scale

        logger.info(f"[{greek_name.upper()} SURFACE DEBUG] Strike range: {strike_grid.min():.2f} - {strike_grid.max():.2f}")
        logger.info(f"[{greek_name.upper()} SURFACE DEBUG] DTE range: {dte_grid.min():.0f} - {dte_grid.max():.0f}")
        logger.info(f"[{greek_name.upper()} SURFACE DEBUG] {greek_name} range: {greek_display.min():.4f} - {greek_display.max():.4f}")

        # Convert numpy arrays to lists for JSON serialization
        strike_grid_list = strike_grid.tolist()
        dte_grid_list = dte_grid.tolist()
        greek_grid_list = greek_display.tolist()

        colorscale = _get_greek_colorscale(greek_name)
        display_name = _get_greek_display_name(greek_name)
        units = _get_greek_units(greek_name)

        fig = go.Figure(data=[
            go.Surface(
                x=strike_grid_list,
                y=dte_grid_list,
                z=greek_grid_list,
                colorscale=colorscale,
                colorbar=dict(
                    title=dict(
                        text=units,
                        font=dict(size=13, family='Inter, sans-serif', color='#1e293b')
                    ),
                    tickfont=dict(size=11, family='Inter, sans-serif', color='#475569'),
                    thickness=20,
                    len=0.7,
                    x=1.02,
                    xpad=10,
                    outlinewidth=0
                ),
                contours=dict(
                    z=dict(
                        show=True,
                        usecolormap=True,
                        highlightcolor="white",
                        project=dict(z=True)
                    )
                ),
                lighting=dict(
                    ambient=0.6,
                    diffuse=0.8,
                    specular=0.4,
                    roughness=0.5,
                    fresnel=0.3
                ),
                lightposition=dict(x=1000, y=1000, z=2000),
                hovertemplate=f'<b>Strike:</b> $%{{x:.2f}}<br><b>DTE:</b> %{{y:.0f}} days<br><b>{display_name}:</b> %{{z:.4f}}<extra></extra>'
            )
        ])

        # Add ATM strike marker
        fig.add_trace(go.Scatter3d(
            x=np.full(20, spot_price),
            y=np.linspace(dte_grid.min(), dte_grid.max(), 20),
            z=np.full(20, greek_display.max() * 1.02),
            mode='lines',
            line=dict(color='#64748b', width=3, dash='dot'),
            name='ATM Strike',
            hovertemplate=f'<b>Spot: ${spot_price:.2f}</b><extra></extra>'
        ))

        fig.update_layout(
            title=dict(
                text=f'<b>{underlying}</b> {display_name} Surface',
                font=dict(size=18, family='Inter, sans-serif', color='#0f172a'),
                x=0.5,
                xanchor='center'
            ),
            scene=dict(
                xaxis=dict(
                    title=dict(text='Strike Price ($)', font=dict(size=13, color='#475569')),
                    backgroundcolor='#f8fafc',
                    gridcolor='#cbd5e1',
                    showbackground=True,
                    tickfont=dict(size=10, color='#64748b')
                ),
                yaxis=dict(
                    title=dict(text='Days to Expiration', font=dict(size=13, color='#475569')),
                    backgroundcolor='#f8fafc',
                    gridcolor='#cbd5e1',
                    showbackground=True,
                    tickfont=dict(size=10, color='#64748b')
                ),
                zaxis=dict(
                    title=dict(text=f'{display_name} ({units})', font=dict(size=13, color='#475569')),
                    backgroundcolor='#f8fafc',
                    gridcolor='#cbd5e1',
                    showbackground=True,
                    tickfont=dict(size=10, color='#64748b')
                ),
                camera=dict(
                    eye=dict(x=1.6, y=-1.6, z=1.4),
                    center=dict(x=0, y=0, z=-0.1)
                ),
                bgcolor='#ffffff'
            ),
            width=1000,
            height=700,
            showlegend=False,
            hovermode='closest',
            paper_bgcolor='#ffffff',
            plot_bgcolor='#ffffff',
            font=dict(family='Inter, sans-serif', color='#1e293b'),
            margin=dict(l=0, r=0, t=60, b=0)
        )

        chart_dict = fig.to_dict()

        return {
            'id': f'{chart_id}_{greek_name}_surface',
            'title': f'{underlying} {display_name} Surface',
            'plotly': chart_dict
        }

    except Exception as e:
        logger.error(f"Failed to build {greek_name} 3D surface chart: {e}", exc_info=True)
        return None


async def _build_greeks_smile_chart(
    underlying: str,
    spot_price: float,
    greeks_points: Dict[str, Any],
    chart_id: str,
    target_dte: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Build Greeks smile chart (all Greeks vs strike for a specific expiration).
    Shows delta, gamma, theta, vega in one combined view.
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        strikes = np.array(greeks_points['strikes'])
        dte = np.array(greeks_points['dte'])
        deltas = np.array(greeks_points['deltas'])
        gammas = np.array(greeks_points['gammas'])
        thetas = np.array(greeks_points['thetas'])
        vegas = np.array(greeks_points['vegas'])
        option_types = np.array(greeks_points['option_types'])

        # If no target_dte specified, use closest to 30 days
        if target_dte is None:
            unique_dte = np.unique(dte)
            target_dte = unique_dte[np.argmin(np.abs(unique_dte - 30))]

        # Filter to target expiration (±3 days tolerance)
        mask = np.abs(dte - target_dte) <= 3

        if mask.sum() < 3:
            logger.warning(f"Not enough data points for Greeks smile at {target_dte} DTE")
            return None

        smile_strikes = strikes[mask]
        smile_deltas = deltas[mask]
        smile_gammas = gammas[mask]
        smile_thetas = thetas[mask]
        smile_vegas = vegas[mask]
        smile_types = option_types[mask]

        # Sort by strike
        sort_idx = np.argsort(smile_strikes)
        smile_strikes = smile_strikes[sort_idx]
        smile_deltas = smile_deltas[sort_idx]
        smile_gammas = smile_gammas[sort_idx]
        smile_thetas = smile_thetas[sort_idx]
        smile_vegas = smile_vegas[sort_idx]

        # Create subplots (2x2 grid for each Greek)
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Delta', 'Gamma', 'Theta', 'Vega'),
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )

        # Delta
        fig.add_trace(go.Scatter(
            x=smile_strikes,
            y=smile_deltas,
            mode='lines+markers',
            name='Delta',
            marker=dict(size=6, color='#10b981'),
            line=dict(width=2, color='#10b981', shape='spline'),
            hovertemplate='<b>Strike:</b> $%{x:.2f}<br><b>Delta:</b> %{y:.4f}<extra></extra>'
        ), row=1, col=1)

        # Gamma
        fig.add_trace(go.Scatter(
            x=smile_strikes,
            y=smile_gammas,
            mode='lines+markers',
            name='Gamma',
            marker=dict(size=6, color='#3b82f6'),
            line=dict(width=2, color='#3b82f6', shape='spline'),
            hovertemplate='<b>Strike:</b> $%{x:.2f}<br><b>Gamma:</b> %{y:.4f}<extra></extra>'
        ), row=1, col=2)

        # Theta
        fig.add_trace(go.Scatter(
            x=smile_strikes,
            y=smile_thetas,
            mode='lines+markers',
            name='Theta',
            marker=dict(size=6, color='#f59e0b'),
            line=dict(width=2, color='#f59e0b', shape='spline'),
            hovertemplate='<b>Strike:</b> $%{x:.2f}<br><b>Theta:</b> $%{y:.4f}<extra></extra>'
        ), row=2, col=1)

        # Vega
        fig.add_trace(go.Scatter(
            x=smile_strikes,
            y=smile_vegas,
            mode='lines+markers',
            name='Vega',
            marker=dict(size=6, color='#8b5cf6'),
            line=dict(width=2, color='#8b5cf6', shape='spline'),
            hovertemplate='<b>Strike:</b> $%{x:.2f}<br><b>Vega:</b> $%{y:.4f}<extra></extra>'
        ), row=2, col=2)

        # Add ATM vertical lines to each subplot
        for row, col in [(1, 1), (1, 2), (2, 1), (2, 2)]:
            fig.add_vline(
                x=spot_price,
                line_dash='dash',
                line_color='#64748b',
                line_width=1,
                row=row, col=col
            )

        fig.update_layout(
            title=dict(
                text=f'<b>{underlying}</b> Greeks Smile · {target_dte} Days to Expiration',
                font=dict(size=17, family='Inter, sans-serif', color='#0f172a'),
                x=0.5,
                xanchor='center'
            ),
            width=1000,
            height=700,
            showlegend=False,
            paper_bgcolor='#ffffff',
            plot_bgcolor='#f8fafc',
            font=dict(family='Inter, sans-serif'),
            margin=dict(l=60, r=30, t=80, b=60)
        )

        # Update all x-axes
        fig.update_xaxes(
            title_text='Strike ($)',
            gridcolor='#e2e8f0',
            tickfont=dict(size=10, color='#64748b')
        )

        # Update y-axes with appropriate titles
        fig.update_yaxes(title_text='Delta (Δ)', row=1, col=1, gridcolor='#e2e8f0')
        fig.update_yaxes(title_text='Gamma (Γ)', row=1, col=2, gridcolor='#e2e8f0')
        fig.update_yaxes(title_text='Theta ($/day)', row=2, col=1, gridcolor='#e2e8f0')
        fig.update_yaxes(title_text='Vega ($/1%)', row=2, col=2, gridcolor='#e2e8f0')

        logger.info(f"[GREEKS SMILE DEBUG] Target DTE: {target_dte}, points: {mask.sum()}")

        return {
            'id': f'{chart_id}_greeks_smile',
            'title': f'{underlying} Greeks Smile ({target_dte} DTE)',
            'plotly': fig.to_dict()
        }

    except Exception as e:
        logger.error(f"Failed to build Greeks smile chart: {e}", exc_info=True)
        return None


async def _build_greeks_term_structure_chart(
    underlying: str,
    spot_price: float,
    greeks_points: Dict[str, Any],
    chart_id: str
) -> Optional[Dict[str, Any]]:
    """
    Build Greeks term structure chart showing ATM Greeks vs DTE.
    Shows how each Greek changes across expiration dates.
    """
    try:
        import plotly.graph_objects as go

        dte = np.array(greeks_points['dte'])
        moneyness = np.array(greeks_points['moneyness'])
        gammas = np.array(greeks_points['gammas'])
        thetas = np.array(greeks_points['thetas'])
        vegas = np.array(greeks_points['vegas'])

        # Get unique expiries
        unique_dtes = np.unique(dte)

        if len(unique_dtes) < 2:
            logger.warning("Not enough expiries for Greeks term structure chart")
            return None

        # ATM mask
        atm_mask = (moneyness >= 0.97) & (moneyness <= 1.03)

        # Compute ATM Greeks for each expiry
        term_dte = []
        term_gamma = []
        term_theta = []
        term_vega = []

        for d in sorted(unique_dtes):
            expiry_atm_mask = (dte == d) & atm_mask

            if expiry_atm_mask.sum() < 1:
                continue

            term_dte.append(d)
            term_gamma.append(float(np.median(gammas[expiry_atm_mask])))
            term_theta.append(float(np.median(thetas[expiry_atm_mask])))
            term_vega.append(float(np.median(vegas[expiry_atm_mask])))

        if len(term_dte) < 2:
            logger.warning("Not enough valid expiries for Greeks term structure")
            return None

        fig = go.Figure()

        # Gamma term structure (scaled for visibility)
        gamma_scaled = [g * 100 for g in term_gamma]
        fig.add_trace(go.Scatter(
            x=term_dte,
            y=gamma_scaled,
            mode='lines+markers',
            name='Gamma (×100)',
            marker=dict(size=10, color='#3b82f6', line=dict(width=1, color='white')),
            line=dict(width=3, color='#3b82f6', shape='spline'),
            hovertemplate='<b>DTE:</b> %{x} days<br><b>Gamma:</b> %{y:.4f}<extra></extra>'
        ))

        # Theta term structure
        fig.add_trace(go.Scatter(
            x=term_dte,
            y=term_theta,
            mode='lines+markers',
            name='Theta',
            marker=dict(size=10, color='#f59e0b', line=dict(width=1, color='white')),
            line=dict(width=3, color='#f59e0b', shape='spline'),
            yaxis='y2',
            hovertemplate='<b>DTE:</b> %{x} days<br><b>Theta:</b> $%{y:.4f}<extra></extra>'
        ))

        # Vega term structure
        fig.add_trace(go.Scatter(
            x=term_dte,
            y=term_vega,
            mode='lines+markers',
            name='Vega',
            marker=dict(size=10, color='#8b5cf6', line=dict(width=1, color='white')),
            line=dict(width=3, color='#8b5cf6', shape='spline'),
            yaxis='y3',
            hovertemplate='<b>DTE:</b> %{x} days<br><b>Vega:</b> $%{y:.4f}<extra></extra>'
        ))

        fig.update_layout(
            title=dict(
                text=f'<b>{underlying}</b> ATM Greeks Term Structure',
                font=dict(size=17, family='Inter, sans-serif', color='#0f172a'),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(
                title=dict(text='Days to Expiration', font=dict(size=13, color='#475569')),
                gridcolor='#e2e8f0',
                domain=[0.15, 0.85],
                tickfont=dict(size=11, color='#64748b')
            ),
            yaxis=dict(
                title=dict(text='Gamma (×100)', font=dict(size=12, color='#3b82f6')),
                tickfont=dict(color='#3b82f6'),
                gridcolor='#e2e8f0',
                side='left'
            ),
            yaxis2=dict(
                title=dict(text='Theta ($/day)', font=dict(size=12, color='#f59e0b')),
                tickfont=dict(color='#f59e0b'),
                anchor='free',
                overlaying='y',
                side='left',
                position=0
            ),
            yaxis3=dict(
                title=dict(text='Vega ($/1%)', font=dict(size=12, color='#8b5cf6')),
                tickfont=dict(color='#8b5cf6'),
                anchor='x',
                overlaying='y',
                side='right'
            ),
            width=900,
            height=500,
            hovermode='x unified',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1,
                font=dict(size=12),
                bgcolor='rgba(255, 255, 255, 0.9)',
                bordercolor='#cbd5e1',
                borderwidth=1
            ),
            paper_bgcolor='#ffffff',
            plot_bgcolor='#f8fafc',
            font=dict(family='Inter, sans-serif'),
            margin=dict(l=80, r=80, t=80, b=60)
        )

        logger.info(f"[GREEKS TERM] {underlying}: {len(term_dte)} expiries")

        return {
            'id': f'{chart_id}_greeks_term_structure',
            'title': f'{underlying} ATM Greeks Term Structure',
            'plotly': fig.to_dict()
        }

    except Exception as e:
        logger.error(f"Failed to build Greeks term structure chart: {e}", exc_info=True)
        return None


async def _model_greeks_surface_impl(
    underlying: str,
    underlying_price: Optional[float] = None,
    greeks_to_model: Optional[List[str]] = None,
    grid_resolution: int = 30,
    target_dte_for_smile: Optional[int] = None,
    compute_analytics: bool = False,
    max_dte: int = 120
) -> Dict[str, Any]:
    """Implementation of Greeks surface modeling."""
    # Default to all Greeks if none specified
    if greeks_to_model is None:
        greeks_to_model = SUPPORTED_GREEKS.copy()
    else:
        # Validate and normalize Greek names
        greeks_to_model = [g.lower() for g in greeks_to_model if g.lower() in SUPPORTED_GREEKS]
        if not greeks_to_model:
            return {
                'error': f'No valid Greeks specified. Supported: {SUPPORTED_GREEKS}',
                'underlying': underlying,
                'charts': []
            }

    try:
        fmp_server = FMPMarketDataServer()
        polygon_server = PolygonOptionsFuturesServer()

        try:
            await fmp_server.connect()
            await polygon_server.connect()

            # Step 1: Get underlying price
            if underlying_price is None:
                spot_price = await _fetch_underlying_price(fmp_server, underlying)
                if not spot_price:
                    return {
                        'error': f'Failed to fetch price for {underlying}',
                        'underlying': underlying,
                        'charts': []
                    }
            else:
                spot_price = underlying_price

            logger.info(f"Modeling Greeks surfaces for {underlying} at ${spot_price:.2f}")

            # Step 2: Fetch options chain with Greeks
            chain_data = await _fetch_options_chain(polygon_server, underlying, max_dte)

            if not chain_data:
                return {
                    'error': f'No options chain data available for {underlying}',
                    'underlying': underlying,
                    'spot_price': spot_price,
                    'charts': []
                }

            # Step 3: Extract Greeks data points
            greeks_points = _extract_greeks_points(chain_data, spot_price)

            if greeks_points['count'] < 10:
                return {
                    'error': f'Insufficient Greeks data points ({greeks_points["count"]}) for surface modeling',
                    'underlying': underlying,
                    'spot_price': spot_price,
                    'data_points': greeks_points['count'],
                    'charts': []
                }

            logger.info(f"Extracted {greeks_points['count']} Greeks data points")

            # Step 4: Build surface grids for each Greek
            surface_grids = {}
            surface_stats = {}

            for greek_name in greeks_to_model:
                surface_grid = _build_greek_surface_grid(greeks_points, greek_name, grid_resolution)
                if surface_grid:
                    surface_grids[greek_name] = surface_grid

                    # Calculate stats for this Greek
                    greek_array = np.array(greeks_points[f'{greek_name}s'])
                    surface_stats[greek_name] = {
                        'mean': float(greek_array.mean()),
                        'median': float(np.median(greek_array)),
                        'min': float(greek_array.min()),
                        'max': float(greek_array.max()),
                        'std': float(greek_array.std())
                    }

            if not surface_grids:
                return {
                    'error': 'Failed to build any Greeks surfaces',
                    'underlying': underlying,
                    'spot_price': spot_price,
                    'data_points': greeks_points['count'],
                    'charts': []
                }

            # Step 5: Build charts
            chart_id = f"greekssurf_{underlying.lower()}_{abs(hash(str(underlying))) & 0xFFFF:04x}"
            charts = []

            # 3D surface chart for each Greek
            for greek_name in greeks_to_model:
                if greek_name in surface_grids:
                    surface_chart = await _build_greek_3d_surface_chart(
                        underlying, spot_price, surface_grids[greek_name],
                        greek_name, chart_id
                    )
                    if surface_chart:
                        charts.append(surface_chart)

            # Combined Greeks smile chart
            smile_chart = await _build_greeks_smile_chart(
                underlying, spot_price, greeks_points, chart_id, target_dte_for_smile
            )
            if smile_chart:
                charts.append(smile_chart)

            # Greeks term structure chart
            term_chart = await _build_greeks_term_structure_chart(
                underlying, spot_price, greeks_points, chart_id
            )
            if term_chart:
                charts.append(term_chart)

            logger.info(f"Generated {len(charts)} Greeks surface charts")
            charts = wrap_plotly_charts(charts, default_type="greeks_surface_chart")

            # Build result summary (omit raw data arrays to prevent context overflow)
            # Raw data is embedded in the cached charts and can be retrieved via chart IDs
            result = {
                'underlying': underlying,
                'spot_price': spot_price,
                'greeks_modeled': list(surface_grids.keys()),
                'surface_stats': surface_stats,
                'grid_resolution': grid_resolution,
                'data_points': greeks_points['count'],
                'analysis_timestamp': datetime.now().isoformat(),
                # Summary stats instead of raw arrays
                'strike_range': [float(min(greeks_points['strikes'])), float(max(greeks_points['strikes']))],
                'dte_range': [int(min(greeks_points['dte'])), int(max(greeks_points['dte']))],
            }

            # Analytics (when compute_analytics=True)
            if compute_analytics:
                logger.info(f"Computing Greeks analytics for {underlying}")
                analytics = _compute_greeks_analytics(greeks_points, spot_price)
                result['analytics'] = analytics
                logger.info(f"Greeks analytics complete for {underlying}")

            # Final result with charts
            final_result = jsonify_results({
                'status': 'success',
                'results': result,
                'underlying': underlying,
                'charts': charts
            })

            logger.info(f"FINAL RESULT HAS {len(final_result.get('charts', []))} CHARTS")
            logger.info(f"Chart IDs: {[c.get('id', 'NO_ID') for c in final_result.get('charts', [])]}")

            return final_result

        finally:
            await fmp_server.cleanup()
            await polygon_server.cleanup()

    except Exception as e:
        logger.error(f"Greeks surface modeling failed: {e}", exc_info=True)
        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "... (error truncated)"
        return {
            'error': error_msg,
            'underlying': underlying,
            'charts': []
        }


async def model_greeks_surface_internal(
    underlying: str,
    underlying_price: Optional[float] = None,
    greeks_to_model: Optional[List[str]] = None,
    grid_resolution: int = 25,
    target_dte_for_smile: Optional[int] = 30,
    compute_analytics: bool = True,
    max_dte: int = 90
) -> Dict[str, Any]:
    """
    Internal callable for Canvas - Greeks surface modeling.
    
    Uses faster defaults (lower grid resolution, shorter max_dte) for interactive Canvas use.
    """
    return await _model_greeks_surface_impl(
        underlying=underlying,
        underlying_price=underlying_price,
        greeks_to_model=greeks_to_model,
        grid_resolution=grid_resolution,
        target_dte_for_smile=target_dte_for_smile,
        compute_analytics=compute_analytics,
        max_dte=max_dte,
    )


@function_tool
async def model_greeks_surface(
    underlying: str,
    underlying_price: Optional[float] = None,
    greeks_to_model: Optional[List[str]] = None,
    grid_resolution: int = 30,
    target_dte_for_smile: Optional[int] = None,
    compute_analytics: bool = False,
    max_dte: int = 120
) -> Dict[str, Any]:
    """
    Model 3D Greeks surfaces and generate interactive charts.

    Fetches complete options chain from Polygon, extracts Greeks data points,
    interpolates smooth 3D surfaces for each Greek, and generates multiple visualization charts.

    Args:
        underlying: Stock symbol (e.g., 'AAPL', 'SPY')
        underlying_price: Optional price override (fetched from FMP if not provided)
        greeks_to_model: List of Greeks to model ['delta', 'gamma', 'theta', 'vega'].
            Default: all four Greeks
        grid_resolution: Number of grid points for surface interpolation (default: 30)
        target_dte_for_smile: Days to expiration for Greeks smile chart (default: ~30 days)
        compute_analytics: Enable analytics (ATM Greeks, ratios, term slopes)
        max_dte: Maximum days to expiration to fetch (default: 120)

    Returns:
        Dictionary with surface_stats, data_points, charts, and analytics (when enabled)
    """
    return await _model_greeks_surface_impl(
        underlying=underlying,
        underlying_price=underlying_price,
        greeks_to_model=greeks_to_model,
        grid_resolution=grid_resolution,
        target_dte_for_smile=target_dte_for_smile,
        compute_analytics=compute_analytics,
        max_dte=max_dte,
    )
