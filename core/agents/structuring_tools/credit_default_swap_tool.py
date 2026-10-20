"""
Credit Default Swap (CDS) Pricing Tool

Prices credit default swaps using Merton/KMV model for default probability estimation.
Falls back to generic investment-grade assumptions when equity data unavailable.

NO HARDCODING: Uses FMP dynamic discovery for company data, FRED for rates.

LIMITATIONS:
- Model-implied, not market CDS spreads
- Simplified constant hazard rate assumption
- Best for: relative comparisons, screening
- NOT for: trading, regulatory capital
"""

from agents import function_tool
from typing import Dict, Any, Optional, List
import logging
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.EconomicDataServer import EconomicDataServer
from core.utils.risk_adapter import jsonify_results

# Import shared functions from IRS tool
from core.agents.structuring_tools.interest_rate_swap_tool import (
    _fetch_yield_curve,
    _parse_tenor,
    _calculate_discount_factors
)

logger = logging.getLogger(__name__)

# Generic fallback assumptions (BBB-equivalent)
GENERIC_ANNUAL_DEFAULT_RATE = 0.0025  # 0.25% per year
GENERIC_RECOVERY_RATE = 0.40  # 40% recovery

# Recovery rate by asset coverage ratio
def _estimate_recovery_rate(
    total_assets: float,
    total_debt: float,
    tangible_assets: Optional[float] = None
) -> Dict[str, Any]:
    """
    Estimate recovery rate from balance sheet fundamentals.
    
    Recovery rate depends on:
    - Asset coverage ratio = Tangible Assets / Total Debt
    - Higher coverage → higher recovery
    
    Empirical ranges:
    - Coverage > 2.0: 60-70% recovery (asset-rich)
    - Coverage 1.0-2.0: 40-60% recovery (average)
    - Coverage < 1.0: 20-40% recovery (asset-light)
    
    Args:
        total_assets: Total assets ($)
        total_debt: Total debt ($)
        tangible_assets: Tangible assets (if available)
    
    Returns:
        Dict with recovery_rate and explanation
    """
    if total_debt <= 0:
        return {"recovery_rate": 0.70, "explanation": "No debt → high recovery assumed"}
    
    # Use tangible assets if available, otherwise conservative estimate
    if tangible_assets is not None and tangible_assets > 0:
        coverage_ratio = tangible_assets / total_debt
        asset_type = "tangible"
    else:
        # Conservative: assume 70% of total assets are tangible
        coverage_ratio = (total_assets * 0.70) / total_debt
        asset_type = "estimated tangible"
    
    # Map coverage to recovery rate (empirical)
    if coverage_ratio >= 2.0:
        recovery_rate = min(0.70, 0.40 + (coverage_ratio - 2.0) * 0.10)
        explanation = f"High {asset_type} asset coverage ({coverage_ratio:.2f}x)"
    elif coverage_ratio >= 1.0:
        recovery_rate = 0.40 + (coverage_ratio - 1.0) * 0.20
        explanation = f"Moderate {asset_type} asset coverage ({coverage_ratio:.2f}x)"
    else:
        recovery_rate = max(0.20, 0.40 * coverage_ratio)
        explanation = f"Low {asset_type} asset coverage ({coverage_ratio:.2f}x)"
    
    return {
        "recovery_rate": float(recovery_rate),
        "coverage_ratio": float(coverage_ratio),
        "explanation": explanation
    }


