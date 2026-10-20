"""
Equity Option Pricing Tool - Multi-Model Option Valuation
Prices equity options using Black-Scholes, Binomial Tree, or Monte Carlo
Based on pca_analysis_tool.py pattern with FMP data fetching
"""

from agents import function_tool
from typing import List, Optional, Dict, Any
import logging
import math
from datetime import datetime, timedelta

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results

logger = logging.getLogger(__name__)


def _black_scholes_price(S: float, K: float, T: float, r: float, sigma: float, q: float, option_type: str) -> Dict[str, Any]:
    """Black-Scholes closed-form solution with Greeks."""
    if T <= 0:
        intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
        return {
            'price': intrinsic,
            'greeks': {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0},
            'breakdown': {'intrinsic_value': intrinsic, 'time_value': 0.0}
        }

    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    def norm_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def norm_pdf(x):
        return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)

    if option_type == 'call':
        price = S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        delta = math.exp(-q * T) * norm_cdf(d1)
        theta_partial = -(S * norm_pdf(d1) * sigma * math.exp(-q * T)) / (2 * math.sqrt(T))
        theta = theta_partial - r * K * math.exp(-r * T) * norm_cdf(d2) + q * S * math.exp(-q * T) * norm_cdf(d1)
        rho = K * T * math.exp(-r * T) * norm_cdf(d2) / 100
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * math.exp(-q * T) * norm_cdf(-d1)
        delta = -math.exp(-q * T) * norm_cdf(-d1)
        theta_partial = -(S * norm_pdf(d1) * sigma * math.exp(-q * T)) / (2 * math.sqrt(T))
        theta = theta_partial + r * K * math.exp(-r * T) * norm_cdf(-d2) - q * S * math.exp(-q * T) * norm_cdf(-d1)
        rho = -K * T * math.exp(-r * T) * norm_cdf(-d2) / 100

    gamma = (norm_pdf(d1) * math.exp(-q * T)) / (S * sigma * math.sqrt(T))
    vega = S * math.exp(-q * T) * norm_pdf(d1) * math.sqrt(T) / 100
    theta = theta / 365

    intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
    time_value = price - intrinsic

    return {
        'price': price,
        'greeks': {'delta': delta, 'gamma': gamma, 'vega': vega, 'theta': theta, 'rho': rho},
        'breakdown': {'d1': d1, 'd2': d2, 'intrinsic_value': intrinsic, 'time_value': time_value}
    }


def _binomial_tree_core(S: float, K: float, T: float, r: float, sigma: float, q: float,
                        option_type: str, steps: int, american: bool) -> float:
    """Core binomial tree - returns price only."""
    if T <= 0:
        return max(0, S - K) if option_type == 'call' else max(0, K - S)
    
    dt = T / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    
    # Terminal payoffs
    option_values = []
    for j in range(steps + 1):
        stock_price = S * (u ** (steps - j)) * (d ** j)
        if option_type == 'call':
            option_values.append(max(0, stock_price - K))
        else:
            option_values.append(max(0, K - stock_price))
    
    # Backward induction
    for i in range(steps - 1, -1, -1):
        for j in range(i + 1):
            stock_price = S * (u ** (i - j)) * (d ** j)
            continuation = math.exp(-r * dt) * (p * option_values[j] + (1 - p) * option_values[j + 1])
            if american:
                exercise = max(0, stock_price - K) if option_type == 'call' else max(0, K - stock_price)
                option_values[j] = max(continuation, exercise)
            else:
                option_values[j] = continuation
    
    return option_values[0]


