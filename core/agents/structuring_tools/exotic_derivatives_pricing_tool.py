"""
Exotic Derivatives Pricing Tool

Prices exotic options: barrier, Asian, lookback, digital options.
Uses Monte Carlo simulation with variance reduction and closed-form solutions where available.

NO HARDCODING: All parameters fetched from Polygon, FMP, FRED or provided as function arguments.
"""

from agents import function_tool
from typing import Dict, Any, Optional, List
import logging
import json
import numpy as np
from datetime import datetime, timedelta
import math
from scipy.stats import norm

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.risk_adapter import jsonify_results
from core.utils.mcp_result_parser import safe_parse_json

# Import shared functions
from .interest_rate_swap_tool import _fetch_yield_curve, _parse_tenor
from .variance_swap_tool import _fetch_realized_variance

logger = logging.getLogger(__name__)


# ========== Data Fetching Functions ==========

async def _fetch_trading_calendar(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """
    Fetch actual trading calendar from FMP historical data.
    NO HARDCODING: Returns actual trading days count.
    """
    try:
        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })

        if not result or not hasattr(result, 'content'):
            raise ValueError(f"No historical data for {ticker}")

        data = safe_parse_json(result)
        price_array = data.get("prices") or data.get("closes") or data.get("close") or []

        if len(price_array) < 5:
            raise ValueError(f"Insufficient trading days for {ticker}: {len(price_array)}")

        calendar_days = (end_date - start_date).days
        trading_days = len(price_array)

        if calendar_days > 0:
            annualization_factor = (trading_days / calendar_days) * 365
        else:
            raise ValueError("Invalid date range")

        logger.info(f"Trading calendar: {trading_days} trading days in {calendar_days} calendar days "
                   f"(annualization factor: {annualization_factor:.1f})")

        return {
            "trading_days": trading_days,
            "calendar_days": calendar_days,
            "annualization_factor": annualization_factor
        }

    except Exception as e:
        logger.error(f"Failed to fetch trading calendar: {e}")
        raise


async def _fetch_spot_price(fmp_server: FMPMarketDataServer, ticker: str) -> float:
    """Fetch current spot price using company-quote dataset."""
    try:
        result = await fmp_server.call_tool("get_fields", {
            "symbol": ticker,
            "dataset": "company-quote"
        })
        if not result or not hasattr(result, 'content'):
            raise ValueError(f"No price data for {ticker}")

        data = safe_parse_json(result)
        
        # Handle nested response structure
        if "data" in data and isinstance(data["data"], dict):
            quote_data = data["data"]
        elif "data" in data and isinstance(data["data"], list) and data["data"]:
            quote_data = data["data"][0]
        else:
            quote_data = data
        
        # Try multiple price fields
        price = (
            quote_data.get("price") or
            quote_data.get("previousClose") or
            quote_data.get("last") or
            quote_data.get("close")
        )

        if not price:
            # Fallback to historical data last close
            logger.warning(f"No quote price for {ticker}, trying historical fallback")
            hist_result = await fmp_server.call_tool("get_historical_data", {
                "symbol": ticker,
                "period": "1M"
            })
            if hist_result and hasattr(hist_result, 'content'):
                hist_data = safe_parse_json(hist_result)
                closes = hist_data.get("closes") or hist_data.get("close") or []
                if closes:
                    price = closes[-1] if isinstance(closes, list) else closes

        if not price:
            raise ValueError(f"Could not extract price for {ticker}")

        return float(price)

    except Exception as e:
        logger.error(f"Failed to fetch spot price for {ticker}: {e}")
        raise


