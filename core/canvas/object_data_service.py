"""
Object Data Service - Unified interface for fetching data.

Provides a single interface for fetching data by:
- Category (e.g., "Valuation" -> all valuation metrics)
- Specific fields (e.g., ["priceEarningsRatioTTM", "priceToBookRatioTTM"])
- Dataset (e.g., "ratios-ttm")

Automatically routes to the correct MCP server based on object registry.
Includes intelligent caching with different TTLs by data type.
"""

import os
import json
import logging
import time
import datetime
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple

from .object_registry import get_object_type, get_all_data_sources, DataSource
from .object_type_detector import ObjectTypeDetector, ObjectTypeResult
from .data_categories import get_datasets_for_category, get_category_for_dataset
from .field_mappings import resolve_endpoint_alias
from core.utils.mcp_result_parser import safe_extract_content, safe_parse_json

logger = logging.getLogger(__name__)


# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

# TTL in seconds by dataset type
CACHE_TTL = {
    # Price & real-time data: 15 minutes
    "quote": 900,
    "quote-short": 900,
    "price-change": 900,
    "historical-price-full": 900,
    "crypto-historical-eod-full": 900,  # Crypto daily OHLCV
    "forex-historical-eod-full": 900,   # Forex daily OHLCV
    "commodities-historical-eod-full": 900,  # Commodities daily OHLCV
    "intraday": 300,  # 5 minutes for intraday
    
    # Fundamentals: 24 hours (updated after market close)
    "ratios-ttm": 86400,
    "ratios": 86400,
    "key-metrics-ttm": 86400,
    "key-metrics": 86400,
    "income-statement": 86400,
    "balance-sheet-statement": 86400,
    "cash-flow-statement": 86400,
    "financial-growth": 86400,
    "enterprise-values": 86400,
    "discounted-cash-flow": 86400,
    
    # Analyst & estimates: 6 hours
    "analyst-estimates": 21600,
    "analyst-stock-recommendations": 21600,
    "price-target": 21600,
    "price-target-summary": 21600,
    "upgrades-downgrades": 21600,
    
    # Profile & static: 7 days
    "profile": 604800,
    "key-executives": 604800,
    "stock-peers": 604800,
    "company-core-information": 604800,
    
    # Ownership: 24 hours (13F updates quarterly, but check daily)
    "institutional-holder": 86400,
    "mutual-fund-holder": 86400,
    "insider-trading": 86400,
    
    # Earnings: 24 hours
    "earnings": 86400,
    "earnings-surprises": 86400,
    "earnings-calendar": 86400,
    
    # ETF specific: 24 hours
    "etf-holder": 86400,
    "etf-sector-weightings": 86400,
    "etf-country-weightings": 86400,
    
    # News & sentiment: 1 hour
    "stock-news": 3600,
    "press-releases": 3600,
    "social-sentiment": 3600,
    
    # Dividends: 24 hours
    "historical-price-full-dividends": 86400,
    "stock-dividend-calendar": 86400,
    
    # Technical: 15 minutes
    "technical-indicator": 900,
    
    # Default for unknown: 1 hour
    "_default": 3600,
}


@dataclass
class CacheEntry:
    """A cached data entry with expiration."""
    data: Dict[str, Any]
    timestamp: float
    ttl: int
    
    def is_expired(self) -> bool:
        return time.time() > (self.timestamp + self.ttl)
    
    def age_seconds(self) -> float:
        return time.time() - self.timestamp


