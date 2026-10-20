"""
FMP Market Data MCP Server - Refactored Version
Under 500 lines following CODING_RULES.md
Delegates to helper modules for specific functionality
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

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


class MissingRequiredParamsError(Exception):
    """Raised when an endpoint requires parameters not provided by the caller."""

    def __init__(self, details: Dict[str, Any]):
        super().__init__("missing_required_params")
        self.details = details


class FMPMarketDataServer(MCPServer):
    """
    MCP Server for FMP market data discovery and retrieval.
    Refactored to use helper modules and stay under 500 lines.
    """
    
    def __init__(self, api_key: str = None):
        """Initialize FMP Market Data Server with helper modules"""
        super().__init__()
        self._name = "FMPMarketDataServer"
        self.use_structured_content = False  # Required by openai-agents SDK 0.2.0+

        # Load API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("FMP_API_KEY")

        if not api_key:
            raise ValueError("FMP_API_KEY not provided")

        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com"

        # Initialize helper modules
        self.ddc_loader = DDCLoader()
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
        
        logger.info("FMPMarketDataServer initialized (refactored)")
    
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
    
    async def connect(self):
        """Initialize connections"""
        await self.data_fetcher.connect()
        logger.info("FMPMarketDataServer connected")
    
    async def cleanup(self):
        """Cleanup connections"""
        await self.data_fetcher.cleanup()
        self.field_manager.close()
        logger.info("FMPMarketDataServer cleaned up")
    
    def get_available_tools(self) -> List[MCPTool]:
        """Get list of available MCP tools"""
        return [
            MCPTool(
                name="discover_fields",
                description="Probes FMP endpoints to build field catalog for a symbol. Returns cached mappings if < 7 days old. Use to discover available field names before fetching data. Probes max_datasets endpoints (default 80).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol to discover fields for"
                        },
                        "max_datasets": {
                            "type": "integer",
                            "description": "Maximum datasets to probe",
                            "default": 80
                        },
                        "period": {
                            "type": "string",
                            "enum": ["annual", "quarter"],
                            "description": "Time period for analyst estimates and forecasts (annual or quarterly)",
                            "default": "annual"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="discover_market_wide_fields",
                description="Discovers market-wide aggregate fields for sectors and industries by snapshot date. Returns available metrics across entire sectors/industries (not individual stocks). Use to analyze market trends by date.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol (kept for UX consistency; not used by market_wide endpoints)"
                        },
                        "date": {
                            "type": "string",
                            "description": "Snapshot date (YYYY-MM-DD); defaults to today"
                        },
                        "include": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["sector", "industry"]},
                            "description": "Which market_wide groups to include",
                            "default": ["sector", "industry"]
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
                name="discover_valuation_fields",
                description="Probes FMP endpoints to discover valuation metrics: P/E ratios, EV/EBITDA, price multiples, DCF inputs, analyst estimates. Use before comparable company analysis to see available valuation data. Default probes 80 datasets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol to discover valuation fields for"
                        },
                        "max_datasets": {
                            "type": "integer",
                            "description": "Maximum datasets to probe",
                            "default": 80
                        },
                        "period": {
                            "type": "string",
                            "enum": ["annual", "quarter"],
                            "description": "Time period for analyst estimates and forecasts (annual or quarterly)",
                            "default": "annual"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="discover_technical_fields",
                description="Discovers technical analysis fields: RSI, MACD, moving averages, Bollinger Bands, price data, chart endpoints. Use include_intraday=true to discover 1min, 5min, 15min, 30min, 1hour timeframes. Returns available technical indicators.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol to discover technical fields for"
                        },
                        "include_intraday": {
                            "type": "boolean",
                            "description": "Include intraday chart timeframes (1min, 5min, etc)",
                            "default": True
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="run_stock_screener",
                description="Filters stocks using FMP screener with any combination of filters. Example filters: sector, industry, marketCapMoreThan, priceMoreThan, betaMoreThan, volumeMoreThan. Supports sort_by and limit. Returns matching symbols.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return (default from API is 50)"
                        },
                        "order": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "Sort order when sort_by is provided"
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Field to sort by (e.g., marketCap, price, beta)"
                        },
                        "filters": {
                            "type": "object",
                            "description": "Key/value map of screener filters (sector, industry, marketCapMoreThan, etc.)",
                            "additionalProperties": True
                        },
                        "include_raw": {
                            "type": "boolean",
                            "description": "Include raw API payload along with summary stats",
                            "default": True
                        }
                    },
                    "additionalProperties": True
                }
            ),
            MCPTool(
                name="get_fields_batch",
                description="Batch-fetch the SAME dataset/fields for MULTIPLE symbols in one call. Returns per-symbol results with individual BH keys. Use for comps tables, portfolio analytics, or any multi-symbol data pull. MUCH faster than calling get_fields per symbol. EXAMPLE: {{\"symbols\": [\"AAPL\",\"MSFT\",\"NVDA\"], \"dataset\": \"key-metrics-ttm\"}}",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of stock symbols (e.g., ['AAPL','MSFT','NVDA','AMZN'])"
                        },
                        "dataset": {
                            "type": "string",
                            "description": "Single dataset name for all symbols (e.g., 'key-metrics-ttm', 'company-quote')"
                        },
                        "datasets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Multiple dataset names for all symbols"
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific field names to fetch for all symbols"
                        },
                        "params": {
                            "type": "object",
                            "description": "Optional parameters (e.g., {\"period\": \"annual\", \"limit\": 1})",
                            "additionalProperties": True
                        }
                    },
                    "required": ["symbols"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_fields",
                description="Get market data for a symbol. RECOMMENDED: Use 'dataset' or 'datasets' for fast, error-free bulk retrieval (no params needed). Use 'fields' only when you need specific metrics AND are prepared to add required params if you get missing_required_params error. For MULTIPLE symbols with the same dataset, use get_fields_batch instead. EXAMPLE: {{\"symbol\": \"AAPL\", \"dataset\": \"company-quote\"}} or {{\"symbol\": \"AAPL\", \"datasets\": [\"company-profile\", \"company-quote\"]}}",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol (e.g., 'AAPL', 'MSFT')"
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "CAUTION: Specific field names. Many fields require 'params' or return missing_required_params error. Use 'dataset'/'datasets' instead for most cases."
                        },
                        "dataset": {
                            "type": "string",
                            "description": "RECOMMENDED: Single dataset name for bulk data (e.g., 'company-profile', 'company-quote'). Fast and requires NO params. Use list_datasets() to discover available datasets."
                        },
                        "datasets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "RECOMMENDED: Multiple dataset names for bulk retrieval. Fetch multiple datasets in one call. Fast and requires NO params for most datasets."
                        },
                        "params": {
                            "type": "object",
                            "description": "Required parameters for certain fields (e.g., {{\"period\": \"annual\", \"limit\": 1}} for ratio fields). If you get missing_required_params error, either add these params OR switch to dataset approach.",
                            "additionalProperties": True
                        },
                        "historical": {
                            "type": "boolean",
                            "description": "Get historical time series data",
                            "default": False
                        },
                        "period": {
                            "type": "string",
                            "description": "Period for historical data",
                            "default": "annual"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of historical periods",
                            "default": 10
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="list_datasets",
                description="Lists all FMP datasets in catalog (200+ endpoints). Use include_details=true for full endpoint specifications. Returns dataset names for use with get_fields. Helpful for browsing available data sources.",
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
            ),
            MCPTool(
                name="get_historical_data",
                description="Fetches historical OHLCV price bars for charting. Provide symbol and period (1D, 5D, 1M, 3M, 6M, YTD, 1Y, 2Y, 5Y, max) OR start/end dates (YYYY-MM-DD). Returns time series data for plotting.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol"
                        },
                        "period": {
                            "type": "string",
                            "description": "Time period (1D, 5D, 1M, 3M, 6M, YTD, 1Y, 2Y, 5Y, max)"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start date (YYYY-MM-DD)"
                        },
                        "end": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD)"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="list_cached_fields",
                description="Browses cached field catalog (1000+ discovered fields). Provide optional query for search (e.g., 'revenue', 'profit margin'). Returns field names, sources, and timestamps. Faster than discover_fields for known fields.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term (uses LIKE)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 50
                        }
                    },
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_latest_news",
                description="Fetch latest financial news headlines and press releases across all stocks (market-wide) with auto-pagination. Returns structured list with title, publishedDate, site, url, and associated symbols. Automatically fetches multiple pages up to max_results. Use this for: (1) market-wide headlines, (2) recent news scanning, (3) news discovery before drilling into specifics. Data is cached for 30 min. DO NOT use for article content—this returns headlines only; use web_search for full article text.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "news_type": {
                            "type": "string",
                            "enum": ["general", "press-releases", "stock"],
                            "description": "Type: 'general' = broad market news (Fed, macro, indices), 'press-releases' = official company announcements (earnings, acquisitions, guidance), 'stock' = stock-specific news aggregated across all tickers"
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
                name="get_news_by_symbol",
                description="Fetch news headlines or press releases for specific ticker symbol(s) with auto-pagination. Returns structured list with title, text snippet, publishedDate, site, url, and symbol. Automatically fetches multiple pages up to max_results. Use this for: (1) ticker-specific news, (2) company announcements, (3) catalyst research. Data is cached for 30 min. Returns headlines only—use web_search to fetch full article content when needed.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA'). Single symbol only—use multiple calls for multiple tickers or use get_latest_news for market-wide scan."
                        },
                        "news_type": {
                            "type": "string",
                            "enum": ["news", "press-releases"],
                            "description": "Type: 'news' = general stock news (media coverage, analysis, market moves), 'press-releases' = official company announcements (SEC filings, earnings, M&A, guidance updates)"
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
        CRITICAL: Always returns CallToolResult, never raises exceptions.
        """
        try:
            # Validate arguments exist
            if arguments is None:
                arguments = {}

            if name == "discover_fields":
                result = await self._handle_discover_fields(arguments)
            elif name == "discover_market_wide_fields":
                result = await self._handle_discover_market_wide_fields(arguments)
            elif name == "discover_valuation_fields":
                result = await self._handle_discover_valuation_fields(arguments)
            elif name == "discover_technical_fields":
                result = await self._handle_discover_technical_fields(arguments)
            elif name == "get_fields_batch":
                result = await self._handle_get_fields_batch(arguments)
            elif name == "get_fields":
                result = await self._handle_get_fields(arguments)
            elif name == "list_datasets":
                result = await self._handle_list_datasets(arguments)
            elif name == "get_historical_data":
                result = await self._handle_get_historical_data(arguments)
            elif name == "list_cached_fields":
                result = await self._handle_list_cached_fields(arguments)
            elif name == "run_stock_screener":
                result = await self._handle_run_stock_screener(arguments)
            elif name == "get_latest_news":
                result = await self._handle_get_latest_news(arguments)
            elif name == "get_news_by_symbol":
                result = await self._handle_get_news_by_symbol(arguments)
            else:
                logger.warning(f"Unknown tool requested: {name}")
                return CallToolResult(
                    content=[{
                        "type": "text",
                        "text": json.dumps({
                            "error": "unknown_tool",
                            "message": f"Tool '{name}' not found. Available tools: discover_fields, get_fields, get_fields_batch, list_datasets, get_latest_news, get_news_by_symbol, etc.",
                            "requested_tool": name
                        })
                    }],
                    isError=True
                )

            # Canvas/workspace can explicitly request raw dataset JSON.
            if name == "get_fields" and arguments.get("_bh_raw"):
                return CallToolResult(
                    content=[{"type": "text", "text": json.dumps(result, default=str)}],
                    isError=False,
                )

            # Format result - handle all result types gracefully
            from core.agents.binomial_hash import bh_ingest

            # For batch tools, ingest each symbol separately so each gets its own BH key
            if name == "get_fields_batch" and isinstance(result, dict) and "results" in result:
                lines = []
                for sym, sym_data in result.get("results", {}).items():
                    sym_raw = json.dumps(sym_data, default=str)
                    sym_text = bh_ingest(sym_raw, f"get_fields_batch_{sym}")
                    lines.append(f"**{sym}**: {sym_text}")
                if result.get("errors"):
                    for sym, err in result["errors"].items():
                        lines.append(f"**{sym}**: ERROR — {err}")
                text = "\n".join(lines) if lines else "No results"
            elif isinstance(result, str):
                text = bh_ingest(result, name)
            elif isinstance(result, (dict, list)):
                raw = json.dumps(result, default=str)
                text = bh_ingest(raw, name)
            else:
                text = str(result)

            return CallToolResult(
                content=[{"type": "text", "text": text}],
                isError=False,
            )

        except ValueError as e:
            # Parameter validation errors - return helpful error message
            error_msg = str(e)
            logger.warning(
                f"Parameter validation error in {name}: {error_msg}",
                extra={"tool_name": name, "arguments": arguments}
            )
            return CallToolResult(
                content=[{
                    "type": "text",
                    "text": json.dumps({
                        "error": "invalid_parameters",
                        "message": error_msg,
                        "tool": name,
                        "provided_args": list(arguments.keys()) if arguments else [],
                        "suggestion": "Check tool description for required parameters"
                    })
                }],
                isError=True
            )

        except Exception as e:
            # Unexpected errors - log thoroughly but don't crash
            logger.error(
                f"Unexpected error in {name}: {e}",
                exc_info=True,  # Include stack trace
                extra={
                    "tool_name": name,
                    "arguments": arguments,
                    "error_type": type(e).__name__
                }
            )
            return CallToolResult(
                content=[{
                    "type": "text",
                    "text": json.dumps({
                        "error": "tool_execution_failed",
                        "message": f"Tool '{name}' encountered an error: {str(e)}",
                        "error_type": type(e).__name__,
                        "tool": name
                    })
                }],
                isError=True
            )
    
    async def _handle_discover_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle discover_fields tool call"""
        symbol = args["symbol"]
        max_datasets = args.get("max_datasets", 80)
        period = args.get("period", "annual")

        # Build discovery parameters for endpoints that require them (e.g., analyst-estimates)
        # Include sane defaults for technical indicator endpoints to avoid 400s during discovery
        discovery_params = {"period": period, "timeframe": "1day", "periodLength": 14}

        result = await self.field_discovery.discover_fields(symbol, max_datasets, discovery_params=discovery_params)

        # Add informative message about FMP's limitations
        field_count = len(result) if isinstance(result, dict) else 0

        enhanced_result = {
            "fields": result,
            "info": f"Found {field_count} financial fields from FMP (financial statements, ratios, market data). If you need non-financial operational metrics, use web_search.",
            "field_count": field_count
        }

        return enhanced_result
    
    async def _handle_discover_valuation_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle discover_valuation_fields tool call - discovers all fields and lets AI decide what's relevant"""
        symbol = args["symbol"]
        max_datasets = args.get("max_datasets", 80)  # More datasets for comprehensive valuation discovery
        period = args.get("period", "annual")

        # Build discovery parameters for endpoints that require them (e.g., analyst-estimates)
        # Include sane defaults for technical indicator endpoints to avoid 400s during discovery
        discovery_params = {"period": period, "timeframe": "1day", "periodLength": 14}

        # Use existing discovery but with more datasets to ensure we get valuation-relevant endpoints
        result = await self.field_discovery.discover_fields(symbol, max_datasets, discovery_params=discovery_params)

        # Add statistics and metadata
        stats = self.field_discovery.get_field_stats()
        result.update(stats)

        # Add information about which endpoints were discovered
        if "by_endpoint" in stats:
            result["discovered_endpoints"] = list(stats["by_endpoint"].keys())

        return result

    async def _handle_discover_technical_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle discover_technical_fields tool call.

        Uses DDC catalog metadata for fast discovery. Fix: include
        'technical' class datasets (technical indicators) in addition to
        core 'market' datasets so RSI/SMA/EMA/etc. are properly discovered.
        """
        symbol = args["symbol"]

        # SMART OPTIMIZATION: Use DDC catalog instead of expensive API discovery
        logger.debug(f"[OPTIMIZED] Using DDC catalog for technical field discovery (symbol: {symbol})")

        # Get technical analysis endpoints from DDC catalog
        # Note: technical indicators live under the 'technical' class in the catalog
        technical_datasets = self.ddc_loader.filter_by_class("technical")
        market_datasets = self.ddc_loader.filter_by_class("market")

        # Filter for discoverable datasets only
        discoverable_technical = [d for d in technical_datasets if d.discoverable]
        discoverable_market = [d for d in market_datasets if d.discoverable]

        # Create field mappings from catalog metadata
        technical_fields = {}
        endpoint_stats = {}

        # Process technical indicator endpoints
        for dataset in discoverable_technical:
            endpoint_name = dataset.dataset
            endpoint_stats[endpoint_name] = {
                "url": dataset.url,
                "description": dataset.notes or f"Technical data from {endpoint_name}",
                "cache_ttl": dataset.cache_ttl,
                "rate_limit": dataset.rate_limit.dict(),
                "type": "technical"
            }

            # Generate field mappings based on endpoint type
            if "technical-indicator" in endpoint_name:
                # Use field_mappings from DDC catalog if available
                if dataset.field_mappings and "fields" in dataset.field_mappings:
                    # Generate fields from configuration
                    for field_config in dataset.field_mappings["fields"]:
                        field_name = field_config["name"]
                        # Enrich params with sensible defaults for immediate use
                        params = dict(field_config.get("params", {}))
                        if "timeframe" not in params:
                            params["timeframe"] = "1day"
                        if "periodLength" not in params:
                            # Choose defaults by indicator type
                            ind = endpoint_name.split("-")[-1].lower()
                            if ind == "rsi":
                                params["periodLength"] = 14
                            elif ind == "ema":
                                # Common EMA window when unspecified
                                params["periodLength"] = 12
                            elif ind == "sma":
                                params["periodLength"] = 20
                            elif ind in ("bbands", "standarddeviation"):
                                params["periodLength"] = 20
                            elif ind in ("stoch", "williams"):
                                params["periodLength"] = 14
                            else:
                                params["periodLength"] = 14

                        technical_fields[field_name] = {
                            "endpoint": endpoint_name,
                            "description": dataset.notes or f"{field_name.upper()} indicator",
                            "source": "FMP Technical Indicators",
                            "params": params
                        }
                else:
                    # Fallback to simple field name (without _value suffix)
                    indicator_type = endpoint_name.split("-")[-1]
                    # Provide sensible default params
                    default_params = {"timeframe": "1day"}
                    it = indicator_type.lower()
                    if it == "rsi":
                        default_params["periodLength"] = 14
                    elif it == "ema":
                        default_params["periodLength"] = 12
                    elif it == "sma":
                        default_params["periodLength"] = 20
                    elif it in ("bbands", "standarddeviation"):
                        default_params["periodLength"] = 20
                    elif it in ("stoch", "williams"):
                        default_params["periodLength"] = 14
                    else:
                        default_params["periodLength"] = 14
                    technical_fields[indicator_type] = {
                        "endpoint": endpoint_name,
                        "description": f"{indicator_type.upper()} indicator",
                        "source": "FMP Technical Indicators",
                        "params": default_params
                    }
            elif "historical-chart" in endpoint_name:
                # Chart data
                timeframe = endpoint_name.split("-")[-1]  # e.g., "1min", "1day"
                for field in ["open", "high", "low", "close", "volume"]:
                    technical_fields[f"{timeframe}_{field}"] = {
                        "endpoint": endpoint_name,
                        "description": f"{timeframe} {field} price data",
                        "source": "FMP Historical Charts"
                    }

        # Process key market endpoints (quotes, fundamentals)
        key_market_endpoints = ["company-quote", "stock-price-change", "key-metrics", "ratios"]
        for dataset in discoverable_market:
            if dataset.dataset in key_market_endpoints:
                endpoint_name = dataset.dataset
                endpoint_stats[endpoint_name] = {
                    "url": dataset.url,
                    "description": dataset.notes or f"Market data from {endpoint_name}",
                    "cache_ttl": dataset.cache_ttl,
                    "rate_limit": dataset.rate_limit.dict(),
                    "type": "market"
                }

                # Add common financial fields
                if endpoint_name == "company-quote":
                    for field in ["price", "volume", "marketCap", "change", "changesPercentage"]:
                        technical_fields[field] = {
                            "endpoint": endpoint_name,
                            "description": f"Current {field} from real-time quote",
                            "source": "FMP Real-time Quote"
                        }

        # Build response in same format as expensive discovery
        total_fields = len(technical_fields)
        total_endpoints = len(endpoint_stats)

        result = {
            "symbol": symbol,
            "discovery_method": "DDC_catalog_optimized",
            "total_fields_discovered": total_fields,
            "total_endpoints": total_endpoints,
            "fields": technical_fields,
            "by_endpoint": endpoint_stats,
            "discovered_endpoints": list(endpoint_stats.keys()),
            "performance_note": f"⚡ OPTIMIZED: Instant catalog lookup vs expensive API discovery ({total_endpoints} endpoints, {total_fields} fields)"
        }

        logger.debug(f"[OPTIMIZED] DDC catalog discovery complete: {total_endpoints} endpoints, {total_fields} fields (instant vs 50+ seconds)")

        return result

    async def _handle_get_fields_batch(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Batch-fetch the same dataset/fields for multiple symbols concurrently.
        Returns per-symbol results. Each symbol's data gets its own BH key via
        the bh_ingest call in call_tool's result formatting.
        """
        import asyncio

        symbols = args.get("symbols", [])
        if not symbols:
            raise ValueError("get_fields_batch requires 'symbols' (list of stock symbols)")

        # Build per-symbol args (same dataset/fields/params for all)
        base_args = {k: v for k, v in args.items() if k != "symbols"}

        # --- Fast-fail: validate params once before iterating all symbols ---
        fields = base_args.get("fields")
        dataset = base_args.get("dataset")
        datasets = base_args.get("datasets")
        params = base_args.get("params", {})

        if fields and not dataset and not datasets:
            endpoints = self.field_manager.get_endpoints_for_fields(fields)

            # Cache miss — run discovery once with a probe symbol instead of
            # letting every concurrent task trigger its own discovery.
            if not endpoints:
                logger.info(f"get_fields_batch: cache miss for {fields}, running single discovery with {symbols[0]}")
                await self.field_discovery.discover_fields(symbols[0], max_datasets=80, discovery_params=params)
                endpoints = self.field_manager.get_endpoints_for_fields(fields)

            if endpoints:
                missing_requirements: Dict[str, Dict[str, Any]] = {}
                for endpoint_name, endpoint_fields in endpoints.items():
                    ds = self.ddc_loader.get_dataset(endpoint_name)
                    if not ds or not ds.params_schema:
                        continue
                    required = [
                        key for key in ds.params_schema.keys()
                        if key not in ("symbol", "apikey") and key not in params
                    ]
                    if required:
                        missing_requirements[endpoint_name] = {
                            "fields": endpoint_fields,
                            "required_params": required,
                            "notes": ds.notes,
                        }

                if missing_requirements:
                    return {
                        "results": {},
                        "errors": {
                            "_all": {
                                "status": "missing_required_params",
                                "missing_params": missing_requirements,
                                "message": "Some fields require additional parameters; please provide them and retry.",
                            }
                        }
                    }

        sem = asyncio.Semaphore(4)

        async def fetch_one(symbol: str) -> Tuple[str, Any]:
            async with sem:
                try:
                    per_sym_args = {"symbol": symbol, **base_args}
                    return symbol, await self._handle_get_fields(per_sym_args)
                except Exception as e:
                    logger.warning(f"get_fields_batch: {symbol} failed: {e}")
                    return symbol, {"error": str(e)}

        tasks = [fetch_one(sym) for sym in symbols]
        settled = await asyncio.gather(*tasks, return_exceptions=True)

        results: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        for item in settled:
            if isinstance(item, BaseException):
                errors["_gather"] = str(item)
                continue
            sym, payload = item
            if isinstance(payload, dict) and "error" in payload:
                errors[sym] = payload["error"]
            else:
                results[sym] = payload

        response: Dict[str, Any] = {"results": results}
        if errors:
            response["errors"] = errors
        return response

    async def _handle_get_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_fields tool call with historical support"""
        
        # Symbol can be optional for market-wide endpoints
        symbol = args.get("symbol") or args.get("ticker") or args.get("symbols")
        fields = args.get("fields")
        historical = args.get("historical", False)
        params = args.get("params", {})  # Get optional params for endpoints
        dataset = args.get("dataset")
        datasets = args.get("datasets")
        

        # Dataset-first shortcut: allow agents to fetch entire datasets without enumerating fields.
        if dataset or datasets:
            from .field_map_manager import DATASET_ALIASES
            dataset_names: List[str] = []
            if dataset:
                dataset_names.append(DATASET_ALIASES.get(dataset, dataset))
            if datasets:
                dataset_names.extend(DATASET_ALIASES.get(d, d) for d in datasets)

            results, missing = await self._fetch_datasets_direct(symbol, dataset_names, params)

            # When the caller also specified `fields`, trim each dataset's data
            # dict to only those keys.  This prevents returning 50+ metrics when
            # only 6 were requested — avoids context bloat in the LLM conversation.
            if fields and results:
                keep = set(fields)
                for ds_payload in results.values():
                    ds_data = ds_payload.get("data") if isinstance(ds_payload, dict) else None
                    if isinstance(ds_data, dict):
                        trimmed = {k: v for k, v in ds_data.items() if k in keep}
                        if trimmed:
                            ds_payload["data"] = trimmed

            response: Dict[str, Any] = {
                "symbol": symbol,
                "datasets": results,
            }

            if missing:
                response["unfulfilled"] = missing

            return response

        if not fields:
            error_msg = (
                f"Either 'fields' or 'dataset(s)' must be provided to get_fields. "
                f"Received args: {list(args.keys())}"
            )
            logger.error(f"Invalid get_fields call: {error_msg}")
            raise ValueError(error_msg)

        # Compute metadata before fetching
        endpoints = self.field_manager.get_endpoints_for_fields(fields)
        mapping_hits = len([f for f in fields if self.field_manager.get_field_endpoint(f)])
        mapping_misses = len(fields) - mapping_hits

        if historical:
            # Use historical data handler for time series
            period = args.get("period", "annual")
            limit = args.get("limit", 10)

            result = await self.historical_data.get_historical_metrics(
                symbol, fields, period, limit
            )

            return {
                "symbol": symbol,
                "historical": True,
                "period": period,
                "data": result,
                "metadata": {  # NEW - optional field
                    "requested_fields": len(fields),
                    "endpoints_touched": list(endpoints.keys())[:10] if endpoints else [],  # Cap at 10
                    "api_calls": len(endpoints) if endpoints else 0,
                    "cache_used": len(endpoints) > 0,
                    "mapping_hits": mapping_hits,
                    "mapping_misses": mapping_misses
                }
            }
        else:
            # Get current values using targeted extraction
            try:
                result = await self._get_current_fields(symbol, fields, params)
            except MissingRequiredParamsError as exc:
                return {
                    "status": "missing_required_params",
                    "symbol": symbol,
                    "missing_params": exc.details,
                    "message": "Some fields require additional parameters; please provide them and retry."
                }
            
            # Identify which fields were found and which weren't
            found_fields = list(result.keys())
            missing_fields = [f for f in fields if f not in found_fields]
            
            response = {
                "symbol": symbol,
                "historical": False,
                "data": result,
                "found": found_fields,
                "missing": missing_fields
            }
            
            # Add helpful message if fields are missing
            if missing_fields:
                response["message"] = f"Could not find {len(missing_fields)} fields in FMP: {missing_fields[:5]}... Consider using web_search for missing data."
            
        return response
    
    async def _fetch_datasets_direct(
        self,
        symbol: str,
        dataset_names: List[str],
        base_params: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Fetch entire datasets (e.g., balance-sheet-statement) without enumerating fields.
        Returns a tuple of (results, missing_requirements).
        """
        async def fetch_dataset(dataset_name: str) -> Dict[str, Any]:
            """Fetch a single dataset and return dict (not tuple) for gather_dict compatibility."""
            dataset = self.ddc_loader.get_dataset(dataset_name)
            if not dataset:
                return {
                    "error": "dataset_not_found",
                    "details": f"{dataset_name} not present in catalog",
                }

            schema = dataset.params_schema or {}
            truly_required = set(dataset.required_params or []) - {"symbol", "apikey"}
            dataset_params = dict(base_params or {})

            # For market-wide endpoints (no identifier_param like screeners),
            # DON'T auto-fill defaults - all params are optional filters
            # Only auto-fill defaults for endpoints that require a symbol
            if dataset.identifier_param:
                for key, requirement in schema.items():
                    if key in ("symbol", "apikey"):
                        continue
                    if key not in dataset_params:
                        if isinstance(requirement, str) and "|" in requirement:
                            dataset_params[key] = requirement.split("|")[0]
                        elif isinstance(requirement, str) and requirement.lower() in {"number", "integer"}:
                            # For 'page', default to 0 (first page)
                            if key == "page":
                                dataset_params[key] = 0
                            # For 'limit', default to 10 (reasonable for financial data)
                            elif key == "limit":
                                dataset_params[key] = 10
                            else:
                                dataset_params[key] = 1

            # Check for missing required params only for symbol-based endpoints
                missing_keys = [
                    key for key in schema.keys()
                    if key not in ("symbol", "apikey") and key not in dataset_params
                ]

                if missing_keys:
                    return {
                        "error": "missing_required_params",
                        "required_params": missing_keys,
                        "notes": dataset.notes,
                    }

            try:
                data = await self.data_fetcher.fetch_dataset(
                    symbol,
                    dataset,
                    historical_params=dataset_params,
                )
            except Exception as exc:  # noqa: BLE001
                return {
                    "error": "fetch_failed",
                    "details": str(exc),
                }

            return {
                "data": data,
                "params_used": dataset_params,
                "endpoint": dataset.url,
            }

        factories = {
            name: (lambda dataset_name=name: fetch_dataset(dataset_name))
            for name in dataset_names
        }
        raw_results = await gather_dict(factories, concurrency_limit=4)

        results: Dict[str, Any] = {}
        missing: Dict[str, Any] = {}
        for name, payload in raw_results.items():
            # payload can be a list (raw data) or dict (with error or wrapped data)
            if isinstance(payload, dict) and payload.get("error") in {"dataset_not_found", "missing_required_params", "fetch_failed"}:
                missing[name] = payload
            elif isinstance(payload, list):
                # Raw list data - wrap it for consistency
                results[name] = {"data": payload}
            else:
                results[name] = payload

        return results, missing

    async def _get_current_fields(self, symbol: str, fields: List[str], params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get current values for specific fields using targeted extraction.
        This is the core optimization - only fetch from needed endpoints.

        Implements intelligent fallback: if some fields are cached but others aren't,
        it will discover the missing fields without re-probing known ones.
        """
        if params is None:
            params = {}

        # Map fields to endpoints
        endpoints = self.field_manager.get_endpoints_for_fields(fields)

        # Track which fields are found in cache vs missing
        found_fields = set()
        if endpoints:
            for endpoint_fields in endpoints.values():
                found_fields.update(endpoint_fields)

        missing_fields = [f for f in fields if f not in found_fields]

        # Intelligent fallback: discover only missing fields
        if missing_fields:
            if found_fields:
                # Partial cache hit - some fields found, some missing
                logger.info(f"Partial cache hit: {len(found_fields)} fields cached, {len(missing_fields)} missing. Running discovery for: {missing_fields[:5]}...")
            else:
                # Complete cache miss - no fields found
                logger.info(f"Cache miss: No mappings found for {fields[:5]}..., running discovery...")

            # Run discovery to find missing fields (probes up to 80 endpoints)
            await self.field_discovery.discover_fields(symbol, max_datasets=80, discovery_params=params)

            # Re-map all fields after discovery
            endpoints = self.field_manager.get_endpoints_for_fields(fields)

            # Check what we found after discovery
            found_fields = set()
            if endpoints:
                for endpoint_fields in endpoints.values():
                    found_fields.update(endpoint_fields)

            still_missing = [f for f in fields if f not in found_fields]

            if still_missing:
                logger.warning(f"Fields not found after discovery: {still_missing}")

            if not endpoints:
                logger.warning(f"No endpoints mapped after discovery for: {fields}")
                return {}
        
        # Ensure required parameters are present before fetching
        missing_requirements: Dict[str, Dict[str, Any]] = {}
        for endpoint_name, endpoint_fields in endpoints.items():
            dataset = self.ddc_loader.get_dataset(endpoint_name)
            if not dataset or not dataset.params_schema:
                continue

            truly_required = set(dataset.required_params or []) - {"symbol", "apikey"}
            missing = [key for key in truly_required if key not in params]
            if missing:
                missing_requirements[endpoint_name] = {
                    "fields": endpoint_fields,
                    "required_params": missing,
                    "notes": dataset.notes,
                }

        if missing_requirements:
            raise MissingRequiredParamsError(missing_requirements)

        # Fetch from each endpoint
        result = {}
        for endpoint_name, endpoint_fields in endpoints.items():
            dataset = self.ddc_loader.get_dataset(endpoint_name)
            if not dataset:
                logger.warning(f"Dataset {endpoint_name} not found in DDC")
                continue
            
            try:
                # Fetch data from this endpoint
                # Pass params through - data_fetcher will filter based on dataset's params_schema
                # DO NOT HARDCODE - only params matching schema will be used
                data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=params)

                if data:
                    # Extract requested fields
                    for field in endpoint_fields:
                        value = self._extract_field_value(data, field)
                        if value is not None:
                            result[field] = value

            except Exception as e:
                logger.error(f"Error fetching from {endpoint_name}: {e}")
                continue
        
        return result
    
    def _extract_field_value(self, data: Any, field_path: str) -> Any:
        """
        Extract field value from nested data structure.
        Handles dot notation for nested fields.
        """
        if not data:
            return None
        
        # Handle array responses
        if isinstance(data, list) and data:
            data = data[0]
        
        # Navigate nested path
        parts = field_path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current

    async def _handle_run_stock_screener(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle run_stock_screener tool call using FMP company screener."""
        # Ensure the data fetcher is connected before making HTTP calls
        if not self.data_fetcher or not getattr(self.data_fetcher, "session", None):
            await self.connect()

        dataset = self.ddc_loader.get_dataset("stock-screener")
        if not dataset:
            return {"error": "stock-screener dataset not found in catalog"}

        include_raw = args.get("include_raw", True)
        params: Dict[str, Any] = {}
        reserved_keys = {"apikey"}
        if dataset.identifier_param:
            reserved_keys.add(dataset.identifier_param)

        def _write_param(key: str, value: Any):
            if key in reserved_keys:
                return
            if value is None:
                return
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    combined = f"{key}{nested_key[0].upper()}{nested_key[1:]}"
                    _write_param(combined, nested_value)
                return
            if isinstance(value, list):
                params[key] = ",".join(str(item) for item in value if item is not None)
                return
            if isinstance(value, bool):
                params[key] = str(value).lower()
            else:
                params[key] = value

        _write_param("limit", args.get("limit"))
        _write_param("order", args.get("order"))
        if args.get("sort_by"):
            _write_param("sort", args["sort_by"])

        # Handle filters - both nested under "filters" key AND top-level args
        # This supports both: {"filters": {"sector": "Tech"}} and {"sector": "Tech"}
        filters = args.get("filters") or {}
        if isinstance(filters, dict):
            for key, value in filters.items():
                _write_param(key, value)
        
        # Also process top-level filter args (agent often passes them directly)
        known_filters = {
            "sector", "industry", "exchange", "country",
            "marketCapMoreThan", "marketCapLowerThan",
            "priceMoreThan", "priceLowerThan",
            "betaMoreThan", "betaLowerThan",
            "volumeMoreThan", "volumeLowerThan",
            "dividendMoreThan", "dividendLowerThan",
            "peMoreThan", "peLowerThan",
            "isEtf", "isFund", "isActivelyTrading"
        }
        for key in known_filters:
            if key in args and args[key] is not None:
                _write_param(key, args[key])

        try:
            data = await self.data_fetcher.fetch_dataset("", dataset, historical_params=params)
        except MissingRequiredParamsError as exc:
            return {"error": "missing_required_params", "details": exc.details}

        rows: Any = data
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                rows = data["data"]

        if isinstance(rows, list) and args.get("limit"):
            try:
                limit_int = int(args["limit"])
                rows = rows[:limit_int]
            except Exception:  # noqa: BLE001
                pass

        result: Dict[str, Any] = {
            "result_count": len(rows) if isinstance(rows, list) else 0,
            "filters_applied": list(params.keys()),
            "results": rows,
        }
        if include_raw:
            result["raw"] = data
        
        return result

    async def _handle_list_datasets(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle list_datasets tool call"""
        include_details = args.get("include_details", False)
        return self.field_discovery.list_datasets(include_details)
    
    async def fetch_historical_data(
        self, symbol: str, period: str = None, start: str = None, end: str = None
    ) -> Optional[Dict[str, Any]]:
        """Programmatic API for historical data — returns parsed dict.

        Use this from tool code instead of ``call_tool("get_historical_data")``.
        ``call_tool`` runs results through ``bh_ingest`` (for LLM context
        compaction), which converts the JSON into a BH summary string that
        ``safe_parse_json`` cannot parse back.
        """
        raw = await self.historical_data.get_historical_data(symbol, period, start, end)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    async def _handle_get_historical_data(self, args: Dict[str, Any]) -> Optional[str]:
        """Handle get_historical_data tool call (MCP path — bh_ingest applied by call_tool)"""
        symbol = args["symbol"]
        period = args.get("period")
        start = args.get("start")
        end = args.get("end")

        return await self.historical_data.get_historical_data(
            symbol, period, start, end
        )
    
    async def _handle_list_cached_fields(self, args: Dict[str, Any]) -> List[Dict[str, str]]:
        """Compact field listing with search"""
        query = args.get("query", "").lower()
        limit = min(args.get("limit", 50), 100)  # Cap at 100
        
        cursor = self.field_manager.conn.cursor()
        
        if query:
            # Simple LIKE filter
            cursor.execute("""
                SELECT field_name, endpoint_name, field_type 
                FROM field_mappings 
                WHERE LOWER(field_name) LIKE LOWER(?)
                ORDER BY hit_count DESC 
                LIMIT ?
            """, (f"%{query}%", limit))
        else:
            cursor.execute("""
                SELECT field_name, endpoint_name, field_type 
                FROM field_mappings 
                ORDER BY hit_count DESC 
                LIMIT ?
            """, (limit,))
        
        # Compact format
        return [
            {"field": row[0], "endpoint": row[1], "type": row[2]}
            for row in cursor.fetchall()
        ]

    async def _handle_discover_market_wide_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Discover sector/industry snapshot fields by date (market_wide datasets).

        Uses the existing data fetcher and extractor to probe market_wide endpoints with a provided date.
        Keeps symbol-centric discovery unchanged.
        """
        symbol = args.get("symbol", "AAPL")  # not used by endpoints; kept for UX consistency
        date_str = args.get("date")
        include = set(args.get("include", ["sector", "industry"]))
        max_datasets = int(args.get("max_datasets", 10))

        # Validate/normalize date
        try:
            if not date_str:
                date_str = datetime.utcnow().date().isoformat()
            else:
                # Ensure ISO format; will raise on bad input
                datetime.fromisoformat(date_str)
        except Exception:
            date_str = datetime.utcnow().date().isoformat()

        logger.info(f"Starting market_wide discovery (date: {date_str}, include: {sorted(list(include))})")

        # Select discoverable market_wide datasets
        datasets = self.ddc_loader.filter_by_class("market_wide")
        discoverable = [d for d in datasets if d.discoverable]

        # Filter by include groups
        filtered: List[Any] = []
        for d in discoverable:
            name = d.dataset.lower()
            if ("sector" in name and "sector" in include) or ("industry" in name and "industry" in include):
                filtered.append(d)

        if max_datasets:
            filtered = filtered[:max_datasets]

        discovered: Dict[str, Any] = {}
        endpoint_urls: Dict[str, str] = {}
        by_endpoint: Dict[str, Any] = {}

        discovery_params = {"date": date_str}

        for dataset in filtered:
            try:
                data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=discovery_params)
                if data:
                    endpoint_urls[dataset.dataset] = dataset.url
                    fields = self.field_discovery._extract_fields(data, dataset.dataset)
                    discovered.update(fields)
                    by_endpoint[dataset.dataset] = {
                        "url": dataset.url,
                        "count": len(fields)
                    }
            except Exception as e:
                logger.warning(f"Failed to probe {dataset.dataset}: {e}")
                continue

        if discovered:
            self.field_manager.save_discovered_fields(discovered, endpoint_urls)

        result = {
            "symbol": symbol,
            "date": date_str,
            "fields": discovered,
            "field_count": len(discovered),
            "by_endpoint": by_endpoint,
            "discovered_endpoints": list(by_endpoint.keys()),
            "info": f"Discovered market_wide snapshot fields for {date_str}"
        }

        return result

    async def _handle_get_latest_news(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_latest_news tool call - fetch latest news across all stocks with auto-pagination"""
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
            "general": "general-news-latest",
            "press-releases": "press-releases-latest",
            "stock": "stock-news-latest"
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

        except MissingRequiredParamsError as exc:
            return {"error": "missing_required_params", "details": exc.details}

        return {
            "news_type": news_type,
            "start_page": start_page,
            "pages_fetched": pages_fetched,
            "limit_per_page": limit,
            "max_results": max_results,
            "count": len(news_items[:max_results]),
            "data": news_items[:max_results]
        }

    async def _handle_get_news_by_symbol(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_news_by_symbol tool call - fetch news for specific ticker(s) with auto-pagination"""
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
            "news": "stock-news",
            "press-releases": "press-releases"
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

        except MissingRequiredParamsError as exc:
            return {"error": "missing_required_params", "details": exc.details}

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
