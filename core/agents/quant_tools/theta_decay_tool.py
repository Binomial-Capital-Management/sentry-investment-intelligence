"""
SIMPLIFIED Theta Decay Tool - BLACK-SCHOLES ONLY

Uses FMP for prices and calculates Black-Scholes theta. Period.
Theta differs for calls and puts (unlike gamma).
"""
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict  # Required for Pydantic on Python < 3.12
from datetime import datetime, timedelta
import math
import logging
from agents import function_tool

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

logger = logging.getLogger(__name__)


# TypedDict for OpenAI strict schema
class PositionInputRequired(TypedDict):
    underlying: str
    expiry: str
    option_type: str
    strike: float
    quantity: int

class PositionInput(PositionInputRequired, total=False):
    implied_volatility: float

class PriceOverride(TypedDict):
    ticker: str
    price: float


async def _fetch_prices(fmp_server, tickers: List[str]) -> Dict[str, float]:
    """Fetch current prices from FMP."""
    results = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    for ticker in tickers:
        try:
            result = await fmp_server.call_tool("get_historical_data", {
                "symbol": ticker,
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            })

            if not result or not hasattr(result, 'content'):
                continue

            data = safe_parse_json(result)
            prices = data.get("prices") or data.get("closes") or data.get("close") or []

            if prices:
                results[ticker] = float(prices[-1])

        except Exception as e:
            logger.warning(f"Failed to fetch price for {ticker}: {e}")

    return results


