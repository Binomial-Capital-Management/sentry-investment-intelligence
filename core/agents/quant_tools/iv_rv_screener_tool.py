"""
IV/RV Peer Comparison Tool

Analyzes a target ticker's implied volatility vs realized volatility
and ranks it against a peer group provided by the agent.

Key Metrics:
- IV/RV Ratio: > 1.0 means options are pricing more vol than realized
- Peer Percentile: Where target ranks vs comparable stocks
- Relative Signal: Is vol cheap/expensive vs peers?

Alpha Edge:
- Cheap vol vs peers → consider buying vol (straddles, calendars)
- Rich vol vs peers → consider selling vol (strangles, condors)
- Pair trades: Long cheap vol / short rich vol within peer group
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from agents import function_tool

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.options_chain_helpers import fetch_options_chain_simple

logger = logging.getLogger(__name__)


# =============================================================================
# DATA FETCHING
# =============================================================================

async def _fetch_price_history(fmp_server, ticker: str, days: int = 60) -> Optional[List[float]]:
    """Fetch historical prices for realized vol calculation."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 15)  # Buffer for weekends

        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })

        if not result or not hasattr(result, 'content'):
            return None

        data = safe_parse_json(result)
        prices = data.get("prices") or data.get("closes") or data.get("close") or []

        if not prices or len(prices) < 10:
            return None

        return [float(p) for p in prices if p]

    except Exception as e:
        logger.warning(f"Failed to fetch price history for {ticker}: {e}")
        return None


def _compute_realized_vol(prices: List[float], window: int) -> Optional[float]:
    """
    Compute annualized realized volatility from price series.
    
    Returns annualized vol as decimal (e.g., 0.25 for 25%).
    """
    if not prices or len(prices) < window + 1:
        return None

    try:
        recent_prices = prices[-(window + 1):]

        log_returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i-1] > 0 and recent_prices[i] > 0:
                log_returns.append(math.log(recent_prices[i] / recent_prices[i-1]))

        if len(log_returns) < 5:
            return None

        daily_vol = np.std(log_returns, ddof=1)
        annual_vol = daily_vol * math.sqrt(252)

        return float(annual_vol)

    except Exception:
        return None


async def _fetch_spot_price(fmp_server, ticker: str) -> Optional[float]:
    """Get current spot price."""
    try:
        prices = await _fetch_price_history(fmp_server, ticker, days=5)
        if prices:
            return prices[-1]
        return None
    except Exception:
        return None


async def _extract_atm_iv(
    polygon_server,
    ticker: str,
    spot_price: float,
    min_dte: int = 7,
    max_dte: int = 45
) -> Optional[float]:
    """
    Extract ATM implied volatility from options chain.
    
    Uses options in the specified DTE range and averages IV of
    contracts with moneyness between 0.95 and 1.05.
    """
    try:
        contracts = await fetch_options_chain_simple(
            polygon_server,
            ticker,
            min_dte=min_dte,
            max_dte=max_dte,
            limit=250
        )
        
        if not contracts:
            logger.warning(f"No options contracts for {ticker}")
            return None
        
        # Filter to ATM (moneyness 0.95-1.05)
        atm_ivs = []
        
        for contract in contracts:
            details = contract.get('details', {})
            strike = details.get('strike_price')
            iv = contract.get('implied_volatility')
            
            if not strike or not iv:
                continue
            
            strike = float(strike)
            iv = float(iv)
            
            # Check moneyness
            moneyness = strike / spot_price
            if 0.95 <= moneyness <= 1.05 and iv > 0.01:
                atm_ivs.append(iv)
        
        if not atm_ivs:
            # Fallback: use median IV of all contracts
            all_ivs = [
                float(c.get('implied_volatility', 0)) 
                for c in contracts 
                if c.get('implied_volatility') and float(c.get('implied_volatility', 0)) > 0.01
            ]
            if all_ivs:
                return float(np.median(all_ivs))
            return None
        
        return float(np.median(atm_ivs))
        
    except Exception as e:
        logger.warning(f"Failed to extract ATM IV for {ticker}: {e}")
        return None