def _binomial_tree_price(S: float, K: float, T: float, r: float, sigma: float, q: float,
                         option_type: str, steps: int = 100, american: bool = False) -> Dict[str, Any]:
    """Cox-Ross-Rubinstein binomial tree pricing with Greeks via finite difference."""
    if T <= 0:
        intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
        return {'price': intrinsic, 'greeks': {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0}, 'breakdown': {'model': 'binomial_tree'}}

    price = _binomial_tree_core(S, K, T, r, sigma, q, option_type, steps, american)
    
    # Greeks via finite difference
    dS = S * 0.01
    price_up = _binomial_tree_core(S + dS, K, T, r, sigma, q, option_type, steps, american)
    price_down = _binomial_tree_core(S - dS, K, T, r, sigma, q, option_type, steps, american)
    delta = (price_up - price_down) / (2 * dS)
    gamma = (price_up - 2 * price + price_down) / (dS ** 2)
    
    dVol = 0.01
    price_vol_up = _binomial_tree_core(S, K, T, r, sigma + dVol, q, option_type, steps, american)
    vega = (price_vol_up - price) / (dVol * 100)  # Per 1% vol
    
    dT = 1 / 365
    if T > dT:
        price_t_down = _binomial_tree_core(S, K, T - dT, r, sigma, q, option_type, steps, american)
        theta = (price_t_down - price)  # Daily decay
    else:
        theta = 0
    
    dR = 0.01
    price_r_up = _binomial_tree_core(S, K, T, r + dR, sigma, q, option_type, steps, american)
    rho = (price_r_up - price) / (dR * 100)  # Per 1% rate

    dt = T / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)

    # Calculate intrinsic and time value
    intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
    time_value = price - intrinsic

    return {
        'price': price,
        'greeks': {'delta': delta, 'gamma': gamma, 'vega': vega, 'theta': theta, 'rho': rho},
        'breakdown': {
            'model': 'binomial_tree',
            'steps': steps,
            'american': american,
            'up_factor': u,
            'down_factor': d,
            'risk_neutral_prob': p,
            'intrinsic_value': intrinsic,
            'time_value': time_value,
        }
    }


def _monte_carlo_core(S: float, K: float, T: float, r: float, sigma: float, q: float,
                      option_type: str, simulations: int, Z_samples: List[float]) -> float:
    """Core Monte Carlo - returns price using pre-generated random samples."""
    if T <= 0:
        return max(0, S - K) if option_type == 'call' else max(0, K - S)
    
    payoffs = []
    for Z in Z_samples:
        ST = S * math.exp((r - q - 0.5 * sigma ** 2) * T + sigma * math.sqrt(T) * Z)
        payoff = max(ST - K, 0) if option_type == 'call' else max(K - ST, 0)
        payoffs.append(payoff)
    
    return math.exp(-r * T) * sum(payoffs) / len(payoffs)


def _monte_carlo_price(S: float, K: float, T: float, r: float, sigma: float, q: float,
                       option_type: str, simulations: int = 10000, seed: Optional[int] = None) -> Dict[str, Any]:
    """Monte Carlo simulation with Greeks via finite difference (same random path)."""
    if T <= 0:
        intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
        return {'price': intrinsic, 'greeks': {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0}, 'breakdown': {'model': 'monte_carlo'}}

    import random
    if seed is not None:
        random.seed(seed)
    
    # Generate random samples once (reuse for all Greeks)
    Z_samples = [random.gauss(0, 1) for _ in range(simulations)]
    
    # Base price
    price = _monte_carlo_core(S, K, T, r, sigma, q, option_type, simulations, Z_samples)
    
    # Standard error
    payoffs = []
    for Z in Z_samples:
        ST = S * math.exp((r - q - 0.5 * sigma ** 2) * T + sigma * math.sqrt(T) * Z)
        payoffs.append(max(ST - K, 0) if option_type == 'call' else max(K - ST, 0))
    mean_payoff = sum(payoffs) / len(payoffs)
    variance = sum((p - mean_payoff) ** 2 for p in payoffs) / (len(payoffs) - 1)
    std_error = math.exp(-r * T) * math.sqrt(variance / simulations)
    
    # Greeks via finite difference (same random paths)
    dS = S * 0.01
    price_up = _monte_carlo_core(S + dS, K, T, r, sigma, q, option_type, simulations, Z_samples)
    price_down = _monte_carlo_core(S - dS, K, T, r, sigma, q, option_type, simulations, Z_samples)
    delta = (price_up - price_down) / (2 * dS)
    gamma = (price_up - 2 * price + price_down) / (dS ** 2)
    
    dVol = 0.01
    price_vol_up = _monte_carlo_core(S, K, T, r, sigma + dVol, q, option_type, simulations, Z_samples)
    vega = (price_vol_up - price) / (dVol * 100)  # Per 1% vol
    
    dT = 1 / 365
    if T > dT:
        price_t_down = _monte_carlo_core(S, K, T - dT, r, sigma, q, option_type, simulations, Z_samples)
        theta = (price_t_down - price)  # Daily decay
    else:
        theta = 0
    
    dR = 0.01
    price_r_up = _monte_carlo_core(S, K, T, r + dR, sigma, q, option_type, simulations, Z_samples)
    rho = (price_r_up - price) / (dR * 100)  # Per 1% rate

    # Calculate intrinsic and time value
    intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
    time_value = price - intrinsic

    return {
        'price': price,
        'greeks': {'delta': delta, 'gamma': gamma, 'vega': vega, 'theta': theta, 'rho': rho},
        'breakdown': {
            'model': 'monte_carlo',
            'simulations': simulations,
            'std_error': std_error,
            'confidence_95_lower': price - 1.96 * std_error,
            'confidence_95_upper': price + 1.96 * std_error,
            'intrinsic_value': intrinsic,
            'time_value': time_value,
        }
    }


