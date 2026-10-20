"""
Vega Exposure Tool - Volatility Risk Measurement

Uses FMP for prices, Polygon for IV, calculates Black-Scholes vega.
"""
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict  # Required for Pydantic on Python < 3.12
from datetime import datetime, timedelta
import math
import logging
from agents import function_tool

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
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


def _black_scholes_vega(spot, strike, time_to_exp, vol, rate, dividend_yield=0.0):
    """
    Calculate Black-Scholes vega (same for calls and puts) with dividend yield support.
    
    Vega = S × e^(-qT) × N'(d1) × √T
    where q is dividend yield.
    
    Args:
        spot: Current stock price
        strike: Option strike price
        time_to_exp: Time to expiration in years
        vol: Annualized volatility
        rate: Risk-free rate
        dividend_yield: Continuous dividend yield (default 0)
    """
    if time_to_exp <= 0:
        return 0.0

    # d1 with dividend yield: (r - q + σ²/2) instead of (r + σ²/2)
    d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))

    # N'(d1) = normal PDF at d1
    norm_pdf = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * d1 ** 2)

    # Vega = S × e^(-qT) × N'(d1) × √T
    # Divide by 100 to get vega per 1% vol change
    discount = math.exp(-dividend_yield * time_to_exp)
    vega = (spot * discount * norm_pdf * math.sqrt(time_to_exp)) / 100.0

    return vega


def _construct_option_ticker(underlying: str, expiry: str, option_type: str, strike: float) -> str:
    """Construct OCC-format option ticker: O:AAPL250117C00150000"""
    expiry_dt = datetime.strptime(expiry, '%Y-%m-%d')
    yymmdd = expiry_dt.strftime('%y%m%d')
    opt_letter = 'C' if option_type.lower() == 'call' else 'P'
    strike_int = int(strike * 1000)
    return f"O:{underlying}{yymmdd}{opt_letter}{strike_int:08d}"


async def _get_polygon_iv(polygon_server, underlying: str, expiry: str, option_type: str, strike: float) -> Optional[float]:
    """Fetch implied volatility from Polygon snapshot."""
    try:
        ticker = _construct_option_ticker(underlying, expiry, option_type, strike)

        result = await polygon_server.call_tool("get_polygon_options_snapshot", {
            "ticker": ticker
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)
        results = data.get('results', [])

        if results:
            contract = results[0]
            details = contract.get('details', {})
            iv = details.get('implied_volatility')
            if iv:
                return float(iv)

        return None

    except Exception as e:
        logger.debug(f"Polygon IV failed for {ticker}: {e}")
        return None


async def _calculate_vega_impl(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """Internal implementation - can be called directly from other modules."""
    try:
        fmp_server = FMPMarketDataServer()
        polygon_server = PolygonOptionsFuturesServer() if use_polygon else None

        try:
            await fmp_server.connect()
            if polygon_server:
                await polygon_server.connect()

            # Get underlyings
            underlyings = list(set(pos['underlying'] for pos in portfolio_positions))

            # Fetch prices
            if underlying_prices:
                prices = {item['ticker']: item['price'] for item in underlying_prices}
            else:
                prices = await _fetch_prices(fmp_server, underlyings)

            # Calculate vegas
            position_details = []
            total_vega = 0.0
            vega_by_underlying = {}
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

                # Get volatility (for vega calculation)
                user_iv = pos.get('implied_volatility')
                if user_iv and user_iv > 0:
                    vol = user_iv
                elif polygon_server:
                    polygon_iv = await _get_polygon_iv(polygon_server, underlying, expiry_str, option_type, strike)
                    if polygon_iv:
                        vol = polygon_iv
                    else:
                        vol = await _calculate_hist_vol(fmp_server, underlying)
                        if not vol:
                            logger.warning(f"No volatility for {underlying}")
                            failed += 1
                            continue
                else:
                    vol = await _calculate_hist_vol(fmp_server, underlying)
                    if not vol:
                        logger.warning(f"No volatility for {underlying}")
                        failed += 1
                        continue

                # Calculate vega (same for calls and puts)
                vega = _black_scholes_vega(spot, strike, time_to_exp, vol, 0.04)
                position_vega = vega * quantity * 100  # 100 shares per contract
                total_vega += position_vega

                # Track by underlying
                if underlying not in vega_by_underlying:
                    vega_by_underlying[underlying] = 0.0
                vega_by_underlying[underlying] += position_vega

                position_details.append({
                    'underlying': underlying,
                    'vega': vega,
                    'quantity': quantity,
                    'position_vega': position_vega,
                    'volatility': vol
                })

            return {
                'total_vega': total_vega,
                'vega_by_underlying': vega_by_underlying,
                'position_details': position_details,
                'successful_positions': len(position_details),
                'failed_positions': failed,
                'total_positions': len(portfolio_positions)
            }

        finally:
            await fmp_server.cleanup()
            if polygon_server:
                await polygon_server.cleanup()

    except Exception as e:
        logger.error(f"Vega calculation failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'total_vega': 0.0,
            'vega_by_underlying': {},
            'position_details': [],
            'successful_positions': 0,
            'failed_positions': len(portfolio_positions),
            'total_positions': len(portfolio_positions)
        }


@function_tool
async def calculate_vega_exposure(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """
    Calculate portfolio vega exposure using Black-Scholes.

    Args:
        portfolio_positions: List of positions with underlying, expiry, option_type, strike, quantity, implied_volatility (optional)
        underlying_prices: Optional price overrides
        use_polygon: Use Polygon for IV (default True)

    Returns:
        Portfolio vega exposure (P&L change per 1% vol change)
    """
    return await _calculate_vega_impl(portfolio_positions, underlying_prices, use_polygon)