# =============================================================================
# ANALYSIS
# =============================================================================

async def _analyze_single_ticker(
    fmp_server,
    polygon_server,
    ticker: str,
    rv_window: int,
    min_dte: int = 7,
    max_dte: int = 45
) -> Optional[Dict[str, Any]]:
    """Analyze IV/RV for a single ticker. Signal computed later relative to peers."""
    try:
        # Get prices and spot
        prices = await _fetch_price_history(fmp_server, ticker, days=rv_window + 30)
        if not prices:
            return None
        
        spot = prices[-1]
        
        # Compute realized vol
        rv = _compute_realized_vol(prices, rv_window)
        if rv is None or rv < 0.01:
            return None
        
        # Get ATM IV with configurable DTE
        iv = await _extract_atm_iv(polygon_server, ticker, spot, min_dte, max_dte)
        if iv is None or iv < 0.01:
            return None
        
        # Compute ratio (signal determined later relative to peer group)
        iv_rv_ratio = iv / rv
        
        return {
            "ticker": ticker,
            "spot_price": round(spot, 2),
            "atm_iv": round(iv, 4),
            "rv": round(rv, 4),
            "iv_rv_ratio": round(iv_rv_ratio, 3),
            "vol_premium_pct": round((iv_rv_ratio - 1) * 100, 1)
            # signal computed in _rank_results based on peer distribution
        }
        
    except Exception as e:
        logger.warning(f"Failed to analyze {ticker}: {e}")
        return None