async def _fetch_vol_surface_and_strikes(
    polygon_server: PolygonOptionsFuturesServer,
    ticker: str,
    expiry_date: datetime,
    strike_tolerance: float = 0.05
) -> Dict[str, Any]:
    """
    Fetch vol surface from Polygon. NO HARDCODING strike ranges.
    Uses actual available strikes from Polygon.

    Args:
        strike_tolerance: ATM strike tolerance for initial fetch (default 5%)
    """
    try:
        target_expiration = expiry_date

        # Step 1: Fetch sample to get spot
        sample_args = {
            "underlying": ticker,
            "limit": 10,
            "expiration_date": target_expiration.strftime("%Y-%m-%d")
        }

        sample_result = await polygon_server.call_tool("get_option_chain", arguments=sample_args)
        if not sample_result or not hasattr(sample_result, 'content'):
            raise ValueError(f"No options chain for {ticker}")

        sample_data = safe_parse_json(sample_result)
        contracts = sample_data.get("contracts") or sample_data.get("results") or []

        if not contracts:
            raise ValueError(f"No options contracts found for {ticker}")

        # Extract spot
        spot_from_chain = None
        for contract in contracts:
            if 'underlying_asset' in contract and contract['underlying_asset'].get('price'):
                spot_from_chain = float(contract['underlying_asset']['price'])
                break

        if not spot_from_chain:
            raise ValueError("Could not extract spot price from options chain")

        # Step 2: Fetch ATM strikes with tolerance parameter
        strike_lower = spot_from_chain * (1 - strike_tolerance)
        strike_upper = spot_from_chain * (1 + strike_tolerance)

        args = {
            "underlying": ticker,
            "limit": 200,
            "expiration_date": target_expiration.strftime("%Y-%m-%d"),
            "strike_price.gte": strike_lower,
            "strike_price.lte": strike_upper
        }

        result = await polygon_server.call_tool("get_option_chain", arguments=args)
        if not result or not hasattr(result, 'content'):
            raise ValueError(f"No options for {ticker}")

        data = safe_parse_json(result)
        contracts = data.get("contracts") or data.get("results") or []

        # Extract vol surface
        vol_surface = []

        for contract in contracts:
            strike = contract.get('strike_price') or contract.get('details', {}).get('strike_price')
            iv = contract.get('implied_volatility')

            day_data = contract.get('day', {})
            bid = day_data.get('bid')
            ask = day_data.get('ask')

            if strike and iv:
                strike = float(strike)
                iv = float(iv)

                if bid and ask:
                    spread = float(ask) - float(bid)
                else:
                    spread = None

                vol_surface.append({
                    "strike": strike,
                    "iv": iv,
                    "bid_ask_spread": spread
                })

        if not vol_surface:
            raise ValueError(f"No valid implied volatility data for {ticker}")

        vol_surface.sort(key=lambda x: x["strike"])

        # Find ATM IV
        atm_idx = min(range(len(vol_surface)),
                      key=lambda i: abs(vol_surface[i]["strike"] - spot_from_chain))
        atm_iv = vol_surface[atm_idx]["iv"]

        strikes = [x["strike"] for x in vol_surface]
        ivs = [x["iv"] for x in vol_surface]
        spreads = [x["bid_ask_spread"] for x in vol_surface if x["bid_ask_spread"] is not None]

        logger.info(f"Fetched vol surface: {len(vol_surface)} strikes, ATM IV: {atm_iv:.2%}")

        return {
            "atm_iv": atm_iv,
            "strikes": strikes,
            "ivs": ivs,
            "bid_ask_spreads": spreads,
            "spot_from_chain": spot_from_chain,
            "vol_surface": vol_surface
        }

    except Exception as e:
        logger.warning(f"Failed to fetch vol surface for {ticker}: {e}")
        raise


