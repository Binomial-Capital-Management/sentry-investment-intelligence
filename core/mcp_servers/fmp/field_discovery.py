"""
FMP Field Discovery - Handles field discovery and dataset operations
Following KISS principle - focused only on discovery and listing
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .data_fetcher import FMPDataFetcher
from .ddc_loader import DDCLoader, DatasetEntry
from .field_map_manager import FieldMapManager

logger = logging.getLogger(__name__)


# Discovery defaults and configuration
DEFAULT_DISCOVERY_SYMBOL = "AAPL"
DEFAULT_PAGE_SIZE = 50
DEFAULT_ETF_SYMBOL = "SPY"
DEFAULT_FOREX_PAIR = "EURUSD"
DEFAULT_CRYPTO_PAIR = "BTCUSD"
DEFAULT_COMMODITY_SYMBOL = "GCUSD"
DEFAULT_TREASURY_SYMBOL = "US10Y"
DEFAULT_APPLE_CIK = "0000320193"
DEFAULT_APPLE_ISIN = "US0378331005"
DEFAULT_APPLE_CUSIP = "037833100"
DEFAULT_COMPANY_NAME = "Apple"
DEFAULT_EXCHANGE = "NASDAQ"
DEFAULT_MARKET = "US"
DEFAULT_SECTOR = "Technology"
DEFAULT_INDUSTRY = "Semiconductors"
DEFAULT_CURRENCY = "USD"

# Dataset class priority for discovery (lower = higher priority)
CLASS_PRIORITY = {
    "market": 1,
    "analyst": 2,
    "valuation": 3,
    "technical": 4,
    "ownership": 5,
    "insider": 6,
    "institutional": 7,
    "etf": 8,
    "congressional": 9,
    "corporate_actions": 10,
    "esg": 11,
    "documents": 12,
    "news": 13,
    "economics": 14,
    "market_wide": 15,
    "political": 16,
}


def _default_identifier_for_class(dataset: DatasetEntry) -> str:
    """
    Provide a resilient default identifier for datasets when the user-provided
    symbol would yield no data (e.g., ETF/forex endpoints). Keeps discovery robust.
    """
    name = (dataset.dataset or "").lower()
    class_name = dataset.class_.value if dataset.class_ else ""

    # ETF / funds style endpoints prefer a benchmark ETF
    if "etf" in name or "fund" in name or class_name == "etf":
        return DEFAULT_ETF_SYMBOL

    # Forex / currency pairs
    if "forex" in name or "currency" in name:
        return DEFAULT_FOREX_PAIR

    # Crypto feeds
    if "crypto" in name:
        return DEFAULT_CRYPTO_PAIR

    # Commodities / futures
    if "commodity" in name or "futures" in name:
        return DEFAULT_COMMODITY_SYMBOL

    # Treasury or rates datasets
    if "treasury" in name or "yield" in name:
        return DEFAULT_TREASURY_SYMBOL

    return DEFAULT_DISCOVERY_SYMBOL


def resolve_probe_identifier(dataset: DatasetEntry, requested_symbol: Optional[str]) -> Optional[str]:
    """
    Choose the best identifier to probe a dataset. Uses caller symbol when sensible,
    otherwise falls back to class-specific defaults so discovery succeeds.
    """
    param = dataset.identifier_param

    # Datasets that substitute {symbol} in the URL but have no explicit identifier
    if not param and "{symbol}" in (dataset.url or ""):
        return requested_symbol or DEFAULT_DISCOVERY_SYMBOL

    if param == "symbol":
        # Many tradeflow datasets expect special symbols; prefer defaults when request symbol is incompatible
        fallback = _default_identifier_for_class(dataset)
        return requested_symbol or fallback

    if param == "cik":
        # Apple CIK – widely populated in FMP datasets
        return DEFAULT_APPLE_CIK

    if param == "isin":
        return DEFAULT_APPLE_ISIN

    if param == "cusip":
        return DEFAULT_APPLE_CUSIP

    if param == "name":
        return DEFAULT_COMPANY_NAME

    if param == "exchange":
        return DEFAULT_EXCHANGE

    if param == "fund":
        return DEFAULT_ETF_SYMBOL

    if param == "portfolio":
        return requested_symbol or DEFAULT_DISCOVERY_SYMBOL

    if param is None:
        # No identifier needed
        return requested_symbol or DEFAULT_DISCOVERY_SYMBOL

    # Unknown identifier type – fall back to caller symbol, discovery may still succeed
    return requested_symbol


def build_probe_params(dataset: DatasetEntry, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build a best-effort parameter set for discovery based on catalog metadata.
    """
    now = datetime.now()
    last_month = now - timedelta(days=30)

    params: Dict[str, Any] = {
        "period": "annual",
        "year": now.year,
        "quarter": 1,
        "limit": DEFAULT_PAGE_SIZE,
        "page": 0,
        "from": last_month.strftime("%Y-%m-%d"),
        "to": now.strftime("%Y-%m-%d"),
        "periodLength": 14,
        "timeframe": "1day",
    }

    schema = dataset.params_schema or {}
    dataset_name = (dataset.dataset or "").lower()

    if "date" in schema:
        params.setdefault("date", now.date().isoformat())
    if "from" in schema or "to" in schema:
        params.setdefault("from", last_month.strftime("%Y-%m-%d"))
        params.setdefault("to", now.strftime("%Y-%m-%d"))
    if "limit" in schema:
        params.setdefault("limit", DEFAULT_PAGE_SIZE)
    if "page" in schema:
        params.setdefault("page", 0)
    if "year" in schema:
        params.setdefault("year", now.year)
    if "quarter" in schema:
        # Use most recently completed quarter
        quarter = ((now.month - 1) // 3) + 1
        params.setdefault("quarter", quarter)
    if "market" in schema:
        params.setdefault("market", DEFAULT_MARKET)
    if "exchange" in schema:
        params.setdefault("exchange", DEFAULT_EXCHANGE)
    if "sector" in schema:
        params.setdefault("sector", DEFAULT_SECTOR)
    if "industry" in schema:
        params.setdefault("industry", DEFAULT_INDUSTRY)
    if "currency" in schema:
        params.setdefault("currency", DEFAULT_CURRENCY)
    if "fund" in schema:
        params.setdefault("fund", DEFAULT_ETF_SYMBOL)
    if "portfolio" in schema:
        params.setdefault("portfolio", DEFAULT_DISCOVERY_SYMBOL)
    if "interval" in schema:
        params.setdefault("interval", "1day")
    if "timeframe" in schema:
        params.setdefault("timeframe", "1day")
    if "period" in schema and "period" not in params:
        params["period"] = "ttm" if "ttm" in dataset_name else "annual"

    if overrides:
        params.update(overrides)

    return params


class FMPFieldDiscovery:
    """
    Handles field discovery operations for FMP.
    Discovers available fields and manages dataset listings.
    """
    
    def __init__(self, api_key: str, data_fetcher: FMPDataFetcher, 
                 ddc_loader: DDCLoader, field_manager: FieldMapManager):
        """Initialize field discovery with dependencies"""
        self.api_key = api_key
        self.data_fetcher = data_fetcher
        self.ddc_loader = ddc_loader
        self.field_manager = field_manager
        
        # Discovery state
        self.discovered_fields: Dict[str, Any] = {}
        self.discovery_timestamp: Optional[datetime] = None
        self._discovery_lock = asyncio.Lock()
        
    async def discover_fields(
        self,
        symbol: str = DEFAULT_DISCOVERY_SYMBOL,
        max_datasets: int = 80,
        discovery_params: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Discover all available fields for a symbol.

        This is expensive - makes many API calls. Results are cached in field_manager.

        Args:
            symbol: Symbol to use for discovery
            max_datasets: Maximum number of datasets to probe
            discovery_params: Optional parameters for endpoints that require them (e.g., period, year)
            force_refresh: If True, bypass cache and force rediscovery

        Returns:
            Dictionary of field_name -> {value, source, type}
        """
        logger.debug(f"Starting field discovery for {symbol} (max {max_datasets} datasets, force_refresh={force_refresh})")

        # Serialize concurrent discovery calls so only one probes the API;
        # subsequent callers wait and then find the cache populated.
        async with self._discovery_lock:
            return await self._discover_fields_locked(symbol, max_datasets, discovery_params, force_refresh)

    async def _discover_fields_locked(
        self,
        symbol: str,
        max_datasets: int,
        discovery_params: Optional[Dict[str, Any]],
        force_refresh: bool,
    ) -> Dict[str, Any]:
        """Inner discovery logic, called while holding _discovery_lock."""
        # Re-check cache inside the lock — a concurrent caller may have just
        # finished discovery while we were waiting for the lock.
        if not force_refresh and not self.field_manager.needs_refresh(days=7):
            logger.debug("Using cached field mappings (less than 7 days old)")
            cached_fields = self.field_manager.get_all_field_mappings()
            logger.debug(f"Returning {len(cached_fields)} cached fields")
            return cached_fields

        if force_refresh:
            logger.debug("Force refresh enabled - bypassing cache")
        
        discovered = {}
        endpoint_urls = {}
        endpoint_classes = {}  # NEW: Track endpoint classes for priority
        datasets_probed = 0

        # Get discoverable datasets
        discoverable = [
            ds for ds in self.ddc_loader.catalog.datasets
            if ds.discoverable
        ]

        # Sort by priority (ensure institutional / document classes are not starved)
        discoverable.sort(
            key=lambda x: CLASS_PRIORITY.get(x.class_, 999)
        )

        # Filter to probeable datasets
        probeable = []
        for dataset in discoverable[:max_datasets]:
            if not dataset.identifier_param and '{symbol}' not in dataset.url:
                continue
            identifier = resolve_probe_identifier(dataset, symbol)
            if identifier is None:
                continue
            probeable.append((dataset, identifier))

        # Probe datasets in batches of 8 for concurrency
        BATCH_SIZE = 8
        for batch_start in range(0, len(probeable), BATCH_SIZE):
            # Check cancellation between batches
            current_task = asyncio.current_task()
            if current_task and current_task.cancelled():
                logger.info("Field discovery cancelled by user")
                break

            batch = probeable[batch_start:batch_start + BATCH_SIZE]

            async def _probe_one(ds, ident, params=discovery_params):
                try:
                    probe_params = build_probe_params(ds, params)
                    data = await self.data_fetcher.fetch_dataset(
                        ident, ds, historical_params=probe_params,
                    )
                    return (ds, data)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Failed to probe {ds.dataset}: {e}")
                    return (ds, None)

            results = await asyncio.gather(
                *[_probe_one(ds, ident) for ds, ident in batch],
                return_exceptions=True,
            )

            for item in results:
                if isinstance(item, BaseException):
                    if isinstance(item, asyncio.CancelledError):
                        raise item
                    continue
                dataset, data = item
                if data:
                    endpoint_urls[dataset.dataset] = dataset.url
                    endpoint_classes[dataset.dataset] = dataset.class_.value
                    fields = self._extract_fields(data, dataset.dataset)
                    discovered.update(fields)
                    datasets_probed += 1

        # Save to field manager with priority-based logic
        if discovered:
            new_fields = self.field_manager.save_discovered_fields(discovered, endpoint_urls, endpoint_classes)
            logger.debug(f"Discovery complete: {len(discovered)} fields from {datasets_probed} datasets")
            
        # Cache results
        self.discovered_fields = discovered
        self.discovery_timestamp = datetime.now()
        
        return discovered
    
    def _extract_fields(self, data: Any, source: str) -> Dict[str, Any]:
        """
        Extract fields from API response data.
        
        Args:
            data: Response data (dict or list)
            source: Source dataset name
            
        Returns:
            Dict of field_name -> {value, source, type, required_params, notes}
        """
        dataset = self.ddc_loader.get_dataset(source)
        required_params: List[str] = []
        notes = None
        if dataset:
            if dataset.params_schema:
                required_params = [
                    key for key in dataset.params_schema.keys()
                    if key not in ("symbol", "apikey")
                ]
            notes = dataset.notes

        fields = {}
        
        def process_dict(d: dict, prefix: str = ""):
            """Recursively process dictionary"""
            for key, value in d.items():
                field_name = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    # Nested object - recurse
                    process_dict(value, field_name)
                elif isinstance(value, list):
                    # Array - note type but don't recurse into items
                    field_metadata = {
                        "value": f"[{len(value)} items]",
                        "source": source,
                        "type": "array"
                    }
                    if required_params:
                        field_metadata["required_params"] = required_params
                    if notes:
                        field_metadata["notes"] = notes
                    fields[field_name] = field_metadata
                else:
                    # Scalar value
                    field_type = type(value).__name__
                    field_metadata = {
                        "value": value,
                        "source": source,
                        "type": field_type
                    }
                    if required_params:
                        field_metadata["required_params"] = required_params
                    if notes:
                        field_metadata["notes"] = notes
                    fields[field_name] = field_metadata

        # Handle response format
        if isinstance(data, dict):
            process_dict(data)
        elif isinstance(data, list) and data:
            # Use first item for discovery
            if isinstance(data[0], dict):
                process_dict(data[0])
        
        return fields
    
    def list_datasets(self, include_details: bool = False) -> List[Dict[str, Any]]:
        """
        List all available datasets from DDC catalog.
        
        Args:
            include_details: Include full dataset details
            
        Returns:
            List of dataset information
        """
        datasets = []
        
        for dataset in self.ddc_loader.catalog.datasets:
            if include_details:
                # Full details with computed hints for agents
                required_params = [
                    k for k in (dataset.params_schema or {}).keys()
                    if k not in ("symbol", "apikey")
                ]
                # Build sample params and identifier hint
                sample_params = build_probe_params(dataset, overrides=None)
                identifier = resolve_probe_identifier(dataset, None)

                # Sample call hint (non-binding)
                sample_call = {
                    "dataset": dataset.dataset,
                    "symbol": identifier if identifier else None,
                    "params": {k: sample_params.get(k) for k in required_params}
                }

                info = {
                    "dataset": dataset.dataset,
                    "class": dataset.class_,
                    "url": dataset.url,
                    "method": dataset.method,
                    "discoverable": dataset.discoverable,
                    "has_symbol": '{symbol}' in dataset.url,
                    "params": list((dataset.params_schema or {}).keys()),
                    "required_params": required_params,
                    "identifier_param": dataset.identifier_param,
                    "rate_limit": {
                        "rps": dataset.rate_limit.rps,
                        "burst": dataset.rate_limit.burst
                    } if dataset.rate_limit else None,
                    "notes": dataset.notes,
                    "sample_call": sample_call
                }
            else:
                # Basic info only
                info = {
                    "dataset": dataset.dataset,
                    "class": dataset.class_,
                    "discoverable": dataset.discoverable
                }
            
            datasets.append(info)
        
        # Sort by class for better organization
        datasets.sort(key=lambda x: (x["class"], x["dataset"]))
        
        return datasets
    
    def get_dataset_info(self, dataset_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific dataset.
        
        Args:
            dataset_name: Name of the dataset
            
        Returns:
            Dataset information or None if not found
        """
        dataset = self.ddc_loader.get_dataset(dataset_name)
        if not dataset:
            return None
        
        return {
            "dataset": dataset.dataset,
            "class": dataset.class_,
            "url": dataset.url,
            "method": dataset.method,
            "discoverable": dataset.discoverable,
            "has_symbol": '{symbol}' in dataset.url,
            "params": list(dataset.params_schema.keys()) if dataset.params_schema else [],
            "rate_limit": {
                "rps": dataset.rate_limit.rps,
                "burst": dataset.rate_limit.burst
            } if dataset.rate_limit else None,
            "cache_ttl": dataset.cache_ttl,
            "notes": dataset.notes
        }
    
    def get_field_stats(self) -> Dict[str, Any]:
        """Get statistics about discovered fields"""
        stats = self.field_manager.get_statistics()
        
        # Add discovery info
        stats["last_discovery"] = self.discovery_timestamp.isoformat() if self.discovery_timestamp else None
        stats["cached_fields"] = len(self.discovered_fields)
        
        return stats