async def _fetch_company_credit_data(
    ticker: str,
    fmp_server: FMPMarketDataServer
) -> Dict[str, Any]:
    """
    Fetch company credit-relevant data from FMP using dynamic field discovery.

    Fetches:
    - Market capitalization (equity value)
    - Total debt (from balance sheet)
    - Historical stock prices for volatility calculation

    Args:
        ticker: Company ticker symbol
        fmp_server: Connected FMP server instance

    Returns:
        Dict with:
        {
            "market_cap": float - Market capitalization ($)
            "total_debt": float - Total debt ($)
            "equity_volatility": float - Annualized equity volatility
            "stock_price": float - Current stock price
            "data_sources": List[str] - Data sources used
        }

    Raises:
        ValueError: If critical data missing or ticker invalid
    """
    try:
        data_sources = []

        # 1. Get market cap and current price
        logger.info(f"Fetching market data for {ticker}")
        quote_result = await fmp_server.discover_and_fetch(
            ticker=ticker,
            endpoint_category="quote",
            required_fields=["marketCap", "price"]
        )

        if not quote_result or "data" not in quote_result:
            raise ValueError(f"No market data found for {ticker}")

        quote_data = quote_result["data"]
        market_cap = quote_data.get("marketCap")
        stock_price = quote_data.get("price")

        if market_cap is None or market_cap <= 0:
            raise ValueError(f"Invalid market cap for {ticker}: {market_cap}")

        if stock_price is None or stock_price <= 0:
            raise ValueError(f"Invalid stock price for {ticker}: {stock_price}")

        data_sources.append(f"market_cap: FMP quote endpoint ({market_cap:,.0f})")
        logger.info(f"Market cap for {ticker}: ${market_cap:,.0f}")

        # 2. Get debt and assets from balance sheet
        logger.info(f"Fetching balance sheet for {ticker}")
        bs_result = await fmp_server.discover_and_fetch(
            ticker=ticker,
            endpoint_category="balance-sheet-statement",
            required_fields=["totalDebt", "totalAssets"]
        )

        if not bs_result or "data" not in bs_result:
            raise ValueError(f"No balance sheet data found for {ticker}")

        bs_data = bs_result["data"]
        if isinstance(bs_data, list):
            bs_data = bs_data[0]  # Take most recent

        total_debt = bs_data.get("totalDebt")
        total_assets = bs_data.get("totalAssets")
        tangible_assets = bs_data.get("tangibleAssets") or bs_data.get("totalAssets")

        if total_debt is None or total_debt < 0:
            # Use fallback: estimate debt as 10% of market cap
            total_debt = market_cap * 0.10
            data_sources.append(f"total_debt: ESTIMATED (10% of market cap = {total_debt:,.0f})")
            logger.warning(f"No debt data for {ticker}, using 10% market cap estimate")
        else:
            data_sources.append(f"total_debt: FMP balance sheet ({total_debt:,.0f})")
            logger.info(f"Total debt for {ticker}: ${total_debt:,.0f}")
        
        if total_assets is None or total_assets <= 0:
            total_assets = market_cap + total_debt  # Estimate from market value
            data_sources.append(f"total_assets: ESTIMATED ({total_assets:,.0f})")
        else:
            data_sources.append(f"total_assets: FMP balance sheet ({total_assets:,.0f})")

        # 3. Calculate equity volatility from historical prices
        logger.info(f"Fetching historical prices for {ticker} volatility calculation")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 + 30)  # 1 year + buffer

        hist_result = await fmp_server.discover_and_fetch(
            ticker=ticker,
            endpoint_category="historical-price-full",
            required_fields=["historical"],
            params={
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d")
            }
        )

        if not hist_result or "data" not in hist_result:
            raise ValueError(f"No historical price data for {ticker}")

        hist_data = hist_result["data"]
        if "historical" in hist_data:
            hist_prices = hist_data["historical"]
        else:
            hist_prices = hist_data if isinstance(hist_data, list) else []

        if len(hist_prices) < 20:
            raise ValueError(f"Insufficient price history for {ticker}: {len(hist_prices)} days")

        # Extract closing prices
        prices = []
        for entry in hist_prices:
            close_price = entry.get("close") or entry.get("adjClose")
            if close_price and close_price > 0:
                prices.append(float(close_price))

        if len(prices) < 20:
            raise ValueError(f"Insufficient valid prices for {ticker}: {len(prices)}")

        # Calculate log returns
        log_returns = []
        for i in range(1, len(prices)):
            log_returns.append(np.log(prices[i] / prices[i-1]))

        # Calculate volatility
        mean_return = np.mean(log_returns)
        variance = np.sum((r - mean_return)**2 for r in log_returns) / (len(log_returns) - 1)
        daily_vol = np.sqrt(variance)

        # Annualize (252 trading days)
        equity_volatility = daily_vol * np.sqrt(252)

        data_sources.append(f"equity_volatility: calculated from {len(prices)} days of prices ({equity_volatility:.2%})")
        logger.info(f"Equity volatility for {ticker}: {equity_volatility:.2%}")

        return {
            "market_cap": float(market_cap),
            "total_debt": float(total_debt),
            "total_assets": float(total_assets),
            "tangible_assets": float(tangible_assets) if tangible_assets else None,
            "equity_volatility": float(equity_volatility),
            "stock_price": float(stock_price),
            "data_sources": data_sources
        }

    except Exception as e:
        logger.error(f"Failed to fetch credit data for {ticker}: {e}")
        raise