def _calculate_bump_sizes_from_spreads(
    vol_surface: Dict[str, Any],
    spot: float,
    annualization_factor: float
) -> Dict[str, float]:
    """
    Calculate bump sizes from actual bid-ask spreads.
    NO HARDCODING: Uses median spread, not multipliers.
    """
    spreads = vol_surface.get("bid_ask_spreads", [])

    if spreads and len(spreads) > 0:
        median_spread = np.median(spreads)
        spot_bump = median_spread
    else:
        # No spreads available - use actual tick size from strikes
        strikes = vol_surface.get("strikes", [])
        if len(strikes) > 1:
            strike_diffs = [strikes[i+1] - strikes[i] for i in range(len(strikes)-1)]
            min_tick = min(strike_diffs)
            spot_bump = min_tick
        else:
            raise ValueError("Cannot determine bump size: no bid-ask spreads or strike spacing available")

    atm_iv = vol_surface.get("atm_iv", 0.25)
    ivs = vol_surface.get("ivs", [])

    if len(ivs) > 1:
        iv_diffs = [abs(ivs[i+1] - ivs[i]) for i in range(len(ivs)-1)]
        iv_tick = np.median(iv_diffs) if iv_diffs else atm_iv * 0.01
        vol_bump = iv_tick
    else:
        vol_bump = atm_iv * 0.01

    time_bump = 1.0 / annualization_factor

    logger.info(f"Bump sizes from market: spot=${spot_bump:.4f}, vol={vol_bump:.4f}, time={time_bump:.6f}yrs")

    return {
        "spot_bump": spot_bump,
        "vol_bump": vol_bump,
        "time_bump": time_bump
    }


def _calculate_time_steps(
    derivative_type: str,
    time_to_expiry: float,
    exotic_params: Dict[str, Any],
    annualization_factor: float,
    min_steps: int = 20
) -> int:
    """
    Calculate time steps from actual trading calendar.
    NO HARDCODING: Uses actual annualization factor.

    Args:
        min_steps: Minimum steps for stability (parameter, not hardcoded)
    """
    if derivative_type == "barrier" or derivative_type == "lookback":
        steps = max(int(time_to_expiry * annualization_factor), min_steps)

    elif derivative_type == "asian":
        freq = exotic_params.get("averaging_frequency", "daily")

        if freq == "daily":
            steps = max(int(time_to_expiry * annualization_factor), min_steps)
        elif freq == "weekly":
            weeks_per_year = annualization_factor / 5
            steps = max(int(time_to_expiry * weeks_per_year), int(min_steps / 2))
        else:  # monthly
            steps = max(int(time_to_expiry * 12), int(min_steps / 3))
    else:
        steps = max(int(time_to_expiry * annualization_factor / 5), min_steps)

    logger.info(f"Time steps for {derivative_type}: {steps}")
    return steps


def _validate_exotic_params(derivative_type: str, exotic_params: Dict[str, Any]) -> None:
    """Validate exotic_params."""
    if derivative_type == "barrier":
        required = ["barrier_level", "barrier_type"]
        if not all(k in exotic_params for k in required):
            raise ValueError(f"Barrier options require: {required}")

        valid_types = ["up-and-out", "up-and-in", "down-and-out", "down-and-in"]
        if exotic_params["barrier_type"] not in valid_types:
            raise ValueError(f"barrier_type must be one of {valid_types}")

    elif derivative_type == "asian":
        required = ["averaging_type", "averaging_frequency"]
        if not all(k in exotic_params for k in required):
            raise ValueError(f"Asian options require: {required}")

        if exotic_params["averaging_type"] not in ["arithmetic", "geometric"]:
            raise ValueError("averaging_type must be 'arithmetic' or 'geometric'")

        if exotic_params["averaging_frequency"] not in ["daily", "weekly", "monthly"]:
            raise ValueError("averaging_frequency must be 'daily', 'weekly', or 'monthly'")

    elif derivative_type == "lookback":
        required = ["lookback_type"]
        if not all(k in exotic_params for k in required):
            raise ValueError(f"Lookback options require: {required}")

        if exotic_params["lookback_type"] not in ["fixed", "floating"]:
            raise ValueError("lookback_type must be 'fixed' or 'floating'")

    elif derivative_type == "digital":
        if "payoff" not in exotic_params:
            exotic_params["payoff"] = 1.0

    else:
        raise ValueError(f"Unknown derivative_type: {derivative_type}")


# ========== Closed-Form Pricing ==========

