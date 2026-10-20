"""
Volatility Surface Tool - 3D Implied Volatility Surface Modeling + Alpha Analytics

Fetches options chain data from Polygon and models the implied volatility (IV) surface
across strikes and expirations. Generates 3D interactive charts for visualization.

Key Features:
- Polygon options chain fetching for complete IV data (including Greeks)
- 3D surface interpolation using scipy griddata
- Interactive Plotly 3D surface charts
- IV smile (strike cross-section) charts
- Term structure (time cross-section) charts

Alpha Analytics (when compute_analytics=True):
- ATM IV, term slope, put/call skew metrics
- Realized volatility (10d/20d windows) from price history
- Vol risk premium (IV - RV)
- Cross-sectional ranking vs peers (optional)
- Event context (earnings proximity)

Pattern: Follows exact patterns from delta_exposure_tool.py and pca_analysis_tool.py
"""
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict  # Required for Pydantic on Python < 3.12
from datetime import datetime, timedelta
import math
import logging
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from scipy import stats
from agents import function_tool

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
from core.agents.binomial_hash import bh_raw_mode
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)

# Thread-safe cache for large chart data (prevents context overflow in SDK agent)
# Key: unique chart cache ID, Value: list of full chart dictionaries
_CHART_CACHE: Dict[str, List[Dict[str, Any]]] = {}


class PriceOverride(TypedDict):
    ticker: str
    price: float


async def _fetch_underlying_price(fmp_server, ticker: str) -> Optional[float]:
    """Fetch current price for underlying. Pattern from delta_exposure_tool.py:35"""
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

    CRITICAL: Polygon MCP wraps responses as data["data"]["results"], not data["results"]
    See: POLYGON_OPTIONS_DATA_STRUCTURE.md lines 99-108
    """
    from core.agents.quant_tools.options_chain_helpers import fetch_options_chain_paginated
    return await fetch_options_chain_paginated(
        polygon_server, 
        underlying, 
        min_dte=1, 
        max_dte=max_dte,
        max_pages=8,  # More pages for vol surface (need full chain)
        limit_per_page=250
    )


def _parse_option_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Parse OCC format option ticker: O:AAPL250117C00150000

    Returns:
        {
            'underlying': 'AAPL',
            'expiry': datetime,
            'option_type': 'call' or 'put',
            'strike': float,
            'days_to_expiry': int
        }
    """
    try:
        if not ticker.startswith('O:'):
            return None

        # Remove O: prefix
        ticker = ticker[2:]

        # Extract components
        # Format: TICKER + YYMMDD + C/P + STRIKE (8 digits)
        if len(ticker) < 15:  # Minimum length
            return None

        # Find where date starts (6 digits)
        # Work backwards: last 8 chars are strike, before that is C/P, before that is date
        strike_str = ticker[-8:]  # Last 8 digits
        option_type_char = ticker[-9]  # C or P
        date_str = ticker[-15:-9]  # YYMMDD
        underlying = ticker[:-15]  # Everything before date

        # Parse components
        expiry = datetime.strptime(date_str, '%y%m%d')
        option_type = 'call' if option_type_char.upper() == 'C' else 'put'
        strike = int(strike_str) / 1000.0  # Strike in thousandths

        days_to_expiry = (expiry - datetime.now()).days

        return {
            'underlying': underlying,
            'expiry': expiry,
            'option_type': option_type,
            'strike': strike,
            'days_to_expiry': days_to_expiry
        }

    except Exception as e:
        logger.debug(f"Failed to parse option ticker {ticker}: {e}")
        return None


def _extract_iv_points(chain_data: List[Dict[str, Any]], spot_price: float) -> Dict[str, Any]:
    """
    Extract IV surface data points from options chain, including Greeks.

    Uses Polygon structured data (POLYGON_OPTIONS_DATA_STRUCTURE.md lines 132-157):
    - IV: option.get("implied_volatility")
    - Strike: option["details"]["strike_price"]
    - Expiration: option["details"]["expiration_date"]
    - Type: option["details"]["contract_type"]
    - Delta: option["greeks"]["delta"]
    - Volume: option["day"]["volume"]

    Returns:
        {
            'strikes': List[float],
            'expirations': List[datetime],
            'ivs': List[float],
            'moneyness': List[float],  # strike/spot
            'dte': List[int],  # days to expiration
            'option_types': List[str],
            'deltas': List[float],  # Option delta from Polygon
            'volumes': List[int],   # Daily volume for liquidity
        }
    """
    strikes = []
    expirations = []
    ivs = []
    moneyness = []
    dte = []
    option_types = []
    deltas = []
    volumes = []
    open_interests = []

    for contract in chain_data:
        # Extract IV (direct field)
        iv = contract.get('implied_volatility')
        if not iv or iv <= 0:
            continue

        # Extract details (nested structure)
        details = contract.get('details', {})
        strike = details.get('strike_price')
        expiration_str = details.get('expiration_date')
        contract_type = details.get('contract_type')

        if not strike or not expiration_str or not contract_type:
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

        # Extract Greeks (delta for bucketing)
        greeks = contract.get('greeks', {})
        delta = greeks.get('delta')

        # Extract volume for liquidity filtering
        day_data = contract.get('day', {})
        volume = day_data.get('volume', 0) or 0
        open_interest = contract.get('open_interest', 0) or 0

        # Store data point
        strikes.append(float(strike))
        expirations.append(expiry)
        ivs.append(float(iv))
        moneyness.append(float(strike) / spot_price)
        dte.append(days_to_expiry)
        option_types.append(contract_type)
        deltas.append(float(delta) if delta is not None else None)
        volumes.append(int(volume))
        open_interests.append(int(open_interest))

    if not strikes:
        return {
            'strikes': [],
            'expirations': [],
            'ivs': [],
            'moneyness': [],
            'dte': [],
            'option_types': [],
            'deltas': [],
            'volumes': [],
            'open_interests': [],
            'count': 0
        }

    raw_count = len(strikes)
    iv_array = np.array(ivs, dtype=float)
    moneyness_array = np.array(moneyness, dtype=float)
    volume_array = np.array(volumes, dtype=int)
    oi_array = np.array(open_interests, dtype=int)

    # Prefer liquid, near-ATM contracts for a stable surface. Deep ITM/OTM contracts
    # and zero-liquidity quotes tend to produce vertical walls and interpolation spikes.
    near_atm_mask = (moneyness_array >= 0.7) & (moneyness_array <= 1.3)
    liquid_mask = (volume_array > 0) | (oi_array > 0)

    valid_iv = iv_array[np.isfinite(iv_array)]
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
            "Vol surface point filter kept %s/%s contracts (%s)",
            int(final_mask.sum()),
            raw_count,
            filter_label,
        )

        strikes = [value for value, keep in zip(strikes, final_mask) if keep]
        expirations = [value for value, keep in zip(expirations, final_mask) if keep]
        ivs = [value for value, keep in zip(ivs, final_mask) if keep]
        moneyness = [value for value, keep in zip(moneyness, final_mask) if keep]
        dte = [value for value, keep in zip(dte, final_mask) if keep]
        option_types = [value for value, keep in zip(option_types, final_mask) if keep]
        deltas = [value for value, keep in zip(deltas, final_mask) if keep]
        volumes = [value for value, keep in zip(volumes, final_mask) if keep]
        open_interests = [value for value, keep in zip(open_interests, final_mask) if keep]

    return {
        'strikes': strikes,
        'expirations': expirations,
        'ivs': ivs,
        'moneyness': moneyness,
        'dte': dte,
        'option_types': option_types,
        'deltas': deltas,
        'volumes': volumes,
        'open_interests': open_interests,
        'count': len(strikes)
    }


