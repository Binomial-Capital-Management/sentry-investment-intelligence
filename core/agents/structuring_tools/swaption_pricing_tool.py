"""
Swaption Pricing Tool

Prices interest rate swaptions using Black or Bachelier models.
Estimates volatility from historical swap rate movements (similar to equity options).

NO HARDCODING: Uses FRED EconomicDataServer with dynamic field discovery.
"""

from agents import function_tool
from typing import Dict, Any, Optional, List
import logging
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm

from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.risk_adapter import jsonify_results

# Import shared functions from IRS tool
from core.agents.structuring_tools.interest_rate_swap_tool import (
    _fetch_yield_curve,
    _fetch_float_rate,
    _parse_tenor,
    _generate_payment_schedule,
    _interpolate_yield,
    _calculate_discount_factors,
    _calculate_forward_rates,
    TREASURY_SERIES
)

logger = logging.getLogger(__name__)


async def _estimate_swaption_volatility(
    fred_server: EconomicDataServer,
    swap_tenor: str,
    lookback_days: int = 252
) -> float:
    """
    Estimate swaption volatility from historical swap rate movements.

    Same methodology as equity option volatility calculation:
    - Fetch historical rates for the swap tenor
    - Calculate daily log returns
    - Annualize: σ_annual = σ_daily × √252

    Args:
        fred_server: Connected FRED server
        swap_tenor: Swap maturity ("2Y", "5Y", "10Y")
        lookback_days: Days of historical data (default: 252 = 1 year)

    Returns:
        Estimated annualized volatility (decimal)

    Raises:
        ValueError: If insufficient data available
    """
    try:
        tenor_years = _parse_tenor(swap_tenor)

        # Map swap tenor to appropriate treasury series
        if tenor_years <= 0.5:
            series_id = "DGS3MO"
        elif tenor_years <= 1:
            series_id = "DGS1"
        elif tenor_years <= 3:
            series_id = "DGS2"
        elif tenor_years <= 7:
            series_id = "DGS5"
        else:
            series_id = "DGS10"

        # Fetch historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days + 30)  # Extra buffer

        logger.info(f"Fetching {series_id} data for volatility estimation")
        result = await fred_server.get_series_data(
            series_id=series_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )

        if not result["data"] or len(result["data"]) < 20:
            raise ValueError(f"Insufficient data for volatility estimation: {len(result['data'])} points")

        # Extract rates (convert from percentages to decimals)
        rates = [point["value"] / 100.0 for point in result["data"]]

        # Calculate log returns
        log_returns = []
        for i in range(1, len(rates)):
            if rates[i] > 0 and rates[i-1] > 0:  # Avoid log(0)
                log_returns.append(np.log(rates[i] / rates[i-1]))

        if len(log_returns) < 10:
            raise ValueError(f"Insufficient valid returns for volatility: {len(log_returns)}")

        # Calculate volatility
        mean_return = np.mean(log_returns)
        variance = np.sum((r - mean_return)**2 for r in log_returns) / (len(log_returns) - 1)
        daily_vol = np.sqrt(variance)

        # Annualize (252 trading days)
        annual_vol = daily_vol * np.sqrt(252)

        logger.info(f"Estimated {swap_tenor} swaption vol: {annual_vol:.2%} (from {len(rates)} days of {series_id})")

        return float(annual_vol)

    except Exception as e:
        logger.error(f"Volatility estimation failed: {e}")
        raise


