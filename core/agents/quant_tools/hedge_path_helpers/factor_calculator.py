"""
Factor Calculator - Portfolio factor analysis for hedge path optimization.

Calculates:
- Greeks (delta, gamma, vega, theta) from existing exposure tools
- Beta (weighted avg vs SPY) from FMP profiles
- Sector weights from FMP company profiles
- Risk metrics (VaR, max drawdown estimate)

NO HARDCODING: Uses dynamic field discovery for all market data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import math
import logging
import asyncio

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

# Reuse existing Greek calculation implementations
# Use parent directory relative imports since we're in hedge_path_helpers/
from ..delta_exposure_tool import _calculate_delta_impl
from ..gamma_exposure_tool import _calculate_gamma_impl
from ..vega_exposure_tool import _calculate_vega_impl
from ..theta_decay_tool import _calculate_theta_impl

logger = logging.getLogger(__name__)

# Standard Z-scores for VaR calculations (not hardcoded thresholds)
Z_SCORE_95 = 1.645
Z_SCORE_99 = 2.326


@dataclass
class PortfolioFactors:
    """Complete portfolio factor exposure snapshot."""
    
    # Greeks (from existing tools)
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    
    # Market factors
    beta: float = 1.0                    # Weighted avg vs SPY
    correlation_spy: float = 0.0         # Portfolio correlation to market
    
    # Sector weights (discovered from FMP)
    sector_weights: Dict[str, float] = field(default_factory=dict)
    
    # Risk metrics
    var_1d_95: float = 0.0              # 1-day 95% VaR (in $)
    var_1d_99: float = 0.0              # 1-day 99% VaR (in $)
    max_drawdown_estimate: float = 0.0  # Estimated from vol
    
    # Position details for reference
    total_notional: float = 0.0
    position_count: int = 0
    
    # Tracking of ticker discovery
    valid_underlyings: List[str] = field(default_factory=list)
    skipped_underlyings: List[str] = field(default_factory=list)


@dataclass
class FactorTarget:
    """Target factor exposures for hedging."""
    
    # Greek targets (None = no target for this Greek)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    
    # Market factor targets
    beta: Optional[float] = None
    
    # Sector targets (sector -> target weight)
    sector_targets: Dict[str, float] = field(default_factory=dict)
    
    # Risk metric targets
    var_1d_95: Optional[float] = None
    max_drawdown: Optional[float] = None


def _is_stock_ticker(ticker: str) -> bool:
    """
    Check if a ticker appears to be a stock (vs option, crypto, etc).
    
    Filters out:
    - Option symbols (contain spaces + numbers like "AAPL  251220C00190000")
    - Crypto (contains . or - like "ETH.USD-PAXOS")
    - CFD markers (end with N like MPN)
    """
    import re
    
    # Option symbols typically have spaces followed by digits
    if re.search(r'\s+\d', ticker):
        return False
    
    # Crypto symbols often have dots or dashes
    if '.' in ticker or '-' in ticker:
        return False
    
    # Simple stock tickers: letters only, possibly with a single space (like "BRK B")
    # Allow single space for share classes
    clean = ticker.replace(' ', '')
    return clean.isalpha() and len(clean) <= 6


async def _fetch_company_profiles(
    fmp_server: FMPMarketDataServer,
    tickers: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Fetch company profiles for beta and sector data.
    
    Pattern from working tools: NO hasattr check, direct safe_parse_json.
    Filters out option symbols, crypto, etc. before calling FMP.
    """
    profiles = {}
    
    # Filter to stock tickers only (skip options, crypto, etc.)
    stock_tickers = [t for t in tickers if _is_stock_ticker(t)]
    skipped = [t for t in tickers if not _is_stock_ticker(t)]
    
    if skipped:
        logger.info(f"Skipping {len(skipped)} non-stock tickers: {skipped[:10]}{'...' if len(skipped) > 10 else ''}")
    
    for ticker in stock_tickers:
        try:
            # Use dataset="company-profile" directly (FMP recommended approach)
            # No ticker conversion - if FMP doesn't recognize it, we skip gracefully
            result = await fmp_server.call_tool("get_fields", {
                "symbol": ticker,
                "dataset": "company-profile"
            })
            
            data = safe_parse_json(result)
            
            # Debug: log structure to understand FMP response
            if isinstance(data, dict) and "datasets" in data:
                ds = data.get("datasets", {})
                for ds_name, ds_val in (ds.items() if isinstance(ds, dict) else []):
                    cp_data = ds_val.get("data") if isinstance(ds_val, dict) else None
                    logger.info(f"FMP profile for {ticker}: dataset={ds_name}, data_type={type(cp_data).__name__}, has_beta={'beta' in cp_data if isinstance(cp_data, dict) else 'N/A'}")
            else:
                logger.info(f"FMP profile for {ticker}: keys={list(data.keys()) if isinstance(data, dict) else type(data)}")
            
            # Parse FMP response: iterate all datasets, pick first entry with beta/sector
            # FMP structure: {"symbol": "X", "datasets": {"company-profile": {"data": {...profile...}, ...}}}
            # Note: "data" can be a dict (single profile, most common) OR a list
            if isinstance(data, dict) and "datasets" in data:
                datasets = data["datasets"]
                if isinstance(datasets, dict):
                    for ds_name, ds_val in datasets.items():
                        if not isinstance(ds_val, dict):
                            continue
                        cp_data = ds_val.get("data")
                        
                        # Handle dict response (FMP extracts first_item from list)
                        if isinstance(cp_data, dict) and "error" not in cp_data:
                            profiles[ticker] = cp_data
                            logger.info(f"Got profile for {ticker} from {ds_name}: beta={cp_data.get('beta')}, sector={cp_data.get('sector')}")
                            break
                        # Handle list response (fallback)
                        elif isinstance(cp_data, list) and cp_data:
                            profile_data = cp_data[0]
                            if isinstance(profile_data, dict) and "error" not in profile_data:
                                profiles[ticker] = profile_data
                                logger.info(f"Got profile for {ticker} from {ds_name} (list): beta={profile_data.get('beta')}, sector={profile_data.get('sector')}")
                                break
            elif isinstance(data, list) and len(data) > 0:
                # Direct array response
                profiles[ticker] = data[0]
                logger.info(f"Got profile (list) for {ticker}: beta={data[0].get('beta')}, sector={data[0].get('sector')}")
            elif isinstance(data, dict) and (data.get("beta") or data.get("sector")):
                # Direct dict response
                profiles[ticker] = data
                logger.info(f"Got profile (dict) for {ticker}: beta={data.get('beta')}, sector={data.get('sector')}")
            
        except Exception as e:
            logger.warning(f"Profile fetch failed for {ticker}: {e}")
    
    logger.info(f"Fetched profiles for {len(profiles)}/{len(tickers)} tickers: {list(profiles.keys())}")
    return profiles