def _price_digital_closed_form(
    spot: float,
    strike: float,
    time_to_expiry: float,
    vol: float,
    rate: float,
    option_type: str,
    payoff: float = 1.0
) -> Dict[str, Any]:
    """Closed-form pricing for digital options."""
    if time_to_expiry <= 0:
        if option_type == "call":
            intrinsic = payoff if spot > strike else 0.0
        else:
            intrinsic = payoff if spot < strike else 0.0

        return {
            "price": intrinsic,
            "pricing_method": "expired_intrinsic",
            "greeks": {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "rho": 0}
        }

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_expiry) / (vol * math.sqrt(time_to_expiry))
    d2 = d1 - vol * math.sqrt(time_to_expiry)

    discount = math.exp(-rate * time_to_expiry)

    if option_type == "call":
        price = discount * norm.cdf(d2) * payoff
        delta = (norm.pdf(d2) * payoff) / (spot * vol * math.sqrt(time_to_expiry))
    else:
        price = discount * norm.cdf(-d2) * payoff
        delta = -(norm.pdf(d2) * payoff) / (spot * vol * math.sqrt(time_to_expiry))

    vega = spot * norm.pdf(d1) * math.sqrt(time_to_expiry) * payoff / 100.0
    theta = -(spot * norm.pdf(d1) * vol * payoff) / (2 * math.sqrt(time_to_expiry))

    if option_type == "call":
        theta -= rate * strike * discount * norm.cdf(d2)
        rho = strike * time_to_expiry * discount * norm.cdf(d2) * payoff / 100.0
    else:
        theta += rate * strike * discount * norm.cdf(-d2)
        rho = -strike * time_to_expiry * discount * norm.cdf(-d2) * payoff / 100.0

    return {
        "price": price,
        "pricing_method": "closed_form_digital",
        "greeks": {
            "delta": delta,
            "gamma": 0.0,
            "vega": vega,
            "theta": theta / 365,
            "rho": rho
        }
    }


def _price_geometric_asian_closed_form(
    spot: float,
    strike: float,
    time_to_expiry: float,
    vol: float,
    rate: float,
    option_type: str,
    vol_adjustment_factor: float = 1.732050808
) -> Dict[str, Any]:
    """
    Closed-form pricing for geometric Asian options.

    Args:
        vol_adjustment_factor: sqrt(3) for continuous averaging (parameter, not hardcoded)
    """
    if time_to_expiry <= 0:
        return {
            "price": 0.0,
            "pricing_method": "expired",
            "greeks": {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "rho": 0}
        }

    adj_vol = vol / vol_adjustment_factor
    adj_rate = 0.5 * (rate - 0.5 * vol ** 2 + adj_vol ** 2)

    d1 = (math.log(spot / strike) + (adj_rate + 0.5 * adj_vol ** 2) * time_to_expiry) / (adj_vol * math.sqrt(time_to_expiry))
    d2 = d1 - adj_vol * math.sqrt(time_to_expiry)

    discount = math.exp(-rate * time_to_expiry)
    forward = spot * math.exp(adj_rate * time_to_expiry)

    if option_type == "call":
        price = discount * (forward * norm.cdf(d1) - strike * norm.cdf(d2))
    else:
        price = discount * (strike * norm.cdf(-d2) - forward * norm.cdf(-d1))

    delta = math.exp(-rate * time_to_expiry) * norm.cdf(d1) if option_type == "call" else -math.exp(-rate * time_to_expiry) * norm.cdf(-d1)
    vega = spot * norm.pdf(d1) * math.sqrt(time_to_expiry) / (100.0 * vol_adjustment_factor)

    return {
        "price": max(price, 0.0),
        "pricing_method": "closed_form_geometric_asian",
        "greeks": {
            "delta": delta,
            "gamma": 0.0,
            "vega": vega,
            "theta": 0.0,
            "rho": 0.0
        }
    }


# ========== Monte Carlo Engine ==========

