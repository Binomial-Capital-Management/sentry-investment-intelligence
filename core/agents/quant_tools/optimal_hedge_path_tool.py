"""
Optimal Hedge Path Finder - Graph-Based Multi-Factor Risk Optimization

Finds minimum-cost hedging paths from current portfolio state to target
risk profile using Dijkstra optimization.

Supports:
- VaR targets, max drawdown targets
- Greek reductions (delta, gamma, vega)
- Factor neutralization (beta, sector exposure)
- Top-3 alternative paths

Data Sources:
- UW screener-option-contracts: Options with Greeks, liquidity, bid-ask
- FMP stock-screener: Dynamic ETF/stock discovery by beta, sector, volume
- FMP company-profile: Beta, sector for factor analysis

FULLY DYNAMIC: ALL hedge instruments discovered via screeners.
NO HARDCODED ETF lists - everything discovered based on portfolio characteristics.
"""

from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict  # Required for Pydantic on Python < 3.12
import asyncio
import logging
from datetime import datetime
import plotly.graph_objects as go
from core.agents.risk_tools.shared import register_chart_handle, sanitize_tool_output

from agents import function_tool

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results

from .hedge_path_helpers import (
    PortfolioFactors,
    FactorTarget,
    calculate_portfolio_factors,
    translate_risk_targets_to_factors,
    FactorGap,
    ScreenerFilters,
    ScreenerQuery,
    HedgeCandidate,
    calculate_factor_gaps,
    gap_to_screener_filters,
    parse_uw_screener_response,
    parse_fmp_screener_response,
    HedgePath,
    HedgePortfolio,
    dijkstra_multi_objective,
    optimize_hedge_portfolio,
    _safe_float,
    _safe_int,
)

logger = logging.getLogger(__name__)


class PositionInput(TypedDict, total=False):
    """Input position specification."""
    underlying: str           # Ticker symbol (required)
    ticker: str               # Alternative to underlying
    symbol: str               # Alternative to underlying
    quantity: int             # Number of shares/contracts
    shares: int               # Alternative to quantity
    weight: float             # Portfolio weight (0.0-1.0), e.g., 0.25 = 25%
    option_type: str          # 'call' or 'put' (for options)
    strike: float             # Strike price (for options)
    expiry: str               # Expiration date YYYY-MM-DD (for options)
    implied_volatility: float # IV override
    notional: float           # Position notional value
    price: float              # Current price


def _normalize_positions(
    positions: List[PositionInput],
    portfolio_value: float = 1000000
) -> List[Dict[str, Any]]:
    """
    Normalize positions to ensure they have notional values.
    
    Handles multiple input formats:
    1. Direct notional: {"ticker": "AAPL", "notional": 95000}
    2. Shares + price: {"ticker": "AAPL", "shares": 500, "price": 190}
    3. Weight only: {"ticker": "AAPL", "weight": 0.25} → 25% of portfolio_value
    4. Shares only: {"ticker": "AAPL", "shares": 500} → uses $100 default price
    """
    normalized = []
    
    for pos in positions:
        norm_pos = dict(pos)  # Copy
        ticker = pos.get("underlying") or pos.get("ticker") or pos.get("symbol")
        
        # Calculate notional from various inputs
        if pos.get("notional"):
            # Already have notional
            pass
        elif pos.get("weight"):
            # Weight-based: notional = weight * portfolio_value
            norm_pos["notional"] = pos["weight"] * portfolio_value
        elif pos.get("shares") or pos.get("quantity"):
            shares = pos.get("shares") or pos.get("quantity") or 0
            price = pos.get("price", 100)  # Default $100 if no price
            norm_pos["notional"] = abs(shares) * price
        
        normalized.append(norm_pos)
    
    return normalized


async def _execute_fmp_screener(
    fmp_server: FMPMarketDataServer,
    query: ScreenerQuery
) -> List[HedgeCandidate]:
    """
    Execute a single FMP stock screener query and return candidates.
    
    DYNAMIC DISCOVERY: No assumptions about what tickers will be returned.
    
    FMP run_stock_screener expects (from FMPMarketDataServer.py line 1067-1070):
        args = {
            "filters": {"isEtf": True, "betaMoreThan": 0.8, ...},
            "limit": 15
        }
    """
    candidates = []
    
    try:
        # Build filters dict for FMP screener
        filters = {}
        filter_keys = [
            "isEtf", "betaMoreThan", "betaLessThan",
            "volumeMoreThan", "marketCapMoreThan", "marketCapLessThan",
            "sector", "isActivelyTrading",
        ]
        
        for key in filter_keys:
            if key in query.params:
                filters[key] = query.params[key]
        
        # FMP expects filters nested, with limit at top level
        fmp_params = {"filters": filters}
        if "limit" in query.params:
            fmp_params["limit"] = query.params["limit"]
        
        logger.info(f"FMP screener '{query.purpose}': {fmp_params}")
        
        result = await fmp_server.call_tool("run_stock_screener", fmp_params)
        
        if result and hasattr(result, 'content'):
            data = safe_parse_json(result)
            candidates = parse_fmp_screener_response(data, discovery_source=query.purpose)
            logger.info(f"FMP screener '{query.purpose}' returned {len(candidates)} candidates")
    
    except Exception as e:
        logger.warning(f"FMP screener error for '{query.purpose}': {e}")
    
    return candidates


