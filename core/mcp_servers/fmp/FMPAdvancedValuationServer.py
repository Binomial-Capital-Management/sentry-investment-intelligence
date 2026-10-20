"""
FMP Advanced Valuation Server - Specialized MCP server for DCF and valuation data
EXACT COPY of FMPMarketDataServer pattern with valuation tools
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
from .ddc_loader import DDCLoader, DatasetClass
from .data_fetcher import FMPDataFetcher
from .field_discovery import FMPFieldDiscovery
from .historical_data import FMPHistoricalData
from core.utils import gather_dict
from .field_map_manager import FieldMapManager
from .rate_limiter import DatasetRateLimiter

logger = logging.getLogger(__name__)


class FMPAdvancedValuationServer(MCPServer):
    """
    MCP Server for FMP valuation data discovery and retrieval.
    EXACT copy of FMPMarketDataServer architecture.
    """

    def __init__(self, api_key: str = None):
        """Initialize FMP Advanced Valuation Server with helper modules"""
        super().__init__()
        self._name = "FMPAdvancedValuationServer"
        self.use_structured_content = False  # Required by openai-agents SDK 0.2.0+

        # Load API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("FMP_API_KEY")

        if not api_key:
            raise ValueError("FMP_API_KEY not provided")

        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com"  # No /api suffix - valuation catalog uses /stable/ endpoints

        # Initialize helper modules - exactly like market server but with valuation catalog
        valuation_catalog_path = os.path.join(os.path.dirname(__file__), "valuation_catalog.json")
        self.ddc_loader = DDCLoader(valuation_catalog_path)
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

        logger.info("FMPAdvancedValuationServer initialized")

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
                name="discover_dcf_fields",
                description="Probes valuation endpoints to discover DCF input fields (FCF, EBITDA, revenue growth, WACC components). Returns cached mappings if recent. Use before fetching DCF data.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol to discover DCF fields for"
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
                name="discover_forecast_fields",
                description="Probes forecast endpoints to discover analyst estimates and growth projections: revenue forecasts, EPS estimates, consensus ratings. Supports annual/quarter periods. Use before DCF modeling to see available forward-looking data.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol to discover forecast fields for"
                        },
                        "period": {
                            "type": "string",
                            "enum": ["annual", "quarter"],
                            "description": "Time period for analyst estimates (annual or quarterly)",
                            "default": "annual"
                        },
                        "year": {
                            "type": "integer",
                            "description": "Specific year for estimates (optional)"
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
                name="get_dcf_data",
                description="Fetches DCF calculation inputs for a symbol. Optionally provide fields array (FCF, EBITDA, revenue, debt, etc.) or get common DCF fields by default. Returns valuation metrics from optimal endpoints.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol"
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of field names to retrieve (defaults to common DCF fields)"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_valuation_dataset",
                description="Fetches specific valuation dataset by catalog name. Provide dataset identifier with required params. Returns data with missing_params notice if parameters incomplete. Use for direct dataset access when name is known.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock symbol (when required by dataset)"},
                        "dataset": {"type": "string", "description": "Dataset name from the valuation catalog"},
                        "params": {"type": "object", "description": "Dataset-specific params", "additionalProperties": True},
                        "datasets": {"type": "array", "items": {"type": "string"}, "description": "Multiple dataset names to fetch"}
                    },
                    "required": ["dataset"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_forecast_data",
                description="Fetches analyst estimates and growth forecasts for DCF forward-looking assumptions. Provide forecast_types: revenue, earnings, growth. Returns consensus estimates, analyst targets, and growth projections for future periods.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol"
                        },
                        "forecast_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types of forecasts to retrieve",
                            "default": ["revenue", "earnings", "growth"]
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="calculate_wacc_inputs",
                description="Fetches all WACC (Weighted Average Cost of Capital) calculation inputs: cost of equity, cost of debt, market cap, debt values, tax rate, beta. Returns components needed for discount rate calculation in DCF models.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="get_growth_estimates",
                description="Fetches comprehensive growth rate estimates for DCF: revenue growth, earnings growth, terminal growth rate, consensus estimates. Returns historical growth trends and forward projections for terminal value calculations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol"
                        }
                    },
                    "required": ["symbol"],
                    "additionalProperties": False
                }
            ),
            MCPTool(
                name="list_valuation_datasets",
                description="Lists all valuation datasets in catalog (DCF, multiples, forecasts). Use include_details=true for full endpoint specifications. Returns dataset names for use with get_valuation_dataset. Helpful for browsing valuation data sources.",
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
            if name == "discover_dcf_fields":
                result = await self._handle_discover_dcf_fields(arguments)
            elif name == "discover_forecast_fields":
                result = await self._handle_discover_forecast_fields(arguments)
            elif name == "get_valuation_dataset":
                result = await self._handle_get_dataset(arguments)
            elif name == "get_dcf_data":
                result = await self._handle_get_dcf_data(arguments)
            elif name == "get_forecast_data":
                result = await self._handle_get_forecast_data(arguments)
            elif name == "calculate_wacc_inputs":
                result = await self._handle_calculate_wacc_inputs(arguments)
            elif name == "get_growth_estimates":
                result = await self._handle_get_growth_estimates(arguments)
            elif name == "list_valuation_datasets":
                result = await self._handle_list_valuation_datasets(arguments)
            elif name == "get_fields":
                result = await self._handle_get_fields(arguments)
            else:
                return CallToolResult(
                    content=[{"type": "text", "text": f"Unknown tool: {name}"}],
                    isError=True
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

    async def _handle_get_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_fields tool call for data workspace compatibility.
        Delegates to get_dataset for actual fetching.
        """
        # Map get_fields args to get_dataset format
        symbol = args.get("symbol") or args.get("ticker") or ""
        params = args.get("params", {})
        datasets = args.get("datasets") or []
        if args.get("dataset"):
            datasets.append(args["dataset"])
        
        result = await self._handle_get_dataset({
            "symbol": symbol,
            "datasets": datasets,
            "params": params,
        })
        
        # Format response for data workspace compatibility
        # Service expects {"symbol": ..., "datasets": {name: {"data": [...]}}}
        if "datasets" in result:
            formatted_datasets = {}
            for name, data in result["datasets"].items():
                # Wrap raw list data in {"data": ...} if needed
                if isinstance(data, list):
                    formatted_datasets[name] = {"data": data}
                elif isinstance(data, dict) and "data" in data:
                    formatted_datasets[name] = data
                else:
                    formatted_datasets[name] = {"data": data}
            return {
                "symbol": symbol,
                "datasets": formatted_datasets,
            }
        return result

    async def _handle_get_dataset(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dataset-first fetch with basic required param checking."""
        dataset_names: List[str] = []
        ds = args.get("dataset")
        if ds:
            dataset_names.append(ds)
        datasets = args.get("datasets") or []
        dataset_names.extend(datasets)

        if not dataset_names:
            return {"error": "No dataset provided"}

        symbol = args.get("symbol")
        params = args.get("params", {})

        async def fetch_dataset(name: str) -> Dict[str, Any]:
            dataset = self.ddc_loader.get_dataset(name)
            if not dataset:
                return {"error": "dataset_not_found"}

            truly_required = set(dataset.required_params or []) - {"symbol", "apikey"}
            missing = [k for k in truly_required if k not in params]
            if missing:
                return {
                    "error": "missing_required_params",
                    "required_params": missing,
                    "notes": dataset.notes,
                }
            try:
                return await self.data_fetcher.fetch_dataset(symbol or "", dataset, historical_params=params)
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        factories = {name: (lambda dataset_name=name: fetch_dataset(dataset_name)) for name in dataset_names}
        raw_results = await gather_dict(factories, concurrency_limit=4)

        results: Dict[str, Any] = {}
        missing_requirements: Dict[str, Any] = {}
        for name, payload in raw_results.items():
            if isinstance(payload, dict) and payload.get("error") in {"dataset_not_found", "missing_required_params"}:
                missing_requirements[name] = payload
            else:
                results[name] = payload

        out: Dict[str, Any] = {"datasets": results}
        if missing_requirements:
            out["status"] = "missing_required_params"
            out["missing_params"] = missing_requirements
        return out

    async def _handle_discover_dcf_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle discover_dcf_fields tool call"""
        symbol = args.get("symbol", "AAPL")
        max_datasets = args.get("max_datasets", 30)

        if not self.field_discovery:
            return {"error": "Field discovery not initialized"}

        try:
            # Get all valuation datasets from catalog dynamically (NO hardcoding)
            # These contain DCF inputs and calculations
            dcf_datasets = [
                ds.dataset
                for ds in (self.catalog.datasets if self.catalog else [])
                if ds.class_ == DatasetClass.VALUATION
            ]

            if not dcf_datasets:
                logger.warning("No valuation datasets found in catalog")
                dcf_datasets = []  # Empty list for filtering

            # Pass period param for analyst/forecast endpoints that may be included
            discovery_params = {"period": "annual"}
            discovered = await self.field_discovery.discover_fields(symbol, max_datasets, discovery_params=discovery_params)

            # Filter to DCF-relevant fields
            dcf_fields = {}
            for field_name, field_info in discovered.items():
                if any(dataset in field_info.get("source", "") for dataset in dcf_datasets):
                    dcf_fields[field_name] = field_info

            return {
                "discovered_fields": len(dcf_fields),
                "total_datasets": len(set(info["source"] for info in dcf_fields.values())),
                "fields": dcf_fields
            }

        except Exception as e:
            logger.error(f"Error discovering DCF fields: {e}")
            return {"error": str(e)}

    async def _handle_discover_forecast_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle discover_forecast_fields tool call"""
        symbol = args.get("symbol", "AAPL")
        max_datasets = args.get("max_datasets", 10)
        period = args.get("period", "annual")
        year = args.get("year")

        if not self.field_discovery:
            return {"error": "Field discovery not initialized"}

        try:
            # Build discovery parameters for endpoints that need them
            discovery_params = {"period": period}
            if year:
                discovery_params["year"] = year

            # Get forecast AND valuation datasets from catalog dynamically (NO hardcoding)
            # Valuation datasets (DCF) contain forward-looking projections and growth assumptions
            forecast_datasets = [
                ds.dataset
                for ds in (self.catalog.datasets if self.catalog else [])
                if ds.class_ in [DatasetClass.FORECAST, DatasetClass.VALUATION]
            ]

            if not forecast_datasets:
                logger.warning("No forecast or valuation datasets found in catalog")
                forecast_datasets = []  # Empty list for filtering

            discovered = await self.field_discovery.discover_fields(symbol, max_datasets, discovery_params=discovery_params)

            # Filter to forecast-relevant fields
            forecast_fields = {}
            for field_name, field_info in discovered.items():
                if any(dataset in field_info.get("source", "") for dataset in forecast_datasets):
                    forecast_fields[field_name] = field_info

            return {
                "discovered_fields": len(forecast_fields),
                "total_datasets": len(set(info["source"] for info in forecast_fields.values())),
                "fields": forecast_fields
            }

        except Exception as e:
            logger.error(f"Error discovering forecast fields: {e}")
            return {"error": str(e)}

    async def _handle_get_dcf_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_dcf_data tool call"""
        symbol = args.get("symbol")
        fields = args.get("fields", [])

        if not symbol:
            return {"error": "Symbol is required"}

        if not self.data_fetcher or not self.field_manager:
            return {"error": "Data fetcher not initialized"}

        try:
            # Default DCF fields if none specified
            if not fields:
                fields = [
                    "revenue", "operatingIncome", "netIncome", "freeCashFlow",
                    "totalDebt", "totalCash", "sharesOutstanding", "marketCap",
                    "operatingMargin", "netMargin", "returnOnEquity", "returnOnAssets"
                ]

            # Get optimal endpoints for requested fields
            endpoints = self.field_manager.get_endpoints_for_fields(fields)

            result_data = {}
            for endpoint, endpoint_fields in endpoints.items():
                dataset = self.ddc_loader.get_dataset(endpoint)
                if dataset:
                    data = await self.data_fetcher.fetch_dataset(symbol, dataset)
                    if data:
                        result_data.update(data)

            return {
                "symbol": symbol,
                "dcf_data": result_data,
                "fields_requested": fields,
                "endpoints_used": list(endpoints.keys())
            }

        except Exception as e:
            logger.error(f"Error fetching DCF data: {e}")
            return {"error": str(e)}

    async def _handle_get_forecast_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_forecast_data tool call - uses financial-estimates dataset"""
        symbol = args.get("symbol")
        forecast_types = args.get("forecast_types", ["revenue", "earnings", "growth"])

        if not symbol:
            return {"error": "Symbol is required"}

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        try:
            # Use the ONLY forecast dataset available in valuation catalog
            estimates_dataset = self.ddc_loader.get_dataset("financial-estimates")

            if not estimates_dataset:
                logger.warning("financial-estimates dataset not found in valuation catalog")
                return {
                    "symbol": symbol,
                    "forecast_data": {},
                    "forecast_types": forecast_types,
                    "warning": "financial-estimates dataset not available"
                }

            # Fetch analyst estimates (contains revenue, EPS, and other projections)
            estimates_data = await self.data_fetcher.fetch_dataset(symbol, estimates_dataset, historical_params={"period": "annual"})

            if not estimates_data:
                logger.warning(f"No forecast data returned for {symbol} from financial-estimates")
                return {
                    "symbol": symbol,
                    "forecast_data": {},
                    "forecast_types": forecast_types
                }

            # Parse response and organize by forecast type
            forecast_data = {}

            # Extract revenue forecasts if requested
            if "revenue" in forecast_types:
                forecast_data["revenue_forecasts"] = estimates_data

            # Extract earnings forecasts if requested
            if "earnings" in forecast_types:
                forecast_data["earnings_forecasts"] = estimates_data

            # Extract growth estimates if requested
            if "growth" in forecast_types:
                forecast_data["growth_estimates"] = estimates_data

            logger.info(f"Retrieved forecast data for {symbol} from financial-estimates dataset")

            return {
                "symbol": symbol,
                "forecast_data": forecast_data,
                "forecast_types": forecast_types,
                "source_dataset": "financial-estimates"
            }

        except Exception as e:
            logger.error(f"Error fetching forecast data for {symbol}: {e}")
            return {"error": str(e)}

    async def _handle_calculate_wacc_inputs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle calculate_wacc_inputs tool call - uses available valuation datasets"""
        symbol = args.get("symbol")

        if not symbol:
            return {"error": "Symbol is required"}

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        try:
            wacc_data = {}

            # Check for DCF valuation which may contain WACC calculation
            dcf_dataset = self.ddc_loader.get_dataset("discounted-cash-flow")
            if dcf_dataset:
                dcf_data = await self.data_fetcher.fetch_dataset(symbol, dcf_dataset)
                if dcf_data:
                    wacc_data["dcf_valuation"] = dcf_data
                    logger.info(f"Retrieved DCF data for {symbol} (may contain WACC)")

            # Note: balance-sheet-statement, key-metrics, and company-profile
            # are in the main FMPMarketDataServer catalog, not valuation catalog
            logger.info(f"WACC calculation requires data from FMPMarketDataServer:")
            logger.info(f"  - balance-sheet-statement (debt/equity)")
            logger.info(f"  - key-metrics-ttm (beta, market cap)")
            logger.info(f"  - company-profile (industry, sector)")

            return {
                "symbol": symbol,
                "wacc_inputs": wacc_data,
                "source_dataset": "discounted-cash-flow",
                "note": "Complete WACC calculation requires FMPMarketDataServer for balance sheet and key metrics"
            }

        except Exception as e:
            logger.error(f"Error fetching WACC inputs for {symbol}: {e}")
            return {"error": str(e)}

    async def _handle_get_growth_estimates(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_growth_estimates tool call - uses financial-estimates dataset"""
        symbol = args.get("symbol")

        if not symbol:
            return {"error": "Symbol is required"}

        if not self.data_fetcher:
            return {"error": "Data fetcher not initialized"}

        try:
            # Use the ONLY forecast dataset available in valuation catalog
            estimates_dataset = self.ddc_loader.get_dataset("financial-estimates")

            if not estimates_dataset:
                logger.warning("financial-estimates dataset not found in valuation catalog")
                return {
                    "symbol": symbol,
                    "growth_estimates": {},
                    "warning": "financial-estimates dataset not available"
                }

            # Fetch analyst estimates (contains revenue, EPS, and other projections)
            estimates_data = await self.data_fetcher.fetch_dataset(symbol, estimates_dataset, historical_params={"period": "annual"})

            if not estimates_data:
                logger.warning(f"No growth estimates returned for {symbol} from financial-estimates")
                return {
                    "symbol": symbol,
                    "growth_estimates": {}
                }

            # Return estimates data - agent can calculate growth rates from projections
            logger.info(f"Retrieved growth estimates for {symbol} from financial-estimates dataset")

            return {
                "symbol": symbol,
                "growth_estimates": estimates_data,
                "source_dataset": "financial-estimates",
                "note": "Growth rates can be calculated from year-over-year revenue/earnings projections"
            }

        except Exception as e:
            logger.error(f"Error fetching growth estimates for {symbol}: {e}")
            return {"error": str(e)}

    async def _handle_list_valuation_datasets(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_valuation_datasets tool call"""
        include_details = args.get("include_details", False)

        if not self.field_discovery:
            return {"error": "Field discovery not initialized"}

        try:
            datasets = self.field_discovery.list_datasets(include_details)

            # Filter to valuation and forecast datasets
            valuation_datasets = [
                ds for ds in datasets
                if ds.get("class") in ["valuation", "forecast"]
            ]

            return {
                "total_datasets": len(valuation_datasets),
                "valuation_datasets": len([ds for ds in valuation_datasets if ds.get("class") == "valuation"]),
                "forecast_datasets": len([ds for ds in valuation_datasets if ds.get("class") == "forecast"]),
                "datasets": valuation_datasets
            }

        except Exception as e:
            logger.error(f"Error listing valuation datasets: {e}")
            return {"error": str(e)}

    async def connect(self):
        """Initialize connections"""
        await self.data_fetcher.connect()
        logger.info("FMPAdvancedValuationServer connected")

    async def cleanup(self):
        """Cleanup connections"""
        await self.data_fetcher.cleanup()
        self.field_manager.close()
        logger.info("FMPAdvancedValuationServer cleaned up")


# Factory function for easy instantiation
def create_fmp_advanced_valuation_server(api_key: str = None) -> FMPAdvancedValuationServer:
    """
    Create an FMP Advanced Valuation Server instance.

    Args:
        api_key: FMP API key (if not provided, reads from FMP_API_KEY environment variable)

    Returns:
        Configured FMPAdvancedValuationServer instance
    """
    if not api_key:
        api_key = os.getenv("FMP_API_KEY")
        if not api_key:
            raise ValueError("FMP_API_KEY environment variable or api_key parameter required")

    return FMPAdvancedValuationServer(api_key)