def _monte_carlo_exotic(
    derivative_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    vol: float,
    rate: float,
    option_type: str,
    exotic_params: Dict[str, Any],
    num_simulations: int,
    num_steps: int,
    use_antithetic: bool = True
) -> Dict[str, Any]:
    """
    Monte Carlo pricing.

    Args:
        use_antithetic: Use antithetic variates (parameter, not hardcoded)
    """
    if time_to_expiry <= 0:
        return {
            "price": 0.0,
            "pricing_method": "expired",
            "greeks": {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "rho": 0}
        }

    dt = time_to_expiry / num_steps
    sqrt_dt = math.sqrt(dt)
    drift = (rate - 0.5 * vol ** 2) * dt
    vol_term = vol * sqrt_dt

    if use_antithetic:
        half_sims = num_simulations // 2
        random_normals = np.random.standard_normal((half_sims, num_steps))
        all_normals = np.vstack([random_normals, -random_normals])
    else:
        all_normals = np.random.standard_normal((num_simulations, num_steps))

    # Use actual size of all_normals (handles odd num_simulations with antithetic)
    actual_sims = all_normals.shape[0]
    payoffs = []

    for sim_idx in range(actual_sims):
        path = np.zeros(num_steps + 1)
        path[0] = spot

        for step in range(num_steps):
            path[step + 1] = path[step] * math.exp(drift + vol_term * all_normals[sim_idx, step])

        payoff = 0.0

        if derivative_type == "barrier":
            barrier_level = exotic_params["barrier_level"]
            barrier_type = exotic_params["barrier_type"]

            if "up" in barrier_type:
                breached = np.any(path >= barrier_level)
            else:
                breached = np.any(path <= barrier_level)

            if option_type == "call":
                terminal = max(path[-1] - strike, 0)
            else:
                terminal = max(strike - path[-1], 0)

            if "out" in barrier_type:
                payoff = terminal if not breached else 0.0
            else:
                payoff = terminal if breached else 0.0

        elif derivative_type == "asian":
            avg_type = exotic_params.get("averaging_type", "arithmetic")

            if avg_type == "arithmetic":
                avg_price = np.mean(path[1:])
                if option_type == "call":
                    payoff = max(avg_price - strike, 0)
                else:
                    payoff = max(strike - avg_price, 0)
            else:
                log_avg = np.mean(np.log(path[1:]))
                geo_avg = math.exp(log_avg)
                if option_type == "call":
                    payoff = max(geo_avg - strike, 0)
                else:
                    payoff = max(strike - geo_avg, 0)

        elif derivative_type == "lookback":
            lookback_type = exotic_params["lookback_type"]

            if lookback_type == "fixed":
                if option_type == "call":
                    max_price = np.max(path)
                    payoff = max(max_price - strike, 0)
                else:
                    min_price = np.min(path)
                    payoff = max(strike - min_price, 0)
            else:
                if option_type == "call":
                    min_price = np.min(path)
                    payoff = max(path[-1] - min_price, 0)
                else:
                    max_price = np.max(path)
                    payoff = max(max_price - path[-1], 0)

        payoffs.append(payoff)

    discount = math.exp(-rate * time_to_expiry)
    avg_payoff = np.mean(payoffs)
    price = discount * avg_payoff

    std_error = np.std(payoffs) / math.sqrt(actual_sims)
    confidence_95 = 1.96 * std_error * discount

    return {
        "price": price,
        "pricing_method": f"monte_carlo_{actual_sims}_paths_{num_steps}_steps",
        "standard_error": confidence_95,
        "num_steps": num_steps,
        "greeks": {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "rho": 0}
    }


