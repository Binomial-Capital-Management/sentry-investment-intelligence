"""
SIMPLIFIED Gamma Exposure Tool - BLACK-SCHOLES ONLY

Uses FMP for prices and calculates Black-Scholes gamma. Period.
Gamma is identical for calls and puts at same strike.
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


def _black_scholes_gamma(spot, strike, time_to_exp, vol, rate, dividend_yield=0.0):
    """
    Calculate Black-Scholes gamma with dividend yield support.

    Gamma is identical for calls and puts at the same strike.
    Γ = e^(-qT) × N'(d1) / (S × σ × √T)
    where N'(d1) is the standard normal PDF and q is dividend yield.
    
    Args:
        spot: Current stock price
        strike: Option strike price
        time_to_exp: Time to expiration in years
        vol: Annualized volatility
        rate: Risk-free rate
        dividend_yield: Continuous dividend yield (default 0)
    """
    if time_to_exp <= 0 or vol <= 0 or spot <= 0:
        return 0.0

    # Calculate d1 with dividend yield: (r - q + σ²/2) instead of (r + σ²/2)
    d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))

    # Standard normal PDF: N'(x) = (1/√(2π)) × exp(-x²/2)
    norm_pdf_d1 = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * d1 ** 2)

    # Gamma formula with dividend adjustment
    discount = math.exp(-dividend_yield * time_to_exp)
    gamma = discount * norm_pdf_d1 / (spot * vol * math.sqrt(time_to_exp))

    return gamma


async def _calculate_gamma_impl(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None,
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

            # Calculate gammas
            position_details = []
            total_gamma = 0.0
            gamma_by_underlying = {}
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

                # Expired options have zero gamma
                if time_to_exp <= 0:
                    logger.info(f"Expired option for {underlying}, gamma = 0")
                    position_details.append({
                        'underlying': underlying,
                        'gamma': 0.0,
                        'quantity': quantity,
                        'position_gamma': 0.0,
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

                # Calculate gamma (same for calls and puts)
                gamma = _black_scholes_gamma(spot, strike, time_to_exp, vol, 0.04)
                position_gamma = gamma * quantity * 100  # 100 shares per contract
                total_gamma += position_gamma

                # Aggregate by underlying
                if underlying not in gamma_by_underlying:
                    gamma_by_underlying[underlying] = 0.0
                gamma_by_underlying[underlying] += position_gamma

                position_details.append({
                    'underlying': underlying,
                    'gamma': gamma,
                    'quantity': quantity,
                    'position_gamma': position_gamma,
                    'volatility': vol,
                    'spot_price': spot
                })

            # Calculate gamma-adjusted notional (gamma × spot²)
            # This represents $ P&L from 1% spot move
            total_gamma_notional = 0.0
            for detail in position_details:
                if 'spot_price' in detail:
                    gamma_notional = detail['position_gamma'] * (detail['spot_price'] ** 2)
                    total_gamma_notional += gamma_notional

            return {
                'total_gamma': total_gamma,
                'gamma_by_underlying': gamma_by_underlying,
                'total_gamma_notional': total_gamma_notional,
                'position_details': position_details,
                'successful_positions': len(position_details),
                'failed_positions': failed,
                'total_positions': len(portfolio_positions),
                'note': 'Gamma measures delta sensitivity to spot moves. High gamma = large delta changes.'
            }

        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Gamma calculation failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'total_gamma': 0.0,
            'gamma_by_underlying': {},
            'total_gamma_notional': 0.0,
            'position_details': [],
            'successful_positions': 0,
            'failed_positions': len(portfolio_positions),
            'total_positions': len(portfolio_positions)
        }


@function_tool
async def calculate_gamma_exposure(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """
    Calculate portfolio gamma exposure using Black-Scholes.

    Gamma measures delta sensitivity to spot price changes.
    High gamma = large delta swings from small price moves.

    Args:
        portfolio_positions: List of positions with underlying, expiry, option_type, strike, quantity, implied_volatility (optional)
        underlying_prices: Optional price overrides
        use_polygon: Ignored (for API consistency)

    Returns:
        Portfolio gamma exposure with breakdown by underlying
    """
    return await _calculate_gamma_impl(portfolio_positions, underlying_prices, use_polygon)