def _calculate_forward_swap_rate(
    payment_dates: List[datetime],
    discount_factors: List[float],
    pricing_date: datetime
) -> float:
    """
    Calculate forward swap rate from discount factors.

    Formula:
        Forward_Swap_Rate = (DF_start - DF_end) / Annuity_Factor

    Where:
        DF_start = 1.0 (discount factor at pricing date)
        DF_end = discount factor to final payment date
        Annuity = Σ(DF_i × τ_i) for all payment periods

    Args:
        payment_dates: List of swap payment dates
        discount_factors: Discount factors for each payment
        pricing_date: Valuation date

    Returns:
        Forward swap rate (decimal)
    """
    if not payment_dates or not discount_factors:
        raise ValueError("Empty payment schedule or discount factors")

    # Calculate annuity factor
    annuity = 0.0
    for i, (pmt_date, df) in enumerate(zip(payment_dates, discount_factors)):
        # Day count fraction (30/360 convention)
        if i == 0:
            tau = (pmt_date - pricing_date).days / 360.0
        else:
            tau = (pmt_date - payment_dates[i-1]).days / 360.0

        annuity += df * tau

    # Forward swap rate = (DF_0 - DF_n) / Annuity
    # DF_0 = 1.0 (at pricing date)
    # DF_n = last discount factor
    forward_rate = (1.0 - discount_factors[-1]) / annuity

    return float(forward_rate)


def _calculate_annuity_factor(
    payment_dates: List[datetime],
    discount_factors: List[float],
    pricing_date: datetime
) -> float:
    """
    Calculate annuity factor (PV of receiving 1% on all payment dates).

    Formula:
        Annuity = Σ(DF_i × τ_i)

    Where:
        DF_i = discount factor to payment date i
        τ_i = day count fraction for period i (30/360)

    Args:
        payment_dates: List of payment dates
        discount_factors: Discount factors for each payment
        pricing_date: Valuation date

    Returns:
        Annuity factor (present value per 1% rate)
    """
    annuity = 0.0

    for i, (pmt_date, df) in enumerate(zip(payment_dates, discount_factors)):
        # Day count fraction (30/360 convention)
        if i == 0:
            tau = (pmt_date - pricing_date).days / 360.0
        else:
            tau = (pmt_date - payment_dates[i-1]).days / 360.0

        annuity += df * tau

    return float(annuity)


