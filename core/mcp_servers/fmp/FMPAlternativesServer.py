"""
FMP Alternative Assets Server - Specialized MCP server for cryptocurrency, forex, and commodities data
EXACT COPY of FMPAdvancedValuationServer pattern with alternative assets tools
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Import MCP base class from agents SDK
from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult

# Import helper modules
from .ddc_loader import DDCLoader
from .data_fetcher import FMPDataFetcher
from .field_discovery import FMPFieldDiscovery
from .historical_data import FMPHistoricalData
from core.utils import gather_dict
from .field_map_manager import FieldMapManager
from .rate_limiter import DatasetRateLimiter

logger = logging.getLogger(__name__)

DEFAULT_INTRADAY_LOOKBACK_DAYS = {
    "1min": 2,
    "5min": 5,
    "15min": 14,
    "30min": 30,
    "1hour": 90,
    "4hour": 180,
    "1day": 365,
}
DEFAULT_INTRADAY_LIMIT = 3000


class FMPAlternativesServer(MCPServer):
    """
    MCP Server for FMP alternative assets (crypto, forex, commodities) data discovery and retrieval.
    EXACT copy of FMPAdvancedValuationServer architecture.
    """

    def __init__(self, api_key: str = None):
        """Initialize FMP Alternative Assets Server with helper modules"""
        super().__init__()
        self._name = "FMPAlternativesServer"
        self.use_structured_content = False  # Required by openai-agents SDK 0.2.0+

        # Load API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("FMP_API_KEY")

        if not api_key:
            raise ValueError("FMP_API_KEY not provided")

        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com"

        # Initialize helper modules - exactly like valuation server but with alternatives catalog
        alternatives_catalog_path = os.path.join(os.path.dirname(__file__), "alternatives_catalog.json")
        self.ddc_loader = DDCLoader(alternatives_catalog_path)
        self.catalog = self.ddc_loader.catalog

        self.field_manager = FieldMapManager()
        self.rate_limiter = DatasetRateLimiter()

        # Data fetcher for all HTTP operations
        self.data_fetcher = FMPDataFetcher(api_key, self.base_url)

        # Field discovery handler
        self.field_discovery = FMPFieldDiscovery(
            api_key, self.data_fetcher, self.ddc_loader, self.field_manager
        )

        # Historical data handler
        self.historical_data = FMPHistoricalData(
            api_key, self.data_fetcher, self.ddc_loader, self.field_manager
        )

        logger.info("FMPAlternativesServer initialized")

    @property
    def name(self) -> str:
        """Server name for MCP"""
        return self._name

    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        """MCP method: List available tools"""
        return self.get_available_tools()

    async def list_prompts(self, run_context, agent) -> List[str]:
        """List available prompts (none for this server)"""
        return []

    async def get_prompt(self, name: str, arguments: Dict[str, Any], run_context, agent) -> str:
        """MCP method: Get a prompt (not implemented for this server)"""
        raise NotImplementedError(f"No prompts available for {self.name}")

    def get_available_tools(self) -> List[MCPTool]:
        """Get list of available MCP tools"""
        return [
            MCPTool(
                name="discover_alternatives_fields",
                description="Probes alternatives endpoints to discover available fields for a symbol (BTCUSD, EURUSD, GCUSD). Returns field catalog from verified endpoints only. Use before fetching specific data to see what's available.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Symbol to discover fields for (crypto: BTCUSD, forex: EURUSD, commodity: GCUSD)"
                        },
                        "max_datasets": {
                            "type": "integer",
                            "description": "Maximum datasets to probe",
                            "default": 10
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_alternatives_dataset",
                description="Fetches specific alternatives dataset. For daily FX rates, use dataset='forex-historical-eod-light' with params={from:'YYYY-MM-DD', to:'YYYY-MM-DD'}. Example: {dataset:'forex-historical-eod-light', symbol:'USDTRY', params:{from:'2025-01-01', to:'2025-01-31'}}",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Generic symbol/pair when required by dataset (e.g., USDTRY, ILSTRY)"},
                        "dataset": {"type": "string", "description": "Dataset name (e.g., forex-historical-eod-light for daily FX rates)"},
                        "params": {"type": "object", "description": "REQUIRED for historical datasets. Must include 'from' and 'to' dates as YYYY-MM-DD. Example: {from:'2025-01-01', to:'2025-01-31'}", "additionalProperties": True},
                        "datasets": {"type": "array", "items": {"type": "string"}, "description": "Multiple dataset names to fetch"}
                    },
                    "required": ["dataset"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_crypto_quote",
                description="Gets live cryptocurrency price and metrics. Provide trading pair symbol like BTCUSD, ETHUSD, SOLUSD. Returns current price, percent change, and market cap.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Cryptocurrency symbol (e.g., BTCUSD, ETHUSD)"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_crypto_historical",
                description="Fetches historical crypto price data. Provide symbol (BTCUSD) and timeframe (1min, 5min, 15min, 30min, 1hour, 4hour). Optional from/to dates. Returns OHLCV bars.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Cryptocurrency symbol"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Timeframe: 1min, 5min, 15min, 30min, 1hour, 4hour",
                            "default": "1hour"
                        },
                        "from": {
                            "type": "string",
                            "description": "Start date (YYYY-MM-DD)"
                        },
                        "to": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD)"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="list_crypto",
                description="Lists all supported cryptocurrencies with symbols and names. Returns complete crypto catalog.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_forex_quote",
                description="Gets live forex rates. Provide currency pair (EURUSD, GBPJPY). Returns current rate, bid/ask, and change.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pair": {
                            "type": "string",
                            "description": "Forex pair (e.g., EURUSD, GBPJPY)"
                        }
                    },
                    "required": ["pair"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_forex_historical",
                description="Fetches INTRADAY forex OHLCV bars. Valid timeframes: 1min, 5min, 1hour ONLY. For DAILY forex rates, use get_alternatives_dataset with dataset='forex-historical-eod-light' instead.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pair": {
                            "type": "string",
                            "description": "Forex pair (e.g., EURUSD, USDTRY, ILSTRY)"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Timeframe: 1min, 5min, 1hour ONLY. For daily rates, use get_alternatives_dataset.",
                            "default": "1hour"
                        },
                        "from": {
                            "type": "string",
                            "description": "Start date (YYYY-MM-DD)"
                        },
                        "to": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD)"
                        }
                    },
                    "required": ["pair"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="list_forex",
                description="Lists all supported forex pairs with symbols and names. Returns complete forex catalog for pair discovery.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_commodities_data",
                description="Fetches commodities data. data_type: quote (live) or historical (OHLCV). For historical, timeframe options: 1min, 5min, 1hour, eod (daily), eod-full. Use 'eod' or 'daily' for end-of-day prices. Example symbols: GCUSD (gold), CLUSD (crude oil).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Commodity symbol (e.g., GCUSD for gold, CLUSD for crude oil)"
                        },
                        "data_type": {
                            "type": "string",
                            "description": "quote or historical",
                            "default": "quote"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "For historical: 1min, 5min, 1hour, eod (daily), eod-full. Use 'eod' for daily data.",
                            "default": "1hour"
                        },
                        "from": {
                            "type": "string",
                            "description": "Start date for historical (YYYY-MM-DD)"
                        },
                        "to": {
                            "type": "string",
                            "description": "End date for historical (YYYY-MM-DD)"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_batch_quotes",
                description="Fetches batch quotes for all symbols in an asset class. Provide asset_class: crypto (all cryptos), forex (all currency pairs), or commodities (all commodities). Returns complete market snapshot in one call.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_class": {
                            "type": "string",
                            "description": "Asset class: crypto, forex, or commodities"
                        }
                    },
                    "required": ["asset_class"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_latest_alternatives_news",
                description="Fetch latest financial news headlines for crypto or forex markets with auto-pagination. Returns structured list with title, publishedDate, site, url, and associated symbols. Automatically fetches multiple pages up to max_results. Use this for: (1) crypto market-wide headlines, (2) forex news scanning, (3) news discovery before drilling into specifics. Data is cached for 30 min. DO NOT use for article content—this returns headlines only; use web_search for full article text.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "news_type": {
                            "type": "string",
                            "enum": ["crypto", "forex"],
                            "description": "Type: 'crypto' = cryptocurrency market news (Bitcoin, Ethereum, DeFi, NFTs), 'forex' = foreign exchange news (currency pairs, central banks, macro FX)"
                        },
                        "page": {
                            "type": "integer",
                            "description": "Starting page number (0-indexed). Auto-paginates from this page until max_results reached. Default 0 for most recent.",
                            "default": 0,
                            "minimum": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Results per page during auto-pagination. Max 100, default 20. Higher values = fewer API calls but more data per call.",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Total number of news items to return (across all pages). Default 100, max 500. Tool auto-paginates until this limit is reached or no more data available.",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 500
                        }
                    },
                    "required": ["news_type"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_alternatives_news_by_symbol",
                description="Fetch news headlines for specific crypto or forex symbol with auto-pagination. Returns structured list with title, text snippet, publishedDate, site, url, and symbol. Automatically fetches multiple pages up to max_results. Use this for: (1) crypto pair-specific news (BTCUSD, ETHUSD), (2) forex pair news (EURUSD, GBPJPY), (3) catalyst research. Data is cached for 30 min. Returns headlines only—use web_search to fetch full article content when needed.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Crypto pair (e.g., 'BTCUSD', 'ETHUSD') or forex pair (e.g., 'EURUSD', 'GBPJPY'). Single symbol only—use multiple calls for multiple symbols or use get_latest_alternatives_news for market-wide scan."
                        },
                        "news_type": {
                            "type": "string",
                            "enum": ["crypto", "forex"],
                            "description": "Type: 'crypto' = cryptocurrency pair news, 'forex' = forex pair news"
                        },
                        "page": {
                            "type": "integer",
                            "description": "Starting page number (0-indexed). Auto-paginates from this page until max_results reached. Default 0 for most recent.",
                            "default": 0,
                            "minimum": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Results per page during auto-pagination. Max 100, default 20. Higher values = fewer API calls but more data per call.",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Total number of news items to return (across all pages). Default 100, max 500. Tool auto-paginates until this limit is reached or no more data available.",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 500
                        }
                    },
                    "required": ["symbol", "news_type"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="list_alternatives_datasets",
                description="Lists all 21 verified crypto/forex/commodities datasets from catalog with class breakdown. Use include_details=true for full endpoint specifications. Helps discover available data before fetching.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_details": {
                            "type": "boolean",
                            "description": "Include full dataset details",
                            "default": False
                        }
                    },
                    "additionalProperties": False
                }
            )
        ]

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> CallToolResult:
        """
        MCP method: Execute a tool.
        Delegates to appropriate handler based on tool name.
        """
        try:
            if name == "discover_alternatives_fields":
                result = await self._handle_discover_alternatives_fields(arguments)
            elif name == "get_alternatives_dataset" or name == "get_fields":
                # get_fields is an alias for compatibility with object_data_service
                result = await self._handle_get_dataset(arguments)
            elif name == "get_crypto_quote":
                result = await self._handle_get_crypto_quote(arguments)
            elif name == "get_crypto_historical":
                result = await self._handle_get_crypto_historical(arguments)
            elif name == "list_crypto":
                result = await self._handle_list_crypto(arguments)
            elif name == "get_forex_quote":
                result = await self._handle_get_forex_quote(arguments)
            elif name == "get_forex_historical":
                result = await self._handle_get_forex_historical(arguments)
            elif name == "list_forex":
                result = await self._handle_list_forex(arguments)
            elif name == "get_commodities_data":
                result = await self._handle_get_commodities_data(arguments)
            elif name == "get_batch_quotes":
                result = await self._handle_get_batch_quotes(arguments)
            elif name == "get_latest_alternatives_news":
                result = await self._handle_get_latest_alternatives_news(arguments)
            elif name == "get_alternatives_news_by_symbol":
                result = await self._handle_get_alternatives_news_by_symbol(arguments)
            elif name == "list_alternatives_datasets":
                result = await self._handle_list_alternatives_datasets(arguments)
            else:
                return CallToolResult(
                    content=[{"type": "text", "text": f"Unknown tool: {name}"}],
                    isError=True
                )

            # Canvas/workspace can explicitly request raw dataset JSON.
            if name == "get_fields" and arguments.get("_bh_raw"):
                return CallToolResult(
                    content=[{"type": "text", "text": json.dumps(result, default=str)}],
                    isError=False,
                )

            # Format result — compact large outputs into data store
            from core.agents.binomial_hash import bh_ingest
            if isinstance(result, str):
                text = bh_ingest(result, name)
            else:
                raw = json.dumps(result, default=str)
                text = bh_ingest(raw, name)

            return CallToolResult(
                content=[{"type": "text", "text": text}],
                isError=False,
            )

        except Exception as e:
            logger.error(f"Error in {name}: {e}")
            return CallToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                isError=True
            )

    async def _handle_discover_alternatives_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Discover fields using only real alternatives_catalog.json endpoints"""
        symbol = args.get("symbol")
        max_datasets = args.get("max_datasets", 10)

        if not symbol:
            return {"error": "Symbol is required"}

        try:
            # Use ONLY real endpoints from alternatives_catalog.json
            real_datasets = [
                "crypto-quote", "crypto-batch-quotes",
                "crypto-historical-1min", "crypto-historical-5min", "crypto-historical-15min",
                "crypto-historical-30min", "crypto-historical-1hour", "crypto-historical-4hour",
                "forex-quote", "forex-batch-quotes",
                "forex-historical-1min", "forex-historical-5min", "forex-historical-15min",
                "forex-historical-30min", "forex-historical-1hour", "forex-historical-4hour",
                "commodities-quote", "commodities-batch-quotes"
            ]

            # Pass period param for discovery to work with all endpoints
            discovery_params = {"period": "annual"}
            discovered = await self.field_discovery.discover_fields(symbol, max_datasets, discovery_params=discovery_params)

            # Filter to only fields from real endpoints
            real_fields = {}
            for field_name, field_info in discovered.items():
                source = field_info.get("source", "")
                if any(dataset in source for dataset in real_datasets):
                    real_fields[field_name] = field_info

            return {
                "symbol": symbol,
                "discovered_fields": len(real_fields),
                "total_endpoints": len(set(info["source"] for info in real_fields.values())),
                "fields": real_fields,
                "note": "Using only verified alternatives_catalog.json endpoints (21 total)"
            }

        except Exception as e:
            logger.error(f"Error discovering alternatives fields: {e}")
            return {"error": str(e)}

    async def _handle_get_crypto_quote(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get real-time crypto quote"""
        symbol = args.get("symbol")
        if not symbol:
            return {"error": "Symbol is required"}

        try:
            dataset = self.ddc_loader.get_dataset("crypto-quote")
            if not dataset:
                return {"error": "crypto-quote dataset not found"}

            data = await self.data_fetcher.fetch_dataset(symbol, dataset)
            return {"symbol": symbol, "quote": data}

        except Exception as e:
            logger.error(f"Error fetching crypto quote: {e}")
            return {"error": str(e)}

    async def _handle_get_crypto_historical(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get historical crypto price data"""
        symbol = args.get("symbol")
        timeframe = args.get("timeframe", "1hour")
        from_date = args.get("from")
        to_date = args.get("to")
        limit = args.get("limit")

        if not symbol:
            return {"error": "Symbol is required"}

        try:
            dataset_name = f"crypto-historical-{timeframe}"
            dataset = self.ddc_loader.get_dataset(dataset_name)
            if not dataset:
                return {"error": f"Dataset {dataset_name} not found. Valid timeframes: 1min, 5min, 15min, 30min, 1hour, 4hour"}

            # Build params
            params: Dict[str, Any] = {"symbol": symbol}

            # Provide sensible defaults when caller omits range
            if not from_date or not to_date:
                now_utc = datetime.utcnow()
                if not to_date:
                    to_date = now_utc.strftime("%Y-%m-%d")
                if not from_date:
                    days_back = DEFAULT_INTRADAY_LOOKBACK_DAYS.get(timeframe, 90)
                    from_date = (now_utc - timedelta(days=days_back)).strftime("%Y-%m-%d")

            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            if limit:
                params["limit"] = limit
            elif timeframe in {"1min", "5min", "15min"}:
                params["limit"] = DEFAULT_INTRADAY_LIMIT

            data = await self.data_fetcher.fetch_dataset(
                symbol,
                dataset,
                historical_params={k: v for k, v in params.items() if k != "symbol"},
            )
            return {"symbol": symbol, "timeframe": timeframe, "historical_data": data}

        except Exception as e:
            logger.error(f"Error fetching crypto historical: {e}")
            return {"error": str(e)}

    async def _handle_list_crypto(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all available cryptocurrencies"""
        try:
            dataset = self.ddc_loader.get_dataset("crypto-list")
            if not dataset:
                return {"error": "crypto-list dataset not found"}

            data = await self.data_fetcher.fetch_dataset("", dataset)
            return {"cryptocurrencies": data}

        except Exception as e:
            logger.error(f"Error listing crypto: {e}")
            return {"error": str(e)}

    async def _handle_get_forex_quote(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get real-time forex quote"""
        pair = args.get("pair")
        if not pair:
            return {"error": "Pair is required"}

        try:
            dataset = self.ddc_loader.get_dataset("forex-quote")
            if not dataset:
                return {"error": "forex-quote dataset not found"}

            data = await self.data_fetcher.fetch_dataset(pair, dataset)
            return {
                "pair": pair,
                "quote": data,
                "source": "Financial Modeling Prep (FMP)",
                "source_type": "market_data",
                "disclaimer": "Market rates, not central bank official rates"
            }

        except Exception as e:
            logger.error(f"Error fetching forex quote: {e}")
            return {"error": str(e)}

    async def _handle_get_forex_historical(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get historical forex price data"""
        pair = args.get("pair")
        timeframe = args.get("timeframe", "1hour")
        from_date = args.get("from")
        to_date = args.get("to")
        limit = args.get("limit")

        if not pair:
            return {"error": "Pair is required"}

        try:
            dataset_name = f"forex-historical-{timeframe}"
            dataset = self.ddc_loader.get_dataset(dataset_name)
            if not dataset:
                return {"error": f"Dataset {dataset_name} not found. Valid timeframes: 1min, 5min, 1hour (use get_alternatives_dataset with forex-historical-eod-light for daily rates)"}

            params: Dict[str, Any] = {"symbol": pair}
            if not from_date or not to_date:
                now_utc = datetime.utcnow()
                if not to_date:
                    to_date = now_utc.strftime("%Y-%m-%d")
                if not from_date:
                    days_back = DEFAULT_INTRADAY_LOOKBACK_DAYS.get(timeframe, 90)
                    from_date = (now_utc - timedelta(days=days_back)).strftime("%Y-%m-%d")

            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            if limit:
                params["limit"] = limit
            elif timeframe in {"1min", "5min", "15min"}:
                params["limit"] = DEFAULT_INTRADAY_LIMIT

            data = await self.data_fetcher.fetch_dataset(
                pair,
                dataset,
                historical_params={k: v for k, v in params.items() if k != "symbol"},
            )
            return {
                "pair": pair,
                "timeframe": timeframe,
                "historical_data": data,
                "source": "Financial Modeling Prep (FMP)",
                "source_type": "market_data",
                "disclaimer": "Market closing rates, not central bank official rates"
            }

        except Exception as e:
            logger.error(f"Error fetching forex historical: {e}")
            return {"error": str(e)}

    async def _handle_list_forex(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all available forex pairs"""
        try:
            dataset = self.ddc_loader.get_dataset("forex-list")
            if not dataset:
                return {"error": "forex-list dataset not found"}

            data = await self.data_fetcher.fetch_dataset("", dataset)
            return {"forex_pairs": data}

        except Exception as e:
            logger.error(f"Error listing forex: {e}")
            return {"error": str(e)}

    async def _handle_get_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for _handle_get_dataset for data workspace compatibility."""
        return await self._handle_get_dataset(args)

    async def _handle_get_dataset(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dataset-first fetch with required param checking."""
        dataset_names: List[str] = []
        ds = args.get("dataset")
        if ds:
            dataset_names.append(ds)
        datasets = args.get("datasets") or []
        dataset_names.extend(datasets)

        if not dataset_names:
            return {"error": "No dataset provided"}

        symbol = args.get("symbol") or ""
        params = args.get("params", {})

        async def fetch_dataset(name: str) -> Dict[str, Any]:
            d = self.ddc_loader.get_dataset(name)
            if not d:
                return {"error": "dataset_not_found"}

            required = []
            if d.params_schema:
                # Build skip keys - include identifier_param since data_fetcher handles it
                skip_keys = {"symbol", "apikey"}
                if d.identifier_param:
                    skip_keys.add(d.identifier_param)
                for key in d.params_schema.keys():
                    if key not in skip_keys and key not in params:
                        required.append(key)
            if required:
                return {
                    "error": "missing_required_params",
                    "required_params": required,
                    "notes": d.notes,
                    "hint": f"Pass {required} inside the 'params' object, not at top level"
                }

            try:
                return await self.data_fetcher.fetch_dataset(symbol, d, historical_params=params)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        factories = {name: (lambda dataset_name=name: fetch_dataset(dataset_name)) for name in dataset_names}
        raw_results = await gather_dict(factories, concurrency_limit=4)

        results: Dict[str, Any] = {}
        missing: Dict[str, Any] = {}
        for name, payload in raw_results.items():
            # payload can be a list (raw data) or dict (with error or wrapped data)
            if isinstance(payload, dict) and payload.get("error") in {"dataset_not_found", "missing_required_params"}:
                missing[name] = payload
            elif isinstance(payload, list):
                # Raw list data - wrap it for consistency
                results[name] = {"data": payload}
            else:
                results[name] = payload

        out: Dict[str, Any] = {"datasets": results}
        if missing:
            out["status"] = "missing_required_params"
            out["missing_params"] = missing
        return out

    async def _handle_get_commodities_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get commodities quotes or historical data"""
        symbol = args.get("symbol")
        data_type = args.get("data_type", "quote")
        timeframe = args.get("timeframe", "1hour")
        from_date = args.get("from")
        to_date = args.get("to")
        limit = args.get("limit")

        if not symbol:
            return {"error": "Symbol is required"}

        try:
            if data_type == "quote":
                dataset = self.ddc_loader.get_dataset("commodities-quote")
                if not dataset:
                    return {"error": "commodities-quote dataset not found"}

                data = await self.data_fetcher.fetch_dataset(symbol, dataset)
                return {"symbol": symbol, "quote": data}

            elif data_type == "historical":
                # Map timeframe to dataset name - support EOD for daily data
                if timeframe in ("eod", "eod-light", "daily"):
                    dataset_name = "commodities-historical-eod-light"
                elif timeframe == "eod-full":
                    dataset_name = "commodities-historical-eod-full"
                else:
                    dataset_name = f"commodities-historical-{timeframe}"
                
                dataset = self.ddc_loader.get_dataset(dataset_name)
                if not dataset:
                    return {"error": f"Dataset {dataset_name} not found. Available: 1min, 5min, 1hour, eod, eod-full"}

                params: Dict[str, Any] = {"symbol": symbol}
                if not from_date or not to_date:
                    now_utc = datetime.utcnow()
                    if not to_date:
                        to_date = now_utc.strftime("%Y-%m-%d")
                    if not from_date:
                        days_back = DEFAULT_INTRADAY_LOOKBACK_DAYS.get(timeframe, 14)
                        from_date = (now_utc - timedelta(days=days_back)).strftime("%Y-%m-%d")

                if from_date:
                    params["from"] = from_date
                if to_date:
                    params["to"] = to_date
                if limit:
                    params["limit"] = limit
                elif timeframe in {"1min", "5min", "15min"}:
                    params["limit"] = DEFAULT_INTRADAY_LIMIT

                data = await self.data_fetcher.fetch_dataset(
                    symbol,
                    dataset,
                    historical_params={k: v for k, v in params.items() if k != "symbol"},
                )
                return {"symbol": symbol, "timeframe": timeframe, "historical_data": data}

            else:
                return {"error": "data_type must be 'quote' or 'historical'"}

        except Exception as e:
            logger.error(f"Error fetching commodities data: {e}")
            return {"error": str(e)}

    async def _handle_get_batch_quotes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get batch quotes for crypto/forex/commodities"""
        asset_class = args.get("asset_class")

        if not asset_class:
            return {"error": "asset_class is required (crypto, forex, or commodities)"}

        try:
            if asset_class == "crypto":
                dataset = self.ddc_loader.get_dataset("crypto-batch-quotes")
            elif asset_class == "forex":
                dataset = self.ddc_loader.get_dataset("forex-batch-quotes")
            elif asset_class == "commodities":
                dataset = self.ddc_loader.get_dataset("commodities-batch-quotes")
            else:
                return {"error": "asset_class must be 'crypto', 'forex', or 'commodities'"}

            if not dataset:
                return {"error": f"{asset_class}-batch-quotes dataset not found"}

            data = await self.data_fetcher.fetch_dataset("", dataset)
            return {"asset_class": asset_class, "batch_quotes": data}

        except Exception as e:
            logger.error(f"Error fetching batch quotes: {e}")
            return {"error": str(e)}

    async def _handle_list_alternatives_datasets(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all 21 verified datasets from alternatives_catalog.json"""
        include_details = args.get("include_details", False)

        try:
            datasets = self.field_discovery.list_datasets(include_details)

            # Filter to crypto, forex, and commodities classes from alternatives_catalog.json
            alternatives_datasets = [
                ds for ds in datasets
                if ds.get("class") in ["crypto", "forex", "commodities"]
            ]

            return {
                "total_datasets": len(alternatives_datasets),
                "crypto_datasets": len([ds for ds in alternatives_datasets if ds.get("class") == "crypto"]),
                "forex_datasets": len([ds for ds in alternatives_datasets if ds.get("class") == "forex"]),
                "commodities_datasets": len([ds for ds in alternatives_datasets if ds.get("class") == "commodities"]),
                "datasets": alternatives_datasets,
                "note": "All 21 endpoints verified from alternatives_catalog.json"
            }

        except Exception as e:
            logger.error(f"Error listing alternatives datasets: {e}")
            return {"error": str(e)}

    async def _handle_get_latest_alternatives_news(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_latest_alternatives_news tool call - fetch latest crypto/forex news with auto-pagination"""
        news_type = args["news_type"]
        start_page = max(0, args.get("page", 0))
        limit = min(max(1, args.get("limit", 20)), 100)
        max_results = args.get("max_results") or 100

        # Validate and cap max_results
        try:
            max_results = max(1, min(int(max_results), 500))
        except (TypeError, ValueError):
            max_results = 100

        # Map news_type to dataset name
        dataset_map = {
            "crypto": "crypto-news-latest",
            "forex": "forex-news-latest"
        }

        if news_type not in dataset_map:
            return {"error": "invalid_parameters", "message": f"news_type must be one of {list(dataset_map.keys())}"}

        dataset_name = dataset_map[news_type]
        dataset = self.ddc_loader.get_dataset(dataset_name)
        if not dataset:
            return {"error": "dataset_not_found", "dataset": dataset_name}

        # Auto-paginate until we hit max_results or run out of data
        news_items: List[Any] = []
        current_page = start_page
        pages_fetched = 0

        try:
            while len(news_items) < max_results:
                params = {"page": current_page, "limit": limit}
                data = await self.data_fetcher.fetch_dataset("", dataset, historical_params=params)

                # Normalize to list
                chunk: List[Any]
                if isinstance(data, list):
                    chunk = data
                else:
                    chunk = [data] if data else []

                if not chunk:
                    break

                news_items.extend(chunk)
                pages_fetched += 1

                # If we got fewer items than limit, we've hit the last page
                if len(chunk) < limit:
                    break

                current_page += 1

        except Exception as exc:
            return {"error": str(exc)}

        return {
            "news_type": news_type,
            "start_page": start_page,
            "pages_fetched": pages_fetched,
            "limit_per_page": limit,
            "max_results": max_results,
            "count": len(news_items[:max_results]),
            "data": news_items[:max_results]
        }

    async def _handle_get_alternatives_news_by_symbol(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_alternatives_news_by_symbol tool call - fetch news for specific crypto/forex symbol with auto-pagination"""
        symbol = args["symbol"].upper()
        news_type = args["news_type"]
        start_page = max(0, args.get("page", 0))
        limit = min(max(1, args.get("limit", 20)), 100)
        max_results = args.get("max_results") or 100

        # Validate and cap max_results
        try:
            max_results = max(1, min(int(max_results), 500))
        except (TypeError, ValueError):
            max_results = 100

        # Map news_type to dataset name
        dataset_map = {
            "crypto": "crypto-news",
            "forex": "forex-news"
        }

        if news_type not in dataset_map:
            return {"error": "invalid_parameters", "message": f"news_type must be one of {list(dataset_map.keys())}"}

        dataset_name = dataset_map[news_type]
        dataset = self.ddc_loader.get_dataset(dataset_name)
        if not dataset:
            return {"error": "dataset_not_found", "dataset": dataset_name}

        # Auto-paginate until we hit max_results or run out of data
        news_items: List[Any] = []
        current_page = start_page
        pages_fetched = 0

        try:
            while len(news_items) < max_results:
                params = {"page": current_page, "limit": limit, "size": limit}
                # Symbol passed via data_fetcher (uses identifier_param "symbols")
                data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=params)

                # Normalize to list
                chunk: List[Any]
                if isinstance(data, list):
                    chunk = data
                else:
                    chunk = [data] if data else []

                if not chunk:
                    break

                news_items.extend(chunk)
                pages_fetched += 1

                # If we got fewer items than limit, we've hit the last page
                if len(chunk) < limit:
                    break

                current_page += 1

        except Exception as exc:
            return {"error": str(exc)}

        return {
            "symbol": symbol,
            "news_type": news_type,
            "start_page": start_page,
            "pages_fetched": pages_fetched,
            "limit_per_page": limit,
            "max_results": max_results,
            "count": len(news_items[:max_results]),
            "data": news_items[:max_results]
        }

    async def connect(self):
        """Initialize connections"""
        await self.data_fetcher.connect()
        logger.info("FMPAlternativesServer connected")

    async def cleanup(self):
        """Cleanup connections"""
        await self.data_fetcher.cleanup()
        self.field_manager.close()
        logger.info("FMPAlternativesServer cleaned up")


# Factory function for easy instantiation
def create_fmp_alternatives_server(api_key: str = None) -> FMPAlternativesServer:
    """
    Create an FMP Crypto & Forex Server instance.

    Args:
        api_key: FMP API key (if not provided, reads from FMP_API_KEY environment variable)

    Returns:
        Configured FMPAlternativesServer instance
    """
    if not api_key:
        api_key = os.getenv("FMP_API_KEY")
        if not api_key:
            raise ValueError("FMP_API_KEY environment variable or api_key parameter required")

    return FMPAlternativesServer(api_key)