def _estimate_survival_curve_merton(
    market_cap: float,
    total_debt: float,
    equity_volatility: float,
    risk_free_rate: float,
    tenor_years: float
) -> Dict[str, Any]:
    """
    Estimate survival curve using Merton/KMV model.

    Merton Model:
    - Distance-to-default: DD = [ln(E/D) + (r + σ_E²/2)T] / (σ_E√T)
    - Default probability: PD = N(-DD)
    - Hazard rate (constant): λ = -ln(1 - PD) / T
    - Survival curve: S(t) = exp(-λ × t)

    Args:
        market_cap: Market capitalization (equity value)
        total_debt: Total debt value
        equity_volatility: Annualized equity volatility
        risk_free_rate: Risk-free rate (decimal)
        tenor_years: CDS tenor in years

    Returns:
        Dict with:
        {
            "survival_curve": Dict[float, float] - Quarterly survival probabilities
            "distance_to_default": float - Merton distance-to-default
            "default_probability": float - Cumulative default probability
            "hazard_rate": float - Constant hazard rate
            "warnings": List[str] - Warnings if any
        }

    Raises:
        ValueError: If inputs invalid or calculation fails
    """
    try:
        warnings = []

        # Validate inputs
        if market_cap <= 0:
            raise ValueError(f"Market cap must be positive: {market_cap}")

        if total_debt <= 0:
            raise ValueError(f"Total debt must be positive: {total_debt}")

        if equity_volatility <= 0 or equity_volatility > 2.0:
            raise ValueError(f"Equity volatility out of reasonable range: {equity_volatility}")

        if tenor_years <= 0:
            raise ValueError(f"Tenor must be positive: {tenor_years}")

        # Calculate distance-to-default
        E = market_cap
        D = total_debt
        sigma_E = equity_volatility
        r = risk_free_rate
        T = tenor_years

        # DD = [ln(E/D) + (r + σ²/2)T] / (σ√T)
        numerator = np.log(E / D) + (r + 0.5 * sigma_E**2) * T
        denominator = sigma_E * np.sqrt(T)

        if denominator <= 0:
            raise ValueError(f"Invalid denominator in DD calculation: {denominator}")

        distance_to_default = numerator / denominator

        # Default probability (cumulative over T years)
        default_probability = norm.cdf(-distance_to_default)

        # Ensure default probability is reasonable
        if default_probability >= 0.99:
            warnings.append(f"Very high default probability ({default_probability:.1%}). Results may be unreliable.")

        if default_probability <= 0.0001:
            warnings.append(f"Very low default probability ({default_probability:.2%}). Model may underestimate risk.")

        # Constant hazard rate: λ = -ln(1 - PD) / T
        if default_probability >= 1.0:
            # Edge case: PD = 1 means infinite hazard rate
            hazard_rate = float('inf')
            warnings.append("Default probability = 100%, hazard rate infinite")
        else:
            hazard_rate = -np.log(1.0 - default_probability) / T

        # Generate quarterly survival curve
        survival_curve = {}
        quarters = int(T * 4)  # Number of quarters

        for i in range(1, quarters + 1):
            t = i * 0.25  # Quarterly intervals
            if hazard_rate == float('inf'):
                survival_prob = 0.0
            else:
                survival_prob = np.exp(-hazard_rate * t)

            survival_curve[float(t)] = float(survival_prob)

        logger.info(f"Merton model: DD={distance_to_default:.2f}, PD={default_probability:.2%}, λ={hazard_rate:.4f}")

        return {
            "survival_curve": survival_curve,
            "distance_to_default": float(distance_to_default),
            "default_probability": float(default_probability),
            "hazard_rate": float(hazard_rate),
            "warnings": warnings
        }

    except Exception as e:
        logger.error(f"Merton model calculation failed: {e}")
        raise


