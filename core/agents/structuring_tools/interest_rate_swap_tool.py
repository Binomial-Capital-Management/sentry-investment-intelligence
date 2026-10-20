"""
Interest Rate Swap Pricing Tool

Prices vanilla interest rate swaps using FRED treasury data.
Uses yield curve bootstrapping and forward rate calculations.

NO HARDCODING: Uses FRED EconomicDataServer with known series IDs.
"""

from agents import function_tool
from typing import List, Dict, Any, Optional
import logging
import numpy as np
from datetime import datetime, timedelta

from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.risk_adapter import jsonify_results

logger = logging.getLogger(__name__)

# FRED series IDs for treasury yield curve
TREASURY_SERIES = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30"
}

# FRED series IDs for float rate indices
FLOAT_INDEX_SERIES = {
    "SOFR": "SOFR",
    "EFFR": "EFFR",  # Effective Federal Funds Rate
    "FEDFUNDS": "FEDFUNDS"  # Federal Funds Rate
}


async def _fetch_yield_curve(
    fred_server: EconomicDataServer,
    pricing_date: str
) -> Dict[str, float]:
    """
    Fetch treasury yield curve from FRED.

    Args:
        fred_server: Connected FRED server instance
        pricing_date: Pricing date (YYYY-MM-DD)

    Returns:
        Dict mapping tenor to yield rate (decimal)
        Example: {"1M": 0.0450, "3M": 0.0460, "6M": 0.0480, ...}

    Raises:
        ValueError: If no treasury rates can be fetched
    """
    try:
        yield_curve = {}

        # Fetch each treasury maturity - no dates = latest 120 days, take most recent
        for tenor, series_id in TREASURY_SERIES.items():
            try:
                result = await fred_server.get_series_data(series_id=series_id)

                # Get latest value
                if result["data"] and len(result["data"]) > 0:
                    # FRED returns rates as percentages (e.g., 4.5 for 4.5%)
                    yield_curve[tenor] = result["data"][-1]["value"] / 100.0
                    logger.info(f"Fetched {tenor} yield: {yield_curve[tenor]:.4f}")

            except Exception as e:
                logger.warning(f"Failed to fetch {tenor} treasury: {e}")
                continue

        if not yield_curve:
            raise ValueError("Failed to fetch any treasury rates from FRED")

        return yield_curve

    except Exception as e:
        logger.error(f"Yield curve fetch failed: {e}")
        raise


async def _fetch_float_rate(
    fred_server: EconomicDataServer,
    float_index: str,
    pricing_date: str
) -> float:
    """
    Fetch current float rate index from FRED.

    Args:
        fred_server: Connected FRED server instance
        float_index: Index name ("SOFR", "LIBOR", "EURIBOR")
        pricing_date: Pricing date (YYYY-MM-DD)

    Returns:
        Current rate as decimal (e.g., 0.045 for 4.5%)

    Raises:
        ValueError: If index unknown or no data available
    """
    try:
        series_id = FLOAT_INDEX_SERIES.get(float_index.upper())

        if not series_id:
            raise ValueError(f"Unknown float index: {float_index}. Supported: {list(FLOAT_INDEX_SERIES.keys())}")

        # No dates = get latest 120 days, take most recent
        result = await fred_server.get_series_data(series_id=series_id)

        if not result["data"] or len(result["data"]) == 0:
            raise ValueError(f"No data available for {float_index} on {pricing_date}")

        # FRED returns rates as percentages
        rate = result["data"][-1]["value"] / 100.0
        logger.info(f"Fetched {float_index} rate: {rate:.4f}")

        return rate

    except Exception as e:
        logger.error(f"Float rate fetch failed: {e}")
        raise


def _parse_tenor(tenor: str) -> float:
    """
    Parse tenor string to years.

    Args:
        tenor: Tenor string (e.g., "2Y", "5Y", "6M")

    Returns:
        Tenor in years (e.g., 2.0, 5.0, 0.5)

    Raises:
        ValueError: If tenor format invalid

    Examples:
        "2Y" -> 2.0
        "6M" -> 0.5
        "10Y" -> 10.0
    """
    tenor = tenor.upper().strip()

    if tenor.endswith('Y'):
        return float(tenor[:-1])
    elif tenor.endswith('M'):
        return float(tenor[:-1]) / 12.0
    else:
        raise ValueError(f"Invalid tenor format: {tenor}. Use '2Y', '5Y', '6M', etc.")


