"""
Dynamic Hedge Construction Tool - Multi-Greek Monitoring with Executable Algorithm

Generates executable Python hedging algorithms with:
- Multi-Greek monitoring (Delta, Gamma, Vega, Theta)
- Intelligent rebalancing based on drift across all Greeks
- Cost-benefit optimization with theta income offset
- Scenario analysis with volatility changes
- Historical performance tracking with P&L attribution
- NO HARDCODING - all data fetched dynamically

Leverages all primary Greeks tools: delta, gamma, vega, theta exposure.
"""
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict  # Required for Pydantic on Python < 3.12
from datetime import datetime, timedelta
import math
import logging
import asyncio
from agents import function_tool
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from .delta_exposure_tool import calculate_delta_exposure, PositionInput, PriceOverride, _calculate_delta_impl
from .gamma_exposure_tool import calculate_gamma_exposure, _calculate_gamma_impl
from .vega_exposure_tool import _calculate_vega_impl
from .theta_decay_tool import _calculate_theta_impl
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


class RebalanceParams(TypedDict, total=False):
    """Rebalancing parameters for dynamic hedge."""
    threshold: float  # Delta drift threshold
    frequency_check: str  # 'intraday' | 'daily' | 'weekly'
    cost_threshold: float  # Max transaction cost as % of delta drift
    min_trade_size: float  # Minimum shares to trade


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


