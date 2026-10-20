"""
FMP TradeFlow Server - Specialized MCP server for institutional activity data
Institutional ownership (13F), insider trading, congressional trades, ETF flows, and ESG ratings
EXACT COPY of FMPAdvancedValuationServer pattern with tradeflow catalog
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import MCP base class from agents SDK
from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult

# Import helper modules
from .ddc_loader import DDCLoader
from .data_fetcher import FMPDataFetcher
from .field_discovery import FMPFieldDiscovery, DEFAULT_PAGE_SIZE
from .historical_data import FMPHistoricalData
from core.utils import gather_dict
from .field_map_manager import FieldMapManager
from .rate_limiter import DatasetRateLimiter

logger = logging.getLogger(__name__)


class FMPTradeFlowServer(MCPServer):
    """
    MCP Server for FMP institutional activity data: 13F, insider trading, congressional trades, ETF, ESG.
    EXACT copy of FMPAdvancedValuationServer architecture.
    """

    def __init__(self, api_key: str = None):
        """Initialize FMP TradeFlow Server with helper modules"""
        super().__init__()
        self._name = "FMPTradeFlowServer"
        self.use_structured_content = False  # Required by openai-agents SDK 0.2.0+

        # Load API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("FMP_API_KEY")

        if not api_key:
            raise ValueError("FMP_API_KEY not provided")

        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com"

        # Initialize helper modules - exactly like valuation server but with tradeflow catalog
        tradeflow_catalog_path = os.path.join(os.path.dirname(__file__), "tradeflow_catalog.json")
        self.ddc_loader = DDCLoader(tradeflow_catalog_path)
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

        logger.info("FMPTradeFlowServer initialized")

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
                name="discover_institutional_fields",
                description="Probes institutional endpoints to discover available fields: 13F filings (institutional ownership), Form 4 (insider trades), STOCK Act (congressional trades), ETF holdings, ESG ratings. Returns field catalog from tradeflow endpoints. Default probes 30 datasets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol to discover institutional fields for"
                        },
                        "max_datasets": {
                            "type": "integer",
                            "description": "Maximum datasets to probe",
                            "default": 30
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_tradeflow_dataset",
                description="Fetches specific tradeflow dataset by catalog name. Provide dataset identifier with optional symbol and params. Returns data with missing_params notice if parameters incomplete. Use for direct dataset access when name is known.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Symbol when required by dataset (optional)"},
                        "dataset": {"type": "string", "description": "Dataset name from the tradeflow catalog"},
                        "params": {"type": "object", "description": "Dataset-specific params", "additionalProperties": True},
                        "datasets": {"type": "array", "items": {"type": "string"}, "description": "Multiple dataset names to fetch"}
                    },
                    "required": ["dataset"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_13f_holdings",
                description="Fetches 13F institutional ownership. data_types: latest (all recent filings), extract (CIK historical by quarter), analytics (who holds this symbol), performance (CIK performance metrics). Symbol required for analytics, CIK for extract/performance. Year/quarter default to the most recent completed quarter if omitted.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol for 13F holdings"
                        },
                        "cik": {
                            "type": "string",
                            "description": "Optional CIK number for specific institutional holder"
                        },
                        "data_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["latest", "extract", "analytics", "performance"]},
                            "description": "Select one or more 13F views",
                            "default": ["latest", "analytics"]
                        },
                        "year": {
                            "type": "integer",
                            "description": "Filing year (defaults to most recent completed quarter's year)"
                        },
                        "quarter": {
                            "type": "integer",
                            "description": "Filing quarter 1-4 (defaults to most recent completed quarter)",
                            "enum": [1, 2, 3, 4]
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number for pagination",
                            "default": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Results per page",
                            "default": DEFAULT_PAGE_SIZE
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_insider_trading",
                description="Fetches insider trading (Form 4 filings). data_types: transactions (buys/sells), statistics (aggregated activity), beneficial (ownership changes). Filter by symbol or insider name. Supports pagination.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol for insider trading data"
                        },
                        "name": {
                            "type": "string",
                            "description": "Optional insider name for specific person search"
                        },
                        "data_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["transactions", "statistics", "beneficial"]},
                            "description": "Select insider data views",
                            "default": ["transactions", "statistics"]
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number for pagination",
                            "default": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Results per page",
                            "default": DEFAULT_PAGE_SIZE
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_congressional_trades",
                description="Fetches congressional trading (STOCK Act disclosures). Filter by chambers=['senate', 'house'], optional symbol or legislator name. Returns reported stock transactions from Congress members.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Optional stock symbol filter"},
                        "name": {"type": "string", "description": "Optional legislator name"},
                        "chambers": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["senate", "house"]},
                            "description": "Chambers to query",
                            "default": ["senate", "house"]
                        },
                        "page": {"type": "integer", "description": "Page number", "default": 0},
                        "limit": {"type": "integer", "description": "Results per page", "default": DEFAULT_PAGE_SIZE}
                    },
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_etf_holdings",
                description="Fetches ETF data. data_types: holdings (constituent stocks with weights), info (expense ratio, AUM), sector (sector allocation %), country (geographic exposure %), asset (stocks/bonds/cash breakdown). Auto-aggregates holdings across pages up to max_results.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "ETF symbol"},
                        "data_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["holdings", "info", "sector", "country", "asset"]},
                            "description": "Select ETF views",
                            "default": ["holdings", "info"]
                        },
                        "page": {"type": "integer", "description": "Page number", "default": 0},
                        "limit": {"type": "integer", "description": "Results per page", "default": DEFAULT_PAGE_SIZE},
                        "max_results": {
                            "type": "integer",
                            "description": "Cap on total holdings to auto-aggregate across pages (default 500)"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_esg_ratings",
                description="Fetches ESG (Environmental, Social, Governance) data. data_types: ratings (ESG scores), disclosures (sustainability reports), benchmark (industry averages, no symbol needed). Returns ESG metrics for company analysis.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock symbol (optional for benchmark)"},
                        "data_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["ratings", "disclosures", "benchmark"]},
                            "description": "Select ESG views",
                            "default": ["ratings", "disclosures"]
                        }
                    },
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="list_tradeflow_datasets",
                description="Lists all institutional activity datasets in catalog (13F, insider, congressional, ETF, ESG). Use include_details=true for full endpoint specifications. Returns dataset names for use with get_tradeflow_dataset. Helpful for browsing tradeflow data sources.",
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
                name="get_ma_activity",
                description="Fetches M&A (mergers & acquisitions) activity data. data_types: search (find deals by company name), latest (recent M&A transactions). Returns corporate M&A deals, valuations, and transaction details. Useful for tracking acquisition activity and market consolidation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Company name to search for M&A deals (required for search type)"
                        },
                        "data_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["search", "latest"]},
                            "description": "Select M&A data views",
                            "default": ["latest"]
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number for pagination (latest only)",
                            "default": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Results per page (latest only)",
                            "default": DEFAULT_PAGE_SIZE
                        }
                    },
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_ipo_data",
                description="Fetches IPO (initial public offering) data. data_types: disclosure (IPO filings and prospectus summaries), prospectus (detailed IPO documents). Returns companies in IPO pipeline, offering details, and pre-public company information. Essential for private markets research.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["disclosure", "prospectus"]},
                            "description": "Select IPO data views",
                            "default": ["disclosure", "prospectus"]
                        }
                    },
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_institutional_activity",
                description="Unified access to institutional activity data. Combines 13F holdings, insider trading, congressional trades, and company leadership. activity_types: holdings (13F filings), insider (Form 4 trades), congressional (Senate/House trades), executives (key management). Returns comprehensive institutional positioning and insider behavior. Year/quarter default to the most recent completed quarter if omitted.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol for institutional activity"
                        },
                        "activity_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["holdings", "insider", "congressional", "executives"]},
                            "description": "Types of institutional activity to retrieve",
                            "default": ["holdings", "insider"]
                        },
                        "cik": {
                            "type": "string",
                            "description": "Optional CIK number for specific institutional holder (holdings only)"
                        },
                        "year": {
                            "type": "integer",
                            "description": "Filing year for 13F holdings (defaults to most recent completed quarter's year)"
                        },
                        "quarter": {
                            "type": "integer",
                            "description": "Filing quarter 1-4 for 13F holdings (defaults to most recent completed quarter)",
                            "enum": [1, 2, 3, 4]
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number for pagination",
                            "default": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Results per page",
                            "default": DEFAULT_PAGE_SIZE
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
            if name == "discover_institutional_fields":
                result = await self._handle_discover_institutional_fields(arguments)
            elif name == "get_tradeflow_dataset":
                result = await self._handle_get_dataset(arguments)
            elif name == "get_13f_holdings":
                result = await self._handle_get_13f_holdings(arguments)
            elif name == "get_insider_trading":
                result = await self._handle_get_insider_trading(arguments)
            elif name == "get_congressional_trades":
                result = await self._handle_get_congressional_trades(arguments)
            elif name == "get_etf_holdings":
                result = await self._handle_get_etf_holdings(arguments)
            elif name == "get_esg_ratings":
                result = await self._handle_get_esg_ratings(arguments)
            elif name == "list_tradeflow_datasets":
                result = await self._handle_list_tradeflow_datasets(arguments)
            elif name == "get_ma_activity":
                result = await self._handle_get_ma_activity(arguments)
            elif name == "get_ipo_data":
                result = await self._handle_get_ipo_data(arguments)
            elif name == "get_institutional_activity":
                result = await self._handle_get_institutional_activity(arguments)
            elif name == "get_fields":
                result = await self._handle_get_fields(arguments)
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

    async def _handle_discover_institutional_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle discover_institutional_fields tool call"""
        symbol = args.get("symbol")
        max_datasets = args.get("max_datasets", 30)

        if not self.field_discovery:
            return {"error": "Field discovery not initialized"}

        try:
            # Use real catalog endpoint names
            institutional_datasets = [
                "esg-disclosures", "esg-ratings", "esg-benchmark",
                "etf-holdings", "etf-info", "etf-country-weightings", "etf-asset-exposure", "etf-sector-weightings",
                "funds-disclosure-holders-latest", "funds-disclosure", "funds-disclosure-holders-search", "funds-disclosure-dates",
                "institutional-ownership-latest", "institutional-ownership-extract", "institutional-ownership-dates",
                "insider-trading-latest", "insider-trading-search", "insider-trading-statistics",
                "senate-latest", "house-latest", "senate-trading", "house-trades"
            ]

            # Pass period param for discovery to work with all endpoints
            discovery_params = {"period": "annual"}
            discovered = await self.field_discovery.discover_fields(symbol, max_datasets, discovery_params=discovery_params)

            # Filter to institutional-relevant fields
            institutional_fields = {}
            for field_name, field_info in discovered.items():
                if any(dataset in field_info.get("source", "") for dataset in institutional_datasets):
                    institutional_fields[field_name] = field_info

            return {
                "discovered_fields": len(institutional_fields),
                "total_datasets": len(set(info["source"] for info in institutional_fields.values())),
                "fields": institutional_fields
            }

        except Exception as e:
            logger.error(f"Error discovering institutional fields: {e}")
            return {"error": str(e)}

    @staticmethod
    def _default_13f_quarter() -> tuple[int, int]:
        """Return (year, quarter) for the most recent completed quarter.

        13F filings are due ~45 days after quarter end, so we step back one
        full quarter from the current date to target the period most likely
        to have complete data.
        """
        now = datetime.now()
        current_q = ((now.month - 1) // 3) + 1
        if current_q == 1:
            return now.year - 1, 4
        return now.year, current_q - 1

    async def _handle_get_13f_holdings(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_13f_holdings tool call with multiple data_types support"""
        symbol = args.get("symbol")
        cik = args.get("cik")
        data_types = args.get("data_types", ["latest", "analytics"])
        page = args.get("page", 0)
        limit = args.get("limit", DEFAULT_PAGE_SIZE)

        default_year, default_quarter = self._default_13f_quarter()
        year = args.get("year", default_year)
        quarter = args.get("quarter", default_quarter)

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        results = {}
        base_params = {"page": page, "limit": limit}
        quarterly_params = {**base_params, "year": str(year), "quarter": str(quarter)}

        try:
            for dtype in data_types:
                if dtype == "latest":
                    dataset = self.ddc_loader.get_dataset("institutional-ownership-latest")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset("", dataset, historical_params=base_params)
                        results["latest"] = data

                elif dtype == "extract":
                    if not cik:
                        results["extract"] = {"error": "CIK required for extract data_type"}
                        continue
                    dataset = self.ddc_loader.get_dataset("institutional-ownership-extract")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(cik, dataset, historical_params=quarterly_params)
                        results["extract"] = data

                elif dtype == "analytics":
                    if not symbol:
                        results["analytics"] = {"error": "Symbol required for analytics data_type"}
                        continue
                    dataset = self.ddc_loader.get_dataset("institutional-ownership-extract-analytics-holder")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=quarterly_params)
                        results["analytics"] = data

                elif dtype == "performance":
                    if not cik:
                        results["performance"] = {"error": "CIK required for performance data_type"}
                        continue
                    dataset = self.ddc_loader.get_dataset("institutional-ownership-holder-performance-summary")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(cik, dataset, historical_params=base_params)
                        results["performance"] = data

            return {
                "symbol": symbol,
                "cik": cik,
                "year": year,
                "quarter": quarter,
                "data": results,
                "data_types_requested": data_types,
                "data_types_fulfilled": [k for k, v in results.items() if not isinstance(v, dict) or "error" not in v]
            }

        except Exception as e:
            logger.error(f"Error fetching 13F holdings: {e}")
            return {"error": str(e)}

    async def _handle_get_insider_trading(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_insider_trading tool call"""
        symbol = args.get("symbol")
        transaction_type = args.get("transaction_type")
        page = args.get("page", 0)
        limit = args.get("limit", DEFAULT_PAGE_SIZE)

        if not symbol:
            return {"error": "Symbol is required"}

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        try:
            # Get insider trading dataset
            dataset = self.ddc_loader.get_dataset("insider-trading-latest")
            if not dataset:
                return {"error": "Insider trading dataset not found"}

            # Build params with pagination
            params = {"page": page, "limit": limit}

            data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=params)

            # Filter by symbol (API returns all symbols, we filter client-side)
            if symbol and isinstance(data, list):
                data = [t for t in data if t.get("symbol", "").upper() == symbol.upper()]

            # Filter by transaction type if specified
            if transaction_type and isinstance(data, list):
                data = [t for t in data if t.get("transactionType") == transaction_type]

            return {
                "symbol": symbol,
                "transaction_type": transaction_type,
                "insider_trades": data
            }

        except Exception as e:
            logger.error(f"Error fetching insider trading: {e}")
            return {"error": str(e)}

    async def _handle_get_congressional_trades(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_congressional_trades tool call"""
        symbol = args.get("symbol")
        chamber = args.get("chamber")  # "senate" or "house"
        page = args.get("page", 0)
        limit = args.get("limit", DEFAULT_PAGE_SIZE)

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        try:
            # Get congressional trading dataset
            if chamber == "senate":
                dataset = self.ddc_loader.get_dataset("senate-latest")
            elif chamber == "house":
                dataset = self.ddc_loader.get_dataset("house-latest")
            else:
                dataset = self.ddc_loader.get_dataset("senate-latest")

            if not dataset:
                return {"error": f"Congressional trading dataset not found for {chamber or 'all chambers'}"}

            # Build params with pagination
            params = {"page": page, "limit": limit}

            # Fetch data
            if symbol:
                data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=params)
            else:
                # Fetch all congressional trades
                url = dataset.url
                data = await self._fetch_from_fmp(url, params=params)

            return {
                "symbol": symbol,
                "chamber": chamber,
                "congressional_trades": data
            }

        except Exception as e:
            logger.error(f"Error fetching congressional trades: {e}")
            return {"error": str(e)}

    async def _handle_get_etf_holdings(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_etf_holdings tool call with multiple data_types support"""
        symbol = args.get("symbol")
        data_types = args.get("data_types", ["holdings", "info"])
        start_page = args.get("page", 0)
        limit = args.get("limit", DEFAULT_PAGE_SIZE)
        max_results = args.get("max_results") or 500

        try:
            start_page = max(0, int(start_page))
        except (TypeError, ValueError):
            start_page = 0

        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = DEFAULT_PAGE_SIZE

        try:
            max_results = max(1, min(int(max_results), 5000))
        except (TypeError, ValueError):
            max_results = 500

        if not symbol:
            return {"error": "ETF symbol is required"}

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        results = {}

        try:
            for dtype in data_types:
                if dtype == "holdings":
                    # Fetch holdings with auto-pagination
                    dataset = self.ddc_loader.get_dataset("etf-holdings")
                    if not dataset:
                        results["holdings"] = {"error": "etf-holdings dataset not found"}
                        continue

                    holdings: List[Any] = []
                    current_page = start_page
                    pages_fetched = 0

                    while len(holdings) < max_results:
                        params = {"page": current_page, "limit": limit, "size": limit}
                        data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=params)

                        chunk: List[Any]
                        if isinstance(data, dict) and "holdings" in data:
                            chunk = data.get("holdings") or []
                        elif isinstance(data, list):
                            chunk = data
                        else:
                            chunk = [data] if data else []

                        if not chunk:
                            break

                        holdings.extend(chunk)
                        pages_fetched += 1

                        if len(chunk) < limit:
                            break

                        current_page += 1

                    results["holdings"] = holdings[:max_results]

                elif dtype == "info":
                    dataset = self.ddc_loader.get_dataset("etf-info")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(symbol, dataset)
                        results["info"] = data

                elif dtype == "sector":
                    dataset = self.ddc_loader.get_dataset("etf-sector-weightings")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(symbol, dataset)
                        results["sector"] = data

                elif dtype == "country":
                    dataset = self.ddc_loader.get_dataset("etf-country-weightings")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(symbol, dataset)
                        results["country"] = data

                elif dtype == "asset":
                    dataset = self.ddc_loader.get_dataset("etf-asset-exposure")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(symbol, dataset)
                        results["asset"] = data

            return {
                "etf_symbol": symbol,
                "data": results,
                "data_types_requested": data_types,
                "data_types_fulfilled": list(results.keys())
            }

        except Exception as e:
            logger.error(f"Error fetching ETF holdings: {e}")
            return {"error": str(e)}

    async def _handle_get_esg_ratings(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_esg_ratings tool call"""
        symbol = args.get("symbol")

        if not symbol:
            return {"error": "Symbol is required"}

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        try:
            # Get ESG rating dataset
            dataset = self.ddc_loader.get_dataset("esg-ratings")
            if not dataset:
                return {"error": "ESG rating dataset not found"}

            data = await self.data_fetcher.fetch_dataset(symbol, dataset)

            return {
                "symbol": symbol,
                "esg_data": data
            }

        except Exception as e:
            logger.error(f"Error fetching ESG ratings: {e}")
            return {"error": str(e)}

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
            dataset = self.ddc_loader.get_dataset(name)
            if not dataset:
                return {"error": "dataset_not_found"}

            required = []
            if dataset.params_schema:
                # Build skip keys - include identifier_param since data_fetcher handles it
                skip_keys = {"symbol", "apikey"}
                if dataset.identifier_param:
                    skip_keys.add(dataset.identifier_param)
                for key in dataset.params_schema.keys():
                    if key not in skip_keys and key not in params:
                        required.append(key)
            if required:
                return {
                    "error": "missing_required_params",
                    "required_params": required,
                    "notes": dataset.notes
                }
            try:
                return await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=params)
            except Exception as exc:
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

    async def _handle_get_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic dataset fetch for data workspace compatibility.
        Mirrors the pattern from UW servers and FMPMarketDataServer.
        """
        
        datasets = args.get("datasets") or []
        if args.get("dataset"):
            datasets.append(args["dataset"])
        
        symbol = args.get("symbol") or args.get("ticker") or ""
        extra_params = args.get("params", {})
        
        
        if not datasets:
            return {"error": "No datasets specified", "data": {}}
        
        async def fetch_one(dataset_name: str) -> Dict[str, Any]:
            dataset = self.ddc_loader.get_dataset(dataset_name)
            if not dataset:
                return {"error": f"Dataset '{dataset_name}' not found in tradeflow catalog"}
            
            try:
                # Merge extra params
                fetch_params = dict(extra_params)
                data = await self.data_fetcher.fetch_dataset(symbol, dataset, historical_params=fetch_params)
                return data
            except Exception as e:
                logger.error(f"Error fetching {dataset_name}: {e}")
                return {"error": str(e)}
        
        # Fetch all datasets concurrently
        factories = {name: (lambda n=name: fetch_one(n)) for name in datasets}
        raw_results = await gather_dict(factories, concurrency_limit=4)
        
        # Build response
        all_data = {}
        errors = {}
        for name, result in raw_results.items():
            if isinstance(result, dict) and result.get("error"):
                errors[name] = result["error"]
            else:
                all_data[name] = result
        
        response = {"data": all_data}
        if errors:
            response["errors"] = errors
        return response

    async def _handle_list_tradeflow_datasets(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_tradeflow_datasets tool call"""
        include_details = args.get("include_details", False)

        if not self.field_discovery:
            return {"error": "Field discovery not initialized"}

        try:
            datasets = self.field_discovery.list_datasets(include_details)

            # Filter to institutional datasets (ESG, ETF, insider, congressional)
            tradeflow_datasets = [
                ds for ds in datasets
                if ds.get("class") in ["esg", "etf", "institutional", "insider", "congressional"]
            ]

            return {
                "total_datasets": len(tradeflow_datasets),
                "esg_datasets": len([ds for ds in tradeflow_datasets if ds.get("class") == "esg"]),
                "etf_datasets": len([ds for ds in tradeflow_datasets if ds.get("class") == "etf"]),
                "insider_datasets": len([ds for ds in tradeflow_datasets if ds.get("class") == "insider"]),
                "congressional_datasets": len([ds for ds in tradeflow_datasets if ds.get("class") == "congressional"]),
                "institutional_datasets": len([ds for ds in tradeflow_datasets if ds.get("class") == "institutional"]),
                "datasets": tradeflow_datasets
            }

        except Exception as e:
            logger.error(f"Error listing institutional/tradeflow datasets: {e}")
            return {"error": str(e)}

    async def _fetch_from_fmp(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make direct HTTP request to FMP API.

        Args:
            url: Endpoint URL (without base URL)
            params: Query parameters (apikey added automatically)

        Returns:
            JSON response from FMP API
        """
        # Ensure data fetcher session is initialized
        if not self.data_fetcher.session:
            await self.data_fetcher.connect()

        # Build full URL
        full_url = f"{self.base_url}{url}"

        # Add API key to params
        query_params = {"apikey": self.api_key}
        if params:
            query_params.update(params)

        # Make HTTP request
        async with self.data_fetcher.session.get(full_url, params=query_params) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                error_text = await response.text()
                logger.error(f"FMP API error: {response.status} - {error_text}")
                return {"error": f"API returned {response.status}: {error_text}"}

    async def _handle_get_ma_activity(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_ma_activity tool call"""
        name = args.get("name")
        data_types = args.get("data_types", ["latest"])
        page = args.get("page", 0)
        limit = args.get("limit", DEFAULT_PAGE_SIZE)

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        results = {}
        params = {"page": page, "limit": limit}

        try:
            for dtype in data_types:
                if dtype == "search":
                    # Search M&A deals by company name
                    if not name:
                        results["search"] = {"error": "Company name required for search data_type"}
                        continue

                    dataset = self.ddc_loader.get_dataset("mergers-acquisitions-search")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(name, dataset, historical_params={})
                        results["search"] = data

                elif dtype == "latest":
                    # Latest M&A deals
                    dataset = self.ddc_loader.get_dataset("mergers-acquisitions-latest")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset("", dataset, historical_params=params)
                        results["latest"] = data

            return {
                "name": name,
                "data": results,
                "data_types_requested": data_types,
                "data_types_fulfilled": [k for k, v in results.items() if not isinstance(v, dict) or "error" not in v]
            }

        except Exception as e:
            logger.error(f"Error fetching M&A activity: {e}")
            return {"error": str(e)}

    async def _handle_get_ipo_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_ipo_data tool call"""
        data_types = args.get("data_types", ["disclosure", "prospectus"])

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        results = {}

        try:
            for dtype in data_types:
                if dtype == "disclosure":
                    # IPO disclosure filings
                    dataset = self.ddc_loader.get_dataset("ipos-disclosure")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset("", dataset)
                        results["disclosure"] = data

                elif dtype == "prospectus":
                    # IPO prospectus documents
                    dataset = self.ddc_loader.get_dataset("ipos-prospectus")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset("", dataset)
                        results["prospectus"] = data

            return {
                "data": results,
                "data_types_requested": data_types,
                "data_types_fulfilled": list(results.keys())
            }

        except Exception as e:
            logger.error(f"Error fetching IPO data: {e}")
            return {"error": str(e)}

    async def _handle_get_institutional_activity(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_institutional_activity tool call - unified institutional data access"""
        symbol = args.get("symbol")
        activity_types = args.get("activity_types", ["holdings", "insider"])
        cik = args.get("cik")
        page = args.get("page", 0)
        limit = args.get("limit", DEFAULT_PAGE_SIZE)

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        results = {}
        params = {"page": page, "limit": limit}

        try:
            for activity_type in activity_types:
                if activity_type == "holdings":
                    holdings_args = {
                        "symbol": symbol,
                        "cik": cik,
                        "data_types": ["latest", "analytics"],
                        "page": page,
                        "limit": limit,
                    }
                    if args.get("year"):
                        holdings_args["year"] = args["year"]
                    if args.get("quarter"):
                        holdings_args["quarter"] = args["quarter"]
                    holdings_result = await self._handle_get_13f_holdings(holdings_args)
                    results["holdings"] = holdings_result.get("data", {})

                elif activity_type == "insider":
                    # Delegate to existing insider handler
                    insider_args = {
                        "symbol": symbol,
                        "data_types": ["transactions", "statistics"],
                        "page": page,
                        "limit": limit
                    }
                    insider_result = await self._handle_get_insider_trading(insider_args)
                    results["insider"] = insider_result.get("insider_trades", [])

                elif activity_type == "congressional":
                    # Delegate to existing congressional handler
                    congressional_args = {
                        "symbol": symbol,
                        "chambers": ["senate", "house"],
                        "page": page,
                        "limit": limit
                    }
                    congressional_result = await self._handle_get_congressional_trades(congressional_args)
                    results["congressional"] = congressional_result.get("congressional_trades", [])

                elif activity_type == "executives":
                    # Fetch key executives data
                    if not symbol:
                        results["executives"] = {"error": "Symbol required for executives data"}
                        continue

                    dataset = self.ddc_loader.get_dataset("key-executives")
                    if dataset:
                        data = await self.data_fetcher.fetch_dataset(symbol, dataset)
                        results["executives"] = data

            return {
                "symbol": symbol,
                "data": results,
                "activity_types_requested": activity_types,
                "activity_types_fulfilled": list(results.keys())
            }

        except Exception as e:
            logger.error(f"Error fetching institutional activity: {e}")
            return {"error": str(e)}

    async def connect(self):
        """Initialize connections"""
        await self.data_fetcher.connect()
        logger.info("FMPTradeFlowServer connected")

    async def cleanup(self):
        """Cleanup connections"""
        await self.data_fetcher.cleanup()
        self.field_manager.close()
        logger.info("FMPTradeFlowServer cleaned up")


# Factory function for easy instantiation
def create_fmp_tradeflow_server(api_key: str = None) -> FMPTradeFlowServer:
    """
    Create an FMP Crypto & Forex Server instance.

    Args:
        api_key: FMP API key (if not provided, reads from FMP_API_KEY environment variable)

    Returns:
        Configured FMPTradeFlowServer instance
    """
    if not api_key:
        api_key = os.getenv("FMP_API_KEY")
        if not api_key:
            raise ValueError("FMP_API_KEY environment variable or api_key parameter required")

    return FMPTradeFlowServer(api_key)