def _extract_beta(profile: Dict[str, Any]) -> float:
    """Extract beta from profile with fallback field names."""
    # Try multiple field names (dynamic discovery)
    beta = profile.get('beta') or profile.get('Beta') or profile.get('companyBeta')
    
    if beta and isinstance(beta, (int, float)) and beta > 0:
        return float(beta)
    
    return 1.0  # Default to market beta


def _extract_sector(profile: Dict[str, Any]) -> Optional[str]:
    """Extract sector from profile with fallback field names."""
    sector = profile.get('sector') or profile.get('Sector') or profile.get('gicsSector')
    
    if sector and isinstance(sector, str):
        return sector
    
    return None


async def _calculate_greeks(
    positions: List[Dict[str, Any]],
    underlying_prices: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, float]:
    """Calculate portfolio Greeks using existing tools."""
    
    greeks = {
        "delta": 0.0,
        "gamma": 0.0,
        "vega": 0.0,
        "theta": 0.0
    }
    
    # Filter to option positions only
    option_positions = [
        p for p in positions 
        if p.get("option_type") or p.get("type")
    ]
    
    if not option_positions:
        # For stock-only portfolios, calculate delta from notional or shares
        # Stock delta = notional value (each $1 of stock has $1 of delta)
        for pos in positions:
            # Check for notional first (from normalized positions with weights)
            notional = pos.get("notional", 0)
            if notional:
                # Delta in dollars = notional value
                greeks["delta"] += notional
            else:
                # Fallback: shares * price or just shares
                shares = pos.get("quantity", 0) or pos.get("shares", 0)
                price = pos.get("price", 1.0)  # Default to 1 if no price
                greeks["delta"] += shares * price
        
        logger.info(f"Stock portfolio delta (notional): ${greeks['delta']:,.0f}")
        return greeks
    
    try:
        # Calculate delta
        delta_result = await _calculate_delta_impl(option_positions, underlying_prices)
        greeks["delta"] = delta_result.get("total_delta", 0.0)
        
        # Calculate gamma
        gamma_result = await _calculate_gamma_impl(option_positions, underlying_prices)
        greeks["gamma"] = gamma_result.get("total_gamma", 0.0)
        
        # Calculate vega
        vega_result = await _calculate_vega_impl(option_positions, underlying_prices)
        greeks["vega"] = vega_result.get("total_vega", 0.0)
        
        # Calculate theta
        theta_result = await _calculate_theta_impl(option_positions, underlying_prices)
        greeks["theta"] = theta_result.get("total_theta", 0.0)
        
    except Exception as e:
        logger.warning(f"Greek calculation error: {e}")
    
    return greeks