def _fallback_survival_curve(tenor_years: float) -> Dict[str, Any]:
    """
    Generate generic survival curve using BBB-equivalent assumptions.

    Uses conservative annual default rate of 0.25% (investment-grade).

    Args:
        tenor_years: CDS tenor in years

    Returns:
        Dict with:
        {
            "survival_curve": Dict[float, float] - Quarterly survival probabilities
            "warnings": List[str] - BIG warning about generic data
        }
    """
    warnings = [
        "⚠️ WARNING: Using GENERIC BBB-equivalent assumptions (0.25% annual default rate).",
        "⚠️ Provide survival_curve parameter for accurate pricing.",
        "⚠️ Results suitable for screening only, NOT trading or risk management."
    ]

    # Generate quarterly survival curve
    survival_curve = {}
    quarters = int(tenor_years * 4)

    for i in range(1, quarters + 1):
        t = i * 0.25  # Quarterly intervals
        # Survival = (1 - annual_default_rate)^t
        survival_prob = (1.0 - GENERIC_ANNUAL_DEFAULT_RATE) ** t
        survival_curve[float(t)] = float(survival_prob)

    logger.warning("Using generic survival curve - results are approximate")

    return {
        "survival_curve": survival_curve,
        "warnings": warnings
    }


def _calculate_fair_spread(
    survival_curve: Dict[float, float],
    discount_factors: List[float],
    payment_dates: List[datetime],
    pricing_date: datetime,
    recovery_rate: float
) -> float:
    """
    Calculate fair CDS spread (par spread) that makes CDS value = 0.
    
    Fair Spread = Σ((1-recovery) × DF_i × default_prob_i) / Σ(DF_i × survival_i × Δt_i)
    
    Args:
        survival_curve: Dict mapping time → survival probability
        discount_factors: Discount factors for payment dates
        payment_dates: CDS payment dates (quarterly)
        pricing_date: Valuation date
        recovery_rate: Recovery rate on default (decimal)
    
    Returns:
        Fair spread in basis points
    """
    protection_leg = 0.0
    risky_pv01 = 0.0  # PV of 1bp premium
    prev_survival = 1.0
    
    for i, (pmt_date, df) in enumerate(zip(payment_dates, discount_factors)):
        time_to_payment = (pmt_date - pricing_date).days / 365.25
        
        # Interpolate survival probability
        if time_to_payment in survival_curve:
            survival_prob = survival_curve[time_to_payment]
        else:
            times = sorted(survival_curve.keys())
            if time_to_payment <= times[0]:
                survival_prob = survival_curve[times[0]]
            elif time_to_payment >= times[-1]:
                survival_prob = survival_curve[times[-1]]
            else:
                for j in range(len(times) - 1):
                    if times[j] <= time_to_payment <= times[j+1]:
                        t1, t2 = times[j], times[j+1]
                        s1, s2 = survival_curve[t1], survival_curve[t2]
                        survival_prob = s1 + (s2 - s1) * (time_to_payment - t1) / (t2 - t1)
                        break
        
        # Day count fraction
        if i == 0:
            tau = (pmt_date - pricing_date).days / 360.0
        else:
            tau = (pmt_date - payment_dates[i-1]).days / 360.0
        
        # Risky PV01: PV of receiving 1bp premium
        risky_pv01 += tau * df * survival_prob
        
        # Protection leg
        default_prob = prev_survival - survival_prob
        loss_given_default = 1.0 - recovery_rate
        protection_leg += loss_given_default * default_prob * df
        
        prev_survival = survival_prob
    
    # Fair spread in decimal
    if risky_pv01 > 0:
        fair_spread_decimal = protection_leg / risky_pv01
        return fair_spread_decimal * 10000.0  # Convert to bps
    else:
        return 0.0