def _black_swaption_price(
    forward_rate: float,
    strike: float,
    annuity: float,
    time_to_expiry: float,
    volatility: float,
    option_type: str
) -> Dict[str, float]:
    """
    Black (lognormal) model for swaption pricing.

    Formula:
        C_payer = A × [F×N(d1) - K×N(d2)]
        C_receiver = A × [K×N(-d2) - F×N(-d1)]

    Where:
        d1 = [ln(F/K) + σ²T/2] / (σ√T)
        d2 = d1 - σ√T
        F = forward swap rate
        K = strike rate
        A = annuity factor
        σ = volatility (annualized)
        T = time to expiry (years)

    Args:
        forward_rate: Forward swap rate (decimal)
        strike: Strike rate (decimal)
        annuity: Annuity factor
        time_to_expiry: Time to expiry (years)
        volatility: Annualized volatility (decimal)
        option_type: "payer" or "receiver"

    Returns:
        Dict with price, delta, vega
    """
    # Edge case: At expiry, return intrinsic value
    if time_to_expiry <= 1e-6:
        if option_type == "payer":
            intrinsic = max(0, forward_rate - strike)
        else:
            intrinsic = max(0, strike - forward_rate)

        return {
            "price": annuity * intrinsic,
            "delta": annuity if option_type == "payer" else -annuity,
            "vega": 0.0
        }

    # Edge case: Forward or strike near zero, switch to Bachelier
    if forward_rate <= 1e-6 or strike <= 1e-6:
        logger.warning("Forward rate or strike near zero, using Bachelier model")
        return _bachelier_swaption_price(forward_rate, strike, annuity, time_to_expiry, volatility, option_type)

    # Calculate d1 and d2
    d1 = (np.log(forward_rate / strike) + 0.5 * volatility**2 * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
    d2 = d1 - volatility * np.sqrt(time_to_expiry)

    # Calculate price
    if option_type == "payer":
        price = annuity * (forward_rate * norm.cdf(d1) - strike * norm.cdf(d2))
        delta = annuity * norm.cdf(d1)
    else:  # receiver
        price = annuity * (strike * norm.cdf(-d2) - forward_rate * norm.cdf(-d1))
        delta = -annuity * norm.cdf(-d1)

    # Calculate vega (per 1% vol change)
    vega = annuity * forward_rate * norm.pdf(d1) * np.sqrt(time_to_expiry) / 100.0

    return {
        "price": float(price),
        "delta": float(delta),
        "vega": float(vega)
    }


def _bachelier_swaption_price(
    forward_rate: float,
    strike: float,
    annuity: float,
    time_to_expiry: float,
    volatility: float,
    option_type: str
) -> Dict[str, float]:
    """
    Bachelier (normal) model for swaption pricing.
    Used when rates near zero (allows negative rates).

    Formula:
        C_payer = A × [(F-K)×N(d) + σ√T×n(d)]
        C_receiver = A × [(K-F)×N(-d) + σ√T×n(d)]

    Where:
        d = (F-K) / (σ√T)
        n(d) = normal PDF = exp(-d²/2) / √(2π)
        N(d) = normal CDF

    Args:
        forward_rate: Forward swap rate (decimal)
        strike: Strike rate (decimal)
        annuity: Annuity factor
        time_to_expiry: Time to expiry (years)
        volatility: Annualized volatility (decimal)
        option_type: "payer" or "receiver"

    Returns:
        Dict with price, delta, vega
    """
    # Edge case: At expiry, return intrinsic value
    if time_to_expiry <= 1e-6:
        if option_type == "payer":
            intrinsic = max(0, forward_rate - strike)
        else:
            intrinsic = max(0, strike - forward_rate)

        return {
            "price": annuity * intrinsic,
            "delta": annuity if option_type == "payer" else -annuity,
            "vega": 0.0
        }

    # Calculate d
    vol_sqrt_t = volatility * np.sqrt(time_to_expiry)

    if vol_sqrt_t <= 1e-10:
        # Zero volatility case - intrinsic value only
        if option_type == "payer":
            intrinsic = max(0, forward_rate - strike)
        else:
            intrinsic = max(0, strike - forward_rate)

        return {
            "price": annuity * intrinsic,
            "delta": annuity if option_type == "payer" else -annuity,
            "vega": 0.0
        }

    d = (forward_rate - strike) / vol_sqrt_t

    # Calculate price
    if option_type == "payer":
        price = annuity * ((forward_rate - strike) * norm.cdf(d) + vol_sqrt_t * norm.pdf(d))
        delta = annuity * norm.cdf(d)
    else:  # receiver
        price = annuity * ((strike - forward_rate) * norm.cdf(-d) + vol_sqrt_t * norm.pdf(d))
        delta = -annuity * norm.cdf(-d)

    # Calculate vega (per 1% vol change)
    vega = annuity * norm.pdf(d) * np.sqrt(time_to_expiry) / 100.0

    return {
        "price": float(price),
        "delta": float(delta),
        "vega": float(vega)
    }


async def price_swaption_internal(
    notional: float,
    tenor: str,
    float_index: str,
    payment_freq: str,
    option_type: str,
    expiry: str,
    strike: float,
    pricing_model: Optional[str] = "black",
    volatility: Optional[float] = None,
    pricing_date: Optional[str] = None
) -> dict:
    """
    Price interest rate swaptions using Black or Bachelier models.

    Volatility Handling (same as equity options):
    - If volatility provided: Use directly
    - If volatility=None: Estimate from historical swap rate volatility

    Historical vol estimation:
    1. Fetch 1 year of daily treasury yields for swap maturity
    2. Calculate daily swap rate log returns
    3. Compute annualized volatility: σ_daily × √252

    Args:
        notional: Notional amount ($)
        tenor: Swap maturity ("2Y", "5Y", "10Y")
        float_index: "SOFR" | "LIBOR" | "EURIBOR"
        payment_freq: "quarterly" | "semiannual" | "annual"
        option_type: "payer" | "receiver"
            - payer: Right to enter swap as fixed rate PAYER
            - receiver: Right to enter swap as fixed rate RECEIVER
        expiry: Option expiration date (YYYY-MM-DD)
        strike: Strike rate (decimal, e.g., 0.045 = 4.5%)
        pricing_model: "black" | "bachelier" (default: "black")
            - black: Lognormal model (industry standard)
            - bachelier: Normal model (for near-zero rates)
        volatility: Optional volatility override (annualized decimal, e.g., 0.50 = 50%)
            If not provided, estimated from historical swap rates
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        Dict with:
        {
            "status": "success",
            "swaption_price": float - Swaption premium ($)
            "forward_swap_rate": float - Forward swap rate (decimal)
            "annuity_factor": float - PV of 1% on all payments
            "delta": float - Delta (sensitivity to forward swap rate)
            "vega": float - Vega (sensitivity to volatility, per 1%)
            "time_to_expiry": float - Years to expiry
            "volatility_used": float - Volatility used in pricing
            "inputs": Dict - Echo of inputs
            "data_sources": List[str] - Data sources used
            "summary": str - Human-readable summary
        }

    Examples:
        # Basic payer swaption (right to pay fixed)
        result = await price_swaption(
            notional=10_000_000,
            tenor="5Y",
            float_index="SOFR",
            payment_freq="semiannual",
            option_type="payer",
            expiry="2026-01-15",
            strike=0.045
        )
        print(f"Swaption Price: ${result['swaption_price']:,.2f}")
        print(f"Forward Swap Rate: {result['forward_swap_rate']:.2%}")

        # Receiver swaption with custom volatility
        result = await price_swaption(
            notional=5_000_000,
            tenor="10Y",
            float_index="LIBOR",
            payment_freq="quarterly",
            option_type="receiver",
            expiry="2025-06-30",
            strike=0.038,
            volatility=0.60  # 60% vol from Bloomberg
        )
    """
    try:
        # Set pricing date
        if pricing_date is None:
            pricing_date = datetime.now().strftime("%Y-%m-%d")

        pricing_dt = datetime.strptime(pricing_date, "%Y-%m-%d")

        # Parse expiry
        try:
            expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"expiry must be in YYYY-MM-DD format, got: {expiry}")

        # Calculate time to expiry
        time_to_expiry = (expiry_dt - pricing_dt).days / 365.25

        if time_to_expiry < 0:
            raise ValueError(f"Expiry date {expiry} is in the past (pricing date: {pricing_date})")

        # Validate inputs
        if notional <= 0:
            raise ValueError(f"Notional must be positive: {notional}")

        if not 0 < strike < 1:
            raise ValueError(f"Strike should be decimal (e.g., 0.045 for 4.5%): {strike}")

        option_type = option_type.lower()
        if option_type not in ["payer", "receiver"]:
            raise ValueError(f"option_type must be 'payer' or 'receiver', got: {option_type}")

        pricing_model = pricing_model.lower() if pricing_model else "black"
        if pricing_model not in ["black", "bachelier"]:
            raise ValueError(f"pricing_model must be 'black' or 'bachelier', got: {pricing_model}")

        data_sources = []

        # Connect to FRED
        fred_server = EconomicDataServer()

        try:
            await fred_server.connect()

            # Fetch yield curve
            logger.info(f"Fetching yield curve for {pricing_date}")
            yield_curve = await _fetch_yield_curve(fred_server, pricing_date)
            data_sources.append("yield_curve: FRED treasury series (DGS)")

            # Fetch float rate (for reference)
            logger.info(f"Fetching {float_index} rate")
            current_float_rate = await _fetch_float_rate(fred_server, float_index, pricing_date)
            data_sources.append(f"float_rate: FRED {float_index} ({current_float_rate:.4f})")

            # Fetch or estimate volatility
            if volatility is not None:
                vol = volatility
                data_sources.append(f"volatility: user_override ({vol:.2%})")
            else:
                logger.info(f"Estimating swaption volatility from historical data")
                vol = await _estimate_swaption_volatility(fred_server, tenor, lookback_days=252)
                data_sources.append(f"volatility: estimated from 1Y historical {tenor} swap rates ({vol:.2%})")

        finally:
            await fred_server.cleanup()

        # Calculate swap schedule (reuse IRS tool functions)
        payment_dates = _generate_payment_schedule(pricing_dt, tenor, payment_freq)
        discount_factors = _calculate_discount_factors(payment_dates, yield_curve, pricing_dt)

        # Calculate forward swap rate
        forward_swap_rate = _calculate_forward_swap_rate(payment_dates, discount_factors, pricing_dt)

        # Calculate annuity factor
        annuity_factor = _calculate_annuity_factor(payment_dates, discount_factors, pricing_dt)

        # Price swaption
        if pricing_model == "black":
            result = _black_swaption_price(
                forward_swap_rate,
                strike,
                annuity_factor,
                time_to_expiry,
                vol,
                option_type
            )
        else:  # bachelier
            result = _bachelier_swaption_price(
                forward_swap_rate,
                strike,
                annuity_factor,
                time_to_expiry,
                vol,
                option_type
            )

        # Scale premium by notional
        swaption_premium = result["price"] * notional

        # Build summary
        if option_type == "payer":
            direction = f"right to PAY fixed {strike:.2%}"
        else:
            direction = f"right to RECEIVE fixed {strike:.2%}"

        moneyness = "ATM" if abs(forward_swap_rate - strike) < 0.001 else ("ITM" if (option_type == "payer" and forward_swap_rate > strike) or (option_type == "receiver" and strike > forward_swap_rate) else "OTM")

        # Define underlying swap description
        underlying_swap = f"{tenor} {float_index} swap, {payment_freq} payments"
        
        summary = (
            f"Swaption ({option_type}) on {tenor} swap expiring {expiry}. "
            f"Strike: {strike:.2%}, Forward: {forward_swap_rate:.2%} ({moneyness}). "
            f"Premium: ${swaption_premium:,.2f} (using {pricing_model} model with {vol:.1%} vol)."
        )

        return {
            "status": "success",
            "swaption_price": float(swaption_premium),
            "forward_swap_rate": float(forward_swap_rate),
            "annuity_factor": float(annuity_factor),
            "delta": float(result["delta"] * notional),
            "vega": float(result["vega"] * notional),
            "time_to_expiry": float(time_to_expiry),
            "volatility_used": float(vol),
            "inputs": {
                "underlying_swap": underlying_swap,
                "option_type": option_type,
                "expiry": expiry,
                "strike": strike,
                "pricing_model": pricing_model,
                "pricing_date": pricing_date,
                "notional": notional,
                "tenor": tenor,
                "float_index": float_index,
                "payment_freq": payment_freq
            },
            "data_sources": data_sources,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Swaption pricing failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "calculation_type": "swaption_pricing"
        }