def _build_surface_grid(iv_points: Dict[str, Any], grid_resolution: int = 30) -> Dict[str, Any]:
    """
    Build interpolated 3D surface grid using scipy griddata.

    Args:
        iv_points: Dictionary with strikes, dte, ivs arrays
        grid_resolution: Number of points in each dimension

    Returns:
        {
            'strike_grid': 2D array,
            'dte_grid': 2D array,
            'iv_grid': 2D array (interpolated),
            'strike_range': [min, max],
            'dte_range': [min, max]
        }
    """
    strikes = np.array(iv_points['strikes'], dtype=float)
    dte = np.array(iv_points['dte'], dtype=float)
    ivs = np.array(iv_points['ivs'], dtype=float)

    if len(strikes) < 4:
        logger.warning("Not enough data points for surface interpolation")
        return None

    # Deduplicate identical strike/DTE coordinates so interpolation has one value per point.
    # Polygon chains can contain repeated coordinates across contracts with noisy IVs.
    point_buckets: Dict[tuple[float, float], List[float]] = {}
    for strike, days, iv in zip(strikes, dte, ivs):
        point_buckets.setdefault((float(strike), float(days)), []).append(float(iv))

    unique_points = np.array(list(point_buckets.keys()), dtype=float)
    unique_ivs = np.array(
        [float(np.mean(bucket)) for bucket in point_buckets.values()],
        dtype=float,
    )

    if len(unique_points) < 4:
        logger.warning("Not enough unique strike/DTE points for surface interpolation")
        return None

    # Create grid
    strike_min, strike_max = unique_points[:, 0].min(), unique_points[:, 0].max()
    dte_min, dte_max = unique_points[:, 1].min(), unique_points[:, 1].max()

    strike_range = np.linspace(strike_min, strike_max, grid_resolution)
    dte_range = np.linspace(dte_min, dte_max, grid_resolution)

    strike_grid, dte_grid = np.meshgrid(strike_range, dte_range)

    # Interpolate IV surface. Cubic is best visually but often fails on sparse or
    # irregular chains, so fall back progressively to preserve chartability.
    iv_grid = None
    interpolation_methods = ("linear", "cubic", "nearest")
    for method in interpolation_methods:
        try:
            candidate = griddata(unique_points, unique_ivs, (strike_grid, dte_grid), method=method)
        except Exception as exc:
            logger.warning("Surface interpolation failed with %s method: %s", method, exc)
            continue

        if candidate is None:
            continue

        if np.isnan(candidate).all():
            logger.warning("Surface interpolation produced all-NaN grid with %s method", method)
            continue

        iv_grid = candidate
        logger.info("Surface interpolation succeeded with %s method", method)
        break

    if iv_grid is None:
        logger.warning("Failed to build volatility surface grid with all interpolation methods")
        return None

    # Fill any remaining holes with nearest-neighbor interpolation.
    if np.isnan(iv_grid).any():
        mask = np.isnan(iv_grid)
        nearest_fill = griddata(
            unique_points,
            unique_ivs,
            (strike_grid[mask], dte_grid[mask]),
            method='nearest',
        )
        if nearest_fill is not None:
            iv_grid[mask] = nearest_fill

    if np.isnan(iv_grid).all():
        logger.warning("Surface grid remained all-NaN after nearest-neighbor fill")
        return None

    iv_grid = _smooth_surface_grid(iv_grid, unique_ivs)

    return {
        'strike_grid': strike_grid,
        'dte_grid': dte_grid,
        'iv_grid': iv_grid,
        'strike_range': [strike_min, strike_max],
        'dte_range': [dte_min, dte_max]
    }


def _smooth_surface_grid(iv_grid: np.ndarray, observed_ivs: np.ndarray) -> np.ndarray:
    """
    Apply moderate smoothing to reduce interpolation spikes without flattening the smile.

    Cubic interpolation can overshoot on sparse or irregular chains. Smooth the grid
    and clamp it to the observed IV range so the rendered surface stays realistic.
    """
    if iv_grid.size == 0:
        return iv_grid

    finite_observed = observed_ivs[np.isfinite(observed_ivs)]
    if finite_observed.size == 0:
        return iv_grid

    smoothed = gaussian_filter(iv_grid, sigma=1.0, mode="nearest")
    blended = (0.3 * iv_grid) + (0.7 * smoothed)

    observed_min = float(np.min(finite_observed))
    observed_max = float(np.max(finite_observed))
    return np.clip(blended, observed_min, observed_max)