def _calculate_cds_value(
    notional: float,
    premium_bps: float,
    survival_curve: Dict[float, float],
    discount_factors: List[float],
    payment_dates: List[datetime],
    pricing_date: datetime,
    recovery_rate: float
) -> Dict[str, Any]:
    """
    Calculate CDS value using survival curve and discount factors.

    Premium Leg (protection seller receives):
        PV = Σ(premium × DF_i × survival_i × Δt_i) × notional

    Protection Leg (protection seller pays on default):
        PV = Σ((1-recovery) × DF_i × default_prob_i) × notional

    CDS Value (protection seller perspective):
        Value = Premium_Leg_PV - Protection_Leg_PV

    Args:
        notional: CDS notional amount
        premium_bps: CDS premium in basis points (e.g., 150 = 1.5%)
        survival_curve: Dict mapping time → survival probability
        discount_factors: Discount factors for payment dates
        payment_dates: CDS payment dates (quarterly)
        pricing_date: Valuation date
        recovery_rate: Recovery rate on default (decimal)

    Returns:
        Dict with:
        {
            "cds_value": float - CDS present value ($)
            "upfront_payment": float - Upfront payment if negative value
            "premium_leg_pv": float - PV of premium leg ($)
            "protection_leg_pv": float - PV of protection leg ($)
        }
    """
    try:
        premium_rate = premium_bps / 10000.0  # Convert bps to decimal

        premium_leg_pv = 0.0
        protection_leg_pv = 0.0

        prev_survival = 1.0  # Start with 100% survival

        for i, (pmt_date, df) in enumerate(zip(payment_dates, discount_factors)):
            # Time to payment
            time_to_payment = (pmt_date - pricing_date).days / 365.25

            # Interpolate survival probability
            # Find closest time in survival curve
            if time_to_payment in survival_curve:
                survival_prob = survival_curve[time_to_payment]
            else:
                # Linear interpolation
                times = sorted(survival_curve.keys())
                if time_to_payment <= times[0]:
                    survival_prob = survival_curve[times[0]]
                elif time_to_payment >= times[-1]:
                    survival_prob = survival_curve[times[-1]]
                else:
                    # Find surrounding points
                    for j in range(len(times) - 1):
                        if times[j] <= time_to_payment <= times[j+1]:
                            t1, t2 = times[j], times[j+1]
                            s1, s2 = survival_curve[t1], survival_curve[t2]
                            survival_prob = s1 + (s2 - s1) * (time_to_payment - t1) / (t2 - t1)
                            break

            # Day count fraction (30/360 convention)
            if i == 0:
                tau = (pmt_date - pricing_date).days / 360.0
            else:
                tau = (pmt_date - payment_dates[i-1]).days / 360.0

            # Premium leg: receive premium if no default
            premium_cashflow = notional * premium_rate * tau
            premium_leg_pv += premium_cashflow * df * survival_prob

            # Protection leg: pay (1-recovery) if default occurs
            default_prob = prev_survival - survival_prob  # Default in this period
            loss_given_default = 1.0 - recovery_rate
            protection_cashflow = notional * loss_given_default * default_prob
            protection_leg_pv += protection_cashflow * df

            prev_survival = survival_prob

        # CDS value from protection seller perspective
        cds_value = premium_leg_pv - protection_leg_pv

        # If CDS value is negative, buyer pays upfront
        upfront_payment = -cds_value if cds_value < 0 else 0.0

        return {
            "cds_value": float(cds_value),
            "upfront_payment": float(upfront_payment),
            "premium_leg_pv": float(premium_leg_pv),
            "protection_leg_pv": float(protection_leg_pv)
        }

    except Exception as e:
        logger.error(f"CDS valuation failed: {e}")
        raise