async def _execute_all_fmp_queries(
    fmp_server: FMPMarketDataServer,
    queries: List[ScreenerQuery]
) -> List[HedgeCandidate]:
    """Execute all FMP screener queries in parallel."""
    fmp_queries = [q for q in queries if q.source == "fmp_stock_screener"]
    
    if not fmp_queries:
        return []
    
    # Run queries in parallel
    tasks = [_execute_fmp_screener(fmp_server, q) for q in fmp_queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate candidates, deduplicating by ticker
    seen_tickers = set()
    candidates = []
    
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"FMP query failed: {result}")
            continue
        
        for candidate in result:
            if candidate.ticker not in seen_tickers:
                seen_tickers.add(candidate.ticker)
                candidates.append(candidate)
    
    return candidates


async def _get_options_for_discovered_etfs(
    uw_server: UWOptionsServer,
    etf_candidates: List[HedgeCandidate],
    base_filters: Dict[str, Any],
    max_tickers: int = 10
) -> List[HedgeCandidate]:
    """
    Get options for dynamically discovered ETFs.
    
    Takes the ETFs found via FMP screener and queries UW for their options.
    
    Uses same pattern as nope_divergence_tool.py for UW parsing.
    """
    candidates = []
    
    # Get the most liquid discovered ETFs
    sorted_etfs = sorted(etf_candidates, key=lambda c: c.volume, reverse=True)
    etf_tickers = [c.ticker for c in sorted_etfs[:max_tickers] if c.instrument_type == "etf"]
    
    if not etf_tickers:
        return candidates
    
    try:
        query_filters = base_filters.copy()
        query_filters["ticker"] = ",".join(etf_tickers)
        
        # Ensure Greek filters are strings
        string_fields = ["min_delta", "max_delta", "min_gamma", "max_gamma",
                         "min_vega", "max_vega", "min_theta", "max_theta"]
        for field in string_fields:
            if field in query_filters and not isinstance(query_filters[field], str):
                query_filters[field] = str(query_filters[field])
        
        logger.info(f"UW ETF options query for: {etf_tickers}")
        
        result = await uw_server.call_tool("uw_hottest_contracts", query_filters)
        
        # Match working pattern - NO hasattr check, direct safe_parse_json
        data = safe_parse_json(result)
        
        if data and "data" in data:
            for contract in data["data"]:
                if not isinstance(contract, dict):
                    continue
                
                ticker = (
                    contract.get("ticker") or 
                    contract.get("ticker_symbol") or
                    contract.get("underlying_symbol")
                )
                if not ticker:
                    continue
                
                # Parse option_symbol for strike/expiry if not provided directly
                # Format: SPY251205C00687000 -> expiry=2025-12-05, strike=687.00, type=call
                opt_sym = contract.get("option_symbol") or ""
                parsed_strike = None
                parsed_expiry = None
                parsed_type = None
                if len(opt_sym) >= 15:
                    try:
                        # Last 8 digits = strike * 1000 (e.g., 00687000 = 687.00)
                        parsed_strike = int(opt_sym[-8:]) / 1000.0
                        # Character before strike = C/P
                        parsed_type = "call" if opt_sym[-9] == "C" else "put"
                        # 6 digits before that = YYMMDD
                        date_str = opt_sym[-15:-9]
                        parsed_expiry = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
                    except (ValueError, IndexError):
                        pass
                
                candidate = HedgeCandidate(
                    instrument_type="option",
                    ticker=ticker,
                    option_symbol=opt_sym,
                    strike=contract.get("strike") or contract.get("strike_price") or parsed_strike,
                    expiry=contract.get("expiry") or contract.get("expiration_date") or parsed_expiry,
                    option_type=contract.get("option_type") or contract.get("type") or parsed_type,
                    delta=_safe_float(contract.get("delta")),
                    gamma=_safe_float(contract.get("gamma")),
                    vega=_safe_float(contract.get("vega")),
                    theta=_safe_float(contract.get("theta")),
                    bid=_safe_float(contract.get("bid")),
                    ask=_safe_float(contract.get("ask")),
                    open_interest=_safe_int(contract.get("open_interest") or contract.get("oi")),
                    volume=_safe_int(contract.get("volume") or contract.get("vol")),
                    sector=contract.get("sector"),
                    discovery_source="uw_options_on_discovered_etfs",
                )
                
                # Calculate mid price from bid/ask or fallback to close/avg_price
                if candidate.bid > 0 and candidate.ask > 0:
                    candidate.mid_price = (candidate.bid + candidate.ask) / 2
                elif contract.get("avg_price"):
                    candidate.mid_price = _safe_float(contract.get("avg_price"))
                elif contract.get("close"):
                    candidate.mid_price = _safe_float(contract.get("close"))
                elif contract.get("last"):
                    candidate.mid_price = _safe_float(contract.get("last"))
                
                candidates.append(candidate)
        
        logger.info(f"UW options on discovered ETFs returned {len(candidates)} candidates")
        
    except Exception as e:
        logger.warning(f"UW options query for discovered ETFs failed: {e}", exc_info=True)
    
    return candidates


