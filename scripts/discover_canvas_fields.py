#!/usr/bin/env python3
"""
Canvas Fields Discovery Script

Calls every endpoint from all MCP servers (FMP, Polygon, UW) and records
the response fields in the canvas_fields.db.

Usage:
    python scripts/discover_canvas_fields.py

Requires API keys in environment:
    - FMP_API_KEY
    - POLYGON_API_KEY (optional)
    - UW_API_KEY (optional)

For EFS in production, set CANVAS_FIELDS_DB_PATH env var.
"""

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Probe values by asset/identifier type
PROBE_VALUES = {
    # Standard symbols
    "symbol": "AAPL",
    "ticker": "AAPL",
    "tickers": "AAPL,MSFT",
    "underlying_ticker": "AAPL",
    "equity": "AAPL",
    "etf": "SPY",
    "crypto": "BTCUSD",
    "forex": "EURUSD",
    "commodity": "GCUSD",
    "treasury": "US10Y",
    "index": "SPX",
    # Identifiers
    "cik": "0000320193",  # Apple CIK
    "isin": "US0378331005",  # Apple ISIN
    "cusip": "037833100",  # Apple CUSIP
    "fund": "SPY",
    "name": "Apple",
    "exchange": "NASDAQ",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "market": "US",
    "currency": "USD",
    "portfolio": "AAPL",
    # UW specific
    "flow_group": "all",
    "expiry": "2026-01-17",
    # Polygon specific
    "options_ticker": "O:AAPL260117C00200000",
    "fx_ticker": "C:EURUSD",        # Polygon forex format (C: prefix)
    "crypto_ticker": "X:BTCUSD",    # Polygon crypto format (X: prefix)
    "multiplier": "1",
    "timespan": "day",
    "none": None,
}

# Rate limiting
SEMAPHORE_LIMIT = 10
RETRY_DELAYS = [1, 2, 4, 8, 16]