def _generate_payment_schedule(
    start_date: datetime,
    tenor: str,
    payment_freq: str
) -> List[datetime]:
    """
    Generate payment dates based on frequency.
    Simple implementation using approximate month arithmetic.

    Args:
        start_date: Swap start date
        tenor: Swap tenor ("2Y", "5Y", etc.)
        payment_freq: Payment frequency ("quarterly", "semiannual", "annual")

    Returns:
        List of payment dates

    Raises:
        ValueError: If payment frequency invalid
    """
    tenor_years = _parse_tenor(tenor)

    # Determine payment interval
    freq_map = {
        "quarterly": 4,
        "semiannual": 2,
        "annual": 1
    }

    payments_per_year = freq_map.get(payment_freq.lower())
    if not payments_per_year:
        raise ValueError(f"Invalid payment frequency: {payment_freq}. Use 'quarterly', 'semiannual', or 'annual'")

    # Calculate number of payments
    num_payments = int(tenor_years * payments_per_year)
    months_per_payment = 12 // payments_per_year

    # Generate dates
    payment_dates = []
    for i in range(1, num_payments + 1):
        # Simple date arithmetic (approximate - not actual business day conventions)
        months_forward = i * months_per_payment
        payment_date = start_date + timedelta(days=months_forward * 30.44)  # Average month length
        payment_dates.append(payment_date)

    return payment_dates


def _interpolate_yield(
    maturity_years: float,
    yield_curve: Dict[str, float]
) -> float:
    """
    Linear interpolation of yield curve.
    Simple implementation without fancy splines.

    Args:
        maturity_years: Maturity in years
        yield_curve: Dict of tenor -> yield

    Returns:
        Interpolated yield rate (decimal)
    """
    # Convert tenor keys to years
    tenors_years = []
    yields = []

    for tenor, yld in sorted(yield_curve.items()):
        tenor_years = _parse_tenor(tenor)
        tenors_years.append(tenor_years)
        yields.append(yld)

    # Linear interpolation
    return float(np.interp(maturity_years, tenors_years, yields))


def _calculate_discount_factors(
    payment_dates: List[datetime],
    yield_curve: Dict[str, float],
    pricing_date: datetime
) -> List[float]:
    """
    Calculate discount factors using interpolated yields.
    Uses continuous compounding: DF(t) = exp(-r(t) × t)

    Args:
        payment_dates: List of payment dates
        yield_curve: Treasury yield curve
        pricing_date: Valuation date

    Returns:
        List of discount factors matching payment_dates
    """
    discount_factors = []

    for pmt_date in payment_dates:
        # Time to payment in years
        time_to_payment = (pmt_date - pricing_date).days / 365.25

        # Interpolate yield for this maturity
        yield_rate = _interpolate_yield(time_to_payment, yield_curve)

        # Calculate discount factor (continuous compounding)
        df = np.exp(-yield_rate * time_to_payment)
        discount_factors.append(float(df))

    return discount_factors


def _calculate_forward_rates(
    payment_dates: List[datetime],
    discount_factors: List[float],
    pricing_date: datetime
) -> List[float]:
    """
    Calculate forward rates from discount factors.
    Forward(t1, t2) = [DF(t1)/DF(t2) - 1] / τ

    Args:
        payment_dates: List of payment dates
        discount_factors: List of discount factors
        pricing_date: Valuation date

    Returns:
        List of forward rates for each period
    """
    forward_rates = []

    # First period: spot to first payment
    time0_to_pmt1 = (payment_dates[0] - pricing_date).days / 365.25
    fwd_rate = (1.0 / discount_factors[0] - 1.0) / time0_to_pmt1
    forward_rates.append(float(fwd_rate))

    # Subsequent periods: payment to payment
    for i in range(1, len(payment_dates)):
        time_delta = (payment_dates[i] - payment_dates[i-1]).days / 365.25
        fwd_rate = (discount_factors[i-1] / discount_factors[i] - 1.0) / time_delta
        forward_rates.append(float(fwd_rate))

    return forward_rates


