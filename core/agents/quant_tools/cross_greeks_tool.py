"""
Cross-Greeks Tool - Second-Order Greeks for Advanced Risk Management

Calculates vanna, volga, charm, veta for options portfolios.
Uses FMP for prices, Polygon for IV, calculates Black-Scholes second-order Greeks.
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


def _norm_pdf(x: float) -> float:
    """Normal probability density function N'(x)."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x ** 2)


def _norm_cdf(x: float) -> float:
    """Normal cumulative distribution function N(x) - approximation."""
    # Using approximation for CDF
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _black_scholes_vanna(spot: float, strike: float, time_to_exp: float, vol: float, rate: float) -> float:
    """
    Calculate Black-Scholes vanna (∂²V/∂S∂σ).
    Vanna = -N'(d1) × d2 / (S × σ)
    Same for calls and puts.
    """
    if time_to_exp <= 0 or vol <= 0:
        return 0.0

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))
    d2 = d1 - vol * math.sqrt(time_to_exp)

    norm_pdf_d1 = _norm_pdf(d1)

    # Vanna = -N'(d1) × d2 / (S × σ)
    vanna = -norm_pdf_d1 * d2 / (spot * vol)

    return vanna


def _black_scholes_volga(spot: float, strike: float, time_to_exp: float, vol: float, rate: float) -> float:
    """
    Calculate Black-Scholes volga (∂²V/∂σ²).
    Volga = S × N'(d1) × √T × (d1 × d2) / σ
    Same for calls and puts.
    """
    if time_to_exp <= 0 or vol <= 0:
        return 0.0

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))
    d2 = d1 - vol * math.sqrt(time_to_exp)

    norm_pdf_d1 = _norm_pdf(d1)

    # Volga = S × N'(d1) × √T × (d1 × d2) / σ
    # Divide by 100 to get volga per 1% vol change
    volga = (spot * norm_pdf_d1 * math.sqrt(time_to_exp) * d1 * d2 / vol) / 100.0

    return volga


def _black_scholes_charm(spot: float, strike: float, time_to_exp: float, vol: float, rate: float, option_type: str) -> float:
    """
    Calculate Black-Scholes charm (∂²V/∂S∂t).
    Call: Charm = -N'(d1) × [2rT - d2σ√T] / (2T√T) - r × K × e^(-rT) × N(d2)
    Put: Charm = -N'(d1) × [2rT - d2σ√T] / (2T√T) + r × K × e^(-rT) × N(-d2)
    """
    if time_to_exp <= 0 or vol <= 0:
        return 0.0

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))
    d2 = d1 - vol * math.sqrt(time_to_exp)

    norm_pdf_d1 = _norm_pdf(d1)
    norm_cdf_d2 = _norm_cdf(d2)

    sqrt_t = math.sqrt(time_to_exp)

    # First term (same for calls and puts)
    term1 = -norm_pdf_d1 * (2 * rate * time_to_exp - d2 * vol * sqrt_t) / (2 * time_to_exp * sqrt_t)

    # Second term (sign differs for calls and puts)
    discount_factor = math.exp(-rate * time_to_exp)

    if option_type.lower() == 'call':
        term2 = -rate * strike * discount_factor * norm_cdf_d2
    else:  # put
        term2 = rate * strike * discount_factor * _norm_cdf(-d2)

    charm = term1 + term2

    # Divide by 365 to get daily charm
    return charm / 365.0


def _black_scholes_veta(spot: float, strike: float, time_to_exp: float, vol: float, rate: float) -> float:
    """
    Calculate Black-Scholes veta (∂²V/∂σ∂t).
    Veta = -S × N'(d1) × √T × [r × d1/(σ√T) - (1 + d1×d2)/(2T)]
    Same for calls and puts.
    """
    if time_to_exp <= 0 or vol <= 0:
        return 0.0

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))
    d2 = d1 - vol * math.sqrt(time_to_exp)

    norm_pdf_d1 = _norm_pdf(d1)
    sqrt_t = math.sqrt(time_to_exp)

    # Veta = -S × N'(d1) × √T × [r × d1/(σ√T) - (1 + d1×d2)/(2T)]
    bracket_term = (rate * d1) / (vol * sqrt_t) - (1 + d1 * d2) / (2 * time_to_exp)
    veta = -spot * norm_pdf_d1 * sqrt_t * bracket_term

    # Divide by 365 to get daily veta, and by 100 for 1% vol change
    return veta / (365.0 * 100.0)