def _calculate_implied_vol(market_price: float, S: float, K: float, T: float, r: float, q: float,
                           option_type: str, max_iter: int = 100, tol: float = 1e-6) -> Optional[float]:
    """Calculate implied volatility using Newton-Raphson."""
    if T <= 0:
        return None

    sigma = 0.30

    for _ in range(max_iter):
        result = _black_scholes_price(S, K, T, r, sigma, q, option_type)
        price = result['price']
        vega = result['greeks']['vega'] * 100

        price_diff = price - market_price

        if abs(price_diff) < tol:
            return sigma

        if abs(vega) < 1e-10:
            break

        sigma = sigma - price_diff / vega

        if sigma <= 0.001:
            sigma = 0.001
        elif sigma > 5.0:
            sigma = 5.0

    return None


async def price_equity_options_internal(
    ticker: str,
    strike: float,
    expiry: str,
    option_type: str,
    pricing_model: Optional[str] = None,
    model_params: Optional[Dict[str, Any]] = None,
    underlying_price: Optional[float] = None,
    volatility: Optional[float] = None,
    risk_free_rate: Optional[float] = None,
    dividend_yield: Optional[float] = None,
    market_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Price equity options using Black-Scholes, Binomial Tree, or Monte Carlo.

    Fetches market data from FMP Market Data Server:
    - Underlying price (latest close from get_historical_data)
    - Historical volatility (30-day annualized from price returns)
    - Company data (dividend yield from company-profile/company-quote datasets)

    Args:
        ticker: Underlying ticker symbol
        strike: Strike price
        expiry: Expiration date (YYYY-MM-DD)
        option_type: "call" or "put"
        pricing_model: "black_scholes" | "binomial" | "monte_carlo" (default: "black_scholes")
        model_params: Model-specific parameters (optional)
            - Black-Scholes: None needed
            - Binomial: {"steps": 100, "american": False}
            - Monte Carlo: {"simulations": 10000, "seed": 42}
        underlying_price: Override spot price (optional)
        volatility: Override volatility (optional, annualized)
        risk_free_rate: Override risk-free rate (optional)
        dividend_yield: Override dividend yield (optional)
        market_price: Market price for implied vol calculation (optional)

    Returns:
        Dict with option_price, greeks, implied_volatility, model_inputs, pricing_breakdown, data_sources
    """
    try:
        # Set defaults
        if pricing_model is None:
            pricing_model = 'black_scholes'
        if model_params is None:
            model_params = {}

        # Validation
        option_type = option_type.lower()
        pricing_model = pricing_model.lower()

        if option_type not in ['call', 'put']:
            raise ValueError(f"option_type must be 'call' or 'put', got: {option_type}")

        if pricing_model not in ['black_scholes', 'binomial', 'monte_carlo']:
            raise ValueError(f"pricing_model must be one of: black_scholes, binomial, monte_carlo")

        try:
            expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"expiry must be in YYYY-MM-DD format, got: {expiry}")

        today = datetime.now()
        time_to_expiry = (expiry_date - today).days / 365.25

        data_sources = []

        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Fetch underlying price
            if underlying_price is not None:
                spot_price = underlying_price
                data_sources.append(f"underlying_price: user_override ({spot_price:.2f})")
            else:
                logger.info(f"Fetching price for {ticker}...")
                end_date = datetime.now()
                start_date = end_date - timedelta(days=5)

                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })

                if not result or not hasattr(result, 'content'):
                    raise ValueError(f"No price data for {ticker}")

                data = safe_parse_json(result)
                prices = data.get("prices") or data.get("closes") or data.get("close") or []

                if not prices:
                    raise ValueError(f"No price data returned for {ticker}")

                spot_price = float(prices[-1])
                data_sources.append(f"underlying_price: FMP latest close ({spot_price:.2f})")

            # Fetch volatility
            if volatility is not None:
                vol = volatility
                data_sources.append(f"volatility: user_override ({vol:.4f})")
            else:
                logger.info(f"Calculating historical volatility for {ticker}...")
                end_date = datetime.now()
                start_date = end_date - timedelta(days=40)

                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                })

                if not result or not hasattr(result, 'content'):
                    logger.warning(f"No volatility data for {ticker}, using default 0.30")
                    vol = 0.30
                    data_sources.append(f"volatility: fallback estimate ({vol:.4f})")
                else:
                    data = safe_parse_json(result)
                    price_array = data.get("prices") or data.get("closes") or data.get("close") or []

                    if len(price_array) >= 10:
                        prices_float = [float(p) for p in price_array[:31] if p]

                        # Calculate log returns
                        log_returns = []
                        for i in range(1, len(prices_float)):
                            log_returns.append(math.log(prices_float[i] / prices_float[i-1]))

                        # Annualized volatility
                        mean_return = sum(log_returns) / len(log_returns)
                        variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
                        daily_vol = math.sqrt(variance)
                        vol = daily_vol * math.sqrt(252)

                        data_sources.append(f"volatility: FMP 30-day historical ({vol:.4f})")
                    else:
                        vol = 0.30
                        data_sources.append(f"volatility: fallback estimate ({vol:.4f})")

            # Risk-free rate - fetch from FRED if not provided
            if risk_free_rate is not None:
                rfr = risk_free_rate
                data_sources.append(f"risk_free_rate: user_override ({rfr:.4f})")
            else:
                # Fetch current risk-free rate from FRED (3-month Treasury)
                try:
                    from core.mcp_servers.EconomicDataServer import EconomicDataServer
                    fred_server = EconomicDataServer()
                    await fred_server.connect()

                    try:
                        # Use 3-month Treasury as risk-free proxy (most liquid short-term rate)
                        fred_result = await fred_server.get_series_data(series_id="DGS3MO")

                        if fred_result and fred_result.get("data") and len(fred_result["data"]) > 0:
                            # FRED returns rates as percentages, convert to decimal
                            rfr = fred_result["data"][-1]["value"] / 100.0
                            data_sources.append(f"risk_free_rate: FRED 3M Treasury ({rfr:.4f})")
                            logger.info(f"Fetched risk-free rate from FRED: {rfr:.4f}")
                        else:
                            rfr = 0.045
                            data_sources.append(f"risk_free_rate: fallback assumption ({rfr:.4f})")
                            logger.warning("FRED returned no data for risk-free rate, using fallback")
                    finally:
                        await fred_server.cleanup()

                except Exception as e:
                    logger.warning(f"Failed to fetch risk-free rate from FRED: {e}")
                    rfr = 0.045
                    data_sources.append(f"risk_free_rate: fallback assumption ({rfr:.4f})")

            # Dividend yield
            if dividend_yield is not None:
                div_yield = dividend_yield
                data_sources.append(f"dividend_yield: user_override ({div_yield:.4f})")
            else:
                logger.info(f"Fetching company data for {ticker}...")
                result = await fmp_server.call_tool("get_fields", {
                    "symbol": ticker,
                    "datasets": ["company-profile", "company-quote"]
                })

                div_yield = 0.0
                if result and hasattr(result, 'content'):
                    data = safe_parse_json(result)

                    # Try to extract dividend yield from company data
                    for key in data.keys():
                        if 'dividend' in key.lower() and 'yield' in key.lower():
                            try:
                                div_val = float(data[key])
                                if div_val > 1.0:
                                    div_val = div_val / 100.0
                                div_yield = div_val
                                data_sources.append(f"dividend_yield: FMP {key} ({div_yield:.4f})")
                                break
                            except (ValueError, TypeError):
                                continue

                if div_yield == 0.0:
                    data_sources.append(f"dividend_yield: assumed zero ({div_yield:.4f})")

            # Select pricing model
            if pricing_model == 'black_scholes':
                result = _black_scholes_price(spot_price, strike, time_to_expiry, rfr, vol, div_yield, option_type)
            elif pricing_model == 'binomial':
                steps = model_params.get('steps', 100)
                american = model_params.get('american', False)
                result = _binomial_tree_price(spot_price, strike, time_to_expiry, rfr, vol, div_yield, option_type, steps, american)
            else:
                simulations = model_params.get('simulations', 10000)
                seed = model_params.get('seed', None)
                result = _monte_carlo_price(spot_price, strike, time_to_expiry, rfr, vol, div_yield, option_type, simulations, seed)

            # Implied volatility if market price provided
            implied_vol = None
            if market_price is not None:
                implied_vol = _calculate_implied_vol(market_price, spot_price, strike, time_to_expiry, rfr, div_yield, option_type)
                if implied_vol:
                    data_sources.append(f"implied_volatility: calculated from market price ({implied_vol:.4f})")

            return {
                'status': 'success',
                'option_price': result['price'],
                'greeks': result['greeks'],
                'implied_volatility': implied_vol,
                'model_inputs': {
                    'ticker': ticker,
                    'underlying_price': spot_price,
                    'strike': strike,
                    'expiry': expiry,
                    'time_to_expiry_years': time_to_expiry,
                    'volatility': vol,
                    'risk_free_rate': rfr,
                    'dividend_yield': div_yield,
                    'option_type': option_type,
                    'pricing_model': pricing_model
                },
                'pricing_breakdown': result['breakdown'],
                'data_sources': data_sources
            }

        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Option pricing failed: {e}")
        error_type = 'data_error' if any(
            kw in str(e).lower() for kw in ['no data', 'no price', 'insufficient']
        ) else 'general_error'

        return {
            'status': 'error',
            'error': str(e),
            'error_type': error_type,
            'calculation_type': 'option_pricing'
        }


@function_tool(strict_mode=False)  # Dict[str, Any] not allowed in strict schemas
async def price_equity_options(
    ticker: str,
    strike: float,
    expiry: str,
    option_type: str,
    pricing_model: Optional[str] = None,
    model_params: Optional[Dict[str, Any]] = None,
    underlying_price: Optional[float] = None,
    volatility: Optional[float] = None,
    risk_free_rate: Optional[float] = None,
    dividend_yield: Optional[float] = None,
    market_price: Optional[float] = None
) -> dict:
    """
    Price equity options using Black-Scholes, Binomial Tree, or Monte Carlo.

    Args:
        ticker: Underlying ticker symbol
        strike: Strike price
        expiry: Expiration date (YYYY-MM-DD)
        option_type: "call" or "put"
        pricing_model: "black_scholes" | "binomial" | "monte_carlo" (default: "black_scholes")
        model_params: Model-specific parameters (optional)
        underlying_price: Override spot price (optional)
        volatility: Override volatility (optional, annualized)
        risk_free_rate: Override risk-free rate (optional)
        dividend_yield: Override dividend yield (optional)
        market_price: Market price for implied vol calculation (optional)

    Returns:
        Dict with option_price, greeks, implied_volatility, model_inputs, pricing_breakdown
    """
    result = await price_equity_options_internal(
        ticker=ticker,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
        pricing_model=pricing_model,
        model_params=model_params,
        underlying_price=underlying_price,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        market_price=market_price
    )
    return jsonify_results(result)