class DataCache:
    """In-memory cache for fetched data with per-dataset TTLs."""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, symbol: str, server: str, dataset: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Cache key MUST include server and params to avoid collisions.
        Otherwise the explorer will return "random" results (stale cache from a different query).
        """
        params_sig = ""
        if params:
            try:
                normalized = json.dumps(params, sort_keys=True, default=str, separators=(",", ":"))
                params_sig = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
            except Exception:
                # If params aren't JSON-serializable, still separate entries by a coarse signature
                params_sig = hashlib.sha256(repr(params).encode("utf-8")).hexdigest()[:16]
        return f"{symbol.upper()}:{server}:{dataset}:{params_sig}"
    
    def _get_ttl(self, dataset: str) -> int:
        """Get TTL for a dataset type."""
        # Try exact match first
        if dataset in CACHE_TTL:
            return CACHE_TTL[dataset]
        # Try prefix match
        for key, ttl in CACHE_TTL.items():
            if dataset.startswith(key):
                return ttl
        return CACHE_TTL["_default"]
    
    def get(self, symbol: str, server: str, dataset: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Get cached data if valid."""
        key = self._make_key(symbol, server, dataset, params)
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        return entry.data
    
    def set(self, symbol: str, server: str, dataset: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> None:
        """Cache data with appropriate TTL."""
        key = self._make_key(symbol, server, dataset, params)
        ttl = self._get_ttl(dataset)
        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=ttl,
        )
        logger.debug(f"Cached {key} with TTL {ttl}s")
    
    def get_multi(
        self,
        symbol: str,
        server: str,
        datasets: List[str],
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Get multiple datasets, returning cached data and list of missing datasets.
        
        Returns:
            (cached_data, missing_datasets)
        """
        cached = {}
        missing = []
        
        for ds in datasets:
            data = self.get(symbol, server, ds, params)
            if data is not None:
                cached[ds] = data
            else:
                missing.append(ds)
        
        return cached, missing
    
    def invalidate(self, symbol: str, dataset: Optional[str] = None) -> None:
        """Invalidate cache for symbol, optionally specific dataset."""
        if dataset:
            # Best-effort: remove all servers/params variants for that dataset
            prefix = f"{symbol.upper()}:"
            keys_to_delete = [k for k in self._cache if k.startswith(prefix) and f":{dataset}:" in k]
            for k in keys_to_delete:
                del self._cache[k]
        else:
            # Invalidate all for symbol
            prefix = f"{symbol.upper()}:"
            keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._cache[k]
    
    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
        }


# Global cache instance
_cache = DataCache()


@dataclass
class FetchResult:
    """Result of a data fetch operation."""
    success: bool
    symbol: str
    object_type: str
    data: Dict[str, Any]
    datasets_fetched: List[str]
    errors: List[str]
    cache_info: Dict[str, str] = field(default_factory=dict)
    fetched_at: float = field(default_factory=time.time)
    datasets_failed: Dict[str, str] = field(default_factory=dict)  # dataset -> reason
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "symbol": self.symbol,
            "object_type": self.object_type,
            "data": self.data,
            "datasets_fetched": self.datasets_fetched,
            "errors": self.errors,
            "cache_info": self.cache_info,
            "fetched_at": self.fetched_at,
            "datasets_failed": self.datasets_failed,
        }


class ObjectDataService:
    """
    Unified service for fetching data from MCP servers.
    
    Routes requests to the appropriate MCP server based on
    the object registry configuration.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self._detector = ObjectTypeDetector(api_key=self.api_key)
        self._servers: Dict[str, Any] = {}
        self._field_manager = None
    
    def _get_field_manager(self):
        """Lazy load field manager."""
        if self._field_manager is None:
            from core.mcp_servers.fmp.field_map_manager import FieldMapManager
            self._field_manager = FieldMapManager()
        return self._field_manager
    
    async def _get_server(self, server_name: str):
        """Get or create an MCP server instance."""
        if server_name in self._servers:
            return self._servers[server_name]
        
        # Lazy import and instantiate servers
        server = None
        
        if server_name == "FMPMarketDataServer":
            from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
            server = FMPMarketDataServer(api_key=self.api_key)
            await server.connect()
        
        elif server_name == "FMPAlternativesServer":
            from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
            server = FMPAlternativesServer(api_key=self.api_key)
            await server.connect()
        
        elif server_name == "FMPTradeFlowServer":
            from core.mcp_servers.fmp.FMPTradeFlowServer import FMPTradeFlowServer
            server = FMPTradeFlowServer(api_key=self.api_key)
            await server.connect()
        
        elif server_name == "FMPAdvancedValuationServer":
            from core.mcp_servers.fmp.FMPAdvancedValuationServer import FMPAdvancedValuationServer
            server = FMPAdvancedValuationServer(api_key=self.api_key)
            await server.connect()
        
        elif server_name == "EconomicDataServer":
            from core.mcp_servers.EconomicDataServer import EconomicDataServer
            server = EconomicDataServer()
            await server.connect()

        elif server_name == "PolygonCryptoFXServer":
            from core.mcp_servers.polygon.PolygonCryptoFXServer import PolygonCryptoFXServer
            server = PolygonCryptoFXServer()
            await server.connect()

        elif server_name == "PolygonOptionsFuturesServer":
            from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
            server = PolygonOptionsFuturesServer()
            await server.connect()

        elif server_name == "UWMarketServer":
            from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
            server = UWMarketServer()
            await server.connect()

        elif server_name == "UWInstitutionalServer":
            from core.mcp_servers.unusualwhales.UWInstitutionalServer import UWInstitutionalServer
            server = UWInstitutionalServer()
            await server.connect()

        elif server_name == "UWOptionsServer":
            from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
            server = UWOptionsServer()
            await server.connect()

        elif server_name == "SECFilingServer":
            from core.mcp_servers.SECFilingServer import SECFilingServer
            server = SECFilingServer()
            await server.connect()

        elif server_name == "YFinanceServer":
            from core.mcp_servers.YFinanceServer import YFinanceServer
            server = YFinanceServer()
            await server.connect()
        
        if server:
            self._servers[server_name] = server
        
        return server
    
    async def _fetch_from_server(
        self,
        server,
        server_name: str,
        symbol: str,
        datasets: List[str],
        use_cache: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str], Dict[str, str]]:
        """
        Fetch data from a specific MCP server with caching.
        
        Args:
            server: MCP server instance
            symbol: Ticker symbol
            datasets: List of datasets to fetch
            use_cache: Whether to use cache (default True)
            params: Optional dict of params (from, to, period, limit) to pass to endpoints
            
        Returns:
            Tuple of (data_dict, metadata_dict, failed_dict) where:
            - data_dict: Successfully fetched data by dataset
            - metadata_dict: Cache status per dataset (cached/fetched)
            - failed_dict: Failed datasets with reason
        """
        result_data = {}
        metadata = {}
        failed = {}
        fetch_params = params or {}
        
        # Helper to flatten nested Polygon indicator responses
        def flatten_indicator_data(ds_data):
            """Flatten nested indicator responses with 'values' array."""
            if isinstance(ds_data, dict) and "values" in ds_data and isinstance(ds_data["values"], list):
                values_array = ds_data["values"]
                if values_array and isinstance(values_array[0], dict) and "timestamp" in values_array[0]:
                    return values_array
            return ds_data
        
        # Check cache first
        if use_cache:
            cached, missing = _cache.get_multi(symbol, server_name, datasets, fetch_params)
            if cached:
                for ds, data in cached.items():
                    # Apply flattening to cached data too
                    result_data[ds] = flatten_indicator_data(data)
                    metadata[ds] = "cached"
                logger.debug(f"Cache hit for {symbol}: {list(cached.keys())}")
            datasets_to_fetch = missing
        else:
            datasets_to_fetch = datasets
        
        # Fetch missing datasets
        if datasets_to_fetch:
            try:
                # Some MCP servers (e.g., SEC filings) don't expose `get_fields`.
                # We skip them here so they don't pollute results with tool errors.
                if not self._server_supports_tool(server, "get_fields"):
                    for ds in datasets_to_fetch:
                        failed[ds] = "server_does_not_support_get_fields"
                    return result_data, metadata, failed

                # Get endpoint metadata from registry to determine identifier param
                from core.canvas.canvas_field_registry import get_field_registry
                try:
                    canvas_registry = get_field_registry()
                except Exception:
                    canvas_registry = None
                
                # Build smart params based on endpoint requirements
                smart_params = dict(fetch_params)
                
                # Check first dataset for cardinality and required_params
                # (ideally we'd check each, but for now they're usually consistent per batch)
                first_ds = datasets_to_fetch[0]
                endpoint_meta = None
                if canvas_registry:
                    try:
                        endpoint_meta = canvas_registry.get_endpoint_metadata(first_ds)
                    except Exception:
                        pass
                
                # Determine if we should pass the symbol and under what key
                identifier_key = "symbol"
                should_pass_identifier = True
                
                if endpoint_meta:
                    cardinality = endpoint_meta.get("cardinality", "single")
                    required_params = endpoint_meta.get("required_params") or []
                    req_params_lower = [p.lower() for p in required_params]
                    
                    # Market-wide endpoints (cardinality=none) don't need symbol
                    if cardinality == "none":
                        should_pass_identifier = False
                    # Polygon/UW use 'ticker' instead of 'symbol'
                    elif "ticker" in req_params_lower and "symbol" not in req_params_lower:
                        identifier_key = "ticker"
                    # Multi-ticker endpoints
                    elif "tickers" in req_params_lower:
                        identifier_key = "tickers"
                    # Options use 'options_ticker'
                    elif "options_ticker" in req_params_lower:
                        identifier_key = "options_ticker"
                    # Forex uses 'fx_ticker'
                    elif "fx_ticker" in req_params_lower:
                        identifier_key = "fx_ticker"
                    # Crypto uses 'crypto_ticker'
                    elif "crypto_ticker" in req_params_lower:
                        identifier_key = "crypto_ticker"
                    # Some news endpoints use 'symbols' (plural)
                    elif "symbols" in req_params_lower and "symbol" not in req_params_lower:
                        identifier_key = "symbols"
                    # Name-based lookups (congress, insiders, etc.)
                    elif "name" in req_params_lower and "symbol" not in req_params_lower:
                        identifier_key = "name"
                    # CIK-based lookups (institutional)
                    elif "cik" in req_params_lower and "symbol" not in req_params_lower:
                        identifier_key = "cik"
                    # ID-based lookups
                    elif "id" in req_params_lower and "symbol" not in req_params_lower:
                        identifier_key = "id"
                
                # Build the call args
                call_args = {
                    "datasets": datasets_to_fetch,
                    "params": smart_params,
                    "_bh_raw": True,
                }
                
                # Only add identifier if needed
                if should_pass_identifier:
                    call_args[identifier_key] = symbol
                    # Also pass as 'symbol' for backward compatibility with FMP server
                    if identifier_key != "symbol":
                        call_args["symbol"] = symbol
                
                # Pass params to the MCP server
                result = await server.call_tool("get_fields", call_args)
                
                # Parse the result with the shared MCP parser instead of assuming raw JSON text.
                if result and hasattr(result, "content") and result.content:
                    parsed = safe_parse_json(result, default={})

                    # Some providers may return a raw array or plain text wrapper. Preserve that
                    # as a source-specific failure instead of throwing away the whole fetch pass.
                    if not parsed:
                        raw_content = safe_extract_content(result)
                        preview = (raw_content or "").strip()[:120]
                        if preview:
                            for ds in datasets_to_fetch:
                                failed[ds] = f"unparseable_response: {preview}"
                        else:
                            for ds in datasets_to_fetch:
                                failed[ds] = "empty_or_unparseable_response"
                        return result_data, metadata, failed

                    # Handle nested structure
                    if "datasets" in parsed:
                        for ds_name, ds_value in parsed["datasets"].items():
                            # Check for error in individual dataset
                            if isinstance(ds_value, dict) and "error" in ds_value:
                                error_detail = ds_value.get('details') or ds_value.get('required_params') or 'unknown'
                                error_type = ds_value.get('error', 'fetch_failed')
                                logger.warning(f"Dataset {ds_name} failed: {error_type} - {error_detail}")
                                failed[ds_name] = f"{error_type}: {error_detail}"
                                continue

                            if isinstance(ds_value, dict) and "data" in ds_value:
                                ds_data = ds_value["data"]
                            else:
                                ds_data = ds_value

                            # Check if data is empty or None
                            if not ds_data:
                                failed[ds_name] = "empty_response"
                                continue

                            # Flatten nested Polygon indicator responses
                            ds_data = flatten_indicator_data(ds_data)

                            result_data[ds_name] = ds_data
                            metadata[ds_name] = "fetched"

                            # Cache the result
                            if use_cache and ds_data:
                                _cache.set(symbol, server_name, ds_name, ds_data, fetch_params)
                    else:
                        # Single dataset response
                        for ds in datasets_to_fetch:
                            if ds in parsed:
                                result_data[ds] = parsed[ds]
                                metadata[ds] = "fetched"
                                if use_cache and parsed[ds]:
                                    _cache.set(symbol, server_name, ds, parsed[ds], fetch_params)
                            else:
                                failed[ds] = "not_in_response"
                    
                    # Track unfulfilled datasets
                    if "unfulfilled" in parsed:
                        for ds_name, reason in parsed["unfulfilled"].items():
                            if isinstance(reason, dict):
                                error_type = reason.get('error', 'unfulfilled')
                                error_detail = reason.get('details') or reason.get('required_params') or ''
                                failed[ds_name] = f"{error_type}: {error_detail}"
                            else:
                                failed[ds_name] = str(reason)
                            # Use DEBUG level to avoid log spam for expected parameter issues
                            logger.debug(f"Dataset {ds_name} unfulfilled: {failed[ds_name]}")
                
            except Exception as e:
                logger.error(f"Error fetching from server: {e}")
                for ds in datasets_to_fetch:
                    failed[ds] = f"exception: {str(e)}"
                return {"error": str(e)}, {"error": str(e)}, failed
        
        return result_data, metadata, failed

    @staticmethod
    def _server_supports_tool(server: Any, tool_name: str) -> bool:
        """
        Best-effort introspection for MCP servers.
        Avoids async list_tools() since we don't have run_context/agent here.
        """
        try:
            # Check MCPTool list first (FMP pattern)
            if hasattr(server, "get_available_tools"):
                tools = server.get_available_tools()
                if any(getattr(t, "name", None) == tool_name for t in tools):
                    return True
            if hasattr(server, "get_tools"):
                tools = server.get_tools()
                if any(isinstance(t, dict) and t.get("name") == tool_name for t in tools):
                    return True
            # Check for handler method directly (UW pattern: _handle_get_fields)
            handler_method = f"_handle_{tool_name}"
            if hasattr(server, handler_method) and callable(getattr(server, handler_method)):
                return True
        except Exception:
            return False
        return False

    async def _fetch_via_object_sources(
        self,
        symbol: str,
        datasets: List[str],
        object_type: str,
        force_refresh: bool,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str], Dict[str, str], List[str]]:
        """
        Attempt to fetch datasets by trying the object's declared data sources in order.
        Returns: (data, cache_info, failed, errors)
        """
        obj = get_object_type(object_type)
        if not obj:
            return {}, {}, {ds: "unknown_object_type" for ds in datasets}, [f"Unknown object type: {object_type}"]

        remaining = list(datasets)
        all_data: Dict[str, Any] = {}
        cache_info: Dict[str, str] = {}
        failed: Dict[str, str] = {}
        errors: List[str] = []

        sources = get_all_data_sources(object_type)
        for src in sources:
            if not remaining:
                break

            server = await self._get_server(src.server)
            if not server:
                continue
            supports_tool = self._server_supports_tool(server, "get_fields")
            if not supports_tool:
                continue

            data, metadata, src_failed = await self._fetch_from_server(
                server=server,
                server_name=src.server,
                symbol=symbol,
                datasets=remaining,
                use_cache=not force_refresh,
                params=params,
            )

            if "error" in data:
                errors.append(data.get("error", "Unknown error"))
                # Don't mark everything failed yet; other sources might satisfy.
                continue

            # Merge successes
            for ds, ds_data in data.items():
                all_data[ds] = ds_data
                # If any earlier source marked this dataset as failed, clear it now
                failed.pop(ds, None)
            cache_info.update(metadata)

            # Merge failures but keep trying other sources
            # Prefer specific API errors (403, rate limit) over generic "not found" errors
            GENERIC_ERRORS = {"dataset_not_found", "server_does_not_support_get_fields", "not_in_response"}
            for ds, reason in src_failed.items():
                existing_reason = failed.get(ds)
                if existing_reason is None:
                    # No existing error, set this one
                    failed[ds] = reason
                elif any(generic in existing_reason for generic in GENERIC_ERRORS):
                    # Existing error is generic, prefer the new (possibly more specific) error
                    # unless the new one is also generic
                    if not any(generic in reason for generic in GENERIC_ERRORS):
                        failed[ds] = reason
                # Otherwise keep the existing (more specific) error

            # Update remaining datasets
            remaining = [ds for ds in remaining if ds not in all_data]

        # Anything still remaining never succeeded anywhere
        for ds in remaining:
            failed.setdefault(ds, "not_available_in_sources")

        return all_data, cache_info, failed, errors
    
    async def detect_type(self, symbol: str) -> ObjectTypeResult:
        """Detect the object type for a symbol."""
        return await self._detector.detect(symbol)
    
    async def fetch_category(
        self,
        symbol: str,
        category: str,
        object_type: Optional[str] = None,
        force_refresh: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> FetchResult:
        """
        Fetch all data for a category.
        
        Args:
            symbol: The ticker symbol
            category: Category name (e.g., "Valuation")
            object_type: Optional - will be detected if not provided
            force_refresh: Bypass cache and fetch fresh data
            params: Optional dict of params (from, to, period, limit)
            
        Returns:
            FetchResult with all data for the category
        """
        errors = []
        
        # Detect object type if not provided
        if not object_type:
            type_result = await self.detect_type(symbol)
            object_type = type_result.object_type
        
        # Get datasets for this category
        datasets = get_datasets_for_category(category)
        if not datasets:
            return FetchResult(
                success=False,
                symbol=symbol,
                object_type=object_type,
                data={},
                datasets_fetched=[],
                errors=[f"Unknown category: {category}"],
            )
        
        # Get object's available datasets
        obj = get_object_type(object_type)
        if not obj:
            return FetchResult(
                success=False,
                symbol=symbol,
                object_type=object_type,
                data={},
                datasets_fetched=[],
                errors=[f"Unknown object type: {object_type}"],
            )
        
        # Filter to datasets that the object provides
        available_datasets = [ds for ds in datasets if ds in obj.provides]
        
        if not available_datasets:
            return FetchResult(
                success=False,
                symbol=symbol,
                object_type=object_type,
                data={},
                datasets_fetched=[],
                errors=[f"No datasets available for {category} on {object_type}"],
            )
        
        all_data, cache_info, datasets_failed, src_errors = await self._fetch_via_object_sources(
            symbol=symbol,
            datasets=available_datasets,
            object_type=object_type,
            force_refresh=force_refresh,
            params=params,
        )
        errors.extend(src_errors)

        fetched_datasets = [ds for ds in available_datasets if ds in all_data]
        
        return FetchResult(
            success=len(all_data) > 0,
            symbol=symbol,
            object_type=object_type,
            data=all_data,
            datasets_fetched=fetched_datasets,
            errors=errors,
            cache_info=cache_info,
            datasets_failed=datasets_failed,
        )
    
    async def fetch_datasets(
        self,
        symbol: str,
        datasets: List[str],
        object_type: Optional[str] = None,
        force_refresh: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> FetchResult:
        """
        Fetch specific datasets.
        
        Args:
            symbol: The ticker symbol
            datasets: List of dataset names to fetch
            object_type: Optional - will be detected if not provided
            force_refresh: Bypass cache and fetch fresh data
            params: Optional dict of params (from, to, period, limit)
            
        Returns:
            FetchResult with requested data
        """
        errors = []
        
        # Detect object type if not provided
        if not object_type:
            type_result = await self.detect_type(symbol)
            object_type = type_result.object_type
        
        # Resolve endpoint aliases (e.g., historical-price-full -> crypto-historical-eod-full for crypto)
        # Keep track of original names for response mapping
        original_to_resolved: Dict[str, str] = {}
        resolved_datasets = []
        for ds in datasets:
            resolved = resolve_endpoint_alias(ds, object_type)
            original_to_resolved[ds] = resolved
            resolved_datasets.append(resolved)
        
        # Filter to datasets the object type actually provides (prevents "random" failures)
        obj = get_object_type(object_type)
        datasets_failed: Dict[str, str] = {}
        if obj:
            allowed = [ds for ds in resolved_datasets if ds in obj.provides]
            for original_ds, resolved_ds in original_to_resolved.items():
                if resolved_ds not in allowed:
                    datasets_failed[original_ds] = "not_provided_by_object_type"
            resolved_datasets = allowed

        data: Dict[str, Any] = {}
        metadata: Dict[str, str] = {}
        failed: Dict[str, str] = {}
        if resolved_datasets:
            data, metadata, failed, src_errors = await self._fetch_via_object_sources(
                symbol=symbol,
                datasets=resolved_datasets,
                object_type=object_type,
                force_refresh=force_refresh,
                params=params,
            )
            errors.extend(src_errors)
            
            # Map resolved dataset names back to original names in response
            for original_ds, resolved_ds in original_to_resolved.items():
                if resolved_ds in data and original_ds != resolved_ds:
                    data[original_ds] = data.pop(resolved_ds)
                if resolved_ds in failed and original_ds != resolved_ds:
                    failed[original_ds] = failed.pop(resolved_ds)
                    
        failed.update(datasets_failed)
        
        return FetchResult(
            success=len(data) > 0,
            symbol=symbol,
            object_type=object_type,
            data=data,
            datasets_fetched=[ds for ds in datasets if ds in data],
            errors=errors,
            cache_info=metadata,
            datasets_failed=failed,
        )
    
    async def fetch_fields(
        self,
        symbol: str,
        fields: List[str],
        object_type: Optional[str] = None,
        force_refresh: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> FetchResult:
        """
        Fetch specific fields by name.
        
        Uses the field mappings database to find which endpoints
        contain the requested fields.
        
        Args:
            symbol: The ticker symbol
            fields: List of field names to fetch
            object_type: Optional - will be detected if not provided
            force_refresh: Bypass cache and fetch fresh data
            params: Optional dict of params (from, to, period, limit)
            
        Returns:
            FetchResult with requested field values
        """
        errors = []
        
        # Detect object type if not provided
        if not object_type:
            type_result = await self.detect_type(symbol)
            object_type = type_result.object_type
        
        # Look up fields in field mappings
        fm = self._get_field_manager()
        endpoints_to_fields = fm.get_endpoints_for_fields(fields)
        
        if not endpoints_to_fields:
            return FetchResult(
                success=False,
                symbol=symbol,
                object_type=object_type,
                data={},
                datasets_fetched=[],
                errors=[f"Could not find endpoints for fields: {fields}"],
            )
        
        # Filter endpoints by object type provides (if known)
        obj = get_object_type(object_type)
        datasets_failed: Dict[str, str] = {}
        endpoints = list(endpoints_to_fields.keys())
        if obj:
            filtered = [ep for ep in endpoints if ep in obj.provides]
            for ep in endpoints:
                if ep not in filtered:
                    datasets_failed[ep] = "not_provided_by_object_type"
            endpoints = filtered

        all_data: Dict[str, Any] = {}
        fetched_datasets: List[str] = []
        cache_info: Dict[str, str] = {}

        data: Dict[str, Any] = {}
        failed: Dict[str, str] = {}
        if endpoints:
            data, cache_info, failed, src_errors = await self._fetch_via_object_sources(
                symbol=symbol,
                datasets=endpoints,
                object_type=object_type,
                force_refresh=force_refresh,
                params=params,
            )
            errors.extend(src_errors)

            # Extract just the requested fields
            for endpoint, field_list in endpoints_to_fields.items():
                endpoint_data = data.get(endpoint, {})
                if isinstance(endpoint_data, dict):
                    for field in field_list:
                        if field in endpoint_data:
                            all_data[field] = endpoint_data[field]
                elif isinstance(endpoint_data, list) and len(endpoint_data) > 0 and isinstance(endpoint_data[0], dict):
                    for field in field_list:
                        if field in endpoint_data[0]:
                            all_data[field] = endpoint_data[0][field]

            fetched_datasets = [ds for ds in endpoints if ds in data]
        failed.update(datasets_failed)
        
        return FetchResult(
            success=len(all_data) > 0,
            symbol=symbol,
            object_type=object_type,
            data=all_data,
            datasets_fetched=fetched_datasets,
            errors=errors,
            cache_info=cache_info,
            datasets_failed=failed,
        )
    
    async def search_fields(
        self,
        query: str,
        object_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for fields matching a query.
        
        Args:
            query: Search query
            object_type: Optional filter by object type
            limit: Maximum results
            
        Returns:
            List of matching fields with metadata
        """
        fm = self._get_field_manager()
        
        # SQL LIKE search
        import sqlite3
        conn = sqlite3.connect(fm.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT field_name, endpoint_name, field_type
            FROM field_mappings
            WHERE field_name LIKE ?
            ORDER BY hit_count DESC
            LIMIT ?
        """, (f"%{query}%", limit))
        
        results = []
        for row in cursor.fetchall():
            field_name, endpoint, field_type = row
            category = get_category_for_dataset(endpoint)
            
            # If object_type filter, check if endpoint is provided by that type
            if object_type:
                obj = get_object_type(object_type)
                if obj and endpoint not in obj.provides:
                    continue
            
            results.append({
                "field": field_name,
                "endpoint": endpoint,
                "type": field_type,
                "category": category,
            })
        
        conn.close()
        return results
    
    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return _cache.stats()
    
    def invalidate_cache(
        self, 
        symbol: Optional[str] = None, 
        dataset: Optional[str] = None
    ) -> None:
        """
        Invalidate cache entries.
        
        Args:
            symbol: Optional - invalidate for specific symbol
            dataset: Optional - invalidate specific dataset (requires symbol)
        """
        if symbol:
            _cache.invalidate(symbol, dataset)
        else:
            _cache.clear()
    
    def get_cache_ttl(self, dataset: str) -> int:
        """Get TTL in seconds for a dataset type."""
        return _cache._get_ttl(dataset)
    
    async def fetch_object_summary(
        self,
        symbol: str,
        object_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a quick summary of key metrics for an object card display.
        
        Returns:
            Dict with symbol, type, name, and key metrics (price, change, PE, marketCap)
        """
        # Detect type if not provided
        if not object_type:
            type_result = await self.detect_type(symbol)
            object_type = type_result.object_type
        
        result = {
            "symbol": symbol,
            "type": object_type,
            "name": None,
            "price": None,
            "change": None,
            "changePercent": None,
            "peRatio": None,
            "marketCap": None,
            "sector": None,
        }
        
        # Fetch quote data for price/change
        try:
            quote_result = await self.fetch_datasets(
                symbol=symbol,
                datasets=["company-quote"],
                object_type=object_type,
            )
            if quote_result.success and quote_result.data.get("company-quote"):
                quote = quote_result.data["company-quote"]
                if isinstance(quote, list) and len(quote) > 0:
                    quote = quote[0]
                if isinstance(quote, dict):
                    result["name"] = quote.get("name")
                    result["price"] = quote.get("price")
                    result["change"] = quote.get("change")
                    result["changePercent"] = quote.get("changesPercentage")
                    result["peRatio"] = quote.get("pe")
                    result["marketCap"] = quote.get("marketCap")
        except Exception as e:
            logger.warning(f"Failed to fetch quote for {symbol}: {e}")
        
        # Try to get profile for sector if quote didn't have it
        if not result["sector"] and object_type in ["equity", "etf"]:
            try:
                profile_result = await self.fetch_datasets(
                    symbol=symbol,
                    datasets=["company-profile"],
                    object_type=object_type,
                )
                if profile_result.success and profile_result.data.get("company-profile"):
                    profile = profile_result.data["company-profile"]
                    if isinstance(profile, list) and len(profile) > 0:
                        profile = profile[0]
                    if isinstance(profile, dict):
                        result["sector"] = profile.get("sector")
                        if not result["name"]:
                            result["name"] = profile.get("companyName")
            except Exception as e:
                logger.debug(f"Failed to fetch profile for {symbol}: {e}")
        
        # Fetch PE ratio from ratios-ttm if not present in quote
        if result["peRatio"] is None and object_type in ["equity"]:
            try:
                ratios_result = await self.fetch_datasets(
                    symbol=symbol,
                    datasets=["ratios-ttm"],
                    object_type=object_type,
                )
                if ratios_result.success and ratios_result.data.get("ratios-ttm"):
                    ratios = ratios_result.data["ratios-ttm"]
                    if isinstance(ratios, list) and len(ratios) > 0:
                        ratios = ratios[0]
                    if isinstance(ratios, dict):
                        result["peRatio"] = ratios.get("peRatioTTM") or ratios.get("priceEarningsRatioTTM")
            except Exception as e:
                logger.debug(f"Failed to fetch ratios for {symbol}: {e}")
        
        return result
    
    async def fetch_pivoted_snapshot(
        self,
        symbols: List[str],
        fields: List[str],
        object_type: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch data for multiple symbols and return as a pivoted table.
        
        Args:
            symbols: List of ticker symbols
            fields: List of field names to fetch
            object_type: Optional object type (auto-detected if not provided)
            params: Optional dict of params (from, to, period, limit)
        
        Returns:
            Dict with:
            - columns: ["symbol", field1, field2, ...]
            - data: [[symbol1, val1, val2], [symbol2, val1, val2], ...]
            - errors: list of error messages
        """
        # First, resolve fields to datasets
        field_to_dataset = await self.resolve_fields_to_datasets(fields)
        
        # Determine unique datasets needed
        datasets_needed = list(set(field_to_dataset.values()))
        
        columns = ["symbol"] + fields
        data_rows = []
        unresolved_fields = [f for f in fields if f not in field_to_dataset]
        errors: List[str] = []
        if unresolved_fields:
            errors.append(
                f"Unresolved fields (not found in field mappings): {', '.join(unresolved_fields)}"
            )
        
        for symbol in symbols:
            row = [symbol]
            
            # Detect type for this symbol if not provided
            sym_type = object_type
            if not sym_type:
                try:
                    type_result = await self.detect_type(symbol)
                    sym_type = type_result.object_type
                except:
                    sym_type = "equity"
            
            # Fetch all datasets for this symbol
            try:
                result = await self.fetch_datasets(
                    symbol=symbol,
                    datasets=datasets_needed,
                    object_type=sym_type,
                    params=params,
                )
                
                # Flatten all data into a single dict for easy field lookup
                flat_data = {}
                for ds_name, ds_data in result.data.items():
                    if isinstance(ds_data, list) and len(ds_data) > 0:
                        # Take the first/latest record
                        record = ds_data[0] if isinstance(ds_data[0], dict) else {}
                        flat_data.update(record)
                    elif isinstance(ds_data, dict):
                        flat_data.update(ds_data)
                
                # Extract requested fields
                for field in fields:
                    val = flat_data.get(field)
                    row.append(val)
                    
            except Exception as e:
                errors.append(f"Failed to fetch {symbol}: {str(e)}")
                # Fill with nulls
                for _ in fields:
                    row.append(None)
            
            data_rows.append(row)
        
        return {
            "columns": columns,
            "data": data_rows,
            "row_count": len(data_rows),
            "errors": errors,
        }
    
    async def resolve_fields_to_datasets(
        self,
        fields: List[str],
    ) -> Dict[str, str]:
        """
        Resolve field names to their source datasets.
        
        Uses the field_mappings database to find which dataset contains each field.
        
        Returns:
            Dict mapping field_name -> dataset_name
        """
        fm = self._get_field_manager()
        
        import sqlite3
        conn = sqlite3.connect(fm.db_path)
        cursor = conn.cursor()
        
        result: Dict[str, str] = {}
        for field in fields:
            cursor.execute("""
                SELECT endpoint_name FROM field_mappings
                WHERE field_name = ?
                ORDER BY hit_count DESC
                LIMIT 1
            """, (field,))
            row = cursor.fetchone()
            if row:
                result[field] = row[0]
            else:
                # Try case-insensitive exact match
                cursor.execute("""
                    SELECT endpoint_name FROM field_mappings
                    WHERE LOWER(field_name) = LOWER(?)
                    ORDER BY hit_count DESC
                    LIMIT 1
                """, (field,))
                row = cursor.fetchone()
                if row:
                    result[field] = row[0]
        
        conn.close()
        return result
    
    async def cleanup(self):
        """Clean up all server connections."""
        for server in self._servers.values():
            if hasattr(server, "cleanup"):
                await server.cleanup()
        self._servers.clear()
        
        if self._field_manager:
            self._field_manager.close()
            self._field_manager = None
        
        await self._detector.cleanup()


# Singleton instance
_service: Optional[ObjectDataService] = None


def get_data_service() -> ObjectDataService:
    """Get or create the singleton service instance."""
    global _service
    if _service is None:
        _service = ObjectDataService()
    return _service


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics."""
    return _cache.stats()


def clear_cache() -> None:
    """Clear the entire data cache."""
    _cache.clear()


def get_data_freshness_info() -> Dict[str, Any]:
    """
    Get human-readable info about data freshness by category.
    
    Returns dict with TTL info for each data category.
    """
    return {
        "price_data": {
            "ttl_seconds": 900,
            "ttl_human": "15 minutes",
            "datasets": ["quote", "quote-short", "price-change", "historical-price-full"],
        },
        "intraday_data": {
            "ttl_seconds": 300,
            "ttl_human": "5 minutes",
            "datasets": ["intraday"],
        },
        "fundamentals": {
            "ttl_seconds": 86400,
            "ttl_human": "24 hours",
            "datasets": [
                "ratios-ttm", "ratios", "key-metrics-ttm", "key-metrics",
                "income-statement", "balance-sheet-statement", "cash-flow-statement",
                "financial-growth", "enterprise-values", "discounted-cash-flow"
            ],
        },
        "analyst_data": {
            "ttl_seconds": 21600,
            "ttl_human": "6 hours",
            "datasets": [
                "analyst-estimates", "analyst-stock-recommendations",
                "price-target", "price-target-summary", "upgrades-downgrades"
            ],
        },
        "profile_static": {
            "ttl_seconds": 604800,
            "ttl_human": "7 days",
            "datasets": ["profile", "key-executives", "stock-peers", "company-core-information"],
        },
        "ownership": {
            "ttl_seconds": 86400,
            "ttl_human": "24 hours",
            "datasets": ["institutional-holder", "mutual-fund-holder", "insider-trading"],
        },
        "earnings": {
            "ttl_seconds": 86400,
            "ttl_human": "24 hours", 
            "datasets": ["earnings", "earnings-surprises", "earnings-calendar"],
        },
        "news_sentiment": {
            "ttl_seconds": 3600,
            "ttl_human": "1 hour",
            "datasets": ["stock-news", "press-releases", "social-sentiment"],
        },
    }