async def _calculate_hist_vol(fmp_server, ticker: str, window=30) -> Optional[float]:
    """Calculate historical volatility."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=window + 10)

        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)
        price_array = data.get("prices") or data.get("closes") or data.get("close") or []

        if len(price_array) < 10:
            return None

        prices = [float(p) for p in price_array[:window + 1] if p]

        # Log returns
        log_returns = []
        for i in range(1, len(prices)):
            log_returns.append(math.log(prices[i] / prices[i-1]))

        # Annualized vol
        mean = sum(log_returns) / len(log_returns)
        variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
        daily_vol = math.sqrt(variance)
        annual_vol = daily_vol * math.sqrt(252)

        return annual_vol

    except Exception as e:
        logger.warning(f"Historical vol failed for {ticker}: {e}")
        return None


def _black_scholes_theta(spot, strike, time_to_exp, vol, rate, option_type, dividend_yield=0.0):
    """
    Calculate Black-Scholes theta (daily time decay) with dividend yield support.

    Theta differs for calls and puts. Full formula with dividends:
    Θ_call = -S×N'(d1)×σ×e^(-qT)/(2√T) - r×K×e^(-rT)×N(d2) + q×S×e^(-qT)×N(d1)
    Θ_put  = -S×N'(d1)×σ×e^(-qT)/(2√T) + r×K×e^(-rT)×N(-d2) - q×S×e^(-qT)×N(-d1)

    Negative theta = option loses value over time.
    Returns daily theta (divided by 365).
    
    Args:
        spot: Current stock price
        strike: Option strike price
        time_to_exp: Time to expiration in years
        vol: Annualized volatility
        rate: Risk-free rate
        option_type: 'call' or 'put'
        dividend_yield: Continuous dividend yield (default 0)
    """
    if time_to_exp <= 0 or vol <= 0 or spot <= 0:
        return 0.0

    # Calculate d1 and d2 with dividend yield
    d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))
    d2 = d1 - vol * math.sqrt(time_to_exp)

    # Standard normal PDF: N'(x) = (1/√(2π)) × exp(-x²/2)
    norm_pdf_d1 = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * d1 ** 2)

    # Standard normal CDF using error function
    def norm_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    # Discount factors
    discount_div = math.exp(-dividend_yield * time_to_exp)
    discount_rate = math.exp(-rate * time_to_exp)

    # First term (common to both calls and puts) - with dividend discount
    first_term = -(spot * discount_div * norm_pdf_d1 * vol) / (2.0 * math.sqrt(time_to_exp))

    # Second and third terms (differ for calls and puts)
    if option_type.lower() == 'call':
        second_term = -rate * strike * discount_rate * norm_cdf(d2)
        third_term = dividend_yield * spot * discount_div * norm_cdf(d1)
    else:  # put
        second_term = rate * strike * discount_rate * norm_cdf(-d2)
        third_term = -dividend_yield * spot * discount_div * norm_cdf(-d1)

    # Annual theta
    annual_theta = first_term + second_term + third_term

    # Convert to daily theta (divide by 365)
    daily_theta = annual_theta / 365.0

    return daily_theta


async def _calculate_theta_impl(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None,
    days_forward: int = 1,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """Internal implementation - can be called directly from other modules."""
    try:
        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Get underlyings
            underlyings = list(set(pos['underlying'] for pos in portfolio_positions))

            # Fetch prices
            if underlying_prices:
                prices = {item['ticker']: item['price'] for item in underlying_prices}
            else:
                prices = await _fetch_prices(fmp_server, underlyings)

            # Calculate theta
            position_details = []
            total_theta = 0.0
            theta_by_underlying = {}
            failed = 0

            for pos in portfolio_positions:
                underlying = pos['underlying']
                strike = pos['strike']
                quantity = pos['quantity']
                option_type = pos['option_type']
                expiry_str = pos['expiry']

                # Get price
                spot = prices.get(underlying)
                if not spot:
                    logger.warning(f"No price for {underlying}")
                    failed += 1
                    continue

                # Time to expiry
                expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d')
                days = (expiry_dt - datetime.now()).days
                time_to_exp = max(days / 365.0, 0.0)

                # Expired options have zero theta
                if time_to_exp <= 0:
                    logger.info(f"Expired option for {underlying}, theta = 0")
                    position_details.append({
                        'underlying': underlying,
                        'theta': 0.0,
                        'quantity': quantity,
                        'position_theta': 0.0,
                        'projected_pnl': 0.0,
                        'volatility': 0.0,
                        'note': 'expired'
                    })
                    continue

                # Get volatility
                user_iv = pos.get('implied_volatility')
                if user_iv and user_iv > 0:
                    vol = user_iv
                else:
                    vol = await _calculate_hist_vol(fmp_server, underlying)
                    if not vol:
                        logger.warning(f"No volatility for {underlying}")
                        failed += 1
                        continue

                # Calculate theta (different for calls and puts)
                theta = _black_scholes_theta(spot, strike, time_to_exp, vol, 0.04, option_type)
                position_theta = theta * quantity * 100  # 100 shares per contract
                total_theta += position_theta

                # Project P&L over days_forward
                projected_pnl = position_theta * days_forward

                # Aggregate by underlying
                if underlying not in theta_by_underlying:
                    theta_by_underlying[underlying] = 0.0
                theta_by_underlying[underlying] += position_theta

                position_details.append({
                    'underlying': underlying,
                    'option_type': option_type,
                    'theta': theta,
                    'quantity': quantity,
                    'position_theta': position_theta,
                    'projected_pnl': projected_pnl,
                    'volatility': vol,
                    'spot_price': spot,
                    'time_to_expiry_days': days
                })

            # Calculate total projected P&L
            total_projected_pnl = total_theta * days_forward

            return {
                'total_theta': total_theta,
                'theta_by_underlying': theta_by_underlying,
                'total_projected_pnl': total_projected_pnl,
                'days_forward': days_forward,
                'position_details': position_details,
                'successful_positions': len(position_details),
                'failed_positions': failed,
                'total_positions': len(portfolio_positions),
                'note': f'Theta measures daily time decay. Negative theta = option loses ${abs(total_theta):.2f}/day. Projected {days_forward}-day P&L: ${total_projected_pnl:.2f}'
            }

        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Theta calculation failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'total_theta': 0.0,
            'theta_by_underlying': {},
            'total_projected_pnl': 0.0,
            'days_forward': days_forward,
            'position_details': [],
            'successful_positions': 0,
            'failed_positions': len(portfolio_positions),
            'total_positions': len(portfolio_positions)
        }


@function_tool
async def calculate_theta_decay(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None,
    days_forward: int = 1,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """
    Calculate portfolio theta decay using Black-Scholes.

    Theta measures time decay - how much option value decays per day.

    Args:
        portfolio_positions: List of positions
        underlying_prices: Optional price overrides
        days_forward: Days to project decay (default: 1)
        use_polygon: Ignored

    Returns:
        Portfolio theta exposure with breakdown
    """
    return await _calculate_theta_impl(portfolio_positions, underlying_prices, days_forward, use_polygon)