async def _screen_options_uw(
    uw_server: UWOptionsServer,
    filters: Dict[str, Any],
    target_tickers: Optional[List[str]] = None
) -> List[HedgeCandidate]:
    """
    Screen options using UW hottest_contracts.
    
    Pattern from nope_divergence_tool.py (lines 395-401):
        result = await options_server.call_tool("uw_hottest_contracts", base_filters)
        data = safe_parse_json(result)
        if data and "data" in data:
            for contract in data["data"]:
                ticker = contract.get("ticker") or contract.get("underlying_symbol")
    
    CRITICAL: Greek filters (min_delta, max_delta, etc.) must be STRINGS!
    """
    candidates = []
    
    try:
        # Make a copy to avoid mutating the original
        query_filters = filters.copy()
        
        # If specific tickers requested, filter by them
        if target_tickers:
            query_filters["ticker"] = ",".join(target_tickers[:10])  # Limit to 10
        
        # Ensure Greek filters are strings (UW requirement)
        string_fields = ["min_delta", "max_delta", "min_gamma", "max_gamma",
                         "min_vega", "max_vega", "min_theta", "max_theta"]
        for field in string_fields:
            if field in query_filters and not isinstance(query_filters[field], str):
                query_filters[field] = str(query_filters[field])
        
        logger.info(f"UW query filters: {query_filters}")
        
        result = await uw_server.call_tool("uw_hottest_contracts", query_filters)
        
        # Match working pattern from nope_divergence_tool.py - NO hasattr check
        data = safe_parse_json(result)
        logger.info(f"UW raw response keys: {data.keys() if isinstance(data, dict) else type(data)}")
        
        if data and "data" in data:
            # Parse directly like nope_divergence_tool does
            for contract in data["data"]:
                if not isinstance(contract, dict):
                    continue
                
                ticker = (
                    contract.get("ticker") or 
                    contract.get("ticker_symbol") or
                    contract.get("underlying_symbol")
                )
                if not ticker:
                    continue
                
                # Parse option_symbol for strike/expiry if not provided directly
                # UW format: SPY251205C00687000 -> expiry=2025-12-05, strike=687.00, type=call
                opt_sym = contract.get("option_symbol") or ""
                parsed_strike = None
                parsed_expiry = None
                parsed_type = None
                if len(opt_sym) >= 15:
                    try:
                        # Last 8 digits = strike * 1000 (e.g., 00687000 = 687.00)
                        parsed_strike = int(opt_sym[-8:]) / 1000.0
                        # Character before strike = C/P
                        parsed_type = "call" if opt_sym[-9] == "C" else "put"
                        # 6 digits before that = YYMMDD
                        date_str = opt_sym[-15:-9]
                        parsed_expiry = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
                    except (ValueError, IndexError):
                        pass
                
                candidate = HedgeCandidate(
                    instrument_type="option",
                    ticker=ticker,
                    option_symbol=opt_sym,
                    strike=contract.get("strike") or contract.get("strike_price") or parsed_strike,
                    expiry=contract.get("expiry") or contract.get("expiration_date") or parsed_expiry,
                    option_type=contract.get("option_type") or contract.get("type") or parsed_type,
                    delta=_safe_float(contract.get("delta")),
                    gamma=_safe_float(contract.get("gamma")),
                    vega=_safe_float(contract.get("vega")),
                    theta=_safe_float(contract.get("theta")),
                    bid=_safe_float(contract.get("bid")),
                    ask=_safe_float(contract.get("ask")),
                    open_interest=_safe_int(contract.get("open_interest") or contract.get("oi")),
                    volume=_safe_int(contract.get("volume") or contract.get("vol")),
                    sector=contract.get("sector"),
                    discovery_source="uw_options_on_holdings",
                )
                
                # Calculate mid price from bid/ask or fallback to avg_price/close
                if candidate.bid > 0 and candidate.ask > 0:
                    candidate.mid_price = (candidate.bid + candidate.ask) / 2
                elif contract.get("avg_price"):
                    candidate.mid_price = _safe_float(contract.get("avg_price"))
                elif contract.get("close"):
                    candidate.mid_price = _safe_float(contract.get("close"))
                elif contract.get("last"):
                    candidate.mid_price = _safe_float(contract.get("last"))
                
                candidates.append(candidate)
            
        logger.info(f"UW screening returned {len(candidates)} candidates")
        
    except Exception as e:
        logger.warning(f"UW options screening error: {e}", exc_info=True)
    
    return candidates