def _rank_results(
    target_data: Dict[str, Any],
    peer_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Rank target against peers using statistical measures.
    
    Signals are determined by:
    - Z-score: How many standard deviations from peer mean
    - Percentile: Where target ranks in the distribution
    
    No hardcoded thresholds - everything is relative to THIS peer group.
    """
    # Combine all for ranking
    all_data = [target_data] + peer_data
    all_ratios = [d['iv_rv_ratio'] for d in all_data]
    
    # Sort by IV/RV ratio (highest first = richest vol)
    sorted_data = sorted(all_data, key=lambda x: x['iv_rv_ratio'], reverse=True)
    
    # Assign ranks and signals based on peer distribution
    peer_ratios = [p['iv_rv_ratio'] for p in peer_data]
    
    if peer_ratios:
        peer_mean = float(np.mean(peer_ratios))
        peer_median = float(np.median(peer_ratios))
        peer_std = float(np.std(peer_ratios, ddof=1)) if len(peer_ratios) > 1 else peer_mean * 0.1
        peer_25th = float(np.percentile(peer_ratios, 25))
        peer_75th = float(np.percentile(peer_ratios, 75))
    else:
        peer_mean = peer_median = target_data['iv_rv_ratio']
        peer_std = peer_mean * 0.1
        peer_25th = peer_75th = peer_median
    
    target_ratio = target_data['iv_rv_ratio']
    
    # Z-score: how many std devs from peer mean
    z_score = (target_ratio - peer_mean) / peer_std if peer_std > 0.001 else 0
    
    # Assign ranks
    for i, item in enumerate(sorted_data):
        item['rank'] = i + 1
        item_ratio = item['iv_rv_ratio']
        item_z = (item_ratio - peer_mean) / peer_std if peer_std > 0.001 else 0
        
        # Signal based on z-score (relative to THIS peer group)
        if item_z > 1.0:
            item['signal'] = "RICH"      # >1 std dev above mean
        elif item_z < -1.0:
            item['signal'] = "CHEAP"     # >1 std dev below mean
        elif item_z > 0.5:
            item['signal'] = "SLIGHTLY_RICH"
        elif item_z < -0.5:
            item['signal'] = "SLIGHTLY_CHEAP"
        else:
            item['signal'] = "FAIR"
        
        item['z_score'] = round(item_z, 2)
    
    # Copy signal back to target_data
    target_data['signal'] = next(
        (item['signal'] for item in sorted_data if item['ticker'] == target_data['ticker']),
        "FAIR"
    )
    target_data['z_score'] = round(z_score, 2)
    
    # Find target's rank
    target_rank = next(
        (item['rank'] for item in sorted_data if item['ticker'] == target_data['ticker']),
        len(sorted_data)
    )
    
    # Compute percentile (0 = cheapest, 100 = richest)
    n = len(sorted_data)
    percentile = round((1 - (target_rank - 1) / max(n - 1, 1)) * 100)
    
    # Relative signal based on z-score
    if z_score > 1.0:
        relative_signal = "RICH_VS_PEERS"
    elif z_score < -1.0:
        relative_signal = "CHEAP_VS_PEERS"
    elif z_score > 0.5:
        relative_signal = "ABOVE_AVERAGE"
    elif z_score < -0.5:
        relative_signal = "BELOW_AVERAGE"
    else:
        relative_signal = "IN_LINE_WITH_PEERS"
    
    # Rank label based on percentile
    if percentile >= 90:
        rank_label = "richest"
    elif percentile <= 10:
        rank_label = "cheapest"
    elif percentile >= 70:
        rank_label = "rich_end"
    elif percentile <= 30:
        rank_label = "cheap_end"
    else:
        rank_label = "middle"
    
    return {
        "rank": target_rank,
        "total": n,
        "rank_label": rank_label,
        "percentile": percentile,
        "z_score": round(z_score, 2),
        "peer_mean_ratio": round(peer_mean, 3),
        "peer_median_ratio": round(peer_median, 3),
        "peer_std": round(peer_std, 3),
        "peer_25th": round(peer_25th, 3),
        "peer_75th": round(peer_75th, 3),
        "relative_signal": relative_signal,
        "vs_median_pct": round((target_ratio / peer_median - 1) * 100, 1) if peer_median > 0 else 0
    }


def _generate_alpha_strategy(
    target_data: Dict[str, Any],
    ranking: Dict[str, Any],
    peer_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate actionable alpha strategies based on relative positioning."""
    
    ticker = target_data['ticker']
    ratio = target_data['iv_rv_ratio']
    relative = ranking['relative_signal']
    percentile = ranking['percentile']
    vs_median = ranking['vs_median_pct']
    
    strategies = []
    
    # Strategy 1: Outright vol trade on target
    if relative == "CHEAP_VS_PEERS":
        strategies.append({
            "name": f"Buy {ticker} Volatility",
            "direction": "long_vol",
            "conviction": "medium" if percentile < 30 else "low",
            "rationale": (
                f"{ticker} IV/RV at {ratio:.2f} is {abs(vs_median):.0f}% below peer median. "
                f"If vol converges to peers, long vol has edge."
            ),
            "trade_ideas": [
                f"Buy {ticker} 30-45 DTE ATM straddle",
                f"Buy {ticker} calendar spread (sell front, buy back)",
                f"Long {ticker} calls if directionally bullish"
            ],
            "risk": "Vol can stay cheap if realized vol remains low"
        })
    elif relative == "RICH_VS_PEERS":
        strategies.append({
            "name": f"Sell {ticker} Volatility",
            "direction": "short_vol",
            "conviction": "medium" if percentile > 70 else "low",
            "rationale": (
                f"{ticker} IV/RV at {ratio:.2f} is {vs_median:.0f}% above peer median. "
                f"Vol appears expensive vs comparables."
            ),
            "trade_ideas": [
                f"Sell {ticker} iron condor (defined risk)",
                f"Sell {ticker} put spread if bullish",
                f"Sell {ticker} strangle (undefined risk, higher premium)"
            ],
            "risk": "Event risk or volatility spike can cause losses"
        })
    else:
        strategies.append({
            "name": f"{ticker} Vol is Fair",
            "direction": "neutral",
            "conviction": "low",
            "rationale": (
                f"{ticker} IV/RV at {ratio:.2f} is in line with peers ({ranking['peer_median_ratio']:.2f}). "
                f"No clear relative value edge."
            ),
            "trade_ideas": [
                "Wait for better setup",
                "Use for directional trades (not vol trades)",
                "Consider other factors (earnings, events)"
            ],
            "risk": "N/A"
        })
    
    # Strategy 2: Pair trade if clear divergence
    if peer_data:
        sorted_peers = sorted(peer_data, key=lambda x: x['iv_rv_ratio'], reverse=True)
        richest = sorted_peers[0]
        cheapest = sorted_peers[-1]
        
        spread = richest['iv_rv_ratio'] - cheapest['iv_rv_ratio']
        
        if spread > 0.3:  # Meaningful divergence
            strategies.append({
                "name": "Vol Pair Trade",
                "direction": "relative_value",
                "conviction": "medium" if spread > 0.5 else "low",
                "rationale": (
                    f"Wide spread within peer group: {richest['ticker']} ({richest['iv_rv_ratio']:.2f}) "
                    f"vs {cheapest['ticker']} ({cheapest['iv_rv_ratio']:.2f}). "
                    f"Spread of {spread:.2f} suggests mean reversion opportunity."
                ),
                "trade_ideas": [
                    f"Long {cheapest['ticker']} straddle / Short {richest['ticker']} straddle",
                    f"Buy {cheapest['ticker']} vol via calls, sell {richest['ticker']} vol via puts",
                    "Size to be vega-neutral for pure relative value"
                ],
                "risk": "Spread can widen before converging"
            })
    
    return {
        "primary_strategy": strategies[0] if strategies else None,
        "all_strategies": strategies,
        "summary": strategies[0]['rationale'] if strategies else "No clear signal"
    }


# =============================================================================
# MAIN TOOL
# =============================================================================

# Canvas-friendly internal function for single ticker analysis
async def analyze_iv_rv_internal(
    ticker: str,
    rv_window: int = 20,
    min_dte: int = 14,
    max_dte: int = 45,
) -> Dict[str, Any]:
    """
    Canvas-friendly IV/RV analysis for a single ticker.
    
    Returns IV, RV, ratio, signal, and raw data for chart building.
    """
    ticker = ticker.upper().strip()
    
    fmp_server = FMPMarketDataServer()
    polygon_server = PolygonOptionsFuturesServer()
    
    try:
        await fmp_server.connect()
        await polygon_server.connect()
        
        logger.info(f"[IV_RV] Canvas analysis for {ticker}")
        
        # Fetch price history for RV calculation
        prices = await _fetch_price_history(fmp_server, ticker, days=max(rv_window + 30, 60))
        if not prices or len(prices) < rv_window + 5:
            return {"status": "error", "error": f"Insufficient price data for {ticker}"}
        
        spot = prices[-1]
        
        # Calculate realized vol for multiple windows
        rv_10 = _compute_realized_vol(prices, 10)
        rv_20 = _compute_realized_vol(prices, 20)
        rv_30 = _compute_realized_vol(prices, 30)
        rv_custom = _compute_realized_vol(prices, rv_window)
        
        if rv_custom is None:
            return {"status": "error", "error": f"Could not compute RV for {ticker}"}
        
        # Get ATM IV
        iv = await _extract_atm_iv(polygon_server, ticker, spot, min_dte, max_dte)
        if iv is None:
            return {"status": "error", "error": f"Could not extract IV for {ticker}. Check if options are liquid."}
        
        # Compute ratio
        iv_rv_ratio = iv / rv_custom
        vol_premium_pct = (iv_rv_ratio - 1) * 100
        
        # Historical RV data for percentile calculation
        rv_history = []
        iv_rv_history = []
        for i in range(min(len(prices) - rv_window, 60)):
            start_idx = len(prices) - rv_window - i - 1
            end_idx = len(prices) - i
            if start_idx >= 0:
                window_prices = prices[start_idx:end_idx]
                if len(window_prices) >= rv_window:
                    rv_val = _compute_realized_vol(window_prices, rv_window)
                    if rv_val and rv_val > 0.01:
                        rv_history.append(rv_val)
                        # Simulate historical IV/RV using current IV as proxy
                        # (In production, you'd fetch historical IV)
                        iv_rv_history.append(iv / rv_val)
        
        # Compute percentile rank (where does current ratio sit vs history?)
        if iv_rv_history and len(iv_rv_history) >= 5:
            # Percentile: what % of historical ratios are BELOW current?
            below_count = sum(1 for r in iv_rv_history if r < iv_rv_ratio)
            iv_rv_percentile = (below_count / len(iv_rv_history)) * 100
        else:
            # Fallback: use ratio-based estimate
            iv_rv_percentile = min(100, max(0, (iv_rv_ratio - 0.7) / 0.8 * 100))
        
        # Signal based on PERCENTILE (not absolute thresholds)
        if iv_rv_percentile >= 90:
            signal = "RICH"
            signal_desc = f"IV/RV at {iv_rv_percentile:.0f}th percentile - options are expensive vs recent history"
        elif iv_rv_percentile >= 70:
            signal = "SLIGHTLY_RICH"
            signal_desc = f"IV/RV at {iv_rv_percentile:.0f}th percentile - options are somewhat expensive"
        elif iv_rv_percentile <= 10:
            signal = "CHEAP"
            signal_desc = f"IV/RV at {iv_rv_percentile:.0f}th percentile - options are cheap vs recent history"
        elif iv_rv_percentile <= 30:
            signal = "SLIGHTLY_CHEAP"
            signal_desc = f"IV/RV at {iv_rv_percentile:.0f}th percentile - options are somewhat cheap"
        else:
            signal = "FAIR"
            signal_desc = f"IV/RV at {iv_rv_percentile:.0f}th percentile - in normal range"
        rv_history.reverse()
        
        return {
            "status": "success",
            "ticker": ticker,
            "spot_price": round(spot, 2),
            "iv": round(iv, 4),
            "rv": round(rv_custom, 4),
            "iv_rv_ratio": round(iv_rv_ratio, 3),
            "iv_rv_percentile": round(iv_rv_percentile, 1),
            "vol_premium_pct": round(vol_premium_pct, 1),
            "signal": signal,
            "signal_description": signal_desc,
            "rv_windows": {
                "rv_10d": round(rv_10, 4) if rv_10 else None,
                "rv_20d": round(rv_20, 4) if rv_20 else None,
                "rv_30d": round(rv_30, 4) if rv_30 else None,
                "rv_custom": round(rv_custom, 4),
            },
            "rv_history": rv_history,
            "iv_rv_history": iv_rv_history,
            "params": {
                "rv_window": rv_window,
                "min_dte": min_dte,
                "max_dte": max_dte,
            },
        }
        
    except Exception as e:
        logger.error(f"IV/RV Canvas analysis failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    
    finally:
        await fmp_server.cleanup()
        await polygon_server.cleanup()


@function_tool
async def analyze_iv_rv_vs_peers(
    target: str,
    peers: List[str],
    rv_window: int = 30,
    min_dte: int = 7,
    max_dte: int = 45
) -> Dict[str, Any]:
    """
    Analyze a target ticker's implied vs realized volatility and rank against peers.
    
    This tool computes IV/RV ratios to determine if options are pricing vol
    rich (expensive) or cheap relative to recent realized volatility and
    compared to a peer group.
    
    Signals are determined RELATIVE to the peer group distribution:
    - Z-score > 1: RICH (>1 std dev above peer mean)
    - Z-score < -1: CHEAP (>1 std dev below peer mean)
    - No hardcoded thresholds - everything is relative to THIS peer group
    
    Args:
        target: The main ticker to analyze (e.g., "AAPL")
        peers: List of peer tickers for comparison (e.g., ["MSFT", "GOOGL", "META", "AMZN"])
               Agent should select peers based on context: same sector, market cap, theme
        rv_window: Days of price history for realized vol (default 30)
        min_dte: Minimum days to expiration for ATM IV (default 7)
        max_dte: Maximum days to expiration for ATM IV (default 45)
    
    Returns:
        - target: Target's IV, RV, ratio, z-score, and signal (relative to peers)
        - vs_peers: Rank, percentile, z-score, peer statistics
        - all_ranked: Full comparison data sorted by IV/RV
        - alpha_strategies: Actionable trade ideas based on positioning
    
    Alpha Edge (relative to peers):
        - z-score > 1 (RICH_VS_PEERS) → Consider selling vol
        - z-score < -1 (CHEAP_VS_PEERS) → Consider buying vol
        - Pair trades: Long cheap vol / short rich vol within peer group
    
    Example:
        analyze_iv_rv_vs_peers(
            target="AAPL",
            peers=["MSFT", "GOOGL", "META", "AMZN", "NVDA"],
            rv_window=20,      # 20-day realized vol
            min_dte=14,        # 2-week minimum expiry
            max_dte=60         # 2-month max expiry
        )
    """
    target = target.upper().strip()
    peers = [p.upper().strip() for p in peers if p.strip()]
    
    # Remove target from peers if accidentally included
    peers = [p for p in peers if p != target]
    
    if not peers:
        return {
            "error": "No peers provided. Please provide at least one peer ticker.",
            "target": target
        }
    
    fmp_server = FMPMarketDataServer()
    polygon_server = PolygonOptionsFuturesServer()
    
    try:
        await fmp_server.connect()
        await polygon_server.connect()
        
        # Analyze target
        logger.info(f"[IV_RV] Analyzing target: {target} (RV={rv_window}d, DTE={min_dte}-{max_dte})")
        target_data = await _analyze_single_ticker(
            fmp_server, polygon_server, target, rv_window, min_dte, max_dte
        )
        
        if not target_data:
            return {
                "error": f"Could not analyze {target}. Check if ticker has liquid options.",
                "target": target
            }
        
        # Analyze peers in parallel (batched)
        logger.info(f"[IV_RV] Analyzing {len(peers)} peers")
        
        async def analyze_peer(ticker):
            return await _analyze_single_ticker(fmp_server, polygon_server, ticker, rv_window, min_dte, max_dte)
        
        # Batch to avoid overwhelming APIs
        peer_results = []
        batch_size = 5
        for i in range(0, len(peers), batch_size):
            batch = peers[i:i + batch_size]
            batch_results = await asyncio.gather(*[analyze_peer(p) for p in batch])
            peer_results.extend(batch_results)
        
        # Filter successful peer analyses
        peer_data = [r for r in peer_results if r is not None]
        
        if not peer_data:
            return {
                "error": "Could not analyze any peers. Check if tickers have liquid options.",
                "target": target,
                "target_data": target_data
            }
        
        logger.info(f"[IV_RV] Successfully analyzed {len(peer_data)} peers")
        
        # Rank target vs peers
        ranking = _rank_results(target_data, peer_data)
        
        # Generate alpha strategies
        alpha = _generate_alpha_strategy(target_data, ranking, peer_data)
        
        # Sort all for output (richest to cheapest)
        all_sorted = sorted(
            [target_data] + peer_data,
            key=lambda x: x['iv_rv_ratio'],
            reverse=True
        )
        
        # Mark target in sorted list
        for item in all_sorted:
            item['is_target'] = item['ticker'] == target
        
        return {
            "target": target_data,
            
            "vs_peers": {
                "rank": ranking['rank'],
                "out_of": ranking['total'],
                "rank_label": ranking['rank_label'],
                "percentile": ranking['percentile'],
                "peer_median_ratio": ranking['peer_median_ratio'],
                "relative_signal": ranking['relative_signal'],
                "vs_median_pct": ranking['vs_median_pct']
            },
            
            "all_ranked": all_sorted,
            
            "alpha_strategies": alpha,
            
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "rv_window_days": rv_window,
                "iv_dte_range": {"min": min_dte, "max": max_dte},
                "peers_requested": len(peers),
                "peers_analyzed": len(peer_data),
                "peers_failed": [p for p in peers if p not in [d['ticker'] for d in peer_data]]
            },
            
            "interpretation": (
                f"{target} IV/RV is {target_data['iv_rv_ratio']:.2f} "
                f"(z-score: {ranking['z_score']:+.1f}, rank {ranking['rank']}/{ranking['total']}, "
                f"{ranking['percentile']}th percentile). "
                f"Relative to peers: {ranking['relative_signal'].replace('_', ' ')}. "
                f"{alpha['summary']}"
            )
        }
        
    except Exception as e:
        logger.error(f"IV/RV analysis failed: {e}", exc_info=True)
        return {
            "error": str(e),
            "target": target
        }
    
    finally:
        await fmp_server.cleanup()
        await polygon_server.cleanup()

