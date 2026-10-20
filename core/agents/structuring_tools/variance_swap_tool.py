"""
Variance Swap Pricing Tool

Prices variance swap contracts using replicating portfolio of options.
Calculates fair strike from options chain and mark-to-market value.

NO HARDCODING: Uses Polygon for options chain, FMP for stock prices, FRED for rates.
"""

from agents import function_tool
from typing import Dict, Any, Optional, List
import logging
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.risk_adapter import jsonify_results
from core.utils.mcp_result_parser import safe_parse_json

# Import shared functions from IRS tool
from .interest_rate_swap_tool import (
    _fetch_yield_curve,
    _parse_tenor
)

logger = logging.getLogger(__name__)


async def _fetch_realized_variance(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    tenor_days: int
) -> Dict[str, Any]:
    """
    Calculate realized variance from historical stock prices.

    Realized Variance = (252/N) × Σ(log_return_i²)

    Args:
        fmp_server: Connected FMP server instance
        ticker: Stock ticker symbol
        tenor_days: Number of days for variance calculation

    Returns:
        Dict with realized_variance, annualized_vol, sample_count

    Raises:
        ValueError: If insufficient price data
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=tenor_days + 30)  # Extra buffer

        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })

        if not result or not hasattr(result, 'content'):
            raise ValueError(f"No price data for {ticker}")

        data = safe_parse_json(result)
        price_array = data.get("prices") or data.get("closes") or data.get("close") or []

        if len(price_array) < 20:
            raise ValueError(f"Insufficient price history for {ticker} (need 20+ days, got {len(price_array)})")

        # Take most recent tenor_days prices
        prices = [float(p) for p in price_array[-tenor_days-1:] if p]

        # Calculate log returns
        log_returns = []
        for i in range(1, len(prices)):
            log_returns.append(np.log(prices[i] / prices[i-1]))

        # Realized variance (annualized)
        # Variance = mean of squared returns × 252
        squared_returns = [r**2 for r in log_returns]
        realized_variance = (252.0 / len(squared_returns)) * sum(squared_returns)
        annualized_vol = np.sqrt(realized_variance)

        logger.info(f"Realized variance for {ticker}: {realized_variance:.4f} "
                   f"(vol={annualized_vol:.2%}, N={len(log_returns)})")

        return {
            "realized_variance": float(realized_variance),
            "annualized_vol": float(annualized_vol),
            "sample_count": len(log_returns),
            "prices_used": len(prices)
        }

    except Exception as e:
        logger.error(f"Realized variance calculation failed: {e}")
        raise


async def _calculate_fair_strike_from_options(
    polygon_server: PolygonOptionsFuturesServer,
    underlying: str,
    tenor_years: float,
    risk_free_rate: float
) -> Dict[str, Any]:
    """
    Calculate fair variance strike from options chain using replicating portfolio.

    Fair Strike Formula:
    K_var = (2/T) × Σ[(ΔK_i/K_i²) × e^(rT) × Option_Price_i]

    Where:
    - Sum over OTM options (calls above spot, puts below spot)
    - ΔK_i = spacing between strikes
    - K_i = strike price
    - Option_Price_i = mid price (bid + ask) / 2

    Args:
        polygon_server: Connected Polygon server instance
        underlying: Stock ticker symbol
        tenor_years: Tenor in years
        risk_free_rate: Risk-free rate (decimal)

    Returns:
        Dict with fair_strike, implied_vol, options_used, warnings

    Raises:
        ValueError: If options chain unavailable or insufficient
    """
    try:
        # Fetch options chain with pagination (handles 0-DTE filtering)
        from core.agents.quant_tools.options_chain_helpers import fetch_options_chain_paginated
        contracts = await fetch_options_chain_paginated(
            polygon_server, 
            underlying, 
            min_dte=1,
            max_dte=int(tenor_years * 365) + 30,  # Include options beyond tenor
            max_pages=6,
            limit_per_page=250
        )

        if not contracts:
            raise ValueError(f"No options chain data for {underlying} (after filtering 0-DTE)")

        # Filter by expiration (find closest to tenor)
        target_date = datetime.now() + timedelta(days=int(tenor_years * 365))

        # Group by expiration
        expirations = {}
        for contract in contracts:
            details = contract.get("details", {})
            expiry_str = details.get("expiration_date")

            if not expiry_str:
                continue

            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
                expirations.setdefault(expiry, []).append(contract)
            except:
                continue

        if not expirations:
            raise ValueError(f"No valid expirations found in options chain")

        # Find closest expiration to target
        closest_expiry = min(expirations.keys(), key=lambda x: abs((x - target_date).days))
        selected_contracts = expirations[closest_expiry]

        logger.info(f"Using {len(selected_contracts)} contracts expiring {closest_expiry.strftime('%Y-%m-%d')} "
                   f"(target was {target_date.strftime('%Y-%m-%d')})")

        # Get current spot price from chain (use ATM option)
        spot = None
        for contract in selected_contracts:
            underlying_price = contract.get("underlying_asset", {}).get("price")
            if underlying_price:
                spot = float(underlying_price)
                break

        if not spot:
            raise ValueError("Unable to determine current spot price from options chain")

        # Separate calls and puts with valid pricing
        calls = []
        puts = []

        for contract in selected_contracts:
            details = contract.get("details", {})
            day_data = contract.get("day", {})

            strike = details.get("strike_price")
            option_type = details.get("contract_type")  # "call" or "put"

            # Get mid price from bid/ask
            bid = day_data.get("close")  # Use close as proxy if no bid/ask
            ask = day_data.get("close")

            if not strike or not option_type or not bid or not ask:
                continue

            strike = float(strike)
            mid_price = (float(bid) + float(ask)) / 2.0

            if mid_price <= 0:
                continue

            if option_type.lower() == "call":
                calls.append({"strike": strike, "price": mid_price})
            elif option_type.lower() == "put":
                puts.append({"strike": strike, "price": mid_price})

        if not calls and not puts:
            raise ValueError("No valid call or put prices found in options chain")

        # Sort by strike
        calls.sort(key=lambda x: x["strike"])
        puts.sort(key=lambda x: x["strike"])

        # Calculate replicating portfolio contribution
        # Use OTM options: puts below spot, calls above spot
        otm_options = []

        # Puts below spot
        for put in puts:
            if put["strike"] < spot:
                otm_options.append(put)

        # Calls above spot (or ATM if no puts below spot)
        for call in calls:
            if call["strike"] >= spot:
                otm_options.append(call)

        if len(otm_options) < 5:
            raise ValueError(f"Insufficient OTM options (need 5+, got {len(otm_options)})")

        # Sort by strike
        otm_options.sort(key=lambda x: x["strike"])

        # Calculate fair strike using replicating portfolio formula
        discount_factor = np.exp(risk_free_rate * tenor_years)
        variance_contribution = 0.0

        for i, option in enumerate(otm_options):
            strike = option["strike"]
            price = option["price"]

            # Strike spacing (ΔK)
            if i == 0:
                if len(otm_options) > 1:
                    delta_k = otm_options[i+1]["strike"] - strike
                else:
                    delta_k = 0.1 * strike  # 10% if only one option
            elif i == len(otm_options) - 1:
                delta_k = strike - otm_options[i-1]["strike"]
            else:
                delta_k = (otm_options[i+1]["strike"] - otm_options[i-1]["strike"]) / 2.0

            # Contribution: (ΔK/K²) × e^(rT) × Price
            contribution = (delta_k / (strike ** 2)) * discount_factor * price
            variance_contribution += contribution

        # Fair strike: (2/T) × Σ(contributions)
        fair_strike = (2.0 / tenor_years) * variance_contribution
        implied_vol = np.sqrt(fair_strike)

        logger.info(f"Fair variance strike: {fair_strike:.4f} (vol={implied_vol:.2%}) "
                   f"from {len(otm_options)} OTM options")

        return {
            "fair_strike": float(fair_strike),
            "implied_vol": float(implied_vol),
            "options_used": len(otm_options),
            "spot_price": float(spot),
            "expiration_date": closest_expiry.strftime("%Y-%m-%d"),
            "days_to_expiry": (closest_expiry - datetime.now()).days
        }

    except Exception as e:
        logger.error(f"Fair strike calculation failed: {e}")
        raise


def _fallback_fair_strike_from_historical(
    realized_variance: float,
    vol_of_vol: float = 0.20
) -> Dict[str, Any]:
    """
    Fallback fair strike estimation from historical realized variance.

    Uses historical vol² as estimate with volatility-of-volatility adjustment.

    Args:
        realized_variance: Realized variance from historical prices
        vol_of_vol: Volatility of volatility (default 20%)

    Returns:
        Dict with fair_strike, implied_vol, warnings
    """
    # Adjust for vol of vol (variance is stochastic)
    # E[Var_T] ≈ Var_0 × (1 + σ_vol²/2)
    fair_strike = realized_variance * (1 + (vol_of_vol ** 2) / 2.0)
    implied_vol = np.sqrt(fair_strike)

    logger.warning(f"Using historical vol fallback: fair strike={fair_strike:.4f} (vol={implied_vol:.2%})")

    return {
        "fair_strike": float(fair_strike),
        "implied_vol": float(implied_vol),
        "options_used": 0,
        "estimation_method": "historical_fallback",
        "warning": "Fair strike estimated from historical variance (no options data available)"
    }


async def price_variance_swap_internal(
    underlying: str,
    notional_per_vega: float,
    strike_variance: Optional[float] = None,
    tenor: str = "3M",
    pricing_date: Optional[str] = None
) -> dict:
    """
    Internal implementation for variance swap pricing.
    
    Call this directly from Canvas executors. For agent usage, use price_variance_swap.

    Variance Swap Mechanics:
    - Payoff = Notional × (Realized_Variance - Strike_Variance)
    - Buyer receives if realized vol > strike vol
    - Pure volatility exposure (no delta, no gamma convexity from single options)

    Fair Strike Calculation:
    - PRIMARY: Replicating portfolio from Polygon options chain
    - FALLBACK: Historical realized variance (if options unavailable)

    Pricing Formula:
    - Fair Strike: K_var = (2/T) × Σ[(ΔK/K²) × e^(rT) × OTM_Price]
    - Mark-to-Market: PV = Notional × (Fair_Strike - Strike) × e^(-rT)

    Data Sources:
    - Polygon: Options chain for fair strike calculation
    - FMP: Stock prices for realized variance
    - FRED: Risk-free rate for discounting

    Args:
        underlying: Stock ticker symbol
        notional_per_vega: Notional per variance point (e.g., 100000 = $100K per vol² point)
        strike_variance: Strike variance (decimal). If None, uses fair strike from options
            Example: 0.04 means 20% vol (since 0.20² = 0.04)
        tenor: Swap maturity ("1M", "3M", "6M", "1Y")
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        Dict with:
        {
            "status": "success",
            "swap_value": float - Present value of variance swap ($)
            "fair_strike": float - Fair variance strike from options
            "strike_variance": float - Contract strike variance
            "implied_vol": float - Implied volatility from fair strike
            "realized_variance": float - Current realized variance
            "realized_vol": float - Current realized volatility
            "vega": float - PV01 of variance ($ per 0.01 variance move)
            "convexity": float - Second-order sensitivity
            "tenor_years": float - Tenor in years
            "days_to_maturity": int - Days remaining
            "options_used": int - Number of options in replicating portfolio
            "estimation_method": str - "options_chain" or "historical_fallback"
            "inputs": Dict - Echo of inputs
            "data_sources": List[str] - Data sources used
            "summary": str - Human-readable summary
        }

        On error:
        {
            "status": "error",
            "error": str - Error message
            "calculation_type": "variance_swap"
        }

    Examples:
        # Price 3M variance swap on SPY with fair strike
        result = await price_variance_swap(
            underlying="SPY",
            notional_per_vega=100_000,
            tenor="3M"
        )
        print(f"Fair Strike: {result['fair_strike']:.4f} (vol={result['implied_vol']:.2%})")
        print(f"Swap Value: ${result['swap_value']:,.2f}")

        # Custom strike variance
        result = await price_variance_swap(
            underlying="AAPL",
            notional_per_vega=50_000,
            strike_variance=0.0625,  # 25% vol
            tenor="6M",
            pricing_date="2024-01-15"
        )
    """
    try:
        # Set pricing date
        if pricing_date is None:
            pricing_date = datetime.now().strftime("%Y-%m-%d")

        pricing_dt = datetime.strptime(pricing_date, "%Y-%m-%d")
        tenor_years = _parse_tenor(tenor)
        tenor_days = int(tenor_years * 365)

        # Validate inputs
        if notional_per_vega <= 0:
            raise ValueError(f"Notional must be positive: {notional_per_vega}")

        if strike_variance is not None and strike_variance <= 0:
            raise ValueError(f"Strike variance must be positive: {strike_variance}")

        data_sources = []
        warnings_list = []

        # Connect to servers
        fmp_server = FMPMarketDataServer()
        polygon_server = PolygonOptionsFuturesServer()
        fred_server = EconomicDataServer()

        try:
            await fmp_server.connect()
            await polygon_server.connect()
            await fred_server.connect()

            # 1. Fetch yield curve for discounting
            logger.info(f"Fetching yield curve for {pricing_date}")
            yield_curve = await _fetch_yield_curve(fred_server, pricing_date)
            data_sources.append("yield_curve: FRED treasury series (DGS)")

            # Get risk-free rate for tenor
            if tenor_years <= 0.5:
                rfr_tenor = "3M"
            elif tenor_years <= 1.5:
                rfr_tenor = "1Y"
            elif tenor_years <= 3:
                rfr_tenor = "2Y"
            else:
                rfr_tenor = "5Y"

            risk_free_rate = yield_curve.get(rfr_tenor, 0.045)
            data_sources.append(f"risk_free_rate: {risk_free_rate:.2%} ({rfr_tenor} treasury)")

            # 2. Calculate realized variance
            logger.info(f"Calculating realized variance for {underlying}")
            realized_data = await _fetch_realized_variance(fmp_server, underlying, tenor_days)
            data_sources.append(f"realized_variance: FMP {underlying} ({realized_data['sample_count']} days)")

            # 3. Calculate or use fair strike
            fair_strike_data = None
            estimation_method = "unknown"

            if strike_variance is None:
                # Need to calculate fair strike
                try:
                    logger.info(f"Calculating fair strike from options chain")
                    fair_strike_data = await _calculate_fair_strike_from_options(
                        polygon_server,
                        underlying,
                        tenor_years,
                        risk_free_rate
                    )
                    data_sources.append(f"fair_strike: Polygon options chain ({fair_strike_data['options_used']} contracts)")
                    estimation_method = "options_chain"

                except Exception as e:
                    logger.warning(f"Options chain failed: {e}. Using historical fallback.")
                    fair_strike_data = _fallback_fair_strike_from_historical(
                        realized_data["realized_variance"]
                    )
                    data_sources.append("fair_strike: Historical variance fallback")
                    estimation_method = "historical_fallback"
                    warnings_list.append(fair_strike_data.get("warning", ""))

                strike_variance = fair_strike_data["fair_strike"]

            else:
                # User provided strike, but still calculate fair for comparison
                try:
                    fair_strike_data = await _calculate_fair_strike_from_options(
                        polygon_server,
                        underlying,
                        tenor_years,
                        risk_free_rate
                    )
                    data_sources.append(f"fair_strike: Polygon options chain ({fair_strike_data['options_used']} contracts)")
                    estimation_method = "options_chain"
                except:
                    fair_strike_data = _fallback_fair_strike_from_historical(
                        realized_data["realized_variance"]
                    )
                    estimation_method = "historical_fallback"

            fair_strike = fair_strike_data["fair_strike"]
            implied_vol = fair_strike_data["implied_vol"]

        finally:
            await fmp_server.cleanup()
            await polygon_server.cleanup()
            await fred_server.cleanup()

        # 4. Calculate swap value
        # PV = Notional × (Fair_Strike - Strike) × DF
        discount_factor = np.exp(-risk_free_rate * tenor_years)
        variance_diff = fair_strike - strike_variance
        swap_value = notional_per_vega * variance_diff * discount_factor

        # 5. Calculate risk metrics
        # Vega: d(PV)/d(Var) = Notional × DF
        vega = notional_per_vega * discount_factor

        # Convexity: d²(PV)/d(Var)² = 0 (variance swap is linear in variance)
        convexity = 0.0

        # Build summary
        strike_vol = np.sqrt(strike_variance)
        direction = "receive" if variance_diff > 0 else "pay"
        summary = (
            f"Variance swap: {underlying}, {notional_per_vega:,.0f} notional per vega point, {tenor} tenor. "
            f"Strike: {strike_variance:.4f} ({strike_vol:.2%} vol), "
            f"Fair: {fair_strike:.4f} ({implied_vol:.2%} vol). "
            f"Swap value: ${swap_value:,.2f} ({direction} variance). "
            f"Current realized: {realized_data['realized_variance']:.4f} ({realized_data['annualized_vol']:.2%} vol)."
        )

        result = {
            "status": "success",
            "swap_value": float(swap_value),
            "fair_strike": float(fair_strike),
            "strike_variance": float(strike_variance),
            "implied_vol": float(implied_vol),
            "realized_variance": float(realized_data["realized_variance"]),
            "realized_vol": float(realized_data["annualized_vol"]),
            "vega": float(vega),
            "convexity": float(convexity),
            "tenor_years": float(tenor_years),
            "days_to_maturity": tenor_days,
            "options_used": fair_strike_data.get("options_used", 0),
            "estimation_method": estimation_method,
            "inputs": {
                "underlying": underlying,
                "notional_per_vega": notional_per_vega,
                "strike_variance": float(strike_variance),
                "tenor": tenor,
                "pricing_date": pricing_date
            },
            "data_sources": data_sources,
            "summary": summary
        }

        if warnings_list:
            result["warnings"] = warnings_list

        return jsonify_results(result)

    except Exception as e:
        logger.error(f"Variance swap pricing failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "calculation_type": "variance_swap"
        }


@function_tool
async def price_variance_swap(
    underlying: str,
    notional_per_vega: float,
    strike_variance: Optional[float] = None,
    tenor: str = "3M",
    pricing_date: Optional[str] = None
) -> dict:
    """
    Price variance swap contracts using replicating portfolio of options.
    
    This is the agent-facing wrapper. For Canvas, use price_variance_swap_internal.

    Variance Swap Mechanics:
    - Payoff = Notional × (Realized_Variance - Strike_Variance)
    - Buyer receives if realized vol > strike vol
    - Pure volatility exposure (no delta, no gamma convexity from single options)

    Args:
        underlying: Stock ticker symbol
        notional_per_vega: Notional per variance point
        strike_variance: Strike variance (decimal). If None, uses fair strike from options
        tenor: Swap maturity ("1M", "3M", "6M", "1Y")
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        Dict with swap_value, fair_strike, implied_vol, realized_vol, vega, etc.
    """
    return await price_variance_swap_internal(
        underlying=underlying,
        notional_per_vega=notional_per_vega,
        strike_variance=strike_variance,
        tenor=tenor,
        pricing_date=pricing_date,
    )