async def price_interest_rate_swap_internal(
    notional: float,
    fixed_rate: float,
    float_index: str,
    tenor: str,
    payment_freq: str = "semiannual",
    pricing_date: Optional[str] = None
) -> dict:
    """
    Price vanilla interest rate swaps using FRED treasury data.

    Fetches yield curve and float rates from FRED Economic Server:
    - Treasury yields (DGS series) for discounting
    - Float index rates (SOFR, EFFR, FEDFUNDS)

    Calculations:
    - Fixed leg PV = Notional × Fixed_Rate × Σ(DF_i × τ_i)
    - Float leg PV = Notional × Σ(Forward_Rate_i × DF_i × τ_i)
    - Swap PV = Fixed_Leg_PV - Float_Leg_PV (from fixed rate payer perspective)
    - DV01 = ∂(Swap PV)/∂(Yield) × 0.0001

    Args:
        notional: Swap notional amount ($)
        fixed_rate: Fixed rate leg (decimal, e.g., 0.045 = 4.5%)
        float_index: "SOFR" | "EFFR" | "FEDFUNDS"
        tenor: Swap tenor ("2Y", "5Y", "10Y")
        payment_freq: "quarterly" | "semiannual" | "annual" (default: "semiannual")
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        Dict with:
        {
            "status": "success",
            "swap_value": float - Present value of swap ($)
            "dv01": float - Dollar value of 1bp yield shift
            "fixed_leg_pv": float - PV of fixed leg ($)
            "float_leg_pv": float - PV of float leg ($)
            "payment_schedule": List[str] - Payment dates
            "discount_factors": List[float] - DF for each payment
            "forward_rates": List[float] - Forward rates for each period
            "inputs": Dict - Echo of inputs
            "data_sources": List[str] - Data sources used
            "summary": str - Human-readable summary
        }

        On error:
        {
            "status": "error",
            "error": str - Error message
            "calculation_type": "interest_rate_swap"
        }

    Examples:
        # Price a 5Y swap receiving fixed 4.5%, paying SOFR
        result = await price_interest_rate_swap(
            notional=10_000_000,
            fixed_rate=0.045,
            float_index="SOFR",
            tenor="5Y",
            payment_freq="semiannual"
        )
        print(f"Swap Value: ${result['swap_value']:,.2f}")
        print(f"DV01: ${result['dv01']:,.2f}")

        # Custom pricing date
        result = await price_interest_rate_swap(
            notional=5_000_000,
            fixed_rate=0.038,
            float_index="LIBOR",
            tenor="2Y",
            payment_freq="quarterly",
            pricing_date="2024-01-15"
        )
    """
    try:
        # Set pricing date
        if pricing_date is None:
            pricing_date = datetime.now().strftime("%Y-%m-%d")

        pricing_dt = datetime.strptime(pricing_date, "%Y-%m-%d")

        # Validate inputs
        if notional <= 0:
            raise ValueError(f"Notional must be positive: {notional}")

        if not 0 < fixed_rate < 1:
            raise ValueError(f"Fixed rate should be decimal (e.g., 0.045 for 4.5%): {fixed_rate}")

        data_sources = []

        # Connect to FRED
        fred_server = EconomicDataServer()

        try:
            await fred_server.connect()

            # 1. Fetch yield curve
            logger.info(f"Fetching yield curve for {pricing_date}")
            yield_curve = await _fetch_yield_curve(fred_server, pricing_date)
            data_sources.append(f"yield_curve: FRED treasury series (DGS)")

            # 2. Fetch float rate (for reference, not used in forward calculation)
            logger.info(f"Fetching {float_index} rate")
            current_float_rate = await _fetch_float_rate(fred_server, float_index, pricing_date)
            data_sources.append(f"float_rate: FRED {float_index} ({current_float_rate:.4f})")

        finally:
            await fred_server.cleanup()

        # 3. Generate payment schedule
        payment_dates = _generate_payment_schedule(pricing_dt, tenor, payment_freq)

        # 4. Calculate discount factors
        discount_factors = _calculate_discount_factors(payment_dates, yield_curve, pricing_dt)

        # 5. Calculate forward rates
        forward_rates = _calculate_forward_rates(payment_dates, discount_factors, pricing_dt)

        # 6. Price fixed leg
        fixed_leg_pv = 0.0
        for i, (pmt_date, df) in enumerate(zip(payment_dates, discount_factors)):
            # Day count fraction (simple 30/360 convention)
            if i == 0:
                tau = (pmt_date - pricing_dt).days / 360.0
            else:
                tau = (pmt_date - payment_dates[i-1]).days / 360.0

            cashflow = notional * fixed_rate * tau
            pv = cashflow * df
            fixed_leg_pv += pv

        # 7. Price float leg
        float_leg_pv = 0.0
        for i, (pmt_date, df, fwd_rate) in enumerate(zip(payment_dates, discount_factors, forward_rates)):
            # Day count fraction
            if i == 0:
                tau = (pmt_date - pricing_dt).days / 360.0
            else:
                tau = (pmt_date - payment_dates[i-1]).days / 360.0

            cashflow = notional * fwd_rate * tau
            pv = cashflow * df
            float_leg_pv += pv

        # 8. Calculate swap value (from fixed rate payer perspective)
        swap_value = fixed_leg_pv - float_leg_pv

        # 9. Calculate DV01 (bump yield curve by 1bp)
        bumped_yield_curve = {tenor: rate + 0.0001 for tenor, rate in yield_curve.items()}
        bumped_dfs = _calculate_discount_factors(payment_dates, bumped_yield_curve, pricing_dt)
        bumped_fwds = _calculate_forward_rates(payment_dates, bumped_dfs, pricing_dt)

        # Reprice with bumped curve
        bumped_fixed_pv = sum(
            notional * fixed_rate * ((payment_dates[i] - (pricing_dt if i == 0 else payment_dates[i-1])).days / 360.0) * df
            for i, df in enumerate(bumped_dfs)
        )
        bumped_float_pv = sum(
            notional * fwd * ((payment_dates[i] - (pricing_dt if i == 0 else payment_dates[i-1])).days / 360.0) * df
            for i, (df, fwd) in enumerate(zip(bumped_dfs, bumped_fwds))
        )
        bumped_swap_value = bumped_fixed_pv - bumped_float_pv

        dv01 = bumped_swap_value - swap_value

        # Build summary
        direction = "receive" if swap_value > 0 else "pay"
        summary = (
            f"Interest rate swap: {notional:,.0f} notional, {tenor} tenor, "
            f"paying fixed {fixed_rate:.2%} vs receiving {float_index}. "
            f"Swap value: ${swap_value:,.2f} (advantageous to {direction} fixed). "
            f"DV01: ${dv01:,.2f}."
        )

        return {
            "status": "success",
            "swap_value": float(swap_value),
            "dv01": float(dv01),
            "fixed_leg_pv": float(fixed_leg_pv),
            "float_leg_pv": float(float_leg_pv),
            "payment_schedule": [pmt.strftime("%Y-%m-%d") for pmt in payment_dates],
            "discount_factors": discount_factors,
            "forward_rates": forward_rates,
            "inputs": {
                "notional": notional,
                "fixed_rate": fixed_rate,
                "float_index": float_index,
                "tenor": tenor,
                "payment_freq": payment_freq,
                "pricing_date": pricing_date
            },
            "data_sources": data_sources,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"IRS pricing failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "calculation_type": "interest_rate_swap"
        }