# Database path - configurable via env var for EFS in production
DB_PATH = Path(os.getenv('CANVAS_FIELDS_DB_PATH', str(Path(__file__).parent.parent / "core" / "canvas" / "data" / "canvas_fields.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists


class FieldDiscoverer:
    """Discovers fields from all MCP server endpoints."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
        self.fmp_key = os.getenv("FMP_API_KEY")
        self.polygon_key = os.getenv("POLYGON_API_KEY")
        self.uw_key = os.getenv("UW_API_KEY")
        
        self.stats = {
            "endpoints_called": 0,
            "endpoints_success": 0,
            "endpoints_failed": 0,
            "fields_discovered": 0,
        }

    async def __aenter__(self):
        # Create SSL context that doesn't verify certificates (for local dev)
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=connector
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    def _load_catalog(self, path: Path) -> List[Dict[str, Any]]:
        """Load a catalog JSON file."""
        if not path.exists():
            logger.warning(f"Catalog not found: {path}")
            return []
        
        with open(path) as f:
            data = json.load(f)
        
        return data.get("datasets", [])

    def _get_probe_value(self, dataset: Dict[str, Any]) -> Optional[str]:
        """Determine the appropriate probe value for a dataset."""
        identifier = dataset.get("identifier_param")
        url = dataset.get("url", "")
        dataset_name = dataset.get("dataset", "").lower()
        ds_class = dataset.get("class", "")

        # No identifier needed
        if not identifier and "{symbol}" not in url:
            return None

        # Explicit identifier type
        if identifier in PROBE_VALUES:
            return PROBE_VALUES[identifier]

        # Infer from dataset name or class
        if "etf" in dataset_name or ds_class == "etf":
            return PROBE_VALUES["etf"]
        if "crypto" in dataset_name:
            return PROBE_VALUES["crypto"]
        if "forex" in dataset_name or "currency" in dataset_name:
            return PROBE_VALUES["forex"]
        if "commodity" in dataset_name or "futures" in dataset_name:
            return PROBE_VALUES["commodity"]
        if "treasury" in dataset_name or "yield" in dataset_name:
            return PROBE_VALUES["treasury"]
        if "index" in dataset_name:
            return PROBE_VALUES["index"]

        # Default to equity
        return PROBE_VALUES["equity"]

    def _build_url(self, dataset: Dict[str, Any], base_url: str, probe: Optional[str]) -> str:
        """Build the full URL for an endpoint."""
        url_template = dataset.get("url", "")
        
        # Handle URL patterns
        url = url_template
        if probe:
            url = url.replace("{symbol}", probe)
            url = url.replace("{cik}", probe if dataset.get("identifier_param") == "cik" else "0000320193")
        
        # Remove any remaining placeholders
        import re
        url = re.sub(r"\{[^}]+\}", "", url)
        
        return f"{base_url}{url}"

    def _build_params(self, dataset: Dict[str, Any], probe: Optional[str], api_key: str) -> Dict[str, Any]:
        """Build query parameters for the request."""
        params = {"apikey": api_key}
        schema = dataset.get("params_schema", {})
        identifier = dataset.get("identifier_param")

        # Add identifier as query param if not in URL
        if identifier and probe and "{" + identifier + "}" not in dataset.get("url", ""):
            params[identifier] = probe

        # Add common defaults
        now = datetime.now()
        if "period" in schema:
            params["period"] = "annual"
        if "limit" in schema:
            params["limit"] = 10
        if "year" in schema:
            params["year"] = now.year
        if "quarter" in schema:
            params["quarter"] = ((now.month - 1) // 3) + 1
        if "from" in schema:
            params["from"] = "2024-01-01"
        if "to" in schema:
            params["to"] = now.strftime("%Y-%m-%d")
        if "date" in schema:
            params["date"] = now.strftime("%Y-%m-%d")

        return params

    async def _call_endpoint(
        self, 
        url: str, 
        params: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[Any]:
        """Call an endpoint with retry logic."""
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                async with self.semaphore:
                    async with self.session.get(url, params=params, headers=headers) as resp:
                        if resp.status == 429:
                            logger.warning(f"Rate limited, waiting {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        if resp.status != 200:
                            logger.debug(f"HTTP {resp.status} for {url}")
                            return None
                        return await resp.json()
            except Exception as e:
                logger.debug(f"Error calling {url}: {e}")
                if attempt < len(RETRY_DELAYS) - 1:
                    await asyncio.sleep(delay)
        return None

    def _extract_fields(self, data: Any, endpoint: str) -> List[Tuple[str, str, Optional[str]]]:
        """Extract field names from response data.
        
        Returns list of (field_name, field_type, sample_value).
        """
        fields = []

        def process_dict(d: dict, prefix: str = ""):
            for key, value in d.items():
                field_name = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    process_dict(value, field_name)
                elif isinstance(value, list):
                    fields.append((field_name, "array", f"[{len(value)} items]"))
                    # Also extract fields from first array item if it's a dict
                    if value and isinstance(value[0], dict):
                        for item_key, item_value in value[0].items():
                            item_field_name = f"{field_name}.{item_key}"
                            if isinstance(item_value, dict):
                                process_dict(item_value, item_field_name)
                            elif isinstance(item_value, list):
                                fields.append((item_field_name, "array", f"[{len(item_value)} items]"))
                            else:
                                item_type = type(item_value).__name__
                                sample = str(item_value)[:100] if item_value is not None else None
                                fields.append((item_field_name, item_type, sample))
                else:
                    field_type = type(value).__name__
                    sample = str(value)[:100] if value is not None else None
                    fields.append((field_name, field_type, sample))

        if isinstance(data, dict):
            process_dict(data)
        elif isinstance(data, list) and data:
            if isinstance(data[0], dict):
                process_dict(data[0])

        return fields

    async def discover_fmp(self) -> int:
        """Discover fields from all FMP catalogs."""
        if not self.fmp_key:
            logger.warning("FMP_API_KEY not set, skipping FMP discovery")
            return 0

        # FMP uses /stable/ prefix for newer endpoints
        base_url = "https://financialmodelingprep.com"
        catalog_dir = Path(__file__).parent.parent / "core" / "mcp_servers" / "fmp"
        
        catalogs = [
            catalog_dir / "ddc_catalog.json",
            catalog_dir / "alternatives_catalog.json",
            catalog_dir / "tradeflow_catalog.json",
            catalog_dir / "valuation_catalog.json",
        ]

        total_fields = 0
        
        for catalog_path in catalogs:
            datasets = self._load_catalog(catalog_path)
            logger.info(f"Processing {catalog_path.name}: {len(datasets)} datasets")

            tasks = []
            for dataset in datasets:
                tasks.append(self._discover_fmp_dataset(dataset, base_url))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for count in results:
                if isinstance(count, int):
                    total_fields += count

        return total_fields

    async def _discover_fmp_dataset(self, dataset: Dict[str, Any], base_url: str) -> int:
        """Discover fields from a single FMP dataset."""
        endpoint = dataset.get("dataset", "unknown")
        url_template = dataset.get("url", "")
        
        if not url_template:
            return 0
            
        probe = self._get_probe_value(dataset)
        identifier_param = dataset.get("identifier_param")
        required_params = list(dataset.get("params_schema", {}).keys())

        # Build full URL - FMP URLs are relative paths like /stable/quote
        url = f"{base_url}{url_template}"
        
        # Replace {symbol} in URL if present
        if "{symbol}" in url and probe:
            url = url.replace("{symbol}", probe)
        
        # Build query params
        params = {"apikey": self.fmp_key}
        
        # Add symbol as query param if not in URL and identifier is symbol
        if identifier_param == "symbol" and probe and "{symbol}" not in url_template:
            params["symbol"] = probe
        
        # Add common defaults from schema
        schema = dataset.get("params_schema", {})
        now = datetime.now()
        if "period" in schema:
            params["period"] = "annual"
        if "limit" in schema:
            params["limit"] = 10
        if "year" in schema:
            params["year"] = now.year
        if "quarter" in schema:
            params["quarter"] = ((now.month - 1) // 3) + 1
        if "from" in schema:
            params["from"] = "2024-01-01"
        if "to" in schema:
            params["to"] = now.strftime("%Y-%m-%d")
        if "date" in schema:
            params["date"] = now.strftime("%Y-%m-%d")

        self.stats["endpoints_called"] += 1
        
        data = await self._call_endpoint(url, params)
        if data is None:
            self.stats["endpoints_failed"] += 1
            logger.debug(f"FMP {endpoint}: no data returned")
            return 0

        fields = self._extract_fields(data, endpoint)
        if not fields:
            self.stats["endpoints_failed"] += 1
            return 0

        self.stats["endpoints_success"] += 1
        self._save_fields(fields, endpoint, "fmp", required_params)
        self.stats["fields_discovered"] += len(fields)
        
        logger.debug(f"FMP {endpoint}: {len(fields)} fields")
        return len(fields)

    async def discover_polygon(self) -> int:
        """Discover fields from Polygon catalogs."""
        if not self.polygon_key:
            logger.warning("POLYGON_API_KEY not set, skipping Polygon discovery")
            return 0

        base_url = "https://api.polygon.io"
        catalog_path = Path(__file__).parent.parent / "core" / "mcp_servers" / "polygon" / "polygon_ddc_catalog.json"
        
        datasets = self._load_catalog(catalog_path)
        logger.info(f"Processing Polygon catalog: {len(datasets)} datasets")

        total_fields = 0
        tasks = []
        
        for dataset in datasets:
            tasks.append(self._discover_polygon_dataset(dataset, base_url))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for count in results:
            if isinstance(count, int):
                total_fields += count

        return total_fields

    async def _discover_polygon_dataset(self, dataset: Dict[str, Any], base_url: str) -> int:
        """Discover fields from a single Polygon dataset."""
        endpoint = dataset.get("dataset", "unknown")
        url_template = dataset.get("url", "")
        
        # Skip if no URL
        if not url_template:
            return 0

        required_params = list(dataset.get("params_schema", {}).keys())
        now = datetime.now()
        
        # Build URL with all placeholder substitutions
        url = url_template
        url = url.replace("{symbol}", "AAPL")
        url = url.replace("{ticker}", "AAPL")
        url = url.replace("{stocksTicker}", "AAPL")
        url = url.replace("{underlying_ticker}", "AAPL")
        url = url.replace("{options_ticker}", PROBE_VALUES.get("options_ticker", "O:AAPL260117C00200000"))
        url = url.replace("{fx_ticker}", "C:EURUSD")       # Polygon forex pair format
        url = url.replace("{crypto_ticker}", "X:BTCUSD")   # Polygon crypto pair format
        url = url.replace("{multiplier}", "1")
        url = url.replace("{timespan}", "day")
        url = url.replace("{from}", "2024-01-01")
        url = url.replace("{to}", now.strftime("%Y-%m-%d"))
        url = url.replace("{date}", now.strftime("%Y-%m-%d"))
        url = url.replace("{figi}", "BBG000B9XRY4")  # Apple FIGI
        url = url.replace("{cik}", "320193")
        
        # Remove remaining placeholders
        import re
        url = re.sub(r"\{[^}]+\}", "", url)
        
        # Clean up double slashes from removed placeholders
        while "//" in url and "://" not in url.replace("https://", "").replace("http://", ""):
            url = url.replace("//", "/")
        
        full_url = f"{base_url}{url}"

        params = {"apiKey": self.polygon_key}
        
        # Add common params
        schema = dataset.get("params_schema", {})
        if "limit" in schema:
            params["limit"] = 10
        if "adjusted" in schema:
            params["adjusted"] = "true"

        self.stats["endpoints_called"] += 1
        
        data = await self._call_endpoint(full_url, params)
        if data is None:
            self.stats["endpoints_failed"] += 1
            logger.debug(f"Polygon {endpoint}: no data returned")
            return 0

        # Polygon wraps results in various keys
        if isinstance(data, dict):
            if "results" in data:
                data = data["results"]
            elif "result" in data:
                data = data["result"]

        fields = self._extract_fields(data, endpoint)
        if not fields:
            self.stats["endpoints_failed"] += 1
            return 0

        self.stats["endpoints_success"] += 1
        self._save_fields(fields, endpoint, "polygon", required_params)
        self.stats["fields_discovered"] += len(fields)
        
        logger.debug(f"Polygon {endpoint}: {len(fields)} fields")
        return len(fields)

    async def discover_uw(self) -> int:
        """Discover fields from Unusual Whales catalogs."""
        if not self.uw_key:
            logger.warning("UW_API_KEY not set, skipping UW discovery")
            return 0

        # Catalog URLs already have /api/ prefix
        base_url = "https://api.unusualwhales.com"
        catalog_dir = Path(__file__).parent.parent / "core" / "mcp_servers" / "unusualwhales"
        
        catalogs = [
            catalog_dir / "uw_market_catalog.json",
            catalog_dir / "uw_institutional_catalog.json",
            catalog_dir / "uw_options_catalog.json",
        ]

        total_fields = 0
        
        for catalog_path in catalogs:
            datasets = self._load_catalog(catalog_path)
            logger.info(f"Processing {catalog_path.name}: {len(datasets)} datasets")

            tasks = []
            for dataset in datasets:
                tasks.append(self._discover_uw_dataset(dataset, base_url))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for count in results:
                if isinstance(count, int):
                    total_fields += count

        return total_fields

    async def _discover_uw_dataset(self, dataset: Dict[str, Any], base_url: str) -> int:
        """Discover fields from a single UW dataset."""
        endpoint = dataset.get("dataset", "unknown")
        url_template = dataset.get("url", "")
        
        if not url_template:
            return 0

        identifier_param = dataset.get("identifier_param")
        required_params = list(dataset.get("params_schema", {}).keys())
        
        # Build URL with placeholder substitutions
        url = url_template
        
        # Replace all known placeholders
        url = url.replace("{ticker}", PROBE_VALUES.get("ticker", "AAPL"))
        url = url.replace("{symbol}", PROBE_VALUES.get("symbol", "AAPL"))
        url = url.replace("{flow_group}", PROBE_VALUES.get("flow_group", "all"))
        url = url.replace("{expiry}", PROBE_VALUES.get("expiry", "2026-01-17"))
        url = url.replace("{name}", PROBE_VALUES.get("name", "Pelosi"))
        
        # Remove any remaining placeholders
        import re
        url = re.sub(r"\{[^}]+\}", "", url)
        
        # UW URLs already have /api/ prefix, base is just the domain
        full_url = f"{base_url}{url}"

        headers = {"Authorization": f"Bearer {self.uw_key}"}
        
        # Build query params from schema
        params = {}
        schema = dataset.get("params_schema", {})
        now = datetime.now()
        
        if "ticker" in schema and identifier_param != "ticker":
            params["ticker"] = "AAPL"
        if "tickers" in schema:
            params["tickers"] = "AAPL,MSFT"
        if "date" in schema:
            params["date"] = now.strftime("%Y-%m-%d")
        if "start_date" in schema:
            params["start_date"] = "2024-01-01"
        if "end_date" in schema:
            params["end_date"] = now.strftime("%Y-%m-%d")
        if "limit" in schema:
            params["limit"] = 10
        if "interval" in schema:
            params["interval"] = "1d"

        self.stats["endpoints_called"] += 1
        
        data = await self._call_endpoint(full_url, params, headers=headers)
        if data is None:
            self.stats["endpoints_failed"] += 1
            return 0

        # UW wraps in data key
        if isinstance(data, dict) and "data" in data:
            data = data["data"]

        fields = self._extract_fields(data, endpoint)
        if not fields:
            self.stats["endpoints_failed"] += 1
            return 0

        self.stats["endpoints_success"] += 1
        self._save_fields(fields, endpoint, "uw", required_params)
        self.stats["fields_discovered"] += len(fields)
        
        logger.debug(f"UW {endpoint}: {len(fields)} fields")
        return len(fields)

    def _save_fields(
        self, 
        fields: List[Tuple[str, str, Optional[str]]], 
        endpoint: str, 
        source: str,
        required_params: List[str]
    ):
        """Save discovered fields to the database."""
        # Import mappings for object_type, category, and compatibility metadata
        # Use importlib to avoid __init__.py import issues
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "field_mappings", 
                Path(__file__).parent.parent / "core" / "canvas" / "field_mappings.py"
            )
            fm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fm)
            
            object_types = fm.get_object_types_for_endpoint(endpoint)
            object_type_str = ",".join(object_types) if object_types else "equity"
            category = fm.get_category_for_endpoint(endpoint)
            structure_type = fm.get_structure_type_for_endpoint(endpoint)
            compatibility_group = fm.get_compatibility_group_for_endpoint(endpoint)
            time_key = fm.get_time_key_for_endpoint(endpoint)
            cardinality = fm.get_cardinality_for_endpoint(endpoint)
        except Exception as e:
            logger.warning(f"Failed to load field_mappings: {e}")
            object_type_str = "equity"
            category = "Other"
            structure_type = "unknown"
            compatibility_group = "unknown"
            time_key = None
            cardinality = "single"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        req_params_json = json.dumps(required_params) if required_params else None

        for field_name, field_type, sample_value in fields:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO fields 
                    (field_name, endpoint, source, field_type, sample_value, required_params, 
                     discovered_at, object_type, category, structure_type, compatibility_group, time_key, cardinality)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    field_name,
                    endpoint,
                    source,
                    field_type,
                    sample_value,
                    req_params_json,
                    datetime.now().isoformat(),
                    object_type_str,
                    category,
                    structure_type,
                    compatibility_group,
                    time_key,
                    cardinality,
                ))
            except Exception as e:
                logger.warning(f"Failed to save field {field_name}: {e}")

        conn.commit()
        conn.close()

    async def run(self):
        """Run full discovery across all sources."""
        logger.info("Starting Canvas Fields Discovery")
        logger.info(f"Database: {DB_PATH}")
        
        # Create table if not exists and clear existing data
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fields (
                field_name TEXT,
                endpoint TEXT,
                source TEXT,
                field_type TEXT,
                sample_value TEXT,
                required_params TEXT,
                discovered_at TEXT,
                object_type TEXT,
                category TEXT,
                structure_type TEXT,
                compatibility_group TEXT,
                time_key TEXT,
                cardinality TEXT,
                PRIMARY KEY (field_name, endpoint, source)
            )
        """)
        conn.execute("DELETE FROM fields")
        conn.commit()
        conn.close()
        logger.info("Cleared existing fields")

        # Discover from each source
        fmp_count = await self.discover_fmp()
        logger.info(f"FMP: {fmp_count} fields discovered")

        polygon_count = await self.discover_polygon()
        logger.info(f"Polygon: {polygon_count} fields discovered")

        uw_count = await self.discover_uw()
        logger.info(f"UW: {uw_count} fields discovered")

        # Print summary
        logger.info("=" * 50)
        logger.info("Discovery Complete")
        logger.info(f"Endpoints called: {self.stats['endpoints_called']}")
        logger.info(f"Endpoints success: {self.stats['endpoints_success']}")
        logger.info(f"Endpoints failed: {self.stats['endpoints_failed']}")
        logger.info(f"Total fields: {self.stats['fields_discovered']}")

        # Print DB summary
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT source, COUNT(*) FROM fields GROUP BY source")
        for source, count in cursor.fetchall():
            logger.info(f"  {source}: {count} fields")
        cursor.execute("SELECT COUNT(DISTINCT endpoint) FROM fields")
        logger.info(f"  Unique endpoints: {cursor.fetchone()[0]}")
        conn.close()


async def main():
    async with FieldDiscoverer() as discoverer:
        await discoverer.run()


if __name__ == "__main__":
    asyncio.run(main())