async def find_optimal_hedge_path_internal(
    positions: List[PositionInput],
    portfolio_value: float = 1000000,
    target_var_1d_pct: Optional[float] = None,
    target_max_drawdown_pct: Optional[float] = None,
    delta_reduction_pct: Optional[float] = None,
    gamma_reduction_pct: Optional[float] = None,
    vega_reduction_pct: Optional[float] = None,
    target_beta: Optional[float] = None,
    neutralize_sectors: Optional[List[str]] = None,
    max_cost: Optional[float] = None,
    max_dte: int = 45,
    min_dte: int = 14,
    min_liquidity_oi: int = 500
) -> Dict[str, Any]:
    """
    Find optimal hedging paths from current portfolio to target risk profile.
    
    This tool analyzes your portfolio's factor exposures (Greeks, beta, sectors),
    calculates gaps to your risk targets, and finds the minimum-cost combination
    of hedges to close those gaps.
    
    ═══════════════════════════════════════════════════════════════════════════════
    HOW IT WORKS (FULLY DYNAMIC DISCOVERY)
    ═══════════════════════════════════════════════════════════════════════════════
    
    1. ANALYZE: Calculate current delta, gamma, vega, beta, sector weights
    2. TARGET: Translate your risk targets into factor targets
    3. GAP: Calculate the difference (what needs to be hedged)
    4. DISCOVER: Run multiple screeners to find hedge candidates:
       - UW Options: On your holdings for direct hedges
       - FMP Screener: Beta-matched ETFs based on YOUR portfolio's beta
       - FMP Screener: Sector ETFs for sectors YOU need to hedge
       - FMP Screener: High-liquidity ETFs by volume
       - FMP Screener: Low-beta defensive stocks if you need beta reduction
       - UW Options: On the discovered ETFs for options strategies
    5. OPTIMIZE: Use Dijkstra algorithm to find minimum-cost hedge paths
    6. RETURN: Top 3 paths ranked by cost with full breakdown
    
    NO HARDCODED ETF LISTS - everything is discovered dynamically based on
    your portfolio's actual characteristics and the gaps you need to close.
    
    ═══════════════════════════════════════════════════════════════════════════════
    PARAMETERS
    ═══════════════════════════════════════════════════════════════════════════════
    
    PORTFOLIO INPUT (required):
    ───────────────────────────
    positions: List of position dicts. Multiple formats supported:
    
        FORMAT 1 - Weights (matches your portfolio DB format):
        - ticker: The ticker symbol
        - weight: Portfolio weight as decimal (0.25 = 25%)
        
        FORMAT 2 - Shares + Price:
        - ticker: The ticker symbol
        - shares: Number of shares
        - price: Current price per share
        
        FORMAT 3 - Direct Notional:
        - ticker: The ticker symbol
        - notional: Dollar value of position
        
        For OPTIONS, also include:
        - option_type: "call" or "put"
        - strike: Strike price
        - expiry: Expiration date YYYY-MM-DD
    
    portfolio_value: Total portfolio value in $ (default: 1,000,000)
        Used to convert weights to notional values
    
    RISK TARGETS (pick what you want to achieve):
    ──────────────────────────────────────────────
    • target_var_1d_pct: Target 1-day VaR as % of portfolio (e.g., 0.01 = 1%)
    • target_max_drawdown_pct: Target max drawdown % (e.g., 0.10 = 10%)
    • delta_reduction_pct: Reduce delta by this % (e.g., 0.80 = reduce by 80%)
    • gamma_reduction_pct: Reduce gamma by this %
    • vega_reduction_pct: Reduce vega by this %
    • target_beta: Target portfolio beta (e.g., 0.5 = half market exposure)
    • neutralize_sectors: List of sectors to neutralize (e.g., ["Technology"])
    
    CONSTRAINTS:
    ────────────
    • max_cost: Maximum total hedging cost allowed ($)
    • max_dte: Maximum days to expiration for options (default: 45)
    • min_dte: Minimum days to expiration (default: 14)
    • min_liquidity_oi: Minimum open interest for options (default: 500)
    
    ═══════════════════════════════════════════════════════════════════════════════
    EXAMPLES
    ═══════════════════════════════════════════════════════════════════════════════
    
    # Using weights (matches your portfolio DB format)
    find_optimal_hedge_path(
        positions=[
            {"ticker": "AAPL", "weight": 0.20},   # 20% of portfolio
            {"ticker": "MSFT", "weight": 0.25},   # 25%
            {"ticker": "NVDA", "weight": 0.18},   # 18%
            {"ticker": "GOOGL", "weight": 0.12},  # 12%
            {"ticker": "JPM", "weight": 0.10},    # 10%
            {"ticker": "XOM", "weight": 0.15},    # 15%
        ],
        portfolio_value=500000,  # $500K portfolio
        delta_reduction_pct=0.80,
        neutralize_sectors=["Technology"]
    )
    
    # Using shares + price
    find_optimal_hedge_path(
        positions=[
            {"ticker": "AAPL", "shares": 500, "price": 190},
            {"ticker": "NVDA", "shares": 200, "price": 450}
        ],
        delta_reduction_pct=0.80
    )
    
    # Options portfolio with VaR target
    find_optimal_hedge_path(
        positions=[
            {"underlying": "TSLA", "option_type": "call", "strike": 250, 
             "expiry": "2025-02-21", "quantity": 10}
        ],
        target_var_1d_pct=0.01
    )
    
    ═══════════════════════════════════════════════════════════════════════════════
    OUTPUT
    ═══════════════════════════════════════════════════════════════════════════════
    
    Returns a dict with:
    - current_factors: Current portfolio Greeks, beta, sector weights
    - target_factors: What you're targeting
    - gaps: The difference to be hedged
    - optimal_paths: Top 3 paths with cost, steps, and final factors
    - screener_stats: How many options/ETFs were evaluated + discovery sources
    - discovered_instruments: List of instruments found by each screener
    """
    
    # Validate inputs
    if not positions:
        return {
            "status": "error",
            "error": "No positions provided",
            "help": "Provide at least one position with ticker and quantity"
        }
    
    # Check at least one target is specified
    has_target = any([
        target_var_1d_pct is not None,
        target_max_drawdown_pct is not None,
        delta_reduction_pct is not None,
        gamma_reduction_pct is not None,
        vega_reduction_pct is not None,
        target_beta is not None,
        neutralize_sectors is not None,
    ])
    
    if not has_target:
        return {
            "status": "error",
            "error": "No risk target specified",
            "help": "Specify at least one target: delta_reduction_pct, target_var_1d_pct, target_beta, etc."
        }
    
    # Initialize servers
    try:
        fmp_server = FMPMarketDataServer()
        uw_server = UWOptionsServer()
        
        await asyncio.gather(
            fmp_server.connect(),
            uw_server.connect()
        )
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to initialize data servers: {e}"
        }
    
    try:
        # Normalize positions to ensure notional values are set
        normalized_positions = _normalize_positions(positions, portfolio_value)
        
        # Step 1: Calculate current portfolio factors
        current_factors = await calculate_portfolio_factors(
            positions=normalized_positions,
            fmp_server=fmp_server
        )
        
        # Step 2: Translate risk targets to factor targets
        target_factors = translate_risk_targets_to_factors(
            current=current_factors,
            target_var_1d_pct=target_var_1d_pct,
            target_max_drawdown_pct=target_max_drawdown_pct,
            delta_reduction_pct=delta_reduction_pct,
            gamma_reduction_pct=gamma_reduction_pct,
            vega_reduction_pct=vega_reduction_pct,
            target_beta=target_beta,
            neutralize_sectors=neutralize_sectors,
        )
        
        # Step 3: Calculate gaps
        gaps = calculate_factor_gaps(current_factors, target_factors)
        
        # Step 4: Convert gaps to screener filters (DYNAMIC DISCOVERY)
        portfolio_underlyings = [
            p.get("underlying") or p.get("ticker") or p.get("symbol")
            for p in normalized_positions
            if p.get("underlying") or p.get("ticker") or p.get("symbol")
        ]
        
        screener_filters = gap_to_screener_filters(
            gap=gaps,
            portfolio_factors=current_factors,  # Pass portfolio characteristics
            portfolio_underlyings=portfolio_underlyings,
            min_dte=min_dte,
            max_dte=max_dte,
            min_liquidity_oi=min_liquidity_oi,
        )
        
        # Step 5: Execute ALL screener queries (FULLY DYNAMIC)
        candidates: List[HedgeCandidate] = []
        discovery_log = []  # Track what we discovered from each source
        
        logger.info(f"Screener filters: uw_options={screener_filters.uw_options}, queries_count={len(screener_filters.queries)}")
        
        # 5a. Screen options on portfolio holdings via UW
        if screener_filters.uw_options:
            logger.info(f"Calling UW with filters: {screener_filters.uw_options}")
        else:
            logger.warning("No UW options filters - skipping UW screening")
        
        if screener_filters.uw_options:
            holding_options = await _screen_options_uw(
                uw_server,
                screener_filters.uw_options,
                screener_filters.target_underlyings
            )
            candidates.extend(holding_options)
            discovery_log.append({
                "source": "UW options on holdings",
                "tickers_queried": screener_filters.target_underlyings[:10],
                "found": len(holding_options),
                "sample": [c.ticker for c in holding_options[:5]]
            })
        
        # 5b. Execute all FMP screener queries
        fmp_candidates = await _execute_all_fmp_queries(fmp_server, screener_filters.queries)
        candidates.extend(fmp_candidates)
        
        # Group FMP results by discovery source for logging
        fmp_by_source: Dict[str, List[str]] = {}
        for c in fmp_candidates:
            source = c.discovery_source or "fmp_unknown"
            if source not in fmp_by_source:
                fmp_by_source[source] = []
            fmp_by_source[source].append(c.ticker)
        
        for source, tickers in fmp_by_source.items():
            discovery_log.append({
                "source": source,
                "found": len(tickers),
                "instruments": tickers[:10]  # Show first 10
            })
        
        # 5c. Get options on the discovered ETFs
        discovered_etfs = [c for c in fmp_candidates if c.instrument_type == "etf"]
        if discovered_etfs and screener_filters.uw_options:
            etf_options = await _get_options_for_discovered_etfs(
                uw_server,
                discovered_etfs,
                screener_filters.uw_options,
                max_tickers=10
            )
            candidates.extend(etf_options)
            discovery_log.append({
                "source": "UW options on discovered ETFs",
                "etfs_queried": [c.ticker for c in discovered_etfs[:10]],
                "found": len(etf_options),
                "sample": [c.ticker for c in etf_options[:5]]
            })
        
        if not candidates:
            return {
                "status": "warning",
                "warning": "No hedge candidates found matching criteria",
                "current_factors": _factors_to_dict(current_factors),
                "gaps": _gaps_to_dict(gaps),
                "screener_queries_executed": [
                    {"source": q.source, "purpose": q.purpose, "params": q.params}
                    for q in screener_filters.queries
                ],
                "discovery_log": discovery_log,
                "suggestion": "Try relaxing min_liquidity_oi or expanding DTE range"
            }
        
        # Step 6: Run DIJKSTRA PORTFOLIO BUILDER
        # Dijkstra explores the space of portfolios to find optimal combination
        # of 10-20 instruments that together achieve factor targets
        
        # Calculate target number of instruments: 25-35% of portfolio positions
        num_portfolio_positions = len(portfolio_underlyings)
        min_instruments = max(int(num_portfolio_positions * 0.30), 10)  # At least 10
        min_instruments = min(min_instruments, 20)  # Cap at 20 for practicality
        logger.info(f"Portfolio has {num_portfolio_positions} positions, targeting {min_instruments} hedge instruments")
        
        # Check if delta gap is too small for meaningful hedging
        delta_gap = abs(gaps.delta_gap)
        avg_candidate_price = sum(c.mid_price for c in candidates if c.instrument_type != "option") / max(len([c for c in candidates if c.instrument_type != "option"]), 1)
        target_per_instrument = delta_gap / max(min_instruments, 1)
        
        if target_per_instrument < avg_candidate_price * 0.1 and delta_gap > 0:
            # Gap is very small - need options or cheaper instruments
            logger.warning(f"Delta gap ${delta_gap:.0f} is small relative to avg instrument ${avg_candidate_price:.0f}. Filtering to cheaper instruments.")
            # Filter to only options and cheap stocks
            cheap_candidates = [c for c in candidates if c.instrument_type == "option" or c.mid_price < target_per_instrument * 2]
            if cheap_candidates:
                candidates = cheap_candidates
                logger.info(f"Filtered to {len(candidates)} cheaper candidates")
            else:
                # No cheap candidates - accept fewer instruments
                min_instruments = max(3, int(delta_gap / avg_candidate_price) + 1)
                logger.info(f"No cheap candidates, reducing min_instruments to {min_instruments}")
        
        # Run Dijkstra in PORTFOLIO BUILDING mode
        # max_steps = min_instruments + buffer to allow exploration
        # max_iterations high to explore enough portfolio combinations
        paths = dijkstra_multi_objective(
            start_factors=current_factors,
            target=target_factors,
            candidates=candidates,
            max_steps=min_instruments + 5,  # Allow building past minimum
            k_paths=3,                       # Top 3 portfolio alternatives
            max_iterations=15000,            # Enough to build 10-20 instrument portfolios
            tolerance=0.10,                  # 10% tolerance for multi-factor targets
            min_instruments=min_instruments,
        )
        
        if not paths or not paths[0].steps:
            # Fallback to portfolio optimizer if Dijkstra fails
            logger.warning("Dijkstra failed to find portfolio, trying direct optimization")
            
            # Get portfolio value with fallback
            portfolio_value = None
            if positions:
                portfolio_value = positions[0].get("value") or positions[0].get("portfolio_value")
            if not portfolio_value or portfolio_value <= 0:
                # Try delta, otherwise default to 100k
                if current_factors.delta and abs(current_factors.delta) > 0:
                    portfolio_value = abs(current_factors.delta)
                else:
                    portfolio_value = 100000
            
            hedge_portfolio_result = optimize_hedge_portfolio(
                start_factors=current_factors,
                target=target_factors,
                candidates=candidates,
                num_instruments=min_instruments,
                max_notional_per_instrument=portfolio_value * 0.10,
                max_iterations=3,
            )
            
            if not hedge_portfolio_result or not hedge_portfolio_result.instruments:
                return {
                    "status": "warning",
                    "warning": "Could not find hedge solutions with enough instruments",
                    "current_factors": _factors_to_dict(current_factors),
                    "gaps": _gaps_to_dict(gaps),
                    "candidates_found": len(candidates),
                    "discovery_log": discovery_log,
                    "suggestion": f"Try with fewer instruments (found {len(candidates)} candidates)"
                }
            
            # Use portfolio optimizer result
            hedge_portfolio = []
            for action in hedge_portfolio_result.instruments:
                hedge_portfolio.append({
                    "instrument": action.ticker,
                    "action": action.action_type,
                    "quantity": action.quantity,
                    "description": action.instrument,
                    "cost": round(action.cost, 2),
                    "delta_impact": round(action.factor_impact.delta_change, 2),
                    "beta_dollar_impact": round(action.factor_impact.beta_dollar_change, 2),
                    "notional_impact": round(action.factor_impact.notional_change, 2),
                    "option_details": {
                        "strike": action.strike,
                        "expiry": action.expiry,
                        "type": action.option_type,
                    } if action.option_type else None,
                })
            final_factors = hedge_portfolio_result.final_factors
            total_cost = hedge_portfolio_result.total_cost
            gap_closure_result = hedge_portfolio_result.gap_closure
        else:
            # Use Dijkstra result (PRIMARY PATH)
            best_path = paths[0]
            logger.info(f"Dijkstra found portfolio with {len(best_path.steps)} instruments")
            
            hedge_portfolio = []
            for step in best_path.steps:
                hedge_portfolio.append({
                    "instrument": step.ticker,
                    "action": step.action_type,
                    "quantity": step.quantity,
                    "description": step.instrument,
                    "cost": round(step.cost, 2),
                    "delta_impact": round(step.factor_impact.delta_change, 2),
                    "beta_dollar_impact": round(step.factor_impact.beta_dollar_change, 2),
                    "notional_impact": round(getattr(step.factor_impact, 'notional_change', 0), 2),
                    "option_details": {
                        "strike": step.strike,
                        "expiry": step.expiry,
                        "type": step.option_type,
                    } if step.option_type else None,
                })
            
            final_factors = best_path.final_factors
            total_cost = best_path.total_cost
            gap_closure_result = {
                "delta": best_path.delta_closure_pct,
                "gamma": getattr(best_path, 'gamma_closure_pct', 0),
                "vega": getattr(best_path, 'vega_closure_pct', 0),
            }
        
        # Build charts (use a mock path for compatibility)
        class MockPath:
            def __init__(self, steps, final_factors):
                self.steps = steps
                self.final_factors = final_factors
        
        mock_steps = []
        for h in hedge_portfolio:
            from .hedge_path_helpers.path_optimizer import HedgeAction, FactorImpact
            mock_steps.append(HedgeAction(
                instrument=h.get("description", ""),
                ticker=h.get("instrument", ""),
                action_type=h.get("action", ""),
                quantity=h.get("quantity", 0),
                cost=h.get("cost", 0),
                factor_impact=FactorImpact(
                    delta_change=h.get("delta_impact", 0),
                    beta_dollar_change=h.get("beta_dollar_impact", 0),
                ),
            ))
        
        mock_path = MockPath(mock_steps, final_factors)
        charts = _build_charts(current_factors, target_factors, mock_path)
        
        # Format gap closure for response
        formatted_gap_closure = {}
        if isinstance(gap_closure_result, dict):
            for k, v in gap_closure_result.items():
                if isinstance(v, (int, float)):
                    # Convert to percentage if not already
                    pct = v * 100 if abs(v) <= 1 else v
                    formatted_gap_closure[f"{k}_pct"] = round(pct, 1)
        
        return jsonify_results(sanitize_tool_output({
            "status": "success",
            
            # PRIMARY OUTPUT: The optimal hedge portfolio
            "hedge_portfolio": {
                "instruments": hedge_portfolio,
                "total_cost": round(total_cost, 2),
                "instrument_count": len(hedge_portfolio),
                "total_notional": round(sum(abs(h.get("notional_impact", 0)) for h in hedge_portfolio), 2),
            },
            
            # Factor analysis
            "current_factors": _factors_to_dict(current_factors),
            "target_factors": _target_to_dict(target_factors),
            "final_factors_after_hedge": final_factors,
            "gaps": _gaps_to_dict(gaps),
            "gap_closure": formatted_gap_closure,
            
            "screener_stats": {
                "options_screened": sum(1 for c in candidates if c.instrument_type == "option"),
                "etfs_discovered": sum(1 for c in candidates if c.instrument_type == "etf"),
                "stocks_discovered": sum(1 for c in candidates if c.instrument_type == "stock"),
                "total_candidates": len(candidates),
                "reasoning": screener_filters.reasoning,
            },
            "discovery_log": discovery_log,
            "constraints_used": {
                "min_dte": min_dte,
                "max_dte": max_dte,
                "min_liquidity_oi": min_liquidity_oi,
                "max_cost": max_cost,
                "num_instruments_target": min_instruments,
            },
            "charts": charts,
        }))
        
    except Exception as e:
        logger.error(f"Hedge path optimization error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
    
    finally:
        # Cleanup
        try:
            await fmp_server.cleanup()
            await uw_server.cleanup()
        except Exception:
            pass
    
def _build_charts(current_factors: PortfolioFactors,
                 target_factors: FactorTarget,
                 best_path: Optional[HedgePath]) -> List[Dict[str, Any]]:
    """
    Build Plotly chart payloads and register them in chart cache.
    Returns lightweight chart handles.
    """
    chart_handles: List[Dict[str, Any]] = []
    
    # Hedge allocation chart
    if best_path and best_path.steps:
        tickers = []
        notionals = []
        for step in best_path.steps:
            impact = step.factor_impact
            notional = impact.notional_change if impact.notional_change else impact.delta_change
            tickers.append(step.ticker)
            notionals.append(abs(notional))
        fig_alloc = go.Figure(go.Bar(x=tickers, y=notionals, marker_color="#1f77b4"))
        fig_alloc.update_layout(title="Hedge Notional by Instrument", xaxis_title="Instrument", yaxis_title="Notional ($)")
        chart_handles.append(
            register_chart_handle(
                fig_alloc.to_dict(),
                chart_type="hedge_allocation",
                title="Hedge Notional by Instrument",
                alt_text="Bar chart of hedge notional per instrument"
            )
        )
    
    # Factor before/after (delta, beta)
    final_delta = best_path.final_factors.get("delta") if best_path else current_factors.delta
    final_beta = best_path.final_factors.get("beta") if best_path else current_factors.beta
    fig_factors = go.Figure(data=[
        go.Bar(name="Before", x=["Delta ($)", "Beta"], y=[current_factors.delta, current_factors.beta], marker_color="#636EFA"),
        go.Bar(name="After", x=["Delta ($)", "Beta"], y=[final_delta, final_beta], marker_color="#EF553B"),
    ])
    fig_factors.update_layout(barmode="group", title="Factors Before vs After Hedge")
    chart_handles.append(
        register_chart_handle(
            fig_factors.to_dict(),
            chart_type="factors_before_after",
            title="Factors Before vs After Hedge",
            alt_text="Grouped bars showing delta and beta before vs after hedge"
        )
    )
    
    # Sector weights before/target (top 6)
    current_sw = current_factors.sector_weights or {}
    target_sw = getattr(target_factors, "sector_targets", {}) or {}
    sectors = list(current_sw.keys() | target_sw.keys())
    sectors = sectors[:6]  # top few
    cur_vals = [current_sw.get(s, 0) for s in sectors]
    tgt_vals = [target_sw.get(s, current_sw.get(s, 0)) for s in sectors]
    if sectors:
        fig_sector = go.Figure(data=[
            go.Bar(name="Current", x=sectors, y=cur_vals, marker_color="#00CC96"),
            go.Bar(name="Target", x=sectors, y=tgt_vals, marker_color="#AB63FA"),
        ])
        fig_sector.update_layout(barmode="group", title="Sector Weights (Current vs Target)")
        chart_handles.append(
            register_chart_handle(
                fig_sector.to_dict(),
                chart_type="sector_weights",
                title="Sector Weights (Current vs Target)",
                alt_text="Grouped bars showing sector weights current vs target"
            )
        )
    
    return chart_handles


def _factors_to_dict(factors: PortfolioFactors) -> Dict[str, Any]:
    """Convert PortfolioFactors to output dict."""
    return {
        "delta": round(factors.delta, 2),
        "gamma": round(factors.gamma, 4),
        "vega": round(factors.vega, 2),
        "theta": round(factors.theta, 2),
        "beta": round(factors.beta, 3),
        "var_1d_95": round(factors.var_1d_95, 2),
        "var_1d_99": round(factors.var_1d_99, 2),
        "sector_weights": {k: round(v, 4) for k, v in factors.sector_weights.items()},
        "total_notional": round(factors.total_notional, 2),
        "position_count": factors.position_count,
        "skipped_underlyings": getattr(factors, "skipped_underlyings", []),
    }


def _target_to_dict(target: FactorTarget) -> Dict[str, Any]:
    """Convert FactorTarget to output dict."""
    result = {}
    
    if target.delta is not None:
        result["delta"] = round(target.delta, 2)
    if target.gamma is not None:
        result["gamma"] = round(target.gamma, 4)
    if target.vega is not None:
        result["vega"] = round(target.vega, 2)
    if target.beta is not None:
        result["beta"] = round(target.beta, 3)
    if target.sector_targets:
        result["sector_targets"] = {k: round(v, 4) for k, v in target.sector_targets.items()}
    if target.var_1d_95 is not None:
        result["var_1d_95"] = round(target.var_1d_95, 2)
    
    return result


def _gaps_to_dict(gaps: FactorGap) -> Dict[str, Any]:
    """Convert FactorGap to output dict."""
    result = {
        "delta": round(gaps.delta_gap, 2),
        "gamma": round(gaps.gamma_gap, 4),
        "vega": round(gaps.vega_gap, 2),
        "beta": round(gaps.beta_gap, 3),
    }
    
    if gaps.sector_gaps:
        result["sectors"] = {k: round(v, 4) for k, v in gaps.sector_gaps.items()}
    
    return result


@function_tool
async def find_optimal_hedge_path(
    positions: List[PositionInput],
    portfolio_value: float = 1000000,
    target_var_1d_pct: Optional[float] = None,
    target_max_drawdown_pct: Optional[float] = None,
    delta_reduction_pct: Optional[float] = None,
    gamma_reduction_pct: Optional[float] = None,
    vega_reduction_pct: Optional[float] = None,
    target_beta: Optional[float] = None,
    neutralize_sectors: Optional[List[str]] = None,
    max_cost: Optional[float] = None,
    max_dte: int = 45,
    min_dte: int = 14,
    min_liquidity_oi: int = 500
) -> Dict[str, Any]:
    """
    Find optimal hedging paths using Dijkstra algorithm.
    
    Analyzes portfolio factor exposures and finds minimum-cost hedge combinations.
    """
    return await find_optimal_hedge_path_internal(
        positions=positions,
        portfolio_value=portfolio_value,
        target_var_1d_pct=target_var_1d_pct,
        target_max_drawdown_pct=target_max_drawdown_pct,
        delta_reduction_pct=delta_reduction_pct,
        gamma_reduction_pct=gamma_reduction_pct,
        vega_reduction_pct=vega_reduction_pct,
        target_beta=target_beta,
        neutralize_sectors=neutralize_sectors,
        max_cost=max_cost,
        max_dte=max_dte,
        min_dte=min_dte,
        min_liquidity_oi=min_liquidity_oi,
    )