@function_tool
async def price_swaption(
    notional: float,
    tenor: str,
    float_index: str,
    payment_freq: str,
    option_type: str,
    expiry: str,
    strike: float,
    pricing_model: Optional[str] = "black",
    volatility: Optional[float] = None,
    pricing_date: Optional[str] = None
) -> str:
    """
    Price interest rate swaptions using Black or Bachelier models.

    Args:
        notional: Notional amount ($)
        tenor: Swap maturity ("2Y", "5Y", "10Y")
        float_index: "SOFR" | "LIBOR" | "EURIBOR"
        payment_freq: "quarterly" | "semiannual" | "annual"
        option_type: "payer" | "receiver"
        expiry: Option expiration date (YYYY-MM-DD)
        strike: Strike rate (decimal, e.g., 0.045 = 4.5%)
        pricing_model: "black" | "bachelier" (default: "black")
        volatility: Optional volatility override (annualized decimal)
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        JSON string with swaption pricing analysis
    """
    result = await price_swaption_internal(
        notional=notional,
        tenor=tenor,
        float_index=float_index,
        payment_freq=payment_freq,
        option_type=option_type,
        expiry=expiry,
        strike=strike,
        pricing_model=pricing_model,
        volatility=volatility,
        pricing_date=pricing_date
    )
    
    return jsonify_results(result)
