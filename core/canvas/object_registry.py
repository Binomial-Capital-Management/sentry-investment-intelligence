"""
Canvas Object Registry - Defines core object types and their capabilities.

Each object type declares what data it can provide, which enables the
Tinder-like matching system: objects provide capabilities, tools require
capabilities, and if requirements ⊆ provisions → match.

Capabilities are loaded DYNAMICALLY from ALL MCP server catalogs.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Path to MCP server catalogs
MCP_SERVERS_PATH = Path(__file__).parent.parent / "mcp_servers"


@dataclass
class DataSource:
    """Represents an MCP server that provides data for an object type."""
    server: str
    catalog_path: Optional[str] = None
    class_filter: Optional[str] = None
    asset_class_filter: Optional[str] = None


@dataclass
class ObjectType:
    """
    Defines an object type in the Canvas system.
    
    Attributes:
        name: Internal identifier (e.g., "equity", "crypto")
        display_name: Human-readable name (e.g., "Equity", "Crypto")
        provides: Set of dataset names this object can provide
        data_sources: List of MCP servers that provide data for this type
        parent: Optional parent object type (for nested types like equity_options)
        contains: List of object types this can contain (e.g., portfolio contains equities)
    """
    name: str
    display_name: str
    provides: Set[str]
    data_sources: List[DataSource]
    parent: Optional[str] = None
    contains: Optional[List[str]] = None


def _load_datasets_from_catalog(
    catalog_path: Path,
    class_filter: Optional[str] = None,
    asset_class_filter: Optional[str] = None,
    discoverable_only: bool = True
) -> Set[str]:
    """
    Load dataset names from an MCP catalog JSON file.
    
    Args:
        catalog_path: Path to the catalog JSON file
        class_filter: Optional filter by 'class' field (e.g., 'crypto', 'forex')
        asset_class_filter: Optional filter by 'asset_classes' array (e.g., 'options')
        discoverable_only: Only include datasets marked as discoverable
        
    Returns:
        Set of dataset names
    """
    if not catalog_path.exists():
        logger.warning(f"Catalog not found: {catalog_path}")
        return set()
    
    try:
        with open(catalog_path, 'r') as f:
            catalog = json.load(f)
        
        datasets = set()
        for entry in catalog.get("datasets", []):
            # Apply filters
            if discoverable_only and not entry.get("discoverable", False):
                continue
            if class_filter and entry.get("class") != class_filter:
                continue
            if asset_class_filter:
                asset_classes = entry.get("asset_classes", [])
                if asset_class_filter not in asset_classes:
                    continue
            
            dataset_name = entry.get("dataset")
            if dataset_name:
                datasets.add(dataset_name)
        
        return datasets
    except Exception as e:
        logger.error(f"Error loading catalog {catalog_path}: {e}")
        return set()


def _load_all_datasets_from_catalog(
    catalog_path: Path,
    discoverable_only: bool = True
) -> Set[str]:
    """Load ALL dataset names from a catalog without filtering."""
    return _load_datasets_from_catalog(catalog_path, discoverable_only=discoverable_only)


def _build_object_registry() -> Dict[str, ObjectType]:
    """
    Build the object registry by loading datasets from ALL MCP catalogs.
    """
    # ==========================================================================
    # CATALOG PATHS
    # ==========================================================================
    
    # FMP catalogs
    fmp_ddc = MCP_SERVERS_PATH / "fmp" / "ddc_catalog.json"
    fmp_alternatives = MCP_SERVERS_PATH / "fmp" / "alternatives_catalog.json"
    fmp_tradeflow = MCP_SERVERS_PATH / "fmp" / "tradeflow_catalog.json"
    fmp_valuation = MCP_SERVERS_PATH / "fmp" / "valuation_catalog.json"
    
    # Polygon catalogs
    polygon_ddc = MCP_SERVERS_PATH / "polygon" / "polygon_ddc_catalog.json"
    
    # Unusual Whales catalogs
    uw_options = MCP_SERVERS_PATH / "unusualwhales" / "uw_options_catalog.json"
    uw_market = MCP_SERVERS_PATH / "unusualwhales" / "uw_market_catalog.json"
    uw_institutional = MCP_SERVERS_PATH / "unusualwhales" / "uw_institutional_catalog.json"
    
    # ==========================================================================
    # LOAD DATASETS FROM CATALOGS
    # ==========================================================================
    
    # FMP datasets
    fmp_equity_datasets = _load_datasets_from_catalog(fmp_ddc)
    fmp_valuation_datasets = _load_datasets_from_catalog(fmp_valuation)
    fmp_crypto_datasets = _load_datasets_from_catalog(fmp_alternatives, class_filter="crypto")
    fmp_forex_datasets = _load_datasets_from_catalog(fmp_alternatives, class_filter="forex")
    fmp_commodity_datasets = _load_datasets_from_catalog(fmp_alternatives, class_filter="commodities")
    fmp_etf_datasets = _load_datasets_from_catalog(fmp_tradeflow, class_filter="etf")
    
    # Polygon datasets (by asset class)
    polygon_options_datasets = _load_datasets_from_catalog(polygon_ddc, asset_class_filter="options")
    polygon_forex_datasets = _load_datasets_from_catalog(polygon_ddc, asset_class_filter="forex")
    polygon_crypto_datasets = _load_datasets_from_catalog(polygon_ddc, asset_class_filter="crypto")
    
    # Unusual Whales datasets
    uw_options_datasets = _load_all_datasets_from_catalog(uw_options)
    uw_market_datasets = _load_all_datasets_from_catalog(uw_market)
    uw_institutional_datasets = _load_all_datasets_from_catalog(uw_institutional)
    
    # ==========================================================================
    # BUILD REGISTRY
    # ==========================================================================
    
    return {
        # ----------------------------------------------------------------------
        # PORTFOLIO - User-defined collections of assets
        # A portfolio contains other asset types and can access their capabilities
        # ----------------------------------------------------------------------
        "portfolio": ObjectType(
            name="portfolio",
            display_name="Portfolio",
            provides={"positions", "weights", "returns", "value", "metadata"},
            data_sources=[
                DataSource(server="PortfolioService")
            ],
            contains=["equity", "etf", "crypto", "commodity", "forex"]
        ),
        
        # ----------------------------------------------------------------------
        # EQUITY - Publicly traded stocks
        # FMP: Fundamentals, price, financials, analyst data
        # FMP Valuation: DCF, estimates, ratings
        # UW Market: Earnings, seasonality, short interest, correlations
        # UW Institutional: Insider, institutional, dark pool, congress trades
        # UW Options: Stock-level options analytics (stock-* datasets)
        # SEC: Filings, documents
        # ----------------------------------------------------------------------
        "equity": ObjectType(
            name="equity",
            display_name="Equity",
            provides=(
                fmp_equity_datasets |
                fmp_valuation_datasets |
                uw_market_datasets |
                uw_options_datasets |  # Options flow/greek data for equities
                # All stock-applicable institutional datasets (insider, darkpool, congress, institutional)
                {d for d in uw_institutional_datasets if d.startswith((
                    "insider-", "institution-", "darkpool-", "congress-"
                ))} |
                # Stock-level options analytics from UW (use ticker identifier)
                {d for d in uw_options_datasets if d.startswith("stock-")} |
                # SEC filings
                {"search-filings", "get-filing", "filing-sections", "filing-exhibits"} |
                # ESG datasets from tradeflow_catalog (symbol-specific only)
                {"esg-disclosures"} |
                # Additional FMP endpoints requiring symbol
                {"key-executives", "acquisition-of-beneficial-ownership", "funds-disclosure",
                 "funds-disclosure-dates", "insider-trading-statistics"} |
                # FMP TradeFlow symbol-based institutional and fund datasets
                {"funds-disclosure-holders-latest", "funds-disclosure-holders-search",
                 "institutional-ownership-extract-analytics-holder",
                 "institutional-ownership-symbol-positions-summary"} |
                # FMP TradeFlow CIK/name-based datasets (also accessible via equity)
                {"institutional-ownership-dates", "institutional-ownership-extract",
                 "institutional-ownership-holder-performance-summary",
                 "institutional-ownership-holder-industry-breakdown",
                 "insider-trading-reporting-name", "mergers-acquisitions-search"} |
                # Market-wide FMP endpoints also accessible from equity context
                {"dcf-bulk", "stock-screener", "house-trades"} |
                # Market-wide options flow accessible via equity
                {"flow-alerts", "net-flow-expiry", "screener-option-contracts"} |
                # Option contract-level data (accessible via contract ID derived from stock)
                {"option-contract-flow", "option-contract-historic", 
                 "option-contract-intraday", "option-contract-volume-profile"}
            ),
            data_sources=[
                DataSource(server="FMPMarketDataServer", catalog_path="fmp/ddc_catalog.json"),
                DataSource(server="FMPAdvancedValuationServer", catalog_path="fmp/valuation_catalog.json"),
                DataSource(server="FMPTradeFlowServer", catalog_path="fmp/tradeflow_catalog.json"),
                DataSource(server="UWMarketServer", catalog_path="unusualwhales/uw_market_catalog.json"),
                DataSource(server="UWInstitutionalServer", catalog_path="unusualwhales/uw_institutional_catalog.json"),
                DataSource(server="UWOptionsServer", catalog_path="unusualwhales/uw_options_catalog.json"),
                DataSource(server="SECFilingServer"),
            ]
        ),
        
        # ----------------------------------------------------------------------
        # EQUITY OPTIONS - Options on equities (nested under equity)
        # Polygon: Contract data, chains, trades, quotes, snapshots
        # UW Options: Flow, GEX, IV, max pain, NOPE, screeners
        # ----------------------------------------------------------------------
        "equity_options": ObjectType(
            name="equity_options",
            display_name="Equity Options",
            provides=(
                polygon_options_datasets |
                uw_options_datasets
            ),
            data_sources=[
                DataSource(server="PolygonOptionsFuturesServer", catalog_path="polygon/polygon_ddc_catalog.json", asset_class_filter="options"),
                DataSource(server="UWOptionsServer", catalog_path="unusualwhales/uw_options_catalog.json"),
            ],
            parent="equity"
        ),
        
        # ----------------------------------------------------------------------
        # ETF - Exchange-traded funds
        # FMP: Price, profile (shared with equity)
        # FMP TradeFlow: Holdings, sector weightings
        # UW Institutional: ETF exposure, holdings, flows
        # UW Options: ETF tide (options flow on ETFs)
        # ----------------------------------------------------------------------
        "etf": ObjectType(
            name="etf",
            display_name="ETF",
            provides=(
                fmp_etf_datasets |
                # Shared equity price/profile datasets including all chart intervals
                {"company-quote", "company-profile", "historical-price-full", 
                 "historical-chart-1day", "historical-chart-1min", "historical-chart-5min",
                 "historical-chart-15min", "historical-chart-30min", "historical-chart-1hour",
                 "historical-chart-4hour", "stock-price-change"} |
                # ETF-specific UW datasets
                {d for d in uw_institutional_datasets if d.startswith("etf-")} |
                # ETF tide from UW Options
                {"etf-tide"}
            ),
            data_sources=[
                DataSource(server="FMPTradeFlowServer", catalog_path="fmp/tradeflow_catalog.json", class_filter="etf"),
                DataSource(server="FMPMarketDataServer", catalog_path="fmp/ddc_catalog.json"),
                DataSource(server="UWInstitutionalServer", catalog_path="unusualwhales/uw_institutional_catalog.json"),
                DataSource(server="UWOptionsServer", catalog_path="unusualwhales/uw_options_catalog.json"),
            ]
        ),
        
        # ----------------------------------------------------------------------
        # CRYPTO - Cryptocurrencies
        # FMP Alternatives: Quotes, historical prices
        # FMP MarketData: News (crypto-news uses get_fields via ddc_catalog)
        # Polygon: Aggregates, snapshots, trades, technical indicators
        # ----------------------------------------------------------------------
        "crypto": ObjectType(
            name="crypto",
            display_name="Crypto",
            provides=(
                fmp_crypto_datasets |
                polygon_crypto_datasets |
                {"crypto-news", "crypto-news-latest", "crypto-list"} |  # FMP news + reference list
                # Polygon technical indicators (subscription-limited, but include for consistency)
                {"crypto-indicator-ema", "crypto-indicator-macd", "crypto-indicator-rsi", "crypto-indicator-sma"}
            ),
            data_sources=[
                DataSource(server="FMPAlternativesServer", catalog_path="fmp/alternatives_catalog.json", class_filter="crypto"),
                DataSource(server="FMPMarketDataServer", catalog_path="fmp/ddc_catalog.json"),  # For news
                DataSource(server="PolygonCryptoFXServer", catalog_path="polygon/polygon_ddc_catalog.json", asset_class_filter="crypto"),
            ]
        ),
        
        # ----------------------------------------------------------------------
        # COMMODITY - Physical commodities (gold, oil, etc.)
        # FMP Alternatives: Quotes, historical prices
        # ----------------------------------------------------------------------
        "commodity": ObjectType(
            name="commodity",
            display_name="Commodity",
            provides=fmp_commodity_datasets,
            data_sources=[
                DataSource(server="FMPAlternativesServer", catalog_path="fmp/alternatives_catalog.json", class_filter="commodities"),
            ]
        ),
        
        # ----------------------------------------------------------------------
        # FOREX - Currency pairs
        # FMP Alternatives: Quotes, historical prices
        # FMP MarketData: News (forex-news uses get_fields via ddc_catalog)
        # Polygon: Aggregates, snapshots, quotes, technical indicators
        # ----------------------------------------------------------------------
        "forex": ObjectType(
            name="forex",
            display_name="Forex",
            provides=(
                fmp_forex_datasets |
                polygon_forex_datasets |
                {"forex-news", "forex-news-latest", "forex-list"} |  # FMP news + reference list
                # Polygon technical indicators (subscription-limited, but include for consistency)
                {"forex-indicator-ema", "forex-indicator-macd", "forex-indicator-rsi", "forex-indicator-sma"}
            ),
            data_sources=[
                DataSource(server="FMPAlternativesServer", catalog_path="fmp/alternatives_catalog.json", class_filter="forex"),
                DataSource(server="FMPMarketDataServer", catalog_path="fmp/ddc_catalog.json"),  # For news
                DataSource(server="PolygonCryptoFXServer", catalog_path="polygon/polygon_ddc_catalog.json", asset_class_filter="forex"),
            ]
        ),
        
        # ----------------------------------------------------------------------
        # MARKET - Market-wide data (no symbol required)
        # Aggregated data across all securities: congress trades, dark pool,
        # insider activity, market-wide indicators
        # ----------------------------------------------------------------------
        "market": ObjectType(
            name="market",
            display_name="Market Wide",
            provides=(
                # UW Institutional - ALL datasets (market-wide accessible)
                uw_institutional_datasets |
                # UW Market - ALL datasets  
                uw_market_datasets |
                # UW Options - market-wide and group-based datasets
                {"market-oi-change", "market-total-options-volume", "net-flow-expiry", 
                 "flow-alerts", "screener-option-contracts", "market-tide", "sector-tide",
                 "group-greek-flow", "group-greek-flow-by-expiry", "etf-tide"} |
                # FMP MarketData market-wide datasets
                {"sector-performance", "industry-performance", "stock-screener",
                 "biggest-gainers", "biggest-losers", "most-actives",
                 "sector-pe-snapshot", "industry-pe-snapshot",
                 "historical-sector-pe", "historical-industry-pe",
                 "market-risk-premium", "economic-calendar", "ipo-calendar", 
                 "ipo-confirmed", "earnings-calendar", "stock-news",
                 "senate-disclosure", "house-disclosure", "dcf-bulk", "treasury",
                 # Market-wide news endpoints
                 "general-news-latest", "stock-news-latest", "crypto-news-latest",
                 "forex-news-latest", "press-releases-latest", "fmp-articles",
                 "rss-feed", "rss-feed-8k", "grades-latest-news", "price-target-latest-news",
                 "insider-trading", "insider-trading-rss-feed"} |
                # FMP TradeFlow market-wide datasets (congressional, insider, institutional, M&A, IPO)
                {"senate-latest", "house-latest", "senate-trading", "house-trades",
                 "senate-trades-by-name", "house-trades-by-name",
                 "insider-trading-latest", "insider-trading-search", "insider-trading-transaction-type",
                 "insider-trading-reporting-name",  # Name-based insider search
                 "institutional-ownership-latest", "institutional-ownership-industry-summary",
                 "institutional-ownership-dates", "institutional-ownership-extract",  # CIK-based
                 "institutional-ownership-holder-performance-summary",
                 "institutional-ownership-holder-industry-breakdown",
                 "mergers-acquisitions-latest", "mergers-acquisitions-search",
                 "ipos-disclosure", "ipos-prospectus", "esg-benchmark"} |
                # Polygon market-wide reference endpoints
                {"marketstatus-now", "marketstatus-upcoming", "reference-conditions", 
                 "reference-exchanges", "snapshot-unified"}
            ),
            data_sources=[
                DataSource(server="UWInstitutionalServer", catalog_path="unusualwhales/uw_institutional_catalog.json"),
                DataSource(server="UWMarketServer", catalog_path="unusualwhales/uw_market_catalog.json"),
                DataSource(server="UWOptionsServer", catalog_path="unusualwhales/uw_options_catalog.json"),
                DataSource(server="FMPMarketDataServer", catalog_path="fmp/ddc_catalog.json"),
                DataSource(server="FMPTradeFlowServer", catalog_path="fmp/tradeflow_catalog.json"),
                DataSource(server="FMPAdvancedValuationServer", catalog_path="fmp/valuation_catalog.json"),  # For dcf-bulk
                DataSource(server="PolygonCryptoFXServer", catalog_path="polygon/polygon_ddc_catalog.json"),
            ]
        ),
        
        # ----------------------------------------------------------------------
        # MACRO SERIES - Economic indicators (GDP, CPI, rates, etc.)
        # EconomicDataServer: FRED API for economic data
        # ----------------------------------------------------------------------
        "macro_series": ObjectType(
            name="macro_series",
            display_name="Macro Series",
            provides={"search-series", "get-series", "get-releases", "series-metadata"},
            data_sources=[
                DataSource(server="EconomicDataServer"),
            ]
        ),
        
    }


# Build registry at module load time
OBJECT_REGISTRY: Dict[str, ObjectType] = _build_object_registry()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_object_type(name: str) -> Optional[ObjectType]:
    """Get an object type by name. Supports aliases."""
    # Alias mapping for backward compatibility
    aliases = {
        "macro": "market",  # 'macro' from bulk test maps to 'market' 
    }
    resolved_name = aliases.get(name, name)
    return OBJECT_REGISTRY.get(resolved_name)


def get_all_object_types() -> List[ObjectType]:
    """Get all registered object types."""
    return list(OBJECT_REGISTRY.values())


def list_object_types() -> List[str]:
    """Get all registered object type names."""
    return list(OBJECT_REGISTRY.keys())


def get_combined_capabilities(object_names: List[str]) -> Set[str]:
    """Get the union of capabilities from multiple object types."""
    combined = set()
    for name in object_names:
        obj = get_object_type(name)
        if obj:
            combined |= obj.provides
    return combined


def get_object_with_parent_capabilities(name: str) -> Set[str]:
    """Get capabilities including parent object's capabilities."""
    obj = get_object_type(name)
    if not obj:
        return set()
    
    capabilities = obj.provides.copy()
    
    # Add parent capabilities
    if obj.parent:
        parent = get_object_type(obj.parent)
        if parent:
            capabilities |= parent.provides
    
    return capabilities


