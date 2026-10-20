"""
Gap to Screener - Translate factor gaps into UW/FMP screener filters.

Converts portfolio factor gaps into targeted screener queries to find
efficient hedge candidates. Uses FULLY DYNAMIC discovery patterns.

CRITICAL: UW Greek filters are STRINGS, not floats!

NO HARDCODED ETFs - All instruments discovered via screeners based on
portfolio characteristics (beta, sector weights, liquidity requirements).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import logging

from .factor_calculator import PortfolioFactors, FactorTarget

logger = logging.getLogger(__name__)


@dataclass
class FactorGap:
    """Gap between current and target factor exposures."""
    
    delta_gap: float = 0.0      # Need to add this much delta (negative = need puts)
    gamma_gap: float = 0.0
    vega_gap: float = 0.0
    beta_gap: float = 0.0
    sector_gaps: Dict[str, float] = field(default_factory=dict)
    
    # Meta
    has_greek_gap: bool = False
    has_factor_gap: bool = False
    has_sector_gap: bool = False


@dataclass
class HedgeCandidate:
    """A potential hedge instrument with its characteristics."""
    
    # Instrument identification
    instrument_type: str           # "option" | "etf" | "stock"
    ticker: str                    # Underlying or ETF ticker
    option_symbol: Optional[str] = None  # Full option symbol if applicable
    
    # Option details (if applicable)
    strike: Optional[float] = None
    expiry: Optional[str] = None
    option_type: Optional[str] = None  # "call" | "put"
    
    # Greeks per contract
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    
    # Pricing
    bid: float = 0.0
    ask: float = 0.0
    mid_price: float = 0.0
    
    # Liquidity
    open_interest: int = 0
    volume: int = 0
    
    # Factor impacts (for ETFs/stocks)
    beta: float = 1.0
    sector: Optional[str] = None
    
    # Discovery source (for debugging)
    discovery_source: Optional[str] = None
    
    @property
    def spread(self) -> float:
        """Bid-ask spread."""
        if self.bid > 0:
            return self.ask - self.bid
        return 0.0
    
    @property
    def spread_pct(self) -> float:
        """Spread as percentage of mid price."""
        if self.mid_price > 0:
            return self.spread / self.mid_price
        return 0.0
    
    def cost_for_quantity(self, quantity: int, multiplier: int = 100) -> float:
        """Calculate total cost including slippage for a given quantity."""
        # Use mid price + half spread for slippage estimate
        effective_price = self.mid_price + (self.spread / 2)
        return effective_price * abs(quantity) * multiplier


@dataclass
class ScreenerQuery:
    """A single screener query configuration."""
    
    source: str                    # "fmp_stock_screener" | "uw_options"
    params: Dict[str, Any] = field(default_factory=dict)
    purpose: str = ""              # Human-readable purpose
    priority: int = 1              # Higher = more important


@dataclass
class ScreenerFilters:
    """Collection of screener queries for dynamic discovery."""
    
    # Multiple screener queries (not just one)
    queries: List[ScreenerQuery] = field(default_factory=list)
    
    # UW options filters (for options specifically)
    uw_options: Dict[str, Any] = field(default_factory=dict)
    
    # Tickers to specifically query options for
    target_underlyings: List[str] = field(default_factory=list)
    
    # Overall reasoning
    reasoning: str = ""


def calculate_factor_gaps(
    current: PortfolioFactors,
    target: FactorTarget
) -> FactorGap:
    """
    Calculate gaps between current factors and target.
    
    Gap = Target - Current (negative gap means need to reduce exposure)
    """
    gap = FactorGap()
    
    # Greek gaps
    if target.delta is not None:
        gap.delta_gap = target.delta - current.delta
        gap.has_greek_gap = True
    
    if target.gamma is not None:
        gap.gamma_gap = target.gamma - current.gamma
        gap.has_greek_gap = True
    
    if target.vega is not None:
        gap.vega_gap = target.vega - current.vega
        gap.has_greek_gap = True
    
    # Beta gap
    if target.beta is not None:
        gap.beta_gap = target.beta - current.beta
        gap.has_factor_gap = True
    
    # Sector gaps
    for sector, target_weight in target.sector_targets.items():
        current_weight = current.sector_weights.get(sector, 0.0)
        sector_gap = target_weight - current_weight
        if abs(sector_gap) > 0.01:  # 1% threshold
            gap.sector_gaps[sector] = sector_gap
            gap.has_sector_gap = True
    
    return gap


def _delta_gap_to_option_filters(
    delta_gap: float,
    min_dte: int = 14,
    max_dte: int = 45,
    min_oi: int = 500
) -> Dict[str, Any]:
    """
    Convert delta gap to UW option screener filters.
    
    UW screener-option-contracts params (from catalog + working nope_divergence_tool):
    - min_dte/max_dte: INTEGER
    - min_open_interest: INTEGER  
    - limit: INTEGER (max 250)
    - order: WHAT to sort by ("volume", "open_interest", etc.) - from screener_order_by enum
    - order_direction: "desc" or "asc" (default: desc)
    - type: "call" or "put"
    - min_delta/max_delta: STRING (e.g., "-0.50", "0.5")
    
    Working example from nope_divergence_tool.py line 70:
        {"min_delta": "0.5", "order": "volume", "limit": 100}
    """
    filters: Dict[str, Any] = {
        "min_dte": min_dte,              # INTEGER
        "max_dte": max_dte,              # INTEGER
        "min_open_interest": min_oi,     # INTEGER
        "limit": 100,                    # INTEGER (max 250)
        "order": "volume",               # WHAT to sort by (from screener_order_by enum)
    }
    
    if delta_gap < 0:
        # Need negative delta → buy puts or sell calls
        # Prefer puts for hedging (limited risk)
        filters["type"] = "put"
        # OTM puts have delta between -0.5 and 0
        filters["min_delta"] = "-0.50"   # STRING
        filters["max_delta"] = "-0.10"   # STRING
    else:
        # Need positive delta → buy calls or sell puts
        # Prefer calls for upside participation
        filters["type"] = "call"
        filters["min_delta"] = "0.10"    # STRING
        filters["max_delta"] = "0.50"    # STRING
    
    return filters


def gap_to_screener_filters(
    gap: FactorGap,
    portfolio_factors: Optional[PortfolioFactors] = None,
    portfolio_underlyings: List[str] = None,
    min_dte: int = 14,
    max_dte: int = 45,
    min_liquidity_oi: int = 500
) -> ScreenerFilters:
    """
    Convert factor gaps + portfolio characteristics to MULTIPLE screener queries.
    
    FULLY DYNAMIC DISCOVERY - All hedge instruments found via screeners:
    
    1. Portfolio holdings → UW options screener for direct hedges
    2. Portfolio beta → FMP screener to find beta-matched ETFs
    3. Sector gaps → FMP screener to find sector ETFs
    4. Need low beta → FMP screener to find defensive stocks
    5. Broad hedge → FMP screener for high-liquidity ETFs
    
    Args:
        gap: Factor gaps to close
        portfolio_factors: Current portfolio characteristics (for dynamic queries)
        portfolio_underlyings: Tickers in the portfolio
        min_dte: Minimum days to expiration
        max_dte: Maximum days to expiration
        min_liquidity_oi: Minimum open interest for options
    
    Returns:
        ScreenerFilters with multiple discovery queries
    """
    filters = ScreenerFilters()
    reasoning_parts = []
    underlyings = list(portfolio_underlyings or [])
    filters.target_underlyings = underlyings
    
    # Extract portfolio characteristics for dynamic screening
    portfolio_beta = portfolio_factors.beta if portfolio_factors else 1.0
    portfolio_sectors = list((portfolio_factors.sector_weights if portfolio_factors else {}).keys())
    
    logger.info(f"gap_to_screener_filters: delta_gap={gap.delta_gap}, underlyings={underlyings[:5]}, beta={portfolio_beta}, sectors={portfolio_sectors}")
    
    # =========================================================================
    # QUERY 1: Options on portfolio holdings (direct hedge)
    # =========================================================================
    if gap.delta_gap != 0 and underlyings:
        logger.info(f"Creating UW options filters for delta_gap={gap.delta_gap}")
        filters.uw_options = _delta_gap_to_option_filters(
            gap.delta_gap,
            min_dte=min_dte,
            max_dte=max_dte,
            min_oi=min_liquidity_oi
        )
        
        # Add sectors if we have sector gaps
        if gap.has_sector_gap:
            gap_sectors = list(gap.sector_gaps.keys())
            uw_sectors = _map_sectors_to_uw(gap_sectors)
            if uw_sectors:
                filters.uw_options["sectors"] = uw_sectors
        
        direction = "puts" if gap.delta_gap < 0 else "calls"
        reasoning_parts.append(f"Delta gap {gap.delta_gap:,.0f} → {direction} on holdings")
    
    # =========================================================================
    # QUERY 1B: Options for gamma/vega hedging (broad, higher greeks)
    # =========================================================================
    if gap.has_greek_gap:
        greek_options_filter: Dict[str, Any] = {
            "min_dte": min_dte,
            "max_dte": max_dte,
            "min_open_interest": min_liquidity_oi,
            "limit": 150,
            "order": "volume",
            # Wide delta band to pick higher gamma/vega
            "min_delta": "-0.80",
            "max_delta": "0.80",
            # Let UW pick both calls/puts; omit type
        }
        filters.queries.append(ScreenerQuery(
            source="uw_options",
            params=greek_options_filter,
            purpose="Find high-gamma/vega options for greek hedging",
            priority=1
        ))
        reasoning_parts.append("Discover high-gamma/vega options for greek hedging")
    
    # =========================================================================
    # QUERY 2: Beta-matched ETFs (discover ETFs with similar beta to portfolio)
    # =========================================================================
    if gap.delta_gap != 0:
        # Find ETFs that match portfolio's beta profile for efficient hedging
        beta_lower = max(0.5, portfolio_beta - 0.3)
        beta_upper = portfolio_beta + 0.3
        
        filters.queries.append(ScreenerQuery(
            source="fmp_stock_screener",
            params={
                "isEtf": True,
                "betaMoreThan": beta_lower,
                "betaLessThan": beta_upper,
                "volumeMoreThan": 5000000,  # Liquid ETFs only
                "isActivelyTrading": True,
                "limit": 15,
            },
            purpose=f"Find ETFs with beta {beta_lower:.1f}-{beta_upper:.1f} matching portfolio",
            priority=1
        ))
        reasoning_parts.append(f"Discover beta-matched ETFs (β={portfolio_beta:.2f})")
    
    # =========================================================================
    # QUERY 3: High-liquidity broad ETFs (for general delta hedging)
    # =========================================================================
    if gap.delta_gap != 0:
        filters.queries.append(ScreenerQuery(
            source="fmp_stock_screener",
            params={
                "isEtf": True,
                "volumeMoreThan": 10000000,  # Ultra-liquid
                "isActivelyTrading": True,
                "limit": 20,
            },
            purpose="Find most liquid ETFs for broad hedging",
            priority=2
        ))
        reasoning_parts.append("Discover liquid ETFs by volume")
    
    # =========================================================================
    # QUERY 4: Sector ETFs (for sector gap hedging)
    # =========================================================================
    if gap.has_sector_gap:
        for sector, sector_gap in gap.sector_gaps.items():
            if sector_gap < 0:  # Need to reduce this sector
                filters.queries.append(ScreenerQuery(
                    source="fmp_stock_screener",
                    params={
                        "isEtf": True,
                        "sector": sector,
                        "volumeMoreThan": 1000000,
                        "isActivelyTrading": True,
                        "limit": 10,
                    },
                    purpose=f"Find {sector} ETFs for sector hedge",
                    priority=1
                ))
                reasoning_parts.append(f"Discover {sector} sector ETFs")
        
        # Special handling: Technology overweight → prioritize tech hedges (QQQ/XLK etc.)
        if "Technology" in gap.sector_gaps:
            filters.queries.append(ScreenerQuery(
                source="fmp_stock_screener",
                params={
                    "isEtf": True,
                    "sector": "Technology",
                    "volumeMoreThan": 5000000,
                    "isActivelyTrading": True,
                    "limit": 15,
                },
                purpose="Find Technology ETFs for sector hedge",
                priority=1
            ))
            reasoning_parts.append("Prioritize Technology sector ETFs (QQQ/XLK equivalents)")
            
            # Also add UW options filtered by sector for tech
            tech_options_filter = _delta_gap_to_option_filters(
                gap.delta_gap,
                min_dte=min_dte,
                max_dte=max_dte,
                min_oi=min_liquidity_oi
            )
            tech_options_filter["sectors"] = ["Technology"]
            filters.queries.append(ScreenerQuery(
                source="uw_options",
                params=tech_options_filter,
                purpose="Options on Technology sector underlyings",
                priority=1
            ))
    
    # =========================================================================
    # QUERY 5: Low-beta defensive stocks (for beta reduction)
    # =========================================================================
    if gap.beta_gap < -0.2:  # Need significant beta reduction
        filters.queries.append(ScreenerQuery(
            source="fmp_stock_screener",
            params={
                "isEtf": False,
                "betaLessThan": 0.5,
                "marketCapMoreThan": 10000000000,  # Large cap for liquidity
                "volumeMoreThan": 1000000,
                "isActivelyTrading": True,
                "limit": 20,
            },
            purpose="Find low-beta defensive stocks",
            priority=2
        ))
        reasoning_parts.append(f"Discover low-beta stocks (need β reduction of {abs(gap.beta_gap):.2f})")
    
    # =========================================================================
    # QUERY 6: High-beta stocks (for beta increase)
    # =========================================================================
    if gap.beta_gap > 0.2:  # Need beta increase
        filters.queries.append(ScreenerQuery(
            source="fmp_stock_screener",
            params={
                "isEtf": False,
                "betaMoreThan": 1.5,
                "marketCapMoreThan": 5000000000,  # Mid-large cap
                "volumeMoreThan": 500000,
                "isActivelyTrading": True,
                "limit": 20,
            },
            purpose="Find high-beta stocks",
            priority=2
        ))
        reasoning_parts.append(f"Discover high-beta stocks (need β increase of {gap.beta_gap:.2f})")
    
    # =========================================================================
    # QUERY 7: Inverse/leveraged ETFs (for strong hedging needs)
    # =========================================================================
    if gap.delta_gap < -50000:  # Large negative delta needed
        # Search for inverse ETFs by looking for negative beta
        filters.queries.append(ScreenerQuery(
            source="fmp_stock_screener",
            params={
                "isEtf": True,
                "betaLessThan": 0,  # Negative beta = inverse
                "volumeMoreThan": 1000000,
                "isActivelyTrading": True,
                "limit": 10,
            },
            purpose="Find inverse ETFs for strong hedging",
            priority=3
        ))
        reasoning_parts.append("Discover inverse ETFs for large delta hedge")
    
    # =========================================================================
    # QUERY 8: Options on portfolio's dominant sectors
    # =========================================================================
    if portfolio_sectors and gap.has_sector_gap:
        # Get options on stocks in the sectors we need to hedge
        uw_sectors = _map_sectors_to_uw(list(gap.sector_gaps.keys()))
        if uw_sectors:
            sector_options_filter = _delta_gap_to_option_filters(
                gap.delta_gap,
                min_dte=min_dte,
                max_dte=max_dte,
                min_oi=min_liquidity_oi
            )
            sector_options_filter["sectors"] = uw_sectors
            
            filters.queries.append(ScreenerQuery(
                source="uw_options",
                params=sector_options_filter,
                purpose=f"Find options in sectors: {', '.join(uw_sectors)}",
                priority=1
            ))
    
    filters.reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No gaps to hedge"
    
    return filters


def _map_sectors_to_uw(sectors: List[str]) -> List[str]:
    """Map sector names to UW sector format."""
    uw_sectors = []
    sector_mapping = {
        "Technology": "Technology",
        "Information Technology": "Technology",
        "Financials": "Financial Services",
        "Financial Services": "Financial Services",
        "Healthcare": "Healthcare",
        "Health Care": "Healthcare",
        "Consumer Discretionary": "Consumer Cyclical",
        "Consumer Cyclical": "Consumer Cyclical",
        "Consumer Staples": "Consumer Defensive",
        "Consumer Defensive": "Consumer Defensive",
        "Materials": "Basic Materials",
        "Basic Materials": "Basic Materials",
        "Energy": "Energy",
        "Industrials": "Industrials",
        "Utilities": "Utilities",
        "Real Estate": "Real Estate",
        "Communication Services": "Communication Services",
    }
    
    for s in sectors:
        mapped = sector_mapping.get(s, s)
        if mapped not in uw_sectors:
            uw_sectors.append(mapped)
    
    return uw_sectors


def parse_uw_screener_response(
    response_data: Dict[str, Any]
) -> List[HedgeCandidate]:
    """
    Parse UW screener response into HedgeCandidate objects.
    
    UW screener-option-contracts returns: {"data": [...contracts...]}
    Proof from nope_divergence_tool.py line 397:
        if data and "data" in data:
            for contract in data["data"]:
    
    Handles field name variations dynamically based on UW response structure.
    """
    candidates = []
    
    # UW returns {"data": [...]} - extract the array
    data = response_data.get("data", [])
    if not isinstance(data, list):
        # Fallback: maybe response_data itself is the array
        if isinstance(response_data, list):
            data = response_data
        else:
            return candidates
    
    for contract in data:
        if not isinstance(contract, dict):
            continue
        
        # Extract ticker with fallbacks for UW field name variations
        # UW uses "ticker" or "ticker_symbol" depending on endpoint
        ticker = (
            contract.get("ticker") or 
            contract.get("ticker_symbol") or
            contract.get("underlying_symbol") or 
            contract.get("underlying")
        )
        
        if not ticker:
            continue
        
        candidate = HedgeCandidate(
            instrument_type="option",
            ticker=ticker,
            option_symbol=contract.get("option_symbol") or contract.get("symbol") or contract.get("id"),
            strike=contract.get("strike") or contract.get("strike_price"),
            expiry=contract.get("expiry") or contract.get("expiration_date") or contract.get("expires"),
            option_type=contract.get("option_type") or contract.get("type"),
            delta=_safe_float(contract.get("delta")),
            gamma=_safe_float(contract.get("gamma")),
            vega=_safe_float(contract.get("vega")),
            theta=_safe_float(contract.get("theta")),
            bid=_safe_float(contract.get("bid")),
            ask=_safe_float(contract.get("ask")),
            open_interest=_safe_int(contract.get("open_interest") or contract.get("oi")),
            volume=_safe_int(contract.get("volume") or contract.get("vol")),
            sector=contract.get("sector"),
            discovery_source="uw_options",
        )
        
        # Calculate mid price from bid/ask or fallback to close/last/avg_price
        if candidate.bid > 0 and candidate.ask > 0:
            candidate.mid_price = (candidate.bid + candidate.ask) / 2
        elif contract.get("close"):
            candidate.mid_price = _safe_float(contract.get("close"))
        elif contract.get("last"):
            candidate.mid_price = _safe_float(contract.get("last"))
        elif contract.get("avg_price"):
            candidate.mid_price = _safe_float(contract.get("avg_price"))
        
        candidates.append(candidate)
    
    return candidates


def parse_fmp_screener_response(
    response_data: Any,
    discovery_source: str = "fmp_stock_screener"
) -> List[HedgeCandidate]:
    """
    Parse FMP stock screener response into HedgeCandidate objects.
    
    FMP run_stock_screener returns (from FMPMarketDataServer.py line 1089-1092):
        {
            "result_count": N,
            "filters_applied": [...],
            "results": [...stocks...],  # <-- Data is here
        }
    
    Handles both ETFs and individual stocks.
    """
    candidates = []
    
    # Handle various response formats
    if isinstance(response_data, list):
        data = response_data
    elif isinstance(response_data, dict):
        # FMP screener returns "results", not "data"
        data = response_data.get("results") or response_data.get("data", [])
        if not data:
            # Fallback: maybe response_data itself has stock fields
            if response_data.get("symbol"):
                data = [response_data]
            else:
                data = []
    else:
        return candidates
    
    for item in data:
        if not isinstance(item, dict):
            continue
        
        ticker = item.get("symbol") or item.get("ticker")
        if not ticker:
            continue
        
        # Determine if ETF or stock
        is_etf = item.get("isEtf", False) or item.get("isETF", False)
        instrument_type = "etf" if is_etf else "stock"
        
        # Extract price
        price = (
            item.get("price") or 
            item.get("lastPrice") or 
            item.get("close") or
            0.0
        )
        
        candidate = HedgeCandidate(
            instrument_type=instrument_type,
            ticker=ticker,
            delta=1.0,  # Stock/ETF delta is 1 per share
            gamma=0.0,
            vega=0.0,
            theta=0.0,
            mid_price=_safe_float(price),
            bid=_safe_float(price) * 0.9999,  # Tight spread assumption
            ask=_safe_float(price) * 1.0001,
            beta=_safe_float(item.get("beta", 1.0)),
            sector=item.get("sector"),
            volume=_safe_int(item.get("volume", 0)),
            open_interest=999999,  # N/A for stocks
            discovery_source=discovery_source,
        )
        
        candidates.append(candidate)
    
    return candidates


def create_etf_candidate(
    ticker: str,
    price: float,
    beta: float = 1.0,
    sector: Optional[str] = None,
    discovery_source: str = "manual"
) -> HedgeCandidate:
    """Create a HedgeCandidate for direct ETF/stock hedging."""
    return HedgeCandidate(
        instrument_type="etf",
        ticker=ticker,
        delta=1.0,  # Stock/ETF delta is 1 per share
        gamma=0.0,  # No gamma for stocks
        vega=0.0,   # No vega for stocks
        theta=0.0,  # No theta for stocks
        mid_price=price,
        bid=price * 0.9999,  # Tight spread for liquid ETFs
        ask=price * 1.0001,
        beta=beta,
        sector=sector,
        open_interest=999999,  # Always liquid
        volume=999999,
        discovery_source=discovery_source,
    )


def _safe_float(value: Any) -> float:
    """Safely convert value to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value: Any) -> int:
    """Safely convert value to int."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