# =============================================================================
# ALPHA ANALYTICS HELPERS
# =============================================================================

async def _fetch_price_history(fmp_server, ticker: str, days: int = 30) -> Optional[List[float]]:
    """Fetch historical prices for realized vol calculation."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)  # Buffer for weekends

        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)
        prices = data.get("prices") or data.get("closes") or data.get("close") or []

        if not prices or len(prices) < 5:
            return None

        return [float(p) for p in prices if p]

    except Exception as e:
        logger.warning(f"Failed to fetch price history for {ticker}: {e}")
        return None


def _compute_realized_vol(prices: List[float], window: int) -> Optional[float]:
    """
    Compute annualized realized volatility from price series.

    Args:
        prices: List of prices (most recent last)
        window: Number of days for calculation

    Returns:
        Annualized realized vol as decimal (e.g., 0.25 for 25%)
    """
    if not prices or len(prices) < window + 1:
        return None

    try:
        # Use most recent 'window' days
        recent_prices = prices[-(window + 1):]

        # Log returns
        log_returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i-1] > 0 and recent_prices[i] > 0:
                log_returns.append(math.log(recent_prices[i] / recent_prices[i-1]))

        if len(log_returns) < 5:
            return None

        # Annualized standard deviation of log returns
        daily_vol = np.std(log_returns, ddof=1)
        annual_vol = daily_vol * math.sqrt(252)

        return float(annual_vol)

    except Exception as e:
        logger.warning(f"Failed to compute realized vol: {e}")
        return None


def _compute_surface_analytics(
    iv_points: Dict[str, Any],
    spot_price: float,
    use_delta_buckets: bool = True
) -> Dict[str, Any]:
    """
    Compute surface analytics: ATM IV, term slope, skew metrics.

    Args:
        iv_points: Extracted IV data with deltas
        spot_price: Current underlying price
        use_delta_buckets: Use delta for bucketing (vs moneyness)

    Returns:
        {
            'atm_iv': float,  # ATM implied vol (as decimal)
            'term_slope': float,  # IV change per day (positive = contango)
            'put_skew_25d': float,  # 25d put IV - ATM IV
            'call_skew_25d': float,  # 25d call IV - ATM IV
            'front_iv': float,  # Front month ATM IV
            'back_iv': float,   # Back month ATM IV
            'front_back_spread': float,  # Back - Front
        }
    """
    strikes = np.array(iv_points['strikes'])
    ivs = np.array(iv_points['ivs'])
    dte = np.array(iv_points['dte'])
    moneyness = np.array(iv_points['moneyness'])
    option_types = np.array(iv_points['option_types'])
    deltas = np.array(iv_points['deltas'])

    analytics = {}

    # --- ATM IV ---
    # ATM defined as moneyness closest to 1.0
    atm_mask = (moneyness >= 0.97) & (moneyness <= 1.03)
    if atm_mask.sum() > 0:
        analytics['atm_iv'] = float(np.median(ivs[atm_mask]))
    else:
        # Fallback to overall median
        analytics['atm_iv'] = float(np.median(ivs))

    # --- Term Structure Slope ---
    # Group by DTE buckets and compute ATM IV for each
    unique_dte = np.unique(dte)
    if len(unique_dte) >= 2:
        dte_iv_pairs = []
        for d in unique_dte:
            dte_mask = (dte == d) & atm_mask
            if dte_mask.sum() > 0:
                dte_iv_pairs.append((d, float(np.median(ivs[dte_mask]))))

        if len(dte_iv_pairs) >= 2:
            # Sort by DTE
            dte_iv_pairs.sort(key=lambda x: x[0])

            # Linear regression slope (IV change per day)
            x = np.array([p[0] for p in dte_iv_pairs])
            y = np.array([p[1] for p in dte_iv_pairs])
            if len(x) >= 2:
                slope, _, _, _, _ = stats.linregress(x, y)
                analytics['term_slope'] = float(slope)

            # Front/back spread
            analytics['front_iv'] = dte_iv_pairs[0][1]
            analytics['back_iv'] = dte_iv_pairs[-1][1]
            analytics['front_back_spread'] = analytics['back_iv'] - analytics['front_iv']
        else:
            analytics['term_slope'] = None
            analytics['front_iv'] = None
            analytics['back_iv'] = None
            analytics['front_back_spread'] = None
    else:
        analytics['term_slope'] = None
        analytics['front_iv'] = None
        analytics['back_iv'] = None
        analytics['front_back_spread'] = None

    # --- Skew (25 delta) ---
    # Use delta buckets if available, else fall back to moneyness
    has_deltas = np.sum(deltas != None) > len(deltas) * 0.5

    if use_delta_buckets and has_deltas:
        # 25d put: delta ~ -0.25, 25d call: delta ~ 0.25
        valid_deltas = np.array([d if d is not None else np.nan for d in deltas])

        put_25d_mask = (valid_deltas >= -0.30) & (valid_deltas <= -0.20) & (option_types == 'put')
        call_25d_mask = (valid_deltas >= 0.20) & (valid_deltas <= 0.30) & (option_types == 'call')

        if put_25d_mask.sum() > 0 and 'atm_iv' in analytics:
            analytics['put_skew_25d'] = float(np.median(ivs[put_25d_mask])) - analytics['atm_iv']
        else:
            analytics['put_skew_25d'] = None

        if call_25d_mask.sum() > 0 and 'atm_iv' in analytics:
            analytics['call_skew_25d'] = float(np.median(ivs[call_25d_mask])) - analytics['atm_iv']
        else:
            analytics['call_skew_25d'] = None
    else:
        # Fallback: use moneyness buckets (OTM puts ~0.90, OTM calls ~1.10)
        put_otm_mask = (moneyness >= 0.88) & (moneyness <= 0.92) & (option_types == 'put')
        call_otm_mask = (moneyness >= 1.08) & (moneyness <= 1.12) & (option_types == 'call')

        if put_otm_mask.sum() > 0 and 'atm_iv' in analytics:
            analytics['put_skew_25d'] = float(np.median(ivs[put_otm_mask])) - analytics['atm_iv']
        else:
            analytics['put_skew_25d'] = None

        if call_otm_mask.sum() > 0 and 'atm_iv' in analytics:
            analytics['call_skew_25d'] = float(np.median(ivs[call_otm_mask])) - analytics['atm_iv']
        else:
            analytics['call_skew_25d'] = None

    return analytics


async def _fetch_earnings_date(fmp_server, ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch next earnings date for event context."""
    try:
        result = await fmp_server.call_tool("get_earnings_calendar", {
            "symbol": ticker,
            "limit": 1
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)

        # Handle various response structures
        earnings_list = data.get("data") or data.get("earnings") or data
        if isinstance(earnings_list, list) and len(earnings_list) > 0:
            earnings = earnings_list[0]
            date_str = earnings.get("date") or earnings.get("earningsDate")
            if date_str:
                try:
                    earnings_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    days_to_earnings = (earnings_date - datetime.now()).days
                    return {
                        'date': date_str[:10],
                        'days_to_earnings': days_to_earnings
                    }
                except ValueError:
                    pass

        return None

    except Exception as e:
        logger.debug(f"Failed to fetch earnings for {ticker}: {e}")
        return None


async def _compute_event_context(
    fmp_server,
    ticker: str,
    iv_points: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute event context: earnings proximity, whether earnings falls in front expiry.
    """
    context = {
        'days_to_earnings': None,
        'earnings_date': None,
        'earnings_in_front_expiry': None
    }

    earnings_info = await _fetch_earnings_date(fmp_server, ticker)

    if earnings_info:
        context['days_to_earnings'] = earnings_info['days_to_earnings']
        context['earnings_date'] = earnings_info['date']

        # Check if earnings falls within front-month expiry
        if iv_points['dte']:
            front_dte = min(iv_points['dte'])
            context['earnings_in_front_expiry'] = (
                earnings_info['days_to_earnings'] is not None and
                0 <= earnings_info['days_to_earnings'] <= front_dte
            )

    return context


async def _compute_peer_ranking(
    polygon_server,
    fmp_server,
    primary_ticker: str,
    primary_atm_iv: float,
    peer_tickers: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Compute cross-sectional ranking of primary ticker vs peers.

    Returns ranking (1 = highest) for ATM IV among the peer group.
    """
    if not peer_tickers:
        return None

    try:
        peer_ivs = {primary_ticker: primary_atm_iv}

        for peer in peer_tickers:
            if peer == primary_ticker:
                continue

            # Fetch peer's option chain and extract ATM IV
            chain_data = await _fetch_options_chain(polygon_server, peer)
            if not chain_data:
                continue

            peer_price = await _fetch_underlying_price(fmp_server, peer)
            if not peer_price:
                continue

            peer_points = _extract_iv_points(chain_data, peer_price)
            if peer_points['count'] < 5:
                continue

            # Compute ATM IV for peer
            moneyness = np.array(peer_points['moneyness'])
            ivs = np.array(peer_points['ivs'])
            atm_mask = (moneyness >= 0.97) & (moneyness <= 1.03)

            if atm_mask.sum() > 0:
                peer_ivs[peer] = float(np.median(ivs[atm_mask]))

        if len(peer_ivs) < 2:
            return None

        # Rank by ATM IV (1 = highest)
        sorted_peers = sorted(peer_ivs.items(), key=lambda x: x[1], reverse=True)
        rankings = {ticker: rank + 1 for rank, (ticker, _) in enumerate(sorted_peers)}

        return {
            'peers_analyzed': list(peer_ivs.keys()),
            'atm_iv_rank': rankings.get(primary_ticker),
            'atm_iv_values': peer_ivs,
            'rank_total': len(peer_ivs)
        }

    except Exception as e:
        logger.warning(f"Failed to compute peer ranking: {e}")
        return None


async def _build_3d_surface_chart(
    underlying: str,
    spot_price: float,
    surface_grid: Dict[str, Any],
    chart_id: str
) -> Optional[Dict[str, Any]]:
    """Build 3D volatility surface chart. Pattern from pca_analysis_tool.py chart builders"""
    try:
        import plotly.graph_objects as go

        strike_grid = surface_grid['strike_grid']
        dte_grid = surface_grid['dte_grid']
        iv_grid = surface_grid['iv_grid'] * 100  # Convert to percentage

        # DEBUG: Log data ranges to verify data is valid
        logger.info(f"[3D SURFACE DEBUG] Strike range: {strike_grid.min():.2f} - {strike_grid.max():.2f}")
        logger.info(f"[3D SURFACE DEBUG] DTE range: {dte_grid.min():.0f} - {dte_grid.max():.0f}")
        logger.info(f"[3D SURFACE DEBUG] IV range: {iv_grid.min():.2f}% - {iv_grid.max():.2f}%")
        logger.info(f"[3D SURFACE DEBUG] Grid shape: {strike_grid.shape}")

        # CRITICAL: Convert numpy arrays to lists for proper JSON serialization
        # Plotly's to_dict() sometimes doesn't handle nested 2D arrays correctly
        strike_grid_list = strike_grid.tolist()
        dte_grid_list = dte_grid.tolist()
        iv_grid_list = iv_grid.tolist()

        # Premium colorscale with smooth gradients
        colorscale = [
            [0.0, '#0d47a1'],   # Deep blue (low vol)
            [0.2, '#1976d2'],   # Medium blue
            [0.4, '#42a5f5'],   # Light blue
            [0.5, '#4fc3f7'],   # Cyan
            [0.6, '#fdd835'],   # Yellow
            [0.8, '#fb8c00'],   # Orange
            [1.0, '#d32f2f']    # Red (high vol)
        ]

        z_min = float(np.nanmin(iv_grid))
        z_max = float(np.nanmax(iv_grid))
        z_pad = max((z_max - z_min) * 0.08, 2.0)

        fig = go.Figure(data=[
            go.Surface(
                x=strike_grid_list,
                y=dte_grid_list,
                z=iv_grid_list,
                colorscale=colorscale,
                colorbar=dict(
                    title=dict(
                        text='Implied Vol (%)',
                        font=dict(size=13, family='Inter, sans-serif', color='#1e293b')
                    ),
                    tickfont=dict(size=11, family='Inter, sans-serif', color='#475569'),
                    thickness=20,
                    len=0.7,
                    x=0.92,
                    xpad=6,
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
                hovertemplate='<b>Strike:</b> $%{x:.2f}<br><b>DTE:</b> %{y:.0f} days<br><b>IV:</b> %{z:.2f}%<extra></extra>'
            )
        ])

        # Add subtle spot price marker (vertical line instead of plane)
        # Using a thin scatter3d line rather than a heavy surface plane
        z_line = np.linspace(iv_grid.min(), iv_grid.max(), 20)
        y_line = np.full(20, (dte_grid.min() + dte_grid.max()) / 2)  # Center of DTE range
        
        fig.add_trace(go.Scatter3d(
            x=np.full(20, spot_price),
            y=np.linspace(dte_grid.min(), dte_grid.max(), 20),
            z=np.full(20, iv_grid.max() * 1.02),  # Slight offset above surface
            mode='lines',
            line=dict(color='#64748b', width=3, dash='dot'),
            name='ATM Strike',
            hovertemplate=f'<b>Spot: ${spot_price:.2f}</b><extra></extra>'
        ))

        fig.update_layout(
            title=dict(
                text=f'<b>{underlying}</b> Implied Volatility Surface',
                font=dict(size=18, family='Inter, sans-serif', color='#0f172a'),
                x=0.5,
                xanchor='center'
            ),
            scene=dict(
                domain=dict(x=[0.0, 0.86], y=[0.0, 1.0]),
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
                    title=dict(text='Implied Volatility (%)', font=dict(size=13, color='#475569')),
                    backgroundcolor='#f8fafc',
                    gridcolor='#cbd5e1',
                    showbackground=True,
                    tickfont=dict(size=10, color='#64748b'),
                    range=[z_min - z_pad, z_max + z_pad]
                ),
                aspectmode='manual',
                aspectratio=dict(x=1.15, y=1.0, z=0.78),
                camera=dict(
                    eye=dict(x=1.35, y=-1.75, z=1.1),
                    center=dict(x=0.02, y=0.0, z=-0.08)
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
            margin=dict(l=70, r=100, t=60, b=55)
        )

        chart_dict = fig.to_dict()

        # DEBUG: Verify plotly dict has valid data
        if chart_dict.get('data'):
            first_trace = chart_dict['data'][0]
            logger.info(f"[3D SURFACE DEBUG] First trace type: {first_trace.get('type')}")
            x_data = first_trace.get('x', [])
            y_data = first_trace.get('y', [])
            z_data = first_trace.get('z', [])
            logger.info(f"[3D SURFACE DEBUG] Data lengths - x: {len(x_data) if isinstance(x_data, list) else 'array'}, y: {len(y_data) if isinstance(y_data, list) else 'array'}, z: {len(z_data) if isinstance(z_data, list) else 'array'}")

        return {
            'id': f'{chart_id}_3d_surface',
            'title': f'{underlying} 3D Volatility Surface',
            'plotly': chart_dict
        }

    except Exception as e:
        logger.error(f"Failed to build 3D surface chart: {e}", exc_info=True)
        return None


async def _build_iv_smile_chart(
    underlying: str,
    spot_price: float,
    iv_points: Dict[str, Any],
    chart_id: str,
    target_dte: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Build IV smile chart (IV vs strike for a specific expiration).
    Pattern from pca_analysis_tool.py
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        strikes = np.array(iv_points['strikes'])
        dte = np.array(iv_points['dte'])
        ivs = np.array(iv_points['ivs']) * 100
        option_types = iv_points['option_types']

        # If no target_dte specified, use closest to 30 days
        if target_dte is None:
            unique_dte = np.unique(dte)
            target_dte = unique_dte[np.argmin(np.abs(unique_dte - 30))]

        # Filter to target expiration (±3 days tolerance)
        mask = np.abs(dte - target_dte) <= 3

        if mask.sum() < 3:
            logger.warning(f"Not enough data points for IV smile at {target_dte} DTE")
            return None

        smile_strikes = strikes[mask]
        smile_ivs = ivs[mask]
        smile_types = np.array(option_types)[mask]

        # Separate calls and puts
        call_mask = smile_types == 'call'
        put_mask = smile_types == 'put'

        fig = go.Figure()

        # Plot calls with gradient
        if call_mask.any():
            fig.add_trace(go.Scatter(
                x=smile_strikes[call_mask],
                y=smile_ivs[call_mask],
                mode='markers+lines',
                name='Calls',
                marker=dict(
                    size=10,
                    color=smile_ivs[call_mask],
                    colorscale=[[0, '#10b981'], [1, '#059669']],
                    showscale=False,
                    line=dict(width=1, color='white')
                ),
                line=dict(width=3, color='#10b981', shape='spline', smoothing=1.3),
                hovertemplate='<b>Call Strike:</b> $%{x:.2f}<br><b>IV:</b> %{y:.2f}%<extra></extra>'
            ))

        # Plot puts with gradient
        if put_mask.any():
            fig.add_trace(go.Scatter(
                x=smile_strikes[put_mask],
                y=smile_ivs[put_mask],
                mode='markers+lines',
                name='Puts',
                marker=dict(
                    size=10,
                    color=smile_ivs[put_mask],
                    colorscale=[[0, '#f59e0b'], [1, '#d97706']],
                    showscale=False,
                    line=dict(width=1, color='white')
                ),
                line=dict(width=3, color='#f59e0b', shape='spline', smoothing=1.3),
                hovertemplate='<b>Put Strike:</b> $%{x:.2f}<br><b>IV:</b> %{y:.2f}%<extra></extra>'
            ))

        # Add ATM region shading
        fig.add_vrect(
            x0=spot_price * 0.95,
            x1=spot_price * 1.05,
            fillcolor='#3b82f6',
            opacity=0.1,
            layer='below',
            line_width=0,
            annotation_text='ATM',
            annotation_position='top left'
        )

        # Add spot price line
        fig.add_vline(
            x=spot_price,
            line_dash='dash',
            line_color='#3b82f6',
            line_width=2,
            annotation=dict(
                text=f'<b>Spot</b><br>${spot_price:.2f}',
                font=dict(size=11, color='#1e293b'),
                bgcolor='rgba(59, 130, 246, 0.1)',
                bordercolor='#3b82f6',
                borderwidth=1,
                borderpad=4
            )
        )

        fig.update_layout(
            title=dict(
                text=f'<b>{underlying}</b> IV Smile · {target_dte} Days to Expiration',
                font=dict(size=17, family='Inter, sans-serif', color='#0f172a'),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(
                title=dict(text='Strike Price ($)', font=dict(size=13, color='#475569')),
                gridcolor='#e2e8f0',
                showgrid=True,
                tickfont=dict(size=11, color='#64748b'),
                zeroline=False
            ),
            yaxis=dict(
                title=dict(text='Implied Volatility (%)', font=dict(size=13, color='#475569')),
                gridcolor='#e2e8f0',
                showgrid=True,
                tickfont=dict(size=11, color='#64748b'),
                zeroline=False
            ),
            width=900,
            height=550,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1,
                font=dict(size=12, color='#475569'),
                bgcolor='rgba(255, 255, 255, 0.9)',
                bordercolor='#cbd5e1',
                borderwidth=1
            ),
            paper_bgcolor='#ffffff',
            plot_bgcolor='#f8fafc',
            font=dict(family='Inter, sans-serif'),
            margin=dict(l=60, r=30, t=80, b=60)
        )

        chart_dict = fig.to_dict()

        # DEBUG: Log IV smile data
        logger.info(f"[IV SMILE DEBUG] Target DTE: {target_dte}, calls: {call_mask.sum()}, puts: {put_mask.sum()}")
        logger.info(f"[IV SMILE DEBUG] Strike range: {smile_strikes.min():.2f} - {smile_strikes.max():.2f}")
        logger.info(f"[IV SMILE DEBUG] IV range: {smile_ivs.min():.2f}% - {smile_ivs.max():.2f}%")

        return {
            'id': f'{chart_id}_iv_smile',
            'title': f'{underlying} IV Smile ({target_dte} DTE)',
            'plotly': chart_dict
        }

    except Exception as e:
        logger.error(f"Failed to build IV smile chart: {e}", exc_info=True)
        return None


async def _build_term_structure_chart(
    underlying: str,
    spot_price: float,
    iv_points: Dict[str, Any],
    chart_id: str,
    target_strike: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """
    Build term structure chart showing ATM IV vs DTE.
    
    Proper term structure: one ATM IV per expiry, not individual options.
    ATM IV is interpolated from options closest to spot for each expiry.
    """
    try:
        import plotly.graph_objects as go

        strikes = np.array(iv_points['strikes'])
        dte = np.array(iv_points['dte'])
        ivs = np.array(iv_points['ivs']) * 100  # Convert to percentage
        moneyness = np.array(iv_points['moneyness'])

        # Get unique expiries (DTEs)
        unique_dtes = np.unique(dte)
        
        if len(unique_dtes) < 2:
            logger.warning("Not enough expiries for term structure chart")
            return None

        # For each expiry, compute ATM IV by interpolating between strikes closest to spot
        term_structure_dte = []
        term_structure_iv = []
        
        for d in sorted(unique_dtes):
            expiry_mask = dte == d
            expiry_strikes = strikes[expiry_mask]
            expiry_ivs = ivs[expiry_mask]
            expiry_moneyness = moneyness[expiry_mask]
            
            if len(expiry_strikes) < 2:
                continue
            
            # Find ATM IV: average of options with moneyness closest to 1.0
            # Use options within 3% of ATM
            atm_mask = (expiry_moneyness >= 0.97) & (expiry_moneyness <= 1.03)
            
            if atm_mask.sum() > 0:
                atm_iv = np.mean(expiry_ivs[atm_mask])
            else:
                # Fallback: interpolate between two strikes closest to spot
                sorted_idx = np.argsort(np.abs(expiry_strikes - spot_price))
                closest_ivs = expiry_ivs[sorted_idx[:2]]
                atm_iv = np.mean(closest_ivs)
            
            term_structure_dte.append(d)
            term_structure_iv.append(atm_iv)
        
        if len(term_structure_dte) < 2:
            logger.warning("Not enough valid expiries for term structure")
            return None

        # Sort by DTE
        sorted_pairs = sorted(zip(term_structure_dte, term_structure_iv))
        term_structure_dte = [p[0] for p in sorted_pairs]
        term_structure_iv = [p[1] for p in sorted_pairs]

        fig = go.Figure()

        # Single ATM IV term structure line
        fig.add_trace(go.Scatter(
            x=term_structure_dte,
            y=term_structure_iv,
            mode='markers+lines',
            name='ATM IV',
            marker=dict(size=10, color='#3b82f6', line=dict(width=1, color='white')),
            line=dict(width=3, color='#3b82f6', shape='spline', smoothing=0.8),
            hovertemplate='<b>DTE:</b> %{x} days<br><b>ATM IV:</b> %{y:.1f}%<extra></extra>'
        ))

        # Determine term structure shape
        if len(term_structure_iv) >= 2:
            front_iv = term_structure_iv[0]
            back_iv = term_structure_iv[-1]
            if back_iv > front_iv + 1:
                shape_label = "Contango (upward sloping)"
            elif front_iv > back_iv + 1:
                shape_label = "Backwardation (inverted)"
            else:
                shape_label = "Flat"
        else:
            shape_label = ""

        fig.update_layout(
            title=dict(
                text=f'<b>{underlying}</b> ATM IV Term Structure',
                font=dict(size=17, family='Inter, sans-serif', color='#0f172a'),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(
                title=dict(text='Days to Expiration', font=dict(size=13, color='#475569')),
                gridcolor='#e2e8f0',
                showgrid=True,
                tickfont=dict(size=11, color='#64748b'),
                zeroline=False
            ),
            yaxis=dict(
                title=dict(text='ATM Implied Volatility (%)', font=dict(size=13, color='#475569')),
                gridcolor='#e2e8f0',
                showgrid=True,
                tickfont=dict(size=11, color='#64748b'),
                zeroline=False
            ),
            annotations=[dict(
                x=0.02, y=0.98, xref='paper', yref='paper',
                text=shape_label,
                showarrow=False,
                font=dict(size=12, color='#64748b'),
                bgcolor='rgba(255,255,255,0.8)',
                borderpad=4
            )] if shape_label else [],
            width=900,
            height=500,
            hovermode='x unified',
            showlegend=False,
            paper_bgcolor='#ffffff',
            plot_bgcolor='#f8fafc',
            font=dict(family='Inter, sans-serif'),
            margin=dict(l=60, r=30, t=80, b=60)
        )

        logger.info(f"[TERM STRUCTURE] {underlying}: {len(term_structure_dte)} expiries, front={term_structure_iv[0]:.1f}%, back={term_structure_iv[-1]:.1f}%")

        return {
            'id': f'{chart_id}_term_structure',
            'title': f'{underlying} ATM IV Term Structure',
            'plotly': fig.to_dict()
        }

    except Exception as e:
        logger.error(f"Failed to build term structure chart: {e}", exc_info=True)
        return None


async def model_volatility_surface_internal(
    underlying: str,
    underlying_price: Optional[float] = None,
    grid_resolution: int = 30,
    target_dte_for_smile: Optional[int] = None,
    target_strike_for_term: Optional[float] = None,
    compute_analytics: bool = False,
    include_realized_vol: bool = True,
    peer_tickers: Optional[List[str]] = None,
    use_delta_buckets: bool = True
) -> Dict[str, Any]:
    """
    Internal implementation of volatility surface modeling.
    Can be called directly without the @function_tool decorator.
    """
    # Pattern from delta_exposure_tool.py:167-173 for server initialization
    try:
        fmp_server = FMPMarketDataServer()
        polygon_server = PolygonOptionsFuturesServer()

        try:
            await fmp_server.connect()
            await polygon_server.connect()

            with bh_raw_mode():
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

                logger.info(f"Modeling volatility surface for {underlying} at ${spot_price:.2f}")

                # Step 2: Fetch options chain
                chain_data = await _fetch_options_chain(polygon_server, underlying)

                if not chain_data:
                    return {
                        'error': f'No options chain data available for {underlying}',
                        'underlying': underlying,
                        'spot_price': spot_price,
                        'charts': []
                    }

                # Step 3: Extract IV data points
                iv_points = _extract_iv_points(chain_data, spot_price)

                if iv_points['count'] < 10:
                    return {
                        'error': f'Insufficient IV data points ({iv_points["count"]}) for surface modeling',
                        'underlying': underlying,
                        'spot_price': spot_price,
                        'data_points': iv_points['count'],
                        'charts': []
                    }

                logger.info(f"Extracted {iv_points['count']} IV data points")

                # Step 4: Build interpolated surface grid
                surface_grid = _build_surface_grid(iv_points, grid_resolution)

                if not surface_grid:
                    return {
                        'error': 'Failed to interpolate volatility surface',
                        'underlying': underlying,
                        'spot_price': spot_price,
                        'data_points': iv_points['count'],
                        'charts': []
                    }

            # Step 5: Calculate surface statistics
            iv_array = np.array(iv_points['ivs']) * 100
            surface_stats = {
                'mean_iv': float(iv_array.mean()),
                'median_iv': float(np.median(iv_array)),
                'min_iv': float(iv_array.min()),
                'max_iv': float(iv_array.max()),
                'iv_range': float(iv_array.max() - iv_array.min()),
                'data_points': iv_points['count'],
                'strike_range': surface_grid['strike_range'],
                'dte_range': [int(surface_grid['dte_range'][0]), int(surface_grid['dte_range'][1])]
            }

            # Step 6: Build charts - EXACT PATTERN FROM PCA
            chart_id = f"volsurf_{underlying.lower()}_{abs(hash(str(underlying))) & 0xFFFF:04x}"
            charts = []

            # Chart 1: 3D Surface
            surface_chart = await _build_3d_surface_chart(
                underlying, spot_price, surface_grid, chart_id
            )
            if surface_chart:
                charts.append(surface_chart)

            # Chart 2: IV Smile
            smile_chart = await _build_iv_smile_chart(
                underlying, spot_price, iv_points, chart_id, target_dte_for_smile
            )
            if smile_chart:
                charts.append(smile_chart)

            # Chart 3: Term Structure
            term_chart = await _build_term_structure_chart(
                underlying, spot_price, iv_points, chart_id, target_strike_for_term
            )
            if term_chart:
                charts.append(term_chart)

            logger.info(f"Generated {len(charts)} volatility surface charts")
            charts = wrap_plotly_charts(charts, default_type="vol_surface_chart")

            # Build result summary (omit raw data arrays to prevent context overflow)
            # Raw data is embedded in the cached charts and can be retrieved via chart IDs
            result = {
                'underlying': underlying,
                'spot_price': spot_price,
                'surface_stats': surface_stats,
                'grid_resolution': grid_resolution,
                'analysis_timestamp': datetime.now().isoformat(),
                'data_points': iv_points.get('count', len(iv_points.get('strikes', []))),
                # Summary stats instead of raw arrays
                'strike_range': [float(min(iv_points.get('strikes', [0]))), float(max(iv_points.get('strikes', [0])))] if iv_points.get('strikes') else None,
                'dte_range': [int(min(iv_points.get('dte', [0]))), int(max(iv_points.get('dte', [0])))] if iv_points.get('dte') else None,
                'iv_range': [float(min(iv_points.get('ivs', [0]))), float(max(iv_points.get('ivs', [0])))] if iv_points.get('ivs') else None,
            }

            # =================================================================
            # ALPHA ANALYTICS (when compute_analytics=True)
            # =================================================================
            if compute_analytics:
                logger.info(f"Computing alpha analytics for {underlying}")

                # Surface analytics: ATM IV, term slope, skew
                analytics = _compute_surface_analytics(
                    iv_points, spot_price, use_delta_buckets
                )
                result['analytics'] = analytics

                # Realized volatility
                if include_realized_vol:
                    with bh_raw_mode():
                        price_history = await _fetch_price_history(fmp_server, underlying, days=30)
                    if price_history:
                        rv_10d = _compute_realized_vol(price_history, 10)
                        rv_20d = _compute_realized_vol(price_history, 20)

                        result['realized_vol'] = {
                            'rv_10d': rv_10d,
                            'rv_20d': rv_20d
                        }

                        # Vol risk premium (IV - RV)
                        atm_iv = analytics.get('atm_iv')
                        if atm_iv is not None:
                            result['vol_risk_premium'] = {
                                'iv_minus_rv_10d': (atm_iv - rv_10d) if rv_10d else None,
                                'iv_minus_rv_20d': (atm_iv - rv_20d) if rv_20d else None,
                                'iv_rv_ratio': (atm_iv / rv_20d) if rv_20d and rv_20d > 0 else None
                            }
                    else:
                        result['realized_vol'] = {'rv_10d': None, 'rv_20d': None}
                        result['vol_risk_premium'] = None

                # Event context (earnings proximity)
                with bh_raw_mode():
                    event_context = await _compute_event_context(fmp_server, underlying, iv_points)
                result['event_context'] = event_context

                # Cross-sectional ranking (if peers provided)
                if peer_tickers and analytics.get('atm_iv') is not None:
                    with bh_raw_mode():
                        cross_sectional = await _compute_peer_ranking(
                            polygon_server, fmp_server,
                            underlying, analytics['atm_iv'], peer_tickers
                        )
                    if cross_sectional:
                        result['cross_sectional'] = cross_sectional

                logger.info(f"Alpha analytics complete for {underlying}")

            # CRITICAL: Unconditional return with charts array (EXACT PCA PATTERN)
            final_result = jsonify_results({
                'status': 'success',
                'results': result,
                'underlying': underlying,
                'charts': charts  # Always present, even if empty
            })

            # DEBUG: Verify charts are in final result
            logger.info(f"FINAL RESULT HAS {len(final_result.get('charts', []))} CHARTS")
            logger.info(f"Chart IDs: {[c.get('id', 'NO_ID') for c in final_result.get('charts', [])]}")

            return final_result

        finally:
            # Cleanup pattern from delta_exposure_tool.py:258-260
            await fmp_server.cleanup()
            await polygon_server.cleanup()

    except Exception as e:
        logger.error(f"Volatility surface modeling failed: {e}", exc_info=True)
        # Truncate error to prevent SDK context overflow (Qhull errors are massive)
        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "... (error truncated)"
        return {
            'error': error_msg,
            'underlying': underlying,
            'charts': []
        }


@function_tool
async def model_volatility_surface(
    underlying: str,
    underlying_price: Optional[float] = None,
    grid_resolution: int = 30,
    target_dte_for_smile: Optional[int] = None,
    target_strike_for_term: Optional[float] = None,
    compute_analytics: bool = False,
    include_realized_vol: bool = True,
    peer_tickers: Optional[List[str]] = None,
    use_delta_buckets: bool = True
) -> Dict[str, Any]:
    """
    Model 3D implied volatility surface and generate interactive charts.

    Fetches complete options chain from Polygon, extracts IV data points,
    interpolates a smooth 3D surface, and generates multiple visualization charts.

    Args:
        underlying: Stock symbol (e.g., 'AAPL', 'SPY')
        underlying_price: Optional price override (fetched from FMP if not provided)
        grid_resolution: Number of grid points for surface interpolation (default: 30)
        target_dte_for_smile: Days to expiration for IV smile chart (default: ~30 days)
        target_strike_for_term: Strike price for term structure chart (default: ATM)
        compute_analytics: Enable alpha analytics (ATM IV, skew, realized vol, etc).
        include_realized_vol: Include realized vol in analytics (default: True)
        peer_tickers: List of peer tickers for cross-sectional ranking.
        use_delta_buckets: Use delta for skew bucketing vs moneyness (default: True)

    Returns:
        Dictionary with surface_stats, charts (3D surface, IV smile, term structure),
        and optionally analytics, realized_vol, vol_risk_premium when compute_analytics=True.
    """
    return await model_volatility_surface_internal(
        underlying=underlying,
        underlying_price=underlying_price,
        grid_resolution=grid_resolution,
        target_dte_for_smile=target_dte_for_smile,
        target_strike_for_term=target_strike_for_term,
        compute_analytics=compute_analytics,
        include_realized_vol=include_realized_vol,
        peer_tickers=peer_tickers,
        use_delta_buckets=use_delta_buckets,
    )