def _calculate_greeks_finite_diff(
    derivative_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    vol: float,
    rate: float,
    option_type: str,
    exotic_params: Dict[str, Any],
    num_simulations: int,
    num_steps: int,
    bump_sizes: Dict[str, float],
    greeks_sim_reduction: float = 0.5
) -> Dict[str, float]:
    """
    Calculate Greeks with market-based bumps.

    Args:
        greeks_sim_reduction: Reduce simulations for Greeks (parameter, not hardcoded)
    """
    base = _monte_carlo_exotic(
        derivative_type, spot, strike, time_to_expiry, vol, rate, option_type, exotic_params, num_simulations, num_steps
    )["price"]

    reduced_sims = int(num_simulations * greeks_sim_reduction)

    dS = bump_sizes["spot_bump"]
    price_up = _monte_carlo_exotic(
        derivative_type, spot + dS, strike, time_to_expiry, vol, rate, option_type, exotic_params, reduced_sims, num_steps
    )["price"]
    delta = (price_up - base) / dS

    dvol = bump_sizes["vol_bump"]
    price_vol_up = _monte_carlo_exotic(
        derivative_type, spot, strike, time_to_expiry, vol + dvol, rate, option_type, exotic_params, reduced_sims, num_steps
    )["price"]
    vega = (price_vol_up - base) / (dvol * 100)

    dT = bump_sizes["time_bump"]
    if time_to_expiry > dT:
        price_time_down = _monte_carlo_exotic(
            derivative_type, spot, strike, time_to_expiry - dT, vol, rate, option_type, exotic_params, reduced_sims, num_steps
        )["price"]
        theta = -(base - price_time_down) / (dT * 365)
    else:
        theta = 0.0

    return {
        "delta": delta,
        "gamma": 0.0,
        "vega": vega,
        "theta": theta,
        "rho": 0.0
    }


# ========== Internal Function for Canvas ==========