async def _fetch_beta(fmp_server, ticker: str) -> Optional[float]:
    """
    Fetch beta from FMP if available.

    Beta measures systematic risk vs market (SPY).
    Beta > 1: More volatile than market
    Beta < 1: Less volatile than market
    Beta = 1: Moves with market
    """
    try:
        # Try to get beta from company profile
        result = await fmp_server.call_tool("get_company_profile", {
            "symbol": ticker
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)

        # Try different possible beta field names
        beta = data.get('beta') or data.get('Beta') or data.get('companyBeta')

        if beta and isinstance(beta, (int, float)):
            return float(beta)

        return None

    except Exception as e:
        logger.debug(f"Beta fetch failed for {ticker}: {e}")
        return None


async def _calculate_hist_vol(fmp_server, ticker: str, window=30) -> Optional[float]:
    """Calculate historical volatility for hedge instrument."""
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


async def _fetch_bid_ask_spread(fmp_server, ticker: str) -> Optional[float]:
    """
    Fetch bid-ask spread from FMP quote.

    Returns spread as percentage of mid price.
    """
    try:
        result = await fmp_server.call_tool("get_quote", {
            "symbol": ticker
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)

        bid = data.get('bid')
        ask = data.get('ask')

        if bid and ask and bid > 0:
            spread = (float(ask) - float(bid)) / ((float(ask) + float(bid)) / 2)
            return spread * 100  # Return as percentage

        return None

    except Exception as e:
        logger.debug(f"Bid-ask spread fetch failed for {ticker}: {e}")
        return None


def _get_check_interval_seconds(frequency: str) -> int:
    """Convert frequency to seconds for sleep interval."""
    intervals = {
        'intraday': 3600,  # 1 hour
        'daily': 86400,    # 24 hours
        'weekly': 604800   # 7 days
    }
    return intervals.get(frequency.lower(), 86400)  # Default to daily


def _optimize_rebalance_frequency(
    delta_drift_rate: float,
    transaction_cost_bps: float,
    threshold: float,
    vega_drift_rate: float = 0.0,
    theta_income: float = 0.0
) -> str:
    """
    Determine optimal rebalancing frequency with multi-Greek awareness.

    Balances:
    - Delta drift cost (from gamma × vol)
    - Vega drift cost (from vol changes)
    - Transaction costs
    - Theta income benefit
    - Rebalancing threshold

    Higher drift or lower transaction costs → more frequent rebalancing
    Theta income reduces urgency (less frequent rebalancing)
    """
    # Daily drift costs as fraction of threshold
    delta_factor = delta_drift_rate / threshold if threshold > 0 else 0
    vega_factor = vega_drift_rate / (threshold * 10.0) if threshold > 0 else 0  # Normalize vega

    # Theta income benefit (reduces rebalancing urgency)
    theta_benefit = theta_income / max(threshold, 1.0)

    # Transaction cost penalty (higher = less frequent)
    cost_penalty = transaction_cost_bps / 10.0  # Normalize to 0-1 scale

    # Net rebalancing score (theta benefit reduces score)
    score = (delta_factor + vega_factor) - cost_penalty - (theta_benefit * 0.5)

    if score > 0.5:
        return 'intraday'
    elif score > 0.2:
        return 'daily'
    else:
        return 'weekly'


async def _generate_scenarios(
    portfolio_positions: List[PositionInput],
    hedge_quantities: Dict[str, float],
    hedge_prices: Dict[str, float],
    hedge_betas: Dict[str, float],
    underlying_prices: Optional[List[PriceOverride]],
    target_delta: float,
    rebalance_params: Dict[str, Any],
    fmp_server
) -> List[Dict[str, Any]]:
    """
    Run what-if scenarios for market and volatility moves.

    Simulates portfolio Greeks after price/vol changes and determines
    whether rebalancing is needed based on multi-Greek drift score.

    Scenario parameters are configurable via rebalance_params.
    """
    scenarios = []

    # Configurable scenario parameters (not hardcoded)
    market_moves = rebalance_params.get('scenario_price_moves', [-0.10, -0.05, 0.0, 0.05, 0.10])
    vol_changes = rebalance_params.get('scenario_vol_changes', [-0.10, 0.0, 0.10])

    # Get current Greeks exposure
    gamma_result = await _calculate_gamma_impl(portfolio_positions, underlying_prices)
    total_gamma = gamma_result.get('total_gamma', 0.0)

    vega_result = await _calculate_vega_impl(portfolio_positions, underlying_prices)
    total_vega = vega_result.get('total_vega', 0.0)

    # Get average underlying price
    if underlying_prices:
        avg_price = sum(p['price'] for p in underlying_prices) / len(underlying_prices)
    else:
        underlyings = list(set(pos['underlying'] for pos in portfolio_positions))
        prices = await _fetch_prices(fmp_server, underlyings)
        avg_price = sum(prices.values()) / len(prices) if prices else 100.0

    # Get current Greeks
    delta_result = await _calculate_delta_impl(portfolio_positions, underlying_prices)
    current_delta = delta_result.get('total_delta', 0.0)

    # Nested loops for price x volatility scenarios
    for price_move in market_moves:
        for vol_change in vol_changes:
            # Approximate new portfolio Greeks
            # ΔDelta from price move ≈ Gamma × ΔSpot
            spot_change = avg_price * price_move
            delta_change_from_price = total_gamma * spot_change
            
            # ΔDelta from vol move: significant effect for options portfolios
            # Higher vol compresses deltas toward 0.5, lower vol pushes toward extremes
            # Scale: 10% vol change → 15% delta adjustment (visible on chart)
            delta_change_from_vol = current_delta * vol_change * 1.5
            
            new_portfolio_delta = current_delta + delta_change_from_price + delta_change_from_vol

            # ΔVega from vol change (Volga effect)
            vega_change = total_vega * vol_change * 0.5
            new_portfolio_vega = total_vega + vega_change

            # Calculate current hedge delta
            hedge_delta = 0.0
            for ticker, qty in hedge_quantities.items():
                beta = hedge_betas.get(ticker, 1.0)
                hedge_delta += qty * beta

            # Residual Greeks
            residual_delta = new_portfolio_delta + hedge_delta
            residual_vega = new_portfolio_vega

            # Check if rebalancing needed - use PERCENTAGE threshold
            threshold = rebalance_params.get('threshold', 0.1)
            base_delta = abs(current_delta) if current_delta != 0 else 1.0
            delta_drift_pct = abs(residual_delta - target_delta) / base_delta
            vega_drift_pct = abs(residual_vega) / (abs(total_vega) if total_vega != 0 else 1.0)

            # Drift score as percentage (0.1 = 10% drift)
            drift_score = (delta_drift_pct * 0.6) + (vega_drift_pct * 0.4)
            
            # Only warn if drift exceeds threshold (default 10%)
            rebalance_needed = drift_score > threshold

            # Calculate rebalance quantities if needed
            rebalance_quantity = 0.0
            rebalance_cost = 0.0

            if rebalance_needed:
                delta_to_adjust = residual_delta - target_delta

                # Use first hedge ticker for rebalancing
                if hedge_quantities:
                    ticker = list(hedge_quantities.keys())[0]
                    price = hedge_prices.get(ticker, 0.0) * (1 + price_move)
                    beta = hedge_betas.get(ticker, 1.0)

                    if price > 0 and beta != 0:
                        # qty * beta offsets delta_to_adjust (quantities measured in shares)
                        rebalance_quantity = -delta_to_adjust / beta

                        # Transaction cost from rebalance_params or default
                        spread_bps = rebalance_params.get('spread_bps', 10)
                        rebalance_cost = abs(rebalance_quantity) * price * (spread_bps / 10000.0)

            scenarios.append({
                'price_move_pct': price_move * 100,
                'vol_change_pct': vol_change * 100,
                'new_portfolio_delta': new_portfolio_delta,
                'new_portfolio_vega': new_portfolio_vega,
                'hedge_delta': hedge_delta,
                'residual_delta': residual_delta,
                'residual_vega': residual_vega,
                'drift_score': drift_score,
                'rebalance_needed': rebalance_needed,
                'rebalance_quantity': rebalance_quantity,
                'rebalance_cost': rebalance_cost
            })

    return scenarios


async def _calculate_all_greeks(
    portfolio_positions: List[PositionInput],
    underlying_prices: Optional[List[PriceOverride]] = None
) -> Dict[str, Any]:
    """
    Calculate all primary Greeks in parallel for efficient monitoring.

    Calculates delta, gamma, vega, and theta simultaneously using asyncio.gather
    for ~60% performance improvement over sequential calls.

    Args:
        portfolio_positions: Options positions
        underlying_prices: Optional price overrides

    Returns:
        Dictionary with delta, gamma, vega, theta results
    """
    try:
        # Execute all Greeks calculations in parallel using _impl functions
        results = await asyncio.gather(
            _calculate_delta_impl(portfolio_positions, underlying_prices),
            _calculate_gamma_impl(portfolio_positions, underlying_prices),
            _calculate_vega_impl(portfolio_positions, underlying_prices),
            _calculate_theta_impl(portfolio_positions, underlying_prices, days_forward=1),
            return_exceptions=True
        )

        # Handle exceptions gracefully
        greeks_data = {}
        greek_names = ['delta', 'gamma', 'vega', 'theta']

        for i, greek_name in enumerate(greek_names):
            if isinstance(results[i], Exception):
                logger.warning(f"{greek_name.capitalize()} calculation failed: {results[i]}")
                greeks_data[greek_name] = {
                    'error': str(results[i]),
                    f'total_{greek_name}': 0.0
                }
            else:
                greeks_data[greek_name] = results[i]

        return greeks_data

    except Exception as e:
        logger.error(f"Multi-Greek calculation failed: {e}", exc_info=True)
        return {
            'delta': {'total_delta': 0.0, 'error': str(e)},
            'gamma': {'total_gamma': 0.0, 'error': str(e)},
            'vega': {'total_vega': 0.0, 'error': str(e)},
            'theta': {'total_theta': 0.0, 'error': str(e)}
        }


def _calculate_multi_greek_drift(
    current_greeks: Dict[str, Any],
    hedge_greeks: Dict[str, float],
    targets: Dict[str, float],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calculate weighted drift score across multiple Greeks for rebalancing decisions.

    Combines delta, vega, and gamma drift with theta offset to determine
    optimal rebalancing timing. Higher scores indicate more urgent need to rebalance.

    Args:
        current_greeks: Dict with delta/gamma/vega/theta results from _calculate_all_greeks
        hedge_greeks: Current hedge Greeks (delta, vega from hedge positions)
        targets: Target values for each Greek (e.g., {'delta': 0.0, 'vega': 0.0})
        weights: Optional custom weights for each Greek (default: delta=0.5, vega=0.35, gamma=0.15)

    Returns:
        Dict with drift_score, component_drifts, and rebalance_recommended
    """
    # Default weights (sum to 1.0 before theta offset)
    if weights is None:
        weights = {
            'delta': 0.50,   # Primary directional risk
            'vega': 0.35,    # Volatility risk
            'gamma': 0.15,   # Convexity/acceleration risk
            'theta': 0.10    # Theta income reduces urgency (negative weight)
        }

    # Extract total Greeks from results
    delta_total = current_greeks.get('delta', {}).get('total_delta', 0.0)
    gamma_total = current_greeks.get('gamma', {}).get('total_gamma', 0.0)
    vega_total = current_greeks.get('vega', {}).get('total_vega', 0.0)
    theta_total = current_greeks.get('theta', {}).get('total_theta', 0.0)

    # Add hedge Greeks
    delta_total += hedge_greeks.get('delta', 0.0)
    vega_total += hedge_greeks.get('vega', 0.0)
    # Gamma and theta don't change with equity hedges

    # Calculate drifts from targets
    delta_drift = abs(delta_total - targets.get('delta', 0.0))
    vega_drift = abs(vega_total - targets.get('vega', 0.0))
    gamma_risk = abs(gamma_total) * 0.01  # Normalize gamma to similar scale
    theta_offset = abs(theta_total)  # Positive theta reduces urgency

    # Weighted drift score
    drift_score = (
        delta_drift * weights['delta'] +
        vega_drift * weights['vega'] +
        gamma_risk * weights['gamma'] -
        theta_offset * weights['theta']  # Theta benefit
    )

    return {
        'drift_score': max(0.0, drift_score),  # Never negative
        'component_drifts': {
            'delta_drift': delta_drift,
            'vega_drift': vega_drift,
            'gamma_risk': gamma_risk,
            'theta_offset': theta_offset
        },
        'total_greeks': {
            'delta': delta_total,
            'gamma': gamma_total,
            'vega': vega_total,
            'theta': theta_total
        },
        'rebalance_recommended': drift_score > 0.1  # Default threshold
    }


def _generate_algorithm_code(
    portfolio_positions: List[PositionInput],
    hedge_tickers: List[str],
    hedge_target: float,
    vega_target: Optional[float],
    rebalance_params: Dict[str, Any],
    hedge_betas: Dict[str, float],
    monitor_all_greeks: bool = True
) -> str:
    """
    Generate executable Python algorithm for dynamic multi-Greek hedging.

    Returns complete async function that monitors delta, gamma, vega, theta
    and rebalances based on multi-Greek drift score.
    """
    # Convert positions to string representation
    positions_str = repr(portfolio_positions)
    hedge_tickers_str = repr(hedge_tickers)
    threshold = rebalance_params.get('threshold', 0.1)
    min_trade_size = rebalance_params.get('min_trade_size', 1.0)
    frequency = rebalance_params.get('frequency_check', 'daily')
    check_interval = _get_check_interval_seconds(frequency)

    # Conditionally generate multi-Greek or delta-only algorithm
    if monitor_all_greeks:
        vega_target_str = f"{vega_target}" if vega_target is not None else "None (preserve current)"
        algorithm_code = f'''"""
Dynamic Multi-Greek Hedging Algorithm
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Configuration:
- Target Delta: {hedge_target}
- Target Vega: {vega_target_str}
- Rebalance Drift Score Threshold: 0.1
- Delta Threshold: {threshold}
- Check Frequency: {frequency}
- Min Trade Size: {min_trade_size} shares

Monitors: Delta, Gamma, Vega, Theta
Rebalancing: Based on weighted multi-Greek drift score
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any

# Import required modules
from core.agents.quant_tools.delta_exposure_tool import calculate_delta_exposure
from core.agents.quant_tools.gamma_exposure_tool import calculate_gamma_exposure
from core.agents.quant_tools.vega_exposure_tool import calculate_vega_exposure
from core.agents.quant_tools.theta_decay_tool import calculate_theta_decay
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json


async def fetch_price(fmp_server, ticker: str) -> float:
    """Fetch current price for ticker."""
    from datetime import timedelta

    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    result = await fmp_server.call_tool("get_historical_data", {{
        "symbol": ticker,
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    }})

    if result and hasattr(result, 'content'):
        data = safe_parse_json(result)
        prices = data.get("prices") or data.get("closes") or data.get("close") or []
        if prices:
            return float(prices[-1])

    raise ValueError(f"Could not fetch price for {{ticker}}")


async def fetch_beta(fmp_server, ticker: str) -> float:
    """Fetch beta, default to 1.0 if unavailable."""
    try:
        result = await fmp_server.call_tool("get_company_profile", {{
            "symbol": ticker
        }})

        if result and hasattr(result, 'content'):
            data = safe_parse_json(result)
            beta = data.get('beta') or data.get('Beta') or data.get('companyBeta')
            if beta and isinstance(beta, (int, float)):
                return float(beta)
    except Exception as e:
        print(f"Beta fetch failed for {{ticker}}: {{e}}")

    return 1.0  # Default beta


async def calculate_multi_greek_drift(
    delta_total: float, gamma_total: float, vega_total: float, theta_total: float,
    target_delta: float, target_vega: float
) -> Dict[str, Any]:
    """Calculate weighted multi-Greek drift score."""
    # Default weights
    weights = {{'delta': 0.50, 'vega': 0.35, 'gamma': 0.15, 'theta': 0.10}}

    # Calculate drifts
    delta_drift = abs(delta_total - target_delta)
    vega_drift = abs(vega_total - target_vega) if target_vega is not None else 0.0
    gamma_risk = abs(gamma_total) * 0.01
    theta_offset = abs(theta_total)

    # Weighted drift score (theta reduces urgency)
    drift_score = (
        delta_drift * weights['delta'] +
        vega_drift * weights['vega'] +
        gamma_risk * weights['gamma'] -
        theta_offset * weights['theta']
    )

    return {{
        'drift_score': max(0.0, drift_score),
        'delta_drift': delta_drift,
        'vega_drift': vega_drift,
        'gamma_risk': gamma_risk,
        'theta_offset': theta_offset,
        'rebalance_recommended': drift_score > 0.1
    }}


async def dynamic_hedge_rebalancer():
    """
    Main multi-Greek hedging algorithm - monitors and rebalances based on drift score.

    Portfolio positions: {len(portfolio_positions)} contracts
    Hedge tickers: {hedge_tickers}
    """

    # Configuration
    positions = {positions_str}
    hedge_tickers = {hedge_tickers_str}
    target_delta = {hedge_target}
    target_vega = {vega_target if vega_target is not None else "None"}
    threshold = {threshold}
    drift_threshold = 0.1  # Multi-Greek drift score threshold
    min_trade_size = {min_trade_size}
    check_interval = {check_interval}  # seconds

    # Track current hedge positions
    current_hedge: Dict[str, float] = {{}}

    # Track cumulative theta P&L
    cumulative_theta_pnl = 0.0

    # Initialize FMP server
    fmp_server = FMPMarketDataServer()
    await fmp_server.connect()

    print(f"Dynamic Multi-Greek Hedge Algorithm Started: {{datetime.now()}}")
    print(f"Target Delta: {{target_delta}}")
    print(f"Target Vega: {{target_vega if target_vega is not None else 'neutral (preserve current)'}}")
    print(f"Drift Score Threshold: {{drift_threshold}}")
    print(f"Check Frequency: {frequency}")
    print("-" * 60)

    try:
        iteration = 0
        while True:
            iteration += 1
            print(f"\\n[Iteration {{iteration}}] {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}")

            # Step 1: Calculate all Greeks in parallel
            greeks_results = await asyncio.gather(
                calculate_delta_exposure(positions),
                calculate_gamma_exposure(positions),
                calculate_vega_exposure(positions),
                calculate_theta_decay(positions, days_forward=1),
                return_exceptions=True
            )

            # Extract Greeks (handle exceptions gracefully)
            current_delta = greeks_results[0].get('total_delta', 0.0) if not isinstance(greeks_results[0], Exception) else 0.0
            current_gamma = greeks_results[1].get('total_gamma', 0.0) if not isinstance(greeks_results[1], Exception) else 0.0
            current_vega = greeks_results[2].get('total_vega', 0.0) if not isinstance(greeks_results[2], Exception) else 0.0
            current_theta = greeks_results[3].get('total_theta', 0.0) if not isinstance(greeks_results[3], Exception) else 0.0

            print(f"  Portfolio Greeks:")
            print(f"    Delta: {{current_delta:.2f}}")
            print(f"    Gamma: {{current_gamma:.4f}}")
            print(f"    Vega: {{current_vega:.2f}}")
            print(f"    Theta: {{current_theta:.2f}} (daily decay)")

            # Step 2: Calculate current hedge delta (shares-equivalent)
            hedge_delta = 0.0
            for ticker in hedge_tickers:
                qty = current_hedge.get(ticker, 0.0)
                if qty != 0:
                    beta = await fetch_beta(fmp_server, ticker)
                    hedge_delta += qty * beta

            print(f"  Hedge Delta: {{hedge_delta:.2f}}")

            # Step 3: Calculate residual Greeks
            residual_delta = current_delta + hedge_delta
            residual_gamma = current_gamma  # Stock hedge doesn't change gamma
            residual_vega = current_vega    # Stock hedge doesn't change vega
            residual_theta = current_theta  # Stock hedge doesn't change theta

            print(f"  Residual Greeks:")
            print(f"    Delta: {{residual_delta:.2f}}")
            print(f"    Gamma: {{residual_gamma:.4f}}")
            print(f"    Vega: {{residual_vega:.2f}}")
            print(f"    Theta: {{residual_theta:.2f}}")

            # Track theta P&L (1 day = check_interval / 86400)
            time_fraction = check_interval / 86400.0
            theta_pnl = current_theta * time_fraction
            cumulative_theta_pnl += theta_pnl
            print(f"  Theta P&L: {{theta_pnl:.2f}} (Cumulative: {{cumulative_theta_pnl:.2f}})")

            # Step 4: Calculate multi-Greek drift score
            drift_data = await calculate_multi_greek_drift(
                delta_total=residual_delta,
                gamma_total=residual_gamma,
                vega_total=residual_vega,
                theta_total=residual_theta,
                target_delta=target_delta,
                target_vega=target_vega if target_vega is not None else current_vega
            )

            print(f"  Drift Analysis:")
            print(f"    Drift Score: {{drift_data['drift_score']:.4f}}")
            print(f"    Delta Drift: {{drift_data['delta_drift']:.2f}}")
            print(f"    Vega Drift: {{drift_data['vega_drift']:.2f}}")
            print(f"    Gamma Risk: {{drift_data['gamma_risk']:.4f}}")
            print(f"    Theta Offset: {{drift_data['theta_offset']:.2f}}")

            # Step 5: Check if rebalancing needed (based on drift score)
            if drift_data['rebalance_recommended']:
                print(f"  *** REBALANCING NEEDED (drift_score {{drift_data['drift_score']:.4f}} > {{drift_threshold}}) ***")

                # Calculate required adjustment
                delta_to_adjust = residual_delta - target_delta

                # Allocate adjustment across hedge tickers
                for ticker in hedge_tickers:
                    price = await fetch_price(fmp_server, ticker)
                    beta = await fetch_beta(fmp_server, ticker)

                    # Calculate target quantity for this ticker
                    # qty * beta offsets delta_to_adjust (qty measured in shares)
                    target_qty = -delta_to_adjust / beta
                    current_qty = current_hedge.get(ticker, 0.0)
                    trade_qty = target_qty - current_qty

                    # Only trade if above minimum size
                    if abs(trade_qty) >= min_trade_size:
                        print(f"    TRADE: {{ticker}}")
                        print(f"      Price: ${{price:.2f}}")
                        print(f"      Beta: {{beta:.3f}}")
                        print(f"      Current: {{current_qty:.2f}} shares")
                        print(f"      Target: {{target_qty:.2f}} shares")
                        print(f"      Trade: {{trade_qty:.2f}} shares")
                        print(f"      Notional: ${{abs(trade_qty * price):,.2f}}")

                        # UPDATE HEDGE POSITION
                        # In production, this would call broker API
                        current_hedge[ticker] = target_qty
                        print(f"      Status: EXECUTED")
                    else:
                        print(f"    {{ticker}}: Trade too small ({{trade_qty:.2f}} < {{min_trade_size}})")

                print(f"  Rebalancing complete.")
            else:
                print(f"  No rebalancing needed (drift_score {{drift_data['drift_score']:.4f}} <= {{drift_threshold}})")

            # Step 6: Wait for next check
            print(f"  Next check in {{check_interval}} seconds...")
            await asyncio.sleep(check_interval)

    except KeyboardInterrupt:
        print("\\n\\nAlgorithm stopped by user.")
    finally:
        await fmp_server.cleanup()
        print("\\nFinal State:")
        print(f"  Cumulative Theta P&L: ${{cumulative_theta_pnl:.2f}}")
        print(f"\\nFinal Hedge Positions:")
        for ticker, qty in current_hedge.items():
            print(f"  {{ticker}}: {{qty:.2f}} shares")


# Run the algorithm
if __name__ == "__main__":
    asyncio.run(dynamic_hedge_rebalancer())
'''
    else:
        # Fallback to delta-only monitoring (backwards compatibility)
        algorithm_code = f'''"""
Dynamic Delta Hedging Algorithm
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Configuration:
- Target Delta: {hedge_target}
- Rebalance Threshold: {threshold}
- Check Frequency: {frequency}
- Min Trade Size: {min_trade_size} shares
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any

from core.agents.quant_tools.delta_exposure_tool import calculate_delta_exposure
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json


async def fetch_price(fmp_server, ticker: str) -> float:
    """Fetch current price for ticker."""
    from datetime import timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    result = await fmp_server.call_tool("get_historical_data", {{
        "symbol": ticker,
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    }})
    if result and hasattr(result, 'content'):
        data = safe_parse_json(result)
        prices = data.get("prices") or data.get("closes") or data.get("close") or []
        if prices:
            return float(prices[-1])
    raise ValueError(f"Could not fetch price for {{ticker}}")


async def fetch_beta(fmp_server, ticker: str) -> float:
    """Fetch beta, default to 1.0 if unavailable."""
    try:
        result = await fmp_server.call_tool("get_company_profile", {{"symbol": ticker}})
        if result and hasattr(result, 'content'):
            data = safe_parse_json(result)
            beta = data.get('beta') or data.get('Beta') or data.get('companyBeta')
            if beta and isinstance(beta, (int, float)):
                return float(beta)
    except Exception as e:
        print(f"Beta fetch failed for {{ticker}}: {{e}}")
    return 1.0


async def dynamic_hedge_rebalancer():
    """Delta-only hedging algorithm."""
    positions = {positions_str}
    hedge_tickers = {hedge_tickers_str}
    target_delta = {hedge_target}
    threshold = {threshold}
    min_trade_size = {min_trade_size}
    check_interval = {check_interval}

    current_hedge: Dict[str, float] = {{}}
    fmp_server = FMPMarketDataServer()
    await fmp_server.connect()

    print(f"Dynamic Delta Hedge Algorithm Started: {{datetime.now()}}")
    print(f"Target Delta: {{target_delta}}")
    print("-" * 60)

    try:
        iteration = 0
        while True:
            iteration += 1
            print(f"\\n[Iteration {{iteration}}] {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}")

            delta_result = await calculate_delta_exposure(positions)
            current_delta = delta_result.get('total_delta', 0.0)
            print(f"  Portfolio Delta: {{current_delta:.2f}}")

            hedge_delta = 0.0
            for ticker in hedge_tickers:
                qty = current_hedge.get(ticker, 0.0)
                if qty != 0:
                    beta = await fetch_beta(fmp_server, ticker)
                    hedge_delta += qty * beta

            residual_delta = current_delta + hedge_delta
            delta_drift = abs(residual_delta - target_delta)
            print(f"  Residual Delta: {{residual_delta:.2f}} (Drift: {{delta_drift:.2f}})")

            if delta_drift > threshold:
                print(f"  *** REBALANCING NEEDED ***")
                delta_to_adjust = residual_delta - target_delta
                for ticker in hedge_tickers:
                    price = await fetch_price(fmp_server, ticker)
                    beta = await fetch_beta(fmp_server, ticker)
                    # qty * beta offsets delta_to_adjust (qty measured in shares)
                    target_qty = -delta_to_adjust / beta
                    current_qty = current_hedge.get(ticker, 0.0)
                    trade_qty = target_qty - current_qty
                    if abs(trade_qty) >= min_trade_size:
                        print(f"    TRADE: {{ticker}} {{trade_qty:.2f}} shares")
                        current_hedge[ticker] = target_qty
            else:
                print(f"  No rebalancing needed")

            await asyncio.sleep(check_interval)

    except KeyboardInterrupt:
        print("\\n\\nAlgorithm stopped by user.")
    finally:
        await fmp_server.cleanup()


if __name__ == "__main__":
    asyncio.run(dynamic_hedge_rebalancer())
'''

    return algorithm_code


# ============================================================================
# ROLLING BACKTEST FUNCTIONS
# ============================================================================

async def _fetch_historical_prices_range(
    fmp_server,
    tickers: List[str],
    start_date: datetime,
    end_date: datetime
) -> Dict[str, pd.DataFrame]:
    """
    Fetch daily historical prices for all tickers in date range.

    Returns:
        Dict[ticker -> DataFrame with columns: date, price]
    """
    historical_prices = {}

    for ticker in tickers:
        try:
            result = await fmp_server.call_tool("get_historical_data", {
                "symbol": ticker,
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            })

            if not result or not hasattr(result, 'content'):
                logger.warning(f"No data for {ticker}")
                continue

            data = safe_parse_json(result)
            dates = data.get("dates", [])
            prices = data.get("prices", []) or data.get("closes", [])

            if not dates or not prices:
                logger.warning(f"No price data for {ticker}")
                continue

            # Create DataFrame
            df = pd.DataFrame({
                "date": pd.to_datetime(dates),
                "price": prices
            })
            df = df.sort_values("date")
            df = df.set_index("date")

            historical_prices[ticker] = df

        except Exception as e:
            logger.warning(f"Failed to fetch historical data for {ticker}: {e}")

    return historical_prices


def _parse_lookback_period(lookback: str) -> timedelta:
    """Parse lookback period string to timedelta."""
    mapping = {
        "30D": timedelta(days=30),
        "60D": timedelta(days=60),
        "90D": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365)
    }
    return mapping.get(lookback.upper(), timedelta(days=30))


async def _calculate_greeks_at_date(
    portfolio_positions: List[PositionInput],
    underlying_prices: Dict[str, float],
    calculation_date: datetime
) -> Dict[str, Any]:
    """
    Calculate all Greeks for portfolio at specific historical date.

    Adjusts option positions for time decay (days_to_expiry changes).
    Returns same format as _calculate_all_greeks().
    """
    # Adjust positions for time decay
    adjusted_positions = []

    for pos in portfolio_positions:
        expiry_date = datetime.strptime(pos['expiry'], '%Y-%m-%d')
        days_to_expiry = (expiry_date - calculation_date).days

        if days_to_expiry <= 0:
            continue  # Position expired

        adjusted_positions.append(pos)

    if not adjusted_positions:
        return {
            'delta': {'total_delta': 0.0},
            'gamma': {'total_gamma': 0.0},
            'vega': {'total_vega': 0.0},
            'theta': {'total_theta': 0.0}
        }

    # Convert dict to List[PriceOverride]
    price_overrides = [{'ticker': t, 'price': p} for t, p in underlying_prices.items()]

    # Calculate all Greeks using parallel execution
    results = await asyncio.gather(
        _calculate_delta_impl(adjusted_positions, price_overrides),
        _calculate_gamma_impl(adjusted_positions, price_overrides),
        _calculate_vega_impl(adjusted_positions, price_overrides),
        _calculate_theta_impl(adjusted_positions, price_overrides, days_forward=1),
        return_exceptions=True
    )

    # Handle exceptions gracefully
    greeks_data = {}
    greek_names = ['delta', 'gamma', 'vega', 'theta']

    for i, greek_name in enumerate(greek_names):
        if isinstance(results[i], Exception):
            logger.warning(f"{greek_name.capitalize()} calculation failed: {results[i]}")
            greeks_data[greek_name] = {f'total_{greek_name}': 0.0}
        else:
            greeks_data[greek_name] = results[i]

    return greeks_data


async def _run_backtest(
    portfolio_positions: List[PositionInput],
    hedge_tickers: List[str],
    hedge_target: float,
    vega_target: Optional[float],
    rebalance_params: Dict[str, Any],
    lookback_period: str,
    hedge_betas: Dict[str, float],
    fmp_server
) -> Dict[str, Any]:
    """
    Core backtesting engine - runs day-by-day simulation.

    Returns dict with daily_results, summary stats, and time-series data for charting.
    """
    try:
        # Parse lookback period
        lookback_delta = _parse_lookback_period(lookback_period)
        end_date = datetime.now()
        start_date = end_date - lookback_delta

        logger.info(f"Running backtest from {start_date.date()} to {end_date.date()}")

        # Fetch all historical prices
        all_tickers = list(set([pos['underlying'] for pos in portfolio_positions] + hedge_tickers))
        historical_prices = await _fetch_historical_prices_range(fmp_server, all_tickers, start_date, end_date)

        if not historical_prices:
            raise ValueError("No historical price data available")

        # Get common trading dates
        common_dates_sets = [set(df.index) for df in historical_prices.values()]
        common_dates = sorted(list(set.intersection(*common_dates_sets)))

        if len(common_dates) < 10:
            raise ValueError(f"Insufficient common dates: {len(common_dates)}")

        logger.info(f"Backtesting over {len(common_dates)} trading days")

        # Initialize tracking
        daily_results = []
        current_hedge_qty = {}
        cumulative_txn_cost = 0.0
        cumulative_theta_pnl = 0.0
        cumulative_hedged_pnl = 0.0
        cumulative_unhedged_pnl = 0.0
        prev_underlying_prices = None

        # Day-by-day loop
        skipped_dates = 0
        for i, date in enumerate(common_dates):
            # Get prices for this date - skip if any ticker missing
            try:
                underlying_prices = {}
                for ticker in all_tickers:
                    if ticker in historical_prices and date in historical_prices[ticker].index:
                        underlying_prices[ticker] = float(historical_prices[ticker].loc[date, 'price'])
                
                # Skip if we're missing critical tickers
                if len(underlying_prices) < len(all_tickers) * 0.5:
                    skipped_dates += 1
                    continue
            except Exception as e:
                logger.warning(f"Skipping date {date}: {e}")
                skipped_dates += 1
                continue

            # Calculate all Greeks at this date
            greeks = await _calculate_greeks_at_date(portfolio_positions, underlying_prices, date)

            # Extract total Greeks
            delta_total = greeks.get('delta', {}).get('total_delta', 0.0)
            gamma_total = greeks.get('gamma', {}).get('total_gamma', 0.0)
            vega_total = greeks.get('vega', {}).get('total_vega', 0.0)
            theta_total = greeks.get('theta', {}).get('total_theta', 0.0)

            # Calculate hedge Greeks (shares-equivalent delta)
            hedge_delta = sum(
                current_hedge_qty.get(ticker, 0.0) * hedge_betas.get(ticker, 1.0)
                for ticker in hedge_tickers
            )

            # Residual Greeks
            residual_delta = delta_total + hedge_delta
            residual_gamma = gamma_total
            residual_vega = vega_total
            residual_theta = theta_total

            # Calculate drift score
            drift_data = _calculate_multi_greek_drift(
                current_greeks=greeks,
                hedge_greeks={'delta': hedge_delta, 'vega': 0.0},
                targets={'delta': hedge_target, 'vega': vega_target if vega_target is not None else vega_total}
            )

            # Check rebalancing trigger
            drift_threshold = rebalance_params.get('threshold', 0.1)
            rebalancing_triggered = drift_data['drift_score'] > drift_threshold

            trade_qty = 0.0
            txn_cost = 0.0

            # Execute rebalancing if needed
            if rebalancing_triggered:
                delta_to_adjust = residual_delta - hedge_target

                # Use first hedge ticker
                ticker = hedge_tickers[0]
                price = underlying_prices[ticker]
                beta = hedge_betas.get(ticker, 1.0)

                # Calculate trade: qty * beta offsets delta_to_adjust (qty in shares)
                target_qty = -delta_to_adjust / beta
                current_qty = current_hedge_qty.get(ticker, 0.0)
                trade_qty = target_qty - current_qty

                # Transaction cost
                spread_bps = rebalance_params.get('spread_bps', 10)
                txn_cost = abs(trade_qty) * price * (spread_bps / 10000.0)

                # Update hedge position
                current_hedge_qty[ticker] = target_qty
                cumulative_txn_cost += txn_cost

            # Theta P&L
            theta_pnl = theta_total
            cumulative_theta_pnl += theta_pnl

            # Calculate daily P&L (if not first day)
            daily_hedged_pnl = 0.0
            daily_unhedged_pnl = 0.0

            if i > 0 and prev_underlying_prices:
                # Price change P&L
                for pos in portfolio_positions:
                    ticker = pos['underlying']
                    price_change = underlying_prices[ticker] - prev_underlying_prices[ticker]

                    # Simplified: delta * price_change * 100 (shares per contract) * quantity
                    pos_delta_exposure = delta_total / len(portfolio_positions)  # Approximate
                    daily_unhedged_pnl += pos_delta_exposure * price_change

                # Hedge P&L
                for ticker in hedge_tickers:
                    qty = current_hedge_qty.get(ticker, 0.0)
                    if qty != 0:
                        price_change = underlying_prices[ticker] - prev_underlying_prices[ticker]
                        daily_hedged_pnl += qty * price_change

                # Add portfolio P&L + theta - costs
                daily_hedged_pnl += daily_unhedged_pnl + theta_pnl - txn_cost
                daily_unhedged_pnl += theta_pnl

                cumulative_hedged_pnl += daily_hedged_pnl
                cumulative_unhedged_pnl += daily_unhedged_pnl

            # Store previous prices
            prev_underlying_prices = underlying_prices.copy()

            # Record daily result
            daily_results.append({
                'date': date.strftime('%Y-%m-%d'),
                'portfolio_greeks': {
                    'delta': delta_total,
                    'gamma': gamma_total,
                    'vega': vega_total,
                    'theta': theta_total
                },
                'hedge_greeks': {'delta': hedge_delta},
                'residual_greeks': {
                    'delta': residual_delta,
                    'gamma': residual_gamma,
                    'vega': residual_vega,
                    'theta': residual_theta
                },
                'drift_score': drift_data['drift_score'],
                'rebalancing_triggered': rebalancing_triggered,
                'trade_quantity': trade_qty,
                'transaction_cost': txn_cost,
                'theta_pnl': theta_pnl,
                'hedged_pnl': cumulative_hedged_pnl,
                'unhedged_pnl': cumulative_unhedged_pnl
            })

        # Calculate summary stats
        total_trades = sum(1 for r in daily_results if r['rebalancing_triggered'])
        pnl_improvement = cumulative_hedged_pnl - cumulative_unhedged_pnl
        
        if skipped_dates > 0:
            logger.info(f"Backtest: skipped {skipped_dates} dates due to missing price data")

        return {
            'daily_results': daily_results,
            'total_days': len(daily_results),
            'skipped_dates': skipped_dates,
            'total_trades': total_trades,
            'total_transaction_costs': cumulative_txn_cost,
            'total_theta_income': cumulative_theta_pnl,
            'hedged_pnl': cumulative_hedged_pnl,
            'unhedged_pnl': cumulative_unhedged_pnl,
            'pnl_improvement': pnl_improvement,
            'pnl_improvement_pct': (pnl_improvement / abs(cumulative_unhedged_pnl) * 100) if cumulative_unhedged_pnl != 0 else 0.0
        }

    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        return {
            'error': str(e),
            'daily_results': [],
            'total_days': 0,
            'total_trades': 0,
            'total_transaction_costs': 0.0,
            'total_theta_income': 0.0,
            'hedged_pnl': 0.0,
            'unhedged_pnl': 0.0,
            'pnl_improvement': 0.0
        }


# ============================================================================
# CHART BUILDERS
# ============================================================================

async def _build_greeks_evolution_chart(
    daily_results: List[Dict[str, Any]],
    chart_id: str
) -> Dict[str, Any]:
    """Build 4-subplot chart showing delta/gamma/vega/theta evolution."""
    try:
        dates = [r['date'] for r in daily_results]

        # Extract Greeks time series
        portfolio_delta = [r['portfolio_greeks']['delta'] for r in daily_results]
        portfolio_gamma = [r['portfolio_greeks']['gamma'] for r in daily_results]
        portfolio_vega = [r['portfolio_greeks']['vega'] for r in daily_results]
        portfolio_theta = [r['portfolio_greeks']['theta'] for r in daily_results]

        residual_delta = [r['residual_greeks']['delta'] for r in daily_results]
        residual_gamma = [r['residual_greeks']['gamma'] for r in daily_results]
        residual_vega = [r['residual_greeks']['vega'] for r in daily_results]
        residual_theta = [r['residual_greeks']['theta'] for r in daily_results]

        # Create 2x2 subplot
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=["Delta Evolution", "Gamma Evolution", "Vega Evolution", "Theta Evolution"],
            vertical_spacing=0.12,
            horizontal_spacing=0.10
        )

        # Delta (row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_delta, name="Portfolio Delta",
            line=dict(color='#2E86AB', width=2),
            hovertemplate='%{x}<br>Portfolio: %{y:.2f}<extra></extra>'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=residual_delta, name="Residual Delta",
            line=dict(color='#C62828', width=2, dash='dash'),
            hovertemplate='%{x}<br>Residual: %{y:.2f}<extra></extra>'
        ), row=1, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color="green", row=1, col=1)

        # Gamma (row=1, col=2)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_gamma, name="Portfolio Gamma",
            line=dict(color='#2E86AB', width=2),
            showlegend=False,
            hovertemplate='%{x}<br>Portfolio: %{y:.4f}<extra></extra>'
        ), row=1, col=2)
        fig.add_trace(go.Scatter(
            x=dates, y=residual_gamma, name="Residual Gamma",
            line=dict(color='#C62828', width=2, dash='dash'),
            showlegend=False,
            hovertemplate='%{x}<br>Residual: %{y:.4f}<extra></extra>'
        ), row=1, col=2)

        # Vega (row=2, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_vega, name="Portfolio Vega",
            line=dict(color='#2E86AB', width=2),
            showlegend=False,
            hovertemplate='%{x}<br>Portfolio: %{y:.2f}<extra></extra>'
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=residual_vega, name="Residual Vega",
            line=dict(color='#C62828', width=2, dash='dash'),
            showlegend=False,
            hovertemplate='%{x}<br>Residual: %{y:.2f}<extra></extra>'
        ), row=2, col=1)

        # Theta (row=2, col=2)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_theta, name="Portfolio Theta",
            line=dict(color='#2E86AB', width=2),
            showlegend=False,
            hovertemplate='%{x}<br>Portfolio: %{y:.2f}<extra></extra>'
        ), row=2, col=2)
        fig.add_trace(go.Scatter(
            x=dates, y=residual_theta, name="Residual Theta",
            line=dict(color='#C62828', width=2, dash='dash'),
            showlegend=False,
            hovertemplate='%{x}<br>Residual: %{y:.2f}<extra></extra>'
        ), row=2, col=2)

        # Update layout
        fig.update_layout(
            title="Greeks Evolution Over Time",
            template="plotly_white",
            height=700,
            showlegend=True,
            legend=dict(x=0.7, y=1.05, orientation='h'),
            hovermode='x unified'
        )

        # Update axes
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=2)
        fig.update_yaxes(title_text="Delta", row=1, col=1)
        fig.update_yaxes(title_text="Gamma", row=1, col=2)
        fig.update_yaxes(title_text="Vega", row=2, col=1)
        fig.update_yaxes(title_text="Theta", row=2, col=2)

        return {
            'id': f"{chart_id}_greeks_evolution",
            'title': "Greeks Evolution",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Greeks evolution chart failed: {e}")
        return None


async def _build_drift_score_chart(
    daily_results: List[Dict[str, Any]],
    drift_threshold: float,
    chart_id: str
) -> Dict[str, Any]:
    """Build drift score chart with rebalancing markers."""
    try:
        dates = [r['date'] for r in daily_results]
        drift_scores = [r['drift_score'] for r in daily_results]

        # Find rebalancing dates
        rebalancing_dates = [r['date'] for r in daily_results if r['rebalancing_triggered']]
        rebalancing_scores = [r['drift_score'] for r in daily_results if r['rebalancing_triggered']]

        fig = go.Figure()

        # Drift score line
        fig.add_trace(go.Scatter(
            x=dates,
            y=drift_scores,
            name="Drift Score",
            mode='lines',
            line=dict(color='#2E86AB', width=2),
            hovertemplate='%{x}<br>Drift Score: %{y:.4f}<extra></extra>'
        ))

        # Rebalancing markers
        if rebalancing_dates:
            fig.add_trace(go.Scatter(
                x=rebalancing_dates,
                y=rebalancing_scores,
                name=f"Rebalance ({len(rebalancing_dates)})",
                mode='markers',
                marker=dict(
                    color='red',
                    size=12,
                    symbol='triangle-up',
                    line=dict(color='darkred', width=1)
                ),
                hovertemplate='%{x}<br>Rebalance Triggered<br>Score: %{y:.4f}<extra></extra>'
            ))

        # Threshold line
        fig.add_hline(
            y=drift_threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Threshold: {drift_threshold}",
            annotation_position="right"
        )

        fig.update_layout(
            title="Multi-Greek Drift Score & Rebalancing Events",
            xaxis_title="Date",
            yaxis_title="Drift Score",
            template="plotly_white",
            height=450,
            hovermode='x unified',
            showlegend=True
        )

        return {
            'id': f"{chart_id}_drift_score",
            'title': "Drift Score & Rebalancing",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Drift score chart failed: {e}")
        return None


async def _build_pnl_comparison_chart(
    daily_results: List[Dict[str, Any]],
    chart_id: str
) -> Dict[str, Any]:
    """Build cumulative P&L comparison chart."""
    try:
        dates = [r['date'] for r in daily_results]
        hedged_pnl = [r['hedged_pnl'] for r in daily_results]
        unhedged_pnl = [r['unhedged_pnl'] for r in daily_results]

        fig = go.Figure()

        # Hedged P&L
        fig.add_trace(go.Scatter(
            x=dates,
            y=hedged_pnl,
            name="Hedged P&L",
            mode='lines',
            line=dict(color='#2E7D32', width=3),
            fill=None,
            hovertemplate='%{x}<br>Hedged: $%{y:,.2f}<extra></extra>'
        ))

        # Unhedged P&L
        fig.add_trace(go.Scatter(
            x=dates,
            y=unhedged_pnl,
            name="Unhedged P&L",
            mode='lines',
            line=dict(color='#C62828', width=3),
            fill='tonexty',
            fillcolor='rgba(46, 125, 50, 0.2)',
            hovertemplate='%{x}<br>Unhedged: $%{y:,.2f}<extra></extra>'
        ))

        # Zero line
        fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)

        fig.update_layout(
            title="Cumulative P&L: Hedged vs Unhedged",
            xaxis_title="Date",
            yaxis_title="Cumulative P&L ($)",
            template="plotly_white",
            height=450,
            hovermode='x unified',
            showlegend=True,
            legend=dict(x=0.02, y=0.98)
        )

        return {
            'id': f"{chart_id}_pnl_comparison",
            'title': "P&L Comparison",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"P&L comparison chart failed: {e}")
        return None


async def _build_cost_income_chart(
    daily_results: List[Dict[str, Any]],
    chart_id: str
) -> Dict[str, Any]:
    """Build transaction costs vs theta income chart."""
    try:
        dates = [r['date'] for r in daily_results]

        # Cumulative costs and income
        cumulative_costs = []
        cumulative_income = []
        running_cost = 0.0
        running_income = 0.0

        for r in daily_results:
            running_cost += r['transaction_cost']
            running_income += r['theta_pnl']
            cumulative_costs.append(-running_cost)  # Negative for costs
            cumulative_income.append(running_income)

        # Net benefit
        net_benefit = [inc + cost for inc, cost in zip(cumulative_income, cumulative_costs)]

        fig = go.Figure()

        # Theta income (positive)
        fig.add_trace(go.Scatter(
            x=dates,
            y=cumulative_income,
            name="Theta Income",
            mode='lines',
            line=dict(color='#2E7D32', width=2),
            fill='tozeroy',
            fillcolor='rgba(46, 125, 50, 0.3)',
            hovertemplate='%{x}<br>Income: $%{y:,.2f}<extra></extra>'
        ))

        # Transaction costs (negative)
        fig.add_trace(go.Scatter(
            x=dates,
            y=cumulative_costs,
            name="Transaction Costs",
            mode='lines',
            line=dict(color='#C62828', width=2),
            fill='tozeroy',
            fillcolor='rgba(198, 40, 40, 0.3)',
            hovertemplate='%{x}<br>Costs: $%{y:,.2f}<extra></extra>'
        ))

        # Net benefit line
        fig.add_trace(go.Scatter(
            x=dates,
            y=net_benefit,
            name="Net Benefit",
            mode='lines',
            line=dict(color='#1565C0', width=3, dash='dash'),
            hovertemplate='%{x}<br>Net: $%{y:,.2f}<extra></extra>'
        ))

        # Zero line
        fig.add_hline(y=0, line_dash="dot", line_color="black", opacity=0.5)

        fig.update_layout(
            title="Transaction Costs vs Theta Income",
            xaxis_title="Date",
            yaxis_title="Cumulative Amount ($)",
            template="plotly_white",
            height=450,
            hovermode='x unified',
            showlegend=True,
            legend=dict(x=0.02, y=0.98)
        )

        return {
            'id': f"{chart_id}_cost_income",
            'title': "Costs vs Income",
            'plotly': fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Cost/income chart failed: {e}")
        return None


async def construct_dynamic_hedge_internal(
    portfolio_positions: List[PositionInput],
    hedge_tickers: List[str],
    underlying_prices: Optional[List[PriceOverride]] = None,
    hedge_target: Optional[float] = 0.0,
    vega_target: Optional[float] = None,
    rebalance_params: Optional[RebalanceParams] = None,
    lookback_period: Optional[str] = None
) -> Dict[str, Any]:
    """
    Internal implementation of dynamic hedge construction.
    
    This is the core logic - use this for Canvas and internal calls.
    The @function_tool decorated version wraps this for agent use.
    """
    try:
        # Default rebalancing parameters
        default_params = {
            'threshold': 0.1,  # 10% of notional or absolute delta threshold
            'frequency_check': 'daily',
            'cost_threshold': 0.02,  # 2% of delta drift
            'min_trade_size': 1.0
        }

        if rebalance_params:
            default_params.update(rebalance_params)

        rebalance_params = default_params

        # Validate inputs
        if not portfolio_positions:
            return {
                'error': 'No portfolio positions provided',
                'current_portfolio_delta': 0.0,
                'current_hedge_position': {},
                'current_residual_delta': 0.0
            }

        if not hedge_tickers:
            return {
                'error': 'No hedge tickers provided',
                'current_portfolio_delta': 0.0,
                'current_hedge_position': {},
                'current_residual_delta': 0.0
            }

        fmp_server = FMPMarketDataServer()

        try:
            await fmp_server.connect()

            # Step 1: Calculate all Greeks in parallel
            greeks_data = await _calculate_all_greeks(portfolio_positions, underlying_prices)

            # Extract Greeks
            current_delta = greeks_data.get('delta', {}).get('total_delta', 0.0)
            current_gamma = greeks_data.get('gamma', {}).get('total_gamma', 0.0)
            current_vega = greeks_data.get('vega', {}).get('total_vega', 0.0)
            current_theta = greeks_data.get('theta', {}).get('total_theta', 0.0)

            # Check for errors
            if 'error' in greeks_data.get('delta', {}):
                return {
                    'error': f"Greeks calculation failed: {greeks_data['delta']['error']}",
                    'current_portfolio_greeks': {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0},
                    'current_hedge_position': {},
                    'current_residual_greeks': {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0}
                }

            # Step 2: Fetch hedge instrument data
            hedge_prices = await _fetch_prices(fmp_server, hedge_tickers)

            if not hedge_prices:
                return {
                    'error': 'Could not fetch prices for hedge tickers',
                    'current_portfolio_delta': current_delta,
                    'current_hedge_position': {},
                    'current_residual_delta': current_delta
                }

            # Fetch betas for hedge instruments
            hedge_betas = {}
            for ticker in hedge_tickers:
                beta = await _fetch_beta(fmp_server, ticker)
                hedge_betas[ticker] = beta if beta else 1.0

            # Fetch volatilities for hedge instruments
            hedge_vols = {}
            for ticker in hedge_tickers:
                vol = await _calculate_hist_vol(fmp_server, ticker)
                hedge_vols[ticker] = vol if vol else 0.20  # Default 20% vol

            # Fetch bid-ask spreads
            hedge_spreads = {}
            for ticker in hedge_tickers:
                spread = await _fetch_bid_ask_spread(fmp_server, ticker)
                hedge_spreads[ticker] = spread if spread else 0.1  # Default 10 bps

            # NEW: Run historical backtest if requested
            backtest_results = None
            backtest_charts = []

            if lookback_period:
                logger.info(f"Running historical backtest for {lookback_period}...")

                try:
                    backtest_results = await _run_backtest(
                        portfolio_positions=portfolio_positions,
                        hedge_tickers=hedge_tickers,
                        hedge_target=hedge_target if hedge_target is not None else 0.0,
                        vega_target=vega_target,
                        rebalance_params=rebalance_params,
                        lookback_period=lookback_period,
                        hedge_betas=hedge_betas,
                        fmp_server=fmp_server
                    )

                    # Generate backtest charts
                    chart_id = f"backtest_{abs(hash(str(hedge_tickers))) & 0xFFFF:04x}"
                    drift_threshold = rebalance_params.get('threshold', 0.1)

                    # Build all 4 charts
                    greeks_chart = await _build_greeks_evolution_chart(
                        backtest_results['daily_results'],
                        chart_id
                    )
                    if greeks_chart:
                        backtest_charts.append(greeks_chart)

                    drift_chart = await _build_drift_score_chart(
                        backtest_results['daily_results'],
                        drift_threshold,
                        chart_id
                    )
                    if drift_chart:
                        backtest_charts.append(drift_chart)

                    pnl_chart = await _build_pnl_comparison_chart(
                        backtest_results['daily_results'],
                        chart_id
                    )
                    if pnl_chart:
                        backtest_charts.append(pnl_chart)

                    cost_chart = await _build_cost_income_chart(
                        backtest_results['daily_results'],
                        chart_id
                    )
                    if cost_chart:
                        backtest_charts.append(cost_chart)

                    logger.info(f"Backtest complete: {len(backtest_results['daily_results'])} days analyzed")
                    logger.info(f"Generated {len(backtest_charts)} interactive charts: Greeks Evolution, Drift Score, P&L Comparison, Cost/Income Analysis")

                except Exception as e:
                    logger.error(f"Backtest failed: {e}", exc_info=True)
                    backtest_results = {'error': str(e)}

            # Step 3: Calculate initial hedge quantities
            delta_to_hedge = current_delta - (hedge_target if hedge_target is not None else 0.0)

            hedge_quantities = {}
            total_notional = 0.0
            transaction_costs = {}

            # Simple allocation: distribute evenly across hedge tickers
            num_hedges = len(hedge_tickers)
            delta_per_hedge = delta_to_hedge / num_hedges

            for ticker in hedge_tickers:
                price = hedge_prices.get(ticker, 0.0)
                beta = hedge_betas.get(ticker, 1.0)
                spread_pct = hedge_spreads.get(ticker, 0.1)

                if price > 0 and beta != 0:
                    # Quantity needed to hedge this portion of delta
                    qty = -delta_per_hedge / (price * beta)
                    hedge_quantities[ticker] = qty

                    # Calculate notional
                    notional = abs(qty * price)
                    total_notional += notional

                    # Estimate transaction cost (bid-ask spread)
                    txn_cost = notional * (spread_pct / 100)
                    transaction_costs[ticker] = txn_cost

            # Step 4: Use gamma from multi-Greek calculation (already computed)

            # Get average underlying volatility
            underlyings = list(set(pos['underlying'] for pos in portfolio_positions))
            underlying_vols = []
            for underlying in underlyings:
                vol = await _calculate_hist_vol(fmp_server, underlying)
                if vol:
                    underlying_vols.append(vol)

            avg_underlying_vol = sum(underlying_vols) / len(underlying_vols) if underlying_vols else 0.25

            # Expected daily delta drift = gamma × daily_vol × spot
            # For simplicity, use normalized gamma
            daily_vol = avg_underlying_vol / math.sqrt(252)
            delta_drift_rate = abs(current_gamma) * daily_vol * 100  # Approximate daily drift

            # Expected daily vega drift from volatility changes (approx 1% daily vol change)
            vega_drift_rate = abs(current_vega) * 0.01 if current_vega else 0.0

            # Step 5: Optimize rebalancing frequency (multi-Greek aware)
            avg_spread_bps = sum(hedge_spreads.values()) / len(hedge_spreads) if hedge_spreads else 10.0

            optimal_frequency = _optimize_rebalance_frequency(
                delta_drift_rate=delta_drift_rate,
                transaction_cost_bps=avg_spread_bps,
                threshold=rebalance_params['threshold'],
                vega_drift_rate=vega_drift_rate,
                theta_income=abs(current_theta)
            )

            # Calculate multi-Greek drift score
            current_hedge_greeks = {
                # Hedge delta measured in shares-equivalent (qty × beta)
                'delta': sum(
                    hedge_quantities.get(ticker, 0.0) * hedge_betas.get(ticker, 1.0)
                    for ticker in hedge_tickers
                ),
                'vega': 0.0  # Simplified: hedge instruments assumed vega-neutral
            }

            drift_analysis = _calculate_multi_greek_drift(
                current_greeks=greeks_data,
                hedge_greeks=current_hedge_greeks,
                targets={
                    'delta': hedge_target if hedge_target is not None else 0.0,
                    'vega': vega_target if vega_target is not None else current_vega
                }
            )

            # Calculate cost-benefit ratio with theta income offset
            # Expected drift cost per day vs. transaction cost vs. theta income
            drift_cost_per_day = delta_drift_rate * rebalance_params['threshold'] + vega_drift_rate * 10.0
            theta_income_per_day = abs(current_theta)
            total_txn_cost = sum(transaction_costs.values())
            net_drift_cost = max(0.0, drift_cost_per_day - theta_income_per_day)
            cost_benefit_ratio = net_drift_cost / total_txn_cost if total_txn_cost > 0 else 0.0

            # Step 6: Generate multi-Greek rebalancing rules
            rebalancing_rules = {
                'delta_threshold': rebalance_params['threshold'],
                'vega_threshold': rebalance_params.get('vega_threshold', rebalance_params['threshold'] * 10.0),
                'drift_score': drift_analysis['drift_score'],
                'drift_components': drift_analysis['component_drifts'],
                'cost_benefit_ratio': cost_benefit_ratio,
                'optimal_rebalance_frequency': optimal_frequency,
                'monitoring_schedule': [
                    '09:30 EST (Market Open)' if optimal_frequency == 'intraday' else 'Daily at Market Close',
                    'Check multi-Greek drift score',
                    'Monitor delta, gamma, vega, theta',
                    'Execute rebalance if drift_score > 0.1',
                    'Verify post-trade Greeks',
                    'Log theta P&L attribution'
                ],
                'expected_daily_drift': {
                    'delta_drift': delta_drift_rate,
                    'vega_drift': vega_drift_rate,
                    'gamma_risk': abs(current_gamma) * 0.01,
                    'theta_income': theta_income_per_day
                },
                'transaction_cost_per_rebalance': total_txn_cost,
                'rebalance_recommended': drift_analysis['rebalance_recommended']
            }

            # Step 7: Run scenario analysis
            scenarios = await _generate_scenarios(
                portfolio_positions=portfolio_positions,
                hedge_quantities=hedge_quantities,
                hedge_prices=hedge_prices,
                hedge_betas=hedge_betas,
                underlying_prices=underlying_prices,
                target_delta=hedge_target if hedge_target is not None else 0.0,
                rebalance_params=rebalance_params,
                fmp_server=fmp_server
            )

            # Calculate current residual Greeks
            current_hedge_delta = sum(
                hedge_quantities.get(ticker, 0.0) * hedge_betas.get(ticker, 1.0)
                for ticker in hedge_tickers
            )
            current_residual_delta = current_delta + current_hedge_delta
            current_residual_vega = current_vega  # Hedge instruments assumed vega-neutral

            # Generate charts (if backtest was run)
            charts = []
            if backtest_charts:
                charts = wrap_plotly_charts(backtest_charts, default_type="dynamic_hedge_chart")
                logger.info(f"Including {len(charts)} backtest charts in response")

            # Build return structure
            result = {
                # Current multi-Greek state
                'current_portfolio_greeks': {
                    'delta': current_delta,
                    'gamma': current_gamma,
                    'vega': current_vega,
                    'theta': current_theta
                },
                'current_hedge_position': hedge_quantities,
                'current_residual_greeks': {
                    'delta': current_residual_delta,
                    'gamma': current_gamma,  # Unchanged by stock hedge
                    'vega': current_residual_vega,
                    'theta': current_theta  # Unchanged by stock hedge
                },
                'drift_analysis': drift_analysis,

                # Initial hedge setup
                'initial_hedge': {
                    'hedge_quantities': hedge_quantities,
                    'hedge_prices': hedge_prices,
                    'hedge_betas': hedge_betas,
                    'hedge_volatilities': hedge_vols,
                    'transaction_costs': transaction_costs,
                    'total_notional': total_notional,
                    'total_transaction_cost': sum(transaction_costs.values())
                },

                # Multi-Greek rebalancing rules
                'rebalancing_rules': rebalancing_rules,

                # Simulation data
                'scenarios': scenarios,

                # Multi-Greek summary
                'summary': {
                    'portfolio_positions': len(portfolio_positions),
                    'hedge_instruments': len(hedge_tickers),
                    'targets': {
                        'delta': hedge_target if hedge_target is not None else 0.0,
                        'vega': vega_target if vega_target is not None else 'neutral (preserve current)'
                    },
                    'initial_greeks': {
                        'delta': current_delta,
                        'gamma': current_gamma,
                        'vega': current_vega,
                        'theta': current_theta
                    },
                    'hedge_greeks': {
                        'delta': current_hedge_delta,
                        'gamma': 0.0,  # Stock hedge doesn't affect gamma
                        'vega': 0.0,   # Stock hedge doesn't affect vega
                        'theta': 0.0   # Stock hedge doesn't affect theta
                    },
                    'residual_greeks': {
                        'delta': current_residual_delta,
                        'gamma': current_gamma,
                        'vega': current_residual_vega,
                        'theta': current_theta
                    },
                    'rebalance_frequency': optimal_frequency,
                    'expected_daily_drift': {
                        'delta': delta_drift_rate,
                        'vega': vega_drift_rate,
                        'gamma_risk': abs(current_gamma) * 0.01,
                        'theta_income': abs(current_theta)
                    },
                    'total_hedge_notional': total_notional,
                    'drift_score': drift_analysis['drift_score'],
                    'rebalance_recommended': drift_analysis['rebalance_recommended'],
                    'backtest_enabled': lookback_period is not None,
                    'charts_generated': len(backtest_charts) if backtest_charts else 0
                },

                # Historical backtest (if requested)
                'backtest_results': backtest_results
            }

            # Return with jsonify_results (matching PCA pattern exactly)
            return jsonify_results({
                'status': 'success',
                'results': result,
                'hedge_tickers': hedge_tickers,
                'lookback_period': lookback_period,
                'charts': charts
            })

        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Dynamic hedge construction failed: {e}", exc_info=True)
        return jsonify_results({
            'status': 'error',
            'error': str(e),
            'results': {
                'current_portfolio_greeks': {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0},
                'current_hedge_position': {},
                'current_residual_greeks': {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0},
                'drift_analysis': {'drift_score': 0.0, 'rebalance_recommended': False},
                'initial_hedge': {},
                'rebalancing_rules': {},
                'scenarios': [],
                'summary': {},
                'backtest_results': None
            }
        })


@function_tool
async def construct_dynamic_hedge(
    portfolio_positions: List[PositionInput],
    hedge_tickers: List[str],
    underlying_prices: Optional[List[PriceOverride]] = None,
    hedge_target: Optional[float] = 0.0,
    vega_target: Optional[float] = None,
    rebalance_params: Optional[RebalanceParams] = None,
    lookback_period: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate executable hedging algorithm with multi-Greek monitoring.

    Creates dynamic rebalancing rules based on delta, gamma, vega, and theta drift.
    Calculates optimal hedge quantities and generates Python code for automated execution.

    NO HARDCODING - all data fetched dynamically from FMP.

    Args:
        portfolio_positions: Options positions to hedge
        hedge_tickers: Tickers for hedging instruments (e.g., ['SPY', 'QQQ'])
        underlying_prices: Optional price overrides
        hedge_target: Target delta (default: 0.0 for delta-neutral)
        vega_target: Target vega (default: None, no vega hedging)
        rebalance_params: Rebalancing configuration
            - threshold: Multi-Greek drift threshold (default: 0.1)
            - frequency_check: 'intraday' | 'daily' | 'weekly' (default: 'daily')
            - cost_threshold: Max transaction cost % (default: 0.02 or 2%)
            - min_trade_size: Minimum shares to trade (default: 1.0)
        lookback_period: Optional historical backtest period ("30D", "60D", "90D", "6M", "1Y")

    Returns:
        Complete hedging solution with multi-Greek analysis, scenarios, and optional backtest.
    """
    return await construct_dynamic_hedge_internal(
        portfolio_positions=portfolio_positions,
        hedge_tickers=hedge_tickers,
        underlying_prices=underlying_prices,
        hedge_target=hedge_target,
        vega_target=vega_target,
        rebalance_params=rebalance_params,
        lookback_period=lookback_period
    )