async def calculate_cross_greeks_internal(
    portfolio_positions: List[Dict[str, Any]],
    underlying_prices: Optional[List[Dict[str, Any]]] = None,
    use_polygon: bool = True,
    scenarios: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Internal version for Canvas integration.
    Returns raw dictionary without JSON serialization.
    
    Calculate second-order Greeks (vanna, volga, charm, veta) for advanced risk management.

    Args:
        portfolio_positions: List of positions with underlying, expiry, option_type, strike, quantity, implied_volatility (optional)
        underlying_prices: Optional price overrides
        use_polygon: Use Polygon for IV (default True)
        scenarios: Which Greeks to calculate ["vanna", "volga", "charm", "veta"]. Default: all

    Returns:
        Second-order Greeks exposure with breakdowns by underlying
    """
    # Default to all Greeks if none specified
    if not scenarios:
        scenarios = ["vanna", "volga", "charm", "veta"]

    # Normalize scenario names
    scenarios = [s.lower() for s in scenarios]
    valid_scenarios = ["vanna", "volga", "charm", "veta"]
    scenarios = [s for s in scenarios if s in valid_scenarios]

    if not scenarios:
        return {
            'error': 'No valid scenarios provided. Valid options: vanna, volga, charm, veta',
            'successful_positions': 0,
            'failed_positions': len(portfolio_positions),
            'total_positions': len(portfolio_positions)
        }

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

            # Initialize result structure
            results = {}
            for scenario in scenarios:
                results[scenario] = {
                    'total': 0.0,
                    'by_underlying': {},
                    'position_details': []
                }

            failed = 0
            successful = 0

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

                # Get volatility
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

                # Risk-free rate (use constant 4% as in other tools)
                rate = 0.04

                # Calculate requested Greeks
                position_detail = {
                    'underlying': underlying,
                    'quantity': quantity,
                    'volatility': vol,
                    'spot': spot,
                    'strike': strike,
                    'time_to_expiry': time_to_exp
                }

                if 'vanna' in scenarios:
                    vanna = _black_scholes_vanna(spot, strike, time_to_exp, vol, rate)
                    position_vanna = vanna * quantity * 100  # 100 shares per contract
                    results['vanna']['total'] += position_vanna

                    if underlying not in results['vanna']['by_underlying']:
                        results['vanna']['by_underlying'][underlying] = 0.0
                    results['vanna']['by_underlying'][underlying] += position_vanna

                    position_detail['vanna'] = vanna
                    position_detail['position_vanna'] = position_vanna

                if 'volga' in scenarios:
                    volga = _black_scholes_volga(spot, strike, time_to_exp, vol, rate)
                    position_volga = volga * quantity * 100
                    results['volga']['total'] += position_volga

                    if underlying not in results['volga']['by_underlying']:
                        results['volga']['by_underlying'][underlying] = 0.0
                    results['volga']['by_underlying'][underlying] += position_volga

                    position_detail['volga'] = volga
                    position_detail['position_volga'] = position_volga

                if 'charm' in scenarios:
                    charm = _black_scholes_charm(spot, strike, time_to_exp, vol, rate, option_type)
                    position_charm = charm * quantity * 100
                    results['charm']['total'] += position_charm

                    if underlying not in results['charm']['by_underlying']:
                        results['charm']['by_underlying'][underlying] = 0.0
                    results['charm']['by_underlying'][underlying] += position_charm

                    position_detail['charm'] = charm
                    position_detail['position_charm'] = position_charm

                if 'veta' in scenarios:
                    veta = _black_scholes_veta(spot, strike, time_to_exp, vol, rate)
                    position_veta = veta * quantity * 100
                    results['veta']['total'] += position_veta

                    if underlying not in results['veta']['by_underlying']:
                        results['veta']['by_underlying'][underlying] = 0.0
                    results['veta']['by_underlying'][underlying] += position_veta

                    position_detail['veta'] = veta
                    position_detail['position_veta'] = position_veta

                # Add position detail to all calculated Greeks
                for scenario in scenarios:
                    results[scenario]['position_details'].append(position_detail.copy())

                successful += 1

            # Add summary statistics
            results['successful_positions'] = successful
            results['failed_positions'] = failed
            results['total_positions'] = len(portfolio_positions)

            return results

        finally:
            await fmp_server.cleanup()
            if polygon_server:
                await polygon_server.cleanup()

    except Exception as e:
        logger.error(f"Cross-Greeks calculation failed: {e}", exc_info=True)
        error_result = {
            'error': str(e),
            'successful_positions': 0,
            'failed_positions': len(portfolio_positions),
            'total_positions': len(portfolio_positions)
        }

        # Add empty structures for requested scenarios
        for scenario in scenarios:
            error_result[scenario] = {
                'total': 0.0,
                'by_underlying': {},
                'position_details': []
            }

        return error_result


@function_tool
async def calculate_cross_greeks(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None,
    use_polygon: bool = True,
    scenarios: Optional[List[str]] = None
) -> str:
    """
    Calculate second-order Greeks (vanna, volga, charm, veta) for advanced risk management.
    
    Agent-facing wrapper that returns JSON string.
    See calculate_cross_greeks_internal for full documentation.

    Args:
        portfolio_positions: List of positions with underlying, expiry, option_type, strike, quantity, implied_volatility (optional)
        underlying_prices: Optional price overrides
        use_polygon: Use Polygon for IV (default True)
        scenarios: Which Greeks to calculate ["vanna", "volga", "charm", "veta"]. Default: all

    Returns:
        JSON string with second-order Greeks exposure
    """
    import json
    result = await calculate_cross_greeks_internal(
        portfolio_positions=portfolio_positions,
        underlying_prices=underlying_prices,
        use_polygon=use_polygon,
        scenarios=scenarios
    )
    return json.dumps(result, indent=2)