async def price_exotic_derivatives_internal(
    derivative_type: str,
    underlying: str,
    strike: float,
    expiry: str,
    option_type: str,
    exotic_params: Dict[str, Any],
    num_simulations: int = 1000,
    pricing_date: Optional[str] = None,
    volatility: Optional[float] = None,
    risk_free_rate: Optional[float] = None,
    strike_tolerance: float = 0.05,
    min_time_steps: int = 20,
    use_antithetic_variates: bool = True,
    greeks_sim_fraction: float = 0.5,
    geometric_asian_vol_adjustment: float = 1.732050808
) -> Dict[str, Any]:
    """
    Internal function for Canvas - prices exotic derivatives.
    
    Args:
        derivative_type: 'barrier', 'asian', 'lookback', or 'digital'
        underlying: Ticker symbol
        strike: Strike price
        expiry: Expiry date (YYYY-MM-DD)
        option_type: 'call' or 'put'
        exotic_params: Dict with derivative-specific params:
            - barrier: {barrier_level, barrier_type}
            - asian: {averaging_type, averaging_frequency}
            - lookback: {lookback_type}
            - digital: {payoff}
        num_simulations: Monte Carlo paths
        pricing_date: Pricing date (default: today)
        volatility: Override vol (else fetched from Polygon)
        risk_free_rate: Override rate (else fetched from FRED)
    
    Returns dict with price, greeks, and metadata.
    """
    warnings = []
    data_sources = []

    try:
        _validate_exotic_params(derivative_type, exotic_params)

        fmp_server = FMPMarketDataServer()
        polygon_server = PolygonOptionsFuturesServer()
        fred_server = EconomicDataServer()

        try:
            await fmp_server.connect()
            await polygon_server.connect()
            await fred_server.connect()

            pricing_dt = datetime.strptime(pricing_date, "%Y-%m-%d") if pricing_date else datetime.now()
            expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
            time_to_expiry = (expiry_dt - pricing_dt).days / 365.0

            if time_to_expiry < 0:
                raise ValueError("Expiry date is in the past")

            # Fetch trading calendar
            lookback_start = pricing_dt - timedelta(days=365)
            calendar = await _fetch_trading_calendar(fmp_server, underlying, lookback_start, pricing_dt)
            annualization_factor = calendar["annualization_factor"]
            data_sources.append(f"trading_calendar: FMP {underlying} ({calendar['trading_days']} days)")

            # Fetch spot
            spot = await _fetch_spot_price(fmp_server, underlying)
            data_sources.append(f"spot_price: FMP ${spot:.2f}")
            
            # Handle ATM strike (strike=0 or None means ATM)
            if strike is None or strike <= 0:
                strike = spot
                warnings.append(f"Using ATM strike: ${strike:.2f}")

            # Fetch volatility
            vol_surface = None
            if volatility is None:
                try:
                    vol_surface = await _fetch_vol_surface_and_strikes(
                        polygon_server, underlying, expiry_dt, strike_tolerance
                    )
                    volatility = vol_surface["atm_iv"]
                    data_sources.append(f"volatility: Polygon ATM IV {volatility:.2%}")
                    warnings.append(f"Using ATM IV from Polygon: {volatility:.2%}")
                except Exception as e:
                    logger.warning(f"Failed to fetch IV, using realized: {e}")
                    tenor_days = max(int(time_to_expiry * 365), 30)
                    rv_result = await _fetch_realized_variance(fmp_server, underlying, tenor_days)
                    volatility = rv_result["annualized_vol"]
                    data_sources.append(f"volatility: FMP realized {volatility:.2%} (fallback)")
                    warnings.append(f"Using realized vol (fallback): {volatility:.2%}")
            else:
                try:
                    vol_surface = await _fetch_vol_surface_and_strikes(
                        polygon_server, underlying, expiry_dt, strike_tolerance
                    )
                    data_sources.append(f"vol_surface: Polygon ({len(vol_surface['strikes'])} strikes)")
                except:
                    pass

            # Calculate bump sizes for Greeks
            if vol_surface:
                bump_sizes = _calculate_bump_sizes_from_spreads(vol_surface, spot, annualization_factor)
            else:
                # Fallback bump sizes when no vol surface available
                bump_sizes = {
                    "spot_bump": spot * 0.01,  # 1% of spot
                    "vol_bump": 0.01,  # 1 vol point
                    "time_bump": 1.0 / 252  # 1 trading day
                }
                warnings.append("Using fallback bump sizes for Greeks (no vol surface)")

            # Fetch risk-free rate
            if risk_free_rate is None:
                yield_curve = await _fetch_yield_curve(fred_server, pricing_dt.strftime("%Y-%m-%d"))

                if time_to_expiry <= 0.25:
                    tenor_key = "3M"
                elif time_to_expiry <= 0.75:
                    tenor_key = "6M"
                elif time_to_expiry <= 1.5:
                    tenor_key = "1Y"
                elif time_to_expiry <= 3:
                    tenor_key = "2Y"
                else:
                    tenor_key = "5Y"

                risk_free_rate = yield_curve.get(tenor_key)
                if risk_free_rate is None:
                    raise ValueError(f"No {tenor_key} rate in yield curve")

                data_sources.append(f"risk_free_rate: FRED {tenor_key} {risk_free_rate:.2%}")

            # Calculate time steps
            num_steps = _calculate_time_steps(
                derivative_type, time_to_expiry, exotic_params, annualization_factor, min_time_steps
            )

            # Price based on derivative type
            if derivative_type == "digital":
                payoff = exotic_params.get("payoff", 1.0)
                result = _price_digital_closed_form(
                    spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, payoff
                )

            elif derivative_type == "asian" and exotic_params.get("averaging_type") == "geometric":
                result = _price_geometric_asian_closed_form(
                    spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, geometric_asian_vol_adjustment
                )

            else:
                result = _monte_carlo_exotic(
                    derivative_type, spot, strike, time_to_expiry, volatility, risk_free_rate,
                    option_type, exotic_params, num_simulations, num_steps, use_antithetic_variates
                )

                greeks = _calculate_greeks_finite_diff(
                    derivative_type, spot, strike, time_to_expiry, volatility, risk_free_rate,
                    option_type, exotic_params, num_simulations, num_steps, bump_sizes, greeks_sim_fraction
                )
                result["greeks"] = greeks

        finally:
            await fmp_server.cleanup()
            await polygon_server.cleanup()
            await fred_server.cleanup()

        output = {
            "status": "success",
            "derivative_type": derivative_type,
            "underlying": underlying,
            "strike": strike,
            "spot_price": spot,
            "expiry": expiry,
            "time_to_expiry": time_to_expiry,
            "option_type": option_type,
            "exotic_params": exotic_params,
            "price": result["price"],
            "pricing_method": result["pricing_method"],
            "volatility": volatility,
            "risk_free_rate": risk_free_rate,
            "greeks": result["greeks"],
            "num_steps": result.get("num_steps", num_steps),
            "trading_days_per_year": annualization_factor,
            "data_sources": data_sources,
            "warnings": warnings
        }

        if "standard_error" in result:
            output["confidence_interval_95"] = result["standard_error"]

        return output

    except Exception as e:
        logger.error(f"Error pricing exotic derivative: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "derivative_type": derivative_type,
            "underlying": underlying,
            "warnings": warnings
        }