def _generate_quarterly_schedule(
    start_date: datetime,
    tenor: str
) -> List[datetime]:
    """
    Generate quarterly payment schedule for CDS.

    Args:
        start_date: CDS start date
        tenor: CDS tenor (e.g., "5Y")

    Returns:
        List of quarterly payment dates
    """
    tenor_years = _parse_tenor(tenor)
    num_quarters = int(tenor_years * 4)

    payment_dates = []
    for i in range(1, num_quarters + 1):
        # Quarterly payments (90 days)
        payment_date = start_date + timedelta(days=i * 90)
        payment_dates.append(payment_date)

    return payment_dates


async def price_credit_default_swap_internal(
    ticker: str,
    notional: float,
    tenor: str,
    pricing_date: Optional[str] = None
) -> dict:
    """
    Price credit default swaps using Merton model or generic assumptions.

    Pricing Methodology:
    1. Estimate default probability:
       - PRIMARY: Merton/KMV model from equity data (FMP)
       - FALLBACK: Generic BBB-equivalent assumptions (0.25% annual default)
    2. Generate survival curve (quarterly)
    3. Calculate premium leg PV (receive premium if no default)
    4. Calculate protection leg PV (pay 1-recovery on default)
    5. CDS value = Premium_Leg - Protection_Leg

    Data Sources:
    - FMP: Market cap, debt, equity volatility (Merton inputs)
    - FRED: Risk-free rate (treasury yield curve)
    - User override: survival_curve parameter for market data

    Args:
        ticker: Reference entity ticker symbol
        notional: CDS notional amount ($)
        premium_bps: CDS premium in basis points (e.g., 150 = 1.5%)
        tenor: CDS maturity ("1Y", "3Y", "5Y", "10Y")
        recovery_rate: Recovery rate on default (decimal, default: 0.40 = 40%)
        survival_curve: Optional user-provided survival curve
            Dict[str, float] mapping time → survival probability
            Example: {"0.25": 0.999, "0.5": 0.998, "1.0": 0.995, ...}
            Overrides Merton model if provided
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        Dict with:
        {
            "status": "success",
            "cds_value": float - CDS present value ($)
            "upfront_payment": float - Upfront payment if applicable
            "premium_leg_pv": float - PV of premium leg ($)
            "protection_leg_pv": float - PV of protection leg ($)
            "default_probability": float - Cumulative default probability
            "distance_to_default": float - Merton DD (None if fallback/user curve)
            "survival_curve": Dict[float, float] - Survival probabilities
            "estimation_method": str - "merton" | "generic" | "user_provided"
            "inputs": Dict - Echo of inputs
            "data_sources": List[str] - Data sources used
            "warnings": List[str] - Warnings if any
            "summary": str - Human-readable summary
        }

    Examples:
        # Basic CDS pricing using Merton model
        result = await price_credit_default_swap(
            ticker="AAPL",
            notional=10_000_000,
            premium_bps=50,  # 0.50%
            tenor="5Y"
        )
        print(f"CDS Value: ${result['cds_value']:,.2f}")
        print(f"Default Probability: {result['default_probability']:.2%}")

        # Override with market survival curve
        market_curve = {
            "0.25": 0.9995, "0.5": 0.999, "1.0": 0.997,
            "2.0": 0.992, "3.0": 0.985, "5.0": 0.970
        }
        result = await price_credit_default_swap(
            ticker="XYZ",
            notional=5_000_000,
            premium_bps=200,  # 2.0%
            tenor="5Y",
            recovery_rate=0.30,
            survival_curve=market_curve
        )

    LIMITATIONS:
    - Model-implied, not market CDS spreads
    - Simplified constant hazard rate assumption
    - Best for: relative comparisons, screening
    - NOT for: trading, regulatory capital
    """
    try:
        # Set defaults
        if pricing_date is None:
            pricing_date = datetime.now().strftime("%Y-%m-%d")

        pricing_dt = datetime.strptime(pricing_date, "%Y-%m-%d")

        # Validate inputs
        if notional <= 0:
            raise ValueError(f"Notional must be positive: {notional}")

        data_sources = []
        warnings = []
        estimation_method = "unknown"
        distance_to_default = None
        default_probability = None

        # Generate quarterly payment schedule
        payment_dates = _generate_quarterly_schedule(pricing_dt, tenor)
        tenor_years = _parse_tenor(tenor)

        # Connect to FRED for discount factors
        fred_server = EconomicDataServer()

        try:
            await fred_server.connect()

            # Fetch yield curve
            logger.info(f"Fetching yield curve for {pricing_date}")
            yield_curve = await _fetch_yield_curve(fred_server, pricing_date)
            data_sources.append("yield_curve: FRED treasury series (DGS)")

            # Get risk-free rate (for Merton model)
            # Use tenor-matched treasury rate
            if tenor_years <= 1:
                rfr_tenor = "1Y"
            elif tenor_years <= 3:
                rfr_tenor = "2Y"
            elif tenor_years <= 7:
                rfr_tenor = "5Y"
            else:
                rfr_tenor = "10Y"

            risk_free_rate = yield_curve.get(rfr_tenor, 0.045)  # Default to 4.5% if missing
            data_sources.append(f"risk_free_rate: {risk_free_rate:.2%} ({rfr_tenor} treasury)")

        finally:
            await fred_server.cleanup()

        # Calculate discount factors
        discount_factors = _calculate_discount_factors(payment_dates, yield_curve, pricing_dt)

        # Calculate survival curve and recovery rate from company fundamentals
        recovery_rate = None  # Will be set below
        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            logger.info(f"Attempting Merton model for {ticker}")

            try:
                # Fetch credit data
                credit_data = await _fetch_company_credit_data(ticker, fmp_server)
                data_sources.extend(credit_data["data_sources"])

                # Calculate recovery rate from balance sheet
                recovery_result = _estimate_recovery_rate(
                    total_assets=credit_data["total_assets"],
                    total_debt=credit_data["total_debt"],
                    tangible_assets=credit_data.get("tangible_assets")
                )
                recovery_rate = recovery_result["recovery_rate"]
                data_sources.append(f"recovery_rate: {recovery_rate:.0%} from balance sheet ({recovery_result['explanation']})")
                logger.info(f"Estimated recovery rate: {recovery_rate:.0%}")

                # Calculate Merton survival curve
                merton_result = _estimate_survival_curve_merton(
                    market_cap=credit_data["market_cap"],
                    total_debt=credit_data["total_debt"],
                    equity_volatility=credit_data["equity_volatility"],
                    risk_free_rate=risk_free_rate,
                    tenor_years=tenor_years
                )

                survival_curve_final = merton_result["survival_curve"]
                distance_to_default = merton_result["distance_to_default"]
                default_probability = merton_result["default_probability"]
                warnings.extend(merton_result["warnings"])

                estimation_method = "merton"
                data_sources.append(f"estimation_method: Merton/KMV model (DD={distance_to_default:.2f})")

                logger.info(f"Merton model successful: DD={distance_to_default:.2f}, PD={default_probability:.2%}")

            except Exception as merton_error:
                # Fallback to generic assumptions
                logger.warning(f"Merton model failed for {ticker}: {merton_error}")
                logger.info("Falling back to generic BBB-equivalent assumptions")

                fallback_result = _fallback_survival_curve(tenor_years)
                survival_curve_final = fallback_result["survival_curve"]
                warnings.extend(fallback_result["warnings"])
                warnings.append(f"Merton model failed: {str(merton_error)}")

                estimation_method = "generic"
                data_sources.append("estimation_method: Generic BBB-equivalent (0.25% annual default)")

                # Use generic recovery rate
                recovery_rate = GENERIC_RECOVERY_RATE
                data_sources.append(f"recovery_rate: {recovery_rate:.0%} (generic BBB assumption)")

                # Estimate default probability from generic curve
                final_time = max(survival_curve_final.keys())
                default_probability = 1.0 - survival_curve_final[final_time]

        finally:
            await fmp_server.cleanup()

        # Calculate fair CDS spread (par spread where CDS value = 0)
        fair_spread_bps = _calculate_fair_spread(
            survival_curve=survival_curve_final,
            discount_factors=discount_factors,
            payment_dates=payment_dates,
            pricing_date=pricing_dt,
            recovery_rate=recovery_rate
        )
        
        logger.info(f"Fair CDS spread: {fair_spread_bps:.1f} bps")
        data_sources.append(f"fair_spread: {fair_spread_bps:.1f} bps (model-implied)")

        # Calculate CDS value at fair spread (should be ~0)
        cds_result = _calculate_cds_value(
            notional=notional,
            premium_bps=fair_spread_bps,
            survival_curve=survival_curve_final,
            discount_factors=discount_factors,
            payment_dates=payment_dates,
            pricing_date=pricing_dt,
            recovery_rate=recovery_rate
        )

        # Build summary
        if estimation_method == "merton":
            method_desc = f"Merton model (DD={distance_to_default:.2f})"
        elif estimation_method == "generic":
            method_desc = "Generic BBB assumptions"
        else:
            method_desc = "User-provided curve"

        position = "protection seller" if cds_result["cds_value"] > 0 else "protection buyer"

        summary = (
            f"CDS on {ticker}, {tenor} tenor, {notional:,.0f} notional. "
            f"Fair Spread: {fair_spread_bps:.1f} bps, Recovery: {recovery_rate:.0%}. "
            f"Default Probability: {default_probability:.2%} ({method_desc})."
        )

        if cds_result["upfront_payment"] > 0:
            summary += f" Upfront payment: ${cds_result['upfront_payment']:,.2f}."

        return {
            "status": "success",
            "fair_spread_bps": float(fair_spread_bps),
            "recovery_rate": float(recovery_rate),
            "cds_value": float(cds_result["cds_value"]),
            "upfront_payment": float(cds_result["upfront_payment"]),
            "premium_leg_pv": float(cds_result["premium_leg_pv"]),
            "protection_leg_pv": float(cds_result["protection_leg_pv"]),
            "default_probability": float(default_probability) if default_probability is not None else None,
            "distance_to_default": float(distance_to_default) if distance_to_default is not None else None,
            "survival_curve": survival_curve_final,
            "estimation_method": estimation_method,
            "inputs": {
                "ticker": ticker,
                "notional": notional,
                "tenor": tenor,
                "pricing_date": pricing_date
            },
            "data_sources": data_sources,
            "warnings": warnings,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"CDS pricing failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "calculation_type": "credit_default_swap"
        }


@function_tool
async def price_credit_default_swap(
    ticker: str,
    notional: float,
    tenor: str,
    pricing_date: Optional[str] = None
) -> dict:
    """
    Price credit default swaps using Merton model and calculate fair spread.

    Calculates:
    - Fair CDS spread (par spread where CDS value = 0)
    - Recovery rate from balance sheet fundamentals
    - Default probability from Merton/KMV model
    - Distance to default (credit risk metric)

    Args:
        ticker: Reference entity ticker symbol
        notional: CDS notional amount ($)
        tenor: CDS maturity ("1Y", "3Y", "5Y", "10Y")
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        JSON string with fair spread, recovery rate, default probability, and distance to default
    """
    result = await price_credit_default_swap_internal(
        ticker=ticker,
        notional=notional,
        tenor=tenor,
        pricing_date=pricing_date
    )
    return jsonify_results(result)