def _calculate_parametric_var(
    delta: float,
    daily_vol: float,
    z_score: float
) -> float:
    """
    Calculate parametric VaR from delta exposure.
    
    VaR = |delta| * daily_vol * z_score
    
    For delta-dominated portfolios, this captures most of the risk.
    """
    return abs(delta) * daily_vol * z_score


def _estimate_max_drawdown(annual_vol: float) -> float:
    """
    Estimate max drawdown from volatility.
    
    Empirical relationship: E[MaxDD] ≈ 2 * sqrt(T) * σ for random walk
    For 1 year: E[MaxDD] ≈ 2 * σ
    """
    return 2.0 * annual_vol


async def calculate_portfolio_factors(
    positions: List[Dict[str, Any]],
    fmp_server: Optional[FMPMarketDataServer] = None,
    underlying_prices: Optional[List[Dict[str, Any]]] = None,
    daily_vol_estimate: float = 0.015,  # Default 1.5% daily vol if not available
    portfolio_value: float = 1000000    # Used if positions have weights
) -> PortfolioFactors:
    """
    Calculate all portfolio factor exposures.
    
    Args:
        positions: List of position dicts with underlying, quantity, etc.
            Supports multiple formats:
            - {"ticker": "AAPL", "weight": 0.25} (25% of portfolio_value)
            - {"ticker": "AAPL", "notional": 250000}
            - {"ticker": "AAPL", "shares": 500, "price": 190}
        fmp_server: FMP server for profile lookups (optional)
        underlying_prices: Optional price overrides
        daily_vol_estimate: Default daily volatility assumption
        portfolio_value: Total portfolio value (used with weight-based positions)
    
    Returns:
        PortfolioFactors with all exposures calculated
    """
    factors = PortfolioFactors()
    
    if not positions:
        return factors
    
    # Initialize server if not provided
    if fmp_server is None:
        fmp_server = FMPMarketDataServer()
        await fmp_server.connect()
    
    # Extract unique underlyings
    underlyings = list(set(
        p.get("underlying") or p.get("ticker") or p.get("symbol")
        for p in positions
        if p.get("underlying") or p.get("ticker") or p.get("symbol")
    ))
    
    # Fetch company profiles for beta and sector
    profiles = await _fetch_company_profiles(fmp_server, underlyings)
    valid_underlyings = list(underlyings)  # keep all for screening, even if profile missing
    skipped_underlyings = [u for u in underlyings if u not in profiles]
    if skipped_underlyings:
        logger.warning(f"No profile for {len(skipped_underlyings)} tickers (kept for screening): {skipped_underlyings}")
    
    # Calculate Greeks
    greeks = await _calculate_greeks(positions, underlying_prices)
    factors.delta = greeks["delta"]
    factors.gamma = greeks["gamma"]
    factors.vega = greeks["vega"]
    factors.theta = greeks["theta"]
    
    # Calculate weighted beta and sector weights
    # IMPORTANT: Include ALL positions (default beta=1.0 for missing profiles)
    total_weight = 0.0
    weighted_beta = 0.0
    sector_exposure: Dict[str, float] = {}
    
    for pos in positions:
        underlying = pos.get("underlying") or pos.get("ticker") or pos.get("symbol")
        quantity = pos.get("quantity", 0) or pos.get("shares", 0)
        
        # Get notional value - support multiple formats
        if pos.get("notional"):
            notional = pos["notional"]
        elif pos.get("weight"):
            # Weight-based: notional = weight * portfolio_value
            notional = pos["weight"] * portfolio_value
        else:
            # Shares * price (default $100 if no price)
            notional = abs(quantity) * pos.get("price", 100)
        
        # Skip zero-notional positions
        if abs(notional) < 0.01:
            continue
        
        # Always include in total_weight
        total_weight += abs(notional)
        
        if underlying and underlying in profiles:
            profile = profiles[underlying]
            
            # Beta contribution (from profile)
            beta = _extract_beta(profile)
            weighted_beta += beta * abs(notional)
            
            # Sector contribution
            sector = _extract_sector(profile)
            if sector:
                sector_exposure[sector] = sector_exposure.get(sector, 0) + abs(notional)
        else:
            # Default beta=1.0 for positions without profiles
            weighted_beta += 1.0 * abs(notional)
            logger.debug(f"Using default beta=1.0 for {underlying} (no profile)")
    
    # Finalize weighted beta
    if total_weight > 0:
        factors.beta = weighted_beta / total_weight
        factors.total_notional = total_weight
        
        # Normalize sector weights
        for sector, exposure in sector_exposure.items():
            factors.sector_weights[sector] = exposure / total_weight
    
    factors.position_count = len(positions)
    factors.valid_underlyings = valid_underlyings
    factors.skipped_underlyings = skipped_underlyings
    
    # Calculate risk metrics
    factors.var_1d_95 = _calculate_parametric_var(
        factors.delta, daily_vol_estimate, Z_SCORE_95
    )
    factors.var_1d_99 = _calculate_parametric_var(
        factors.delta, daily_vol_estimate, Z_SCORE_99
    )
    
    # Estimate max drawdown (assume 20% annual vol if not known)
    annual_vol = daily_vol_estimate * math.sqrt(252)
    factors.max_drawdown_estimate = _estimate_max_drawdown(annual_vol)
    
    return factors