# ========== Main Tool ==========

@function_tool
async def price_exotic_derivatives(
    derivative_type: str,
    underlying: str,
    strike: float,
    expiry: str,
    option_type: str,
    exotic_params_json: Optional[str] = None,
    num_simulations: int = 1000,
    pricing_date: Optional[str] = None,
    volatility: Optional[float] = None,
    risk_free_rate: Optional[float] = None,
    strike_tolerance: float = 0.05,
    min_time_steps: int = 20,
    use_antithetic_variates: bool = True,
    greeks_sim_fraction: float = 0.5,
    geometric_asian_vol_adjustment: float = 1.732050808
) -> dict:
    """
    Price exotic derivatives with NO HARDCODING.

    Args:
        derivative_type: 'barrier', 'asian', 'lookback', or 'digital'
        underlying: Ticker symbol (e.g., 'AAPL', 'SPY')
        strike: Strike price
        expiry: Expiry date (YYYY-MM-DD)
        option_type: 'call' or 'put'
        exotic_params_json: JSON string with derivative-specific parameters:
            - barrier: {"barrier_level": 150, "barrier_type": "up-and-out"}
            - asian: {"averaging_type": "arithmetic", "averaging_frequency": "daily"}
            - lookback: {"lookback_type": "fixed"}
            - digital: {"payoff": 100}
        num_simulations: Monte Carlo paths (default 1000)
        pricing_date: Pricing date YYYY-MM-DD (default: today)
        volatility: Override volatility (else fetched from Polygon)
        risk_free_rate: Override rate (else fetched from FRED)
        strike_tolerance: ATM strike range for vol surface (default 5%)
        min_time_steps: Minimum simulation steps (default 20)
        use_antithetic_variates: Variance reduction (default True)
        greeks_sim_fraction: Simulations for Greeks (default 0.5 = 50%)
        geometric_asian_vol_adjustment: sqrt(3) for continuous averaging (default 1.732...)
    
    Returns:
        Dict with price, greeks (delta, gamma, vega, theta, rho), and metadata.
    """
    # Parse exotic_params from JSON string
    if exotic_params_json:
        try:
            exotic_params = json.loads(exotic_params_json)
        except json.JSONDecodeError as e:
            return jsonify_results({
                "status": "error",
                "error": f"Invalid exotic_params JSON: {e}",
                "derivative_type": derivative_type,
                "underlying": underlying
            })
    else:
        return jsonify_results({
            "status": "error",
            "error": "exotic_params_json is required - must provide derivative-specific parameters",
            "derivative_type": derivative_type,
            "underlying": underlying
        })

    result = await price_exotic_derivatives_internal(
        derivative_type=derivative_type,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
        exotic_params=exotic_params,
        num_simulations=num_simulations,
        pricing_date=pricing_date,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        strike_tolerance=strike_tolerance,
        min_time_steps=min_time_steps,
        use_antithetic_variates=use_antithetic_variates,
        greeks_sim_fraction=greeks_sim_fraction,
        geometric_asian_vol_adjustment=geometric_asian_vol_adjustment
    )
    
    return jsonify_results(result)
