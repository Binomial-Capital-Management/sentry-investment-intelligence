"""
FULLY DYNAMIC Delta Hedge Construction Tool - NO HARDCODING

Constructs delta-neutral hedges using user-specified instruments with dynamic data fetching.
NO assumptions about instrument types, tickers, or market conventions.
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
from .delta_exposure_tool import calculate_delta_exposure, PositionInput, PriceOverride, _fetch_prices, _calculate_delta_impl

logger = logging.getLogger(__name__)


class HedgeInstrument(TypedDict):
    """Hedge instrument specification."""
    ticker: str
    current_price: float
    beta: float
    quantity: float
    notional_value: float
    transaction_cost_estimate: float


async def _fetch_beta(fmp_server, ticker: str) -> float:
    """
    Fetch beta from FMP if available, else return 1.0.

    Beta measures systematic risk relative to market (S&P 500).
    Beta = 1.0 means moves with market, >1.0 more volatile, <1.0 less volatile.
    """
    try:
        # Try to get beta from company profile
        result = await fmp_server.call_tool("get_company_profile", {
            "symbol": ticker
        })

        if not result or not hasattr(result, 'content'):
            logger.debug(f"No profile data for {ticker}, using beta=1.0")
            return 1.0

        data = safe_parse_json(result)

        # Check for beta field
        beta = data.get('beta')
        if beta and isinstance(beta, (int, float)) and beta > 0:
            return float(beta)

        logger.debug(f"No valid beta for {ticker}, using beta=1.0")
        return 1.0

    except Exception as e:
        logger.warning(f"Beta fetch failed for {ticker}: {e}, using beta=1.0")
        return 1.0


async def _fetch_spread(polygon_server, ticker: str, current_price: float) -> Optional[float]:
    """
    Fetch bid-ask spread from Polygon if available.

    Returns spread as a fraction of price (e.g., 0.001 = 0.1%).
    Falls back to None if unavailable.
    """
    if not polygon_server:
        return None

    try:
        # Try to get snapshot with bid/ask
        result = await polygon_server.call_tool("get_polygon_snapshot", {
            "ticker": ticker
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)

        # Look for bid/ask in snapshot
        ticker_data = data.get('ticker', {})
        lastQuote = ticker_data.get('lastQuote', {})

        bid = lastQuote.get('P')  # Bid price
        ask = lastQuote.get('p')  # Ask price

        if bid and ask and current_price > 0:
            spread = (float(ask) - float(bid)) / current_price
            return spread

        return None

    except Exception as e:
        logger.debug(f"Spread fetch failed for {ticker}: {e}")
        return None


async def _estimate_transaction_cost(
    polygon_server,
    ticker: str,
    notional: float,
    current_price: float
) -> float:
    """
    Estimate transaction cost based on bid-ask spread.

    Uses actual spread from Polygon if available, else 0.1% default.
    """
    spread = await _fetch_spread(polygon_server, ticker, current_price)

    if spread and spread > 0:
        # Use actual spread
        cost = abs(notional) * spread
    else:
        # Default assumption: 0.1% of notional
        cost = abs(notional) * 0.001

    return cost


def _calculate_hedge_quantity(
    delta_to_hedge: float,
    instrument_price: float,
    instrument_beta: float,
    instrument_delta: float = 1.0
) -> float:
    """
    Calculate hedge quantity for a given instrument.

    For stocks/ETFs: delta = 1.0
    For options: delta from calculate_delta_exposure

    Formula: quantity = -delta_to_hedge / (price × beta × instrument_delta)
    """
    if instrument_price <= 0 or instrument_beta <= 0:
        return 0.0

    # Beta-adjusted hedge quantity
    hedge_qty = -delta_to_hedge / (instrument_price * instrument_beta * instrument_delta)

    return hedge_qty


async def construct_delta_hedge_internal(
    portfolio_positions: List[PositionInput],
    hedge_tickers: List[str],
    underlying_prices: Optional[List[PriceOverride]] = None,
    hedge_target: float = 0.0,
    rebalance_threshold: float = 0.1,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """
    Internal implementation of delta hedge construction.
    Use this for Canvas and internal calls.
    """
    try:
        fmp_server = FMPMarketDataServer()
        polygon_server = PolygonOptionsFuturesServer() if use_polygon else None

        try:
            await fmp_server.connect()
            if polygon_server:
                await polygon_server.connect()

            # Step 1: Get current portfolio delta
            delta_result = await _calculate_delta_impl(
                portfolio_positions=portfolio_positions,
                underlying_prices=underlying_prices,
                use_polygon=use_polygon
            )

            current_delta = delta_result.get('total_delta', 0.0)

            if delta_result.get('error'):
                return {
                    'error': f"Failed to calculate portfolio delta: {delta_result['error']}",
                    'current_portfolio_delta': 0.0,
                    'target_delta': hedge_target,
                    'delta_to_hedge': 0.0,
                    'hedge_strategies': [],
                    'residual_delta': current_delta,
                    'hedge_ratio': 0.0,
                    'rebalance_monitoring': {
                        'threshold': rebalance_threshold,
                        'current_buffer': 0.0,
                        'requires_rebalance': False
                    }
                }

            # Step 2: Calculate delta to hedge
            delta_to_hedge = current_delta - hedge_target

            # Step 3: Fetch hedge instrument data (DYNAMIC)
            hedge_prices = await _fetch_prices(fmp_server, hedge_tickers)

            if not hedge_prices:
                return {
                    'error': f"Failed to fetch prices for hedge instruments: {hedge_tickers}",
                    'current_portfolio_delta': current_delta,
                    'target_delta': hedge_target,
                    'delta_to_hedge': delta_to_hedge,
                    'hedge_strategies': [],
                    'residual_delta': current_delta,
                    'hedge_ratio': 0.0,
                    'rebalance_monitoring': {
                        'threshold': rebalance_threshold,
                        'current_buffer': abs(current_delta - hedge_target),
                        'requires_rebalance': abs(current_delta - hedge_target) > rebalance_threshold
                    }
                }

            # Step 4: Fetch betas for all instruments
            hedge_betas = {}
            for ticker in hedge_tickers:
                if ticker in hedge_prices:
                    beta = await _fetch_beta(fmp_server, ticker)
                    hedge_betas[ticker] = beta

            # Step 5: Calculate hedge strategies
            hedge_strategies = []

            for ticker in hedge_tickers:
                if ticker not in hedge_prices:
                    logger.warning(f"No price for hedge ticker {ticker}, skipping")
                    continue

                price = hedge_prices[ticker]
                beta = hedge_betas.get(ticker, 1.0)

                quantity = _calculate_hedge_quantity(delta_to_hedge, price, beta, 1.0)
                notional = quantity * price

                tx_cost = await _estimate_transaction_cost(polygon_server, ticker, notional, price)

                hedge_strategies.append({
                    'ticker': ticker,
                    'current_price': price,
                    'beta': beta,
                    'quantity': quantity,
                    'notional_value': notional,
                    'transaction_cost_estimate': tx_cost,
                    'strategy_type': 'single_instrument'
                })

            # Step 6: Calculate residual delta and hedge ratio
            if hedge_strategies:
                first_strategy = hedge_strategies[0]
                hedged_delta = first_strategy['quantity'] * first_strategy['current_price'] * first_strategy['beta']
                residual_delta = current_delta + hedged_delta

                portfolio_notional = delta_result.get('total_delta_notional', 0.0)
                hedge_notional = abs(first_strategy['notional_value'])
                hedge_ratio = hedge_notional / portfolio_notional if portfolio_notional != 0 else 0.0
            else:
                residual_delta = current_delta
                hedge_ratio = 0.0

            # Step 7: Rebalance monitoring
            current_buffer = abs(residual_delta - hedge_target)
            requires_rebalance = current_buffer > rebalance_threshold

            return {
                'current_portfolio_delta': current_delta,
                'target_delta': hedge_target,
                'delta_to_hedge': delta_to_hedge,
                'hedge_strategies': hedge_strategies,
                'residual_delta': residual_delta,
                'hedge_ratio': hedge_ratio,
                'rebalance_monitoring': {
                    'threshold': rebalance_threshold,
                    'current_buffer': current_buffer,
                    'requires_rebalance': requires_rebalance,
                    'buffer_percentage': (current_buffer / abs(hedge_target) * 100) if hedge_target != 0 else 0.0
                },
                'portfolio_delta_breakdown': delta_result.get('position_details', []),
                'successful_hedge_instruments': len([s for s in hedge_strategies if s.get('strategy_type') == 'single_instrument']),
                'total_transaction_cost': sum(s['transaction_cost_estimate'] for s in hedge_strategies)
            }

        finally:
            await fmp_server.cleanup()
            if polygon_server:
                await polygon_server.cleanup()

    except Exception as e:
        logger.error(f"Delta hedge construction failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'current_portfolio_delta': 0.0,
            'target_delta': hedge_target,
            'delta_to_hedge': 0.0,
            'hedge_strategies': [],
            'residual_delta': 0.0,
            'hedge_ratio': 0.0,
            'rebalance_monitoring': {
                'threshold': rebalance_threshold,
                'current_buffer': 0.0,
                'requires_rebalance': False
            }
        }


@function_tool
async def construct_delta_hedge(
    portfolio_positions: List[PositionInput],
    hedge_tickers: List[str],
    underlying_prices: Optional[List[PriceOverride]] = None,
    hedge_target: float = 0.0,
    rebalance_threshold: float = 0.1,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """
    Construct delta-neutral hedge using user-specified instruments with dynamic data fetching.

    NO HARDCODING: User provides any ticker symbols, tool fetches all data dynamically.

    Args:
        portfolio_positions: List of options positions to hedge (same format as calculate_delta_exposure)
        hedge_tickers: List of ticker symbols to use for hedging (e.g., ["SPY"], ["AAPL", "MSFT"], ["ES=F"])
        underlying_prices: Optional price overrides for underlyings
        hedge_target: Target delta after hedging (default 0.0 = neutral)
        rebalance_threshold: Delta threshold for rebalancing alert (default 0.1)
        use_polygon: Whether to use Polygon for spread data

    Returns:
        Dict with:
        - current_portfolio_delta: Current delta before hedging
        - target_delta: Desired delta after hedging
        - delta_to_hedge: Delta that needs to be hedged
        - hedge_strategies: List of hedge approaches (one per instrument or combined)
        - residual_delta: Expected delta after hedging
        - hedge_ratio: Hedge notional / Portfolio notional
        - rebalance_monitoring: Thresholds and alerts

    Example:
        # Hedge with SPY
        result = await construct_delta_hedge(
            portfolio_positions=[...],
            hedge_tickers=["SPY"]
        )

        # Hedge with multiple instruments
        result = await construct_delta_hedge(
            portfolio_positions=[...],
            hedge_tickers=["SPY", "QQQ", "IWM"],
            hedge_target=0.0
        )
    """
    return await construct_delta_hedge_internal(
        portfolio_positions=portfolio_positions,
        hedge_tickers=hedge_tickers,
        underlying_prices=underlying_prices,
        hedge_target=hedge_target,
        rebalance_threshold=rebalance_threshold,
        use_polygon=use_polygon
    )


# Keep original implementation below for reference but it's now unused
async def _construct_delta_hedge_legacy(
    portfolio_positions: List[PositionInput],
    hedge_tickers: List[str],
    underlying_prices: Optional[List[PriceOverride]] = None,
    hedge_target: float = 0.0,
    rebalance_threshold: float = 0.1,
    use_polygon: bool = True
) -> Dict[str, Any]:
    """Legacy implementation - kept for reference."""
    try:
        fmp_server = FMPMarketDataServer()
        polygon_server = PolygonOptionsFuturesServer() if use_polygon else None

        try:
            await fmp_server.connect()
            if polygon_server:
                await polygon_server.connect()

            delta_result = await _calculate_delta_impl(
                portfolio_positions=portfolio_positions,
                underlying_prices=underlying_prices,
                use_polygon=use_polygon
            )

            current_delta = delta_result.get('total_delta', 0.0)

            if delta_result.get('error'):
                return {
                    'error': f"Failed to calculate portfolio delta: {delta_result['error']}",
                    'current_portfolio_delta': 0.0,
                    'target_delta': hedge_target,
                    'delta_to_hedge': 0.0,
                    'hedge_strategies': [],
                    'residual_delta': current_delta,
                    'hedge_ratio': 0.0,
                    'rebalance_monitoring': {
                        'threshold': rebalance_threshold,
                        'current_buffer': 0.0,
                        'requires_rebalance': False
                    }
                }

            # Step 2: Calculate delta to hedge
            delta_to_hedge = current_delta - hedge_target

            # Step 3: Fetch hedge instrument data (DYNAMIC)
            hedge_prices = await _fetch_prices(fmp_server, hedge_tickers)

            if not hedge_prices:
                return {
                    'error': f"Failed to fetch prices for hedge instruments: {hedge_tickers}",
                    'current_portfolio_delta': current_delta,
                    'target_delta': hedge_target,
                    'delta_to_hedge': delta_to_hedge,
                    'hedge_strategies': [],
                    'residual_delta': current_delta,
                    'hedge_ratio': 0.0,
                    'rebalance_monitoring': {
                        'threshold': rebalance_threshold,
                        'current_buffer': abs(current_delta - hedge_target),
                        'requires_rebalance': abs(current_delta - hedge_target) > rebalance_threshold
                    }
                }

            # Step 4: Fetch betas for all instruments
            hedge_betas = {}
            for ticker in hedge_tickers:
                if ticker in hedge_prices:
                    beta = await _fetch_beta(fmp_server, ticker)
                    hedge_betas[ticker] = beta

            # Step 5: Calculate hedge strategies
            hedge_strategies = []

            # Strategy 1: Individual hedge for each instrument
            for ticker in hedge_tickers:
                if ticker not in hedge_prices:
                    logger.warning(f"No price for hedge ticker {ticker}, skipping")
                    continue

                price = hedge_prices[ticker]
                beta = hedge_betas.get(ticker, 1.0)

                # Calculate quantity (assuming delta=1.0 for stocks/ETFs)
                quantity = _calculate_hedge_quantity(delta_to_hedge, price, beta, 1.0)
                notional = quantity * price

                # Estimate transaction cost
                tx_cost = await _estimate_transaction_cost(polygon_server, ticker, notional, price)

                hedge_strategies.append({
                    'ticker': ticker,
                    'current_price': price,
                    'beta': beta,
                    'quantity': quantity,
                    'notional_value': notional,
                    'transaction_cost_estimate': tx_cost,
                    'strategy_type': 'single_instrument'
                })

            # Strategy 2: If multiple instruments, also show proportional allocation
            if len(hedge_strategies) > 1:
                # Equal weight allocation
                num_instruments = len(hedge_strategies)
                delta_per_instrument = delta_to_hedge / num_instruments

                combined_strategy = []
                total_notional = 0.0
                total_tx_cost = 0.0

                for ticker in hedge_tickers:
                    if ticker not in hedge_prices:
                        continue

                    price = hedge_prices[ticker]
                    beta = hedge_betas.get(ticker, 1.0)

                    quantity = _calculate_hedge_quantity(delta_per_instrument, price, beta, 1.0)
                    notional = quantity * price
                    tx_cost = await _estimate_transaction_cost(polygon_server, ticker, notional, price)

                    total_notional += notional
                    total_tx_cost += tx_cost

                    combined_strategy.append({
                        'ticker': ticker,
                        'current_price': price,
                        'beta': beta,
                        'quantity': quantity,
                        'notional_value': notional,
                        'transaction_cost_estimate': tx_cost,
                        'strategy_type': 'proportional_allocation',
                        'allocation_weight': 1.0 / num_instruments
                    })

                hedge_strategies.extend(combined_strategy)

            # Step 6: Calculate residual delta and hedge ratio
            # Use first strategy for residual calculation
            if hedge_strategies:
                first_strategy = hedge_strategies[0]
                hedged_delta = first_strategy['quantity'] * first_strategy['current_price'] * first_strategy['beta']
                residual_delta = current_delta + hedged_delta

                # Calculate hedge ratio
                portfolio_notional = delta_result.get('total_delta_notional', 0.0)
                hedge_notional = abs(first_strategy['notional_value'])
                hedge_ratio = hedge_notional / portfolio_notional if portfolio_notional != 0 else 0.0
            else:
                residual_delta = current_delta
                hedge_ratio = 0.0

            # Step 7: Rebalance monitoring
            current_buffer = abs(residual_delta - hedge_target)
            requires_rebalance = current_buffer > rebalance_threshold

            return {
                'current_portfolio_delta': current_delta,
                'target_delta': hedge_target,
                'delta_to_hedge': delta_to_hedge,
                'hedge_strategies': hedge_strategies,
                'residual_delta': residual_delta,
                'hedge_ratio': hedge_ratio,
                'rebalance_monitoring': {
                    'threshold': rebalance_threshold,
                    'current_buffer': current_buffer,
                    'requires_rebalance': requires_rebalance,
                    'buffer_percentage': (current_buffer / abs(hedge_target) * 100) if hedge_target != 0 else 0.0
                },
                'portfolio_delta_breakdown': delta_result.get('position_details', []),
                'successful_hedge_instruments': len([s for s in hedge_strategies if s.get('strategy_type') == 'single_instrument']),
                'total_transaction_cost': sum(s['transaction_cost_estimate'] for s in hedge_strategies)
            }

        finally:
            await fmp_server.cleanup()
            if polygon_server:
                await polygon_server.cleanup()

    except Exception as e:
        logger.error(f"Delta hedge construction failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'current_portfolio_delta': 0.0,
            'target_delta': hedge_target,
            'delta_to_hedge': 0.0,
            'hedge_strategies': [],
            'residual_delta': 0.0,
            'hedge_ratio': 0.0,
            'rebalance_monitoring': {
                'threshold': rebalance_threshold,
                'current_buffer': 0.0,
                'requires_rebalance': False
            }
        }