def get_nested_types(parent_name: str) -> List[ObjectType]:
    """Get all object types nested under a parent."""
    return [obj for obj in OBJECT_REGISTRY.values() if obj.parent == parent_name]


def get_objects_providing(dataset: str) -> List[ObjectType]:
    """Find all object types that provide a specific dataset."""
    return [obj for obj in OBJECT_REGISTRY.values() if dataset in obj.provides]


def get_expanded_capabilities(name: str, include_nested: bool = True) -> Set[str]:
    """
    Get all capabilities for an object, including:
    - Its own capabilities
    - Capabilities of contained types (e.g., portfolio contains equity)
    - Optionally, capabilities of nested types (e.g., equity -> equity_options)
    
    Args:
        name: Object type name
        include_nested: Whether to include nested type capabilities
        
    Returns:
        Set of all available dataset names
    """
    obj = get_object_type(name)
    if not obj:
        return set()
    
    capabilities = obj.provides.copy()
    
    # Add capabilities from contained types
    if obj.contains:
        for contained_name in obj.contains:
            contained = get_object_type(contained_name)
            if contained:
                capabilities |= contained.provides
                # Also include nested types of contained objects
                if include_nested:
                    for nested in get_nested_types(contained_name):
                        capabilities |= nested.provides
    
    # Add capabilities from parent (for nested types accessing parent data)
    if obj.parent:
        parent = get_object_type(obj.parent)
        if parent:
            capabilities |= parent.provides
    
    # Add capabilities from nested types
    if include_nested:
        for nested in get_nested_types(name):
            capabilities |= nested.provides
    
    return capabilities


def get_all_data_sources(name: str) -> List[DataSource]:
    """
    Get all data sources for an object, including from contained types.
    """
    obj = get_object_type(name)
    if not obj:
        return []
    
    sources = list(obj.data_sources)
    
    # Add data sources from contained types
    if obj.contains:
        for contained_name in obj.contains:
            contained = get_object_type(contained_name)
            if contained:
                sources.extend(contained.data_sources)
    
    # Deduplicate by server name
    seen = set()
    unique_sources = []
    for src in sources:
        if src.server not in seen:
            seen.add(src.server)
            unique_sources.append(src)
    
    return unique_sources