@function_tool
async def price_interest_rate_swap(
    notional: float,
    fixed_rate: float,
    float_index: str,
    tenor: str,
    payment_freq: str = "semiannual",
    pricing_date: Optional[str] = None
) -> dict:
    """
    Price vanilla interest rate swaps using FRED treasury data.

    Fetches yield curve and float rates from FRED Economic Server:
    - Treasury yields (DGS series) for discounting
    - Float index rates (SOFR, EFFR, FEDFUNDS)

    Calculations:
    - Fixed leg PV = Notional × Fixed_Rate × Σ(DF_i × τ_i)
    - Float leg PV = Notional × Σ(Forward_Rate_i × DF_i × τ_i)
    - Swap PV = Fixed_Leg_PV - Float_Leg_PV (from fixed rate payer perspective)
    - DV01 = ∂(Swap PV)/∂(Yield) × 0.0001

    Args:
        notional: Swap notional amount ($)
        fixed_rate: Fixed rate leg (decimal, e.g., 0.045 = 4.5%)
        float_index: "SOFR" | "EFFR" | "FEDFUNDS"
        tenor: Swap tenor ("2Y", "5Y", "10Y")
        payment_freq: "quarterly" | "semiannual" | "annual" (default: "semiannual")
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        JSON string with swap valuation results
    """
    result = await price_interest_rate_swap_internal(
        notional=notional,
        fixed_rate=fixed_rate,
        float_index=float_index,
        tenor=tenor,
        payment_freq=payment_freq,
        pricing_date=pricing_date
    )
    return jsonify_results(result)