def translate_risk_targets_to_factors(
    current: PortfolioFactors,
    target_var_1d_pct: Optional[float] = None,
    target_max_drawdown_pct: Optional[float] = None,
    delta_reduction_pct: Optional[float] = None,
    gamma_reduction_pct: Optional[float] = None,
    vega_reduction_pct: Optional[float] = None,
    target_beta: Optional[float] = None,
    neutralize_sectors: Optional[List[str]] = None,
    preserve_other_factors: bool = True  # NEW: Don't let hedging make other factors worse
) -> FactorTarget:
    """
    Translate risk targets to factor targets.
    
    Supports:
    - VaR targets (translated to delta targets)
    - Percentage reductions in Greeks
    - Absolute beta targets
    - Sector neutralization
    
    IMPORTANT: When preserve_other_factors=True (default), any factor not explicitly
    targeted will be constrained to not get worse. This prevents hedges that reduce
    delta but increase beta, for example.
    """
    target = FactorTarget()
    
    # Delta target from VaR or percentage reduction
    if delta_reduction_pct is not None:
        # Reduce delta by X%
        target.delta = current.delta * (1 - delta_reduction_pct)
    elif target_var_1d_pct is not None:
        # Interpret target_var_1d_pct as desired fraction of current VaR.
        # Approximate by scaling delta by the same fraction (more stable than back-solving).
        target.delta = current.delta * target_var_1d_pct
        # Preserve sign if short
        if current.delta < 0:
            target.delta = -abs(target.delta)
    
    # Gamma target
    if gamma_reduction_pct is not None:
        target.gamma = current.gamma * (1 - gamma_reduction_pct)
    elif preserve_other_factors and current.gamma != 0:
        # Preserve current gamma (don't let it get worse)
        target.gamma = current.gamma
    
    # Vega target
    if vega_reduction_pct is not None:
        target.vega = current.vega * (1 - vega_reduction_pct)
    elif preserve_other_factors and current.vega != 0:
        # Preserve current vega
        target.vega = current.vega
    
    # Beta target - CRITICAL: Don't let beta increase when reducing risk!
    if target_beta is not None:
        target.beta = target_beta
    elif preserve_other_factors:
        if delta_reduction_pct is not None:
            target.beta = current.beta * (1 - delta_reduction_pct * 0.5)
        elif target_var_1d_pct is not None:
            # Scale beta with same fraction as VaR target when explicit beta not provided
            target.beta = current.beta * target_var_1d_pct
        if target.beta is not None:
            logger.info(f"Auto-setting beta target: {target.beta:.3f} (from {current.beta:.3f})")
    
    # Sector neutralization
    if neutralize_sectors:
        for sector in neutralize_sectors:
            if sector in current.sector_weights:
                # Target neutral (market weight or zero excess)
                target.sector_targets[sector] = 0.0
    elif preserve_other_factors:
        # Preserve sector exposures (don't let them drift too much)
        for sector, weight in current.sector_weights.items():
            # Allow some drift but not dramatic changes
            target.sector_targets[sector] = weight
    
    return target
