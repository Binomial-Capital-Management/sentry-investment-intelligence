"""
Polygon Options MCP server.

Implements Polygon-specific tooling for listed options datasets while reusing
shared infrastructure from polygon_base_server.py. Futures support is not
available in this environment.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from agents.mcp.server import MCPTool

from .polygon_base_server import PolygonBaseServer
from .polygon_ddc_loader import PolygonAssetClass, PolygonAssetGroup, PolygonDatasetClass


class PolygonOptionsFuturesServer(PolygonBaseServer):
    """Expose Polygon options datasets through MCP tools."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        placeholder_rules: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name="PolygonOptionsFuturesServer",
            asset_group=PolygonAssetGroup.OPTIONS,
            api_key=api_key,
            placeholder_rules=placeholder_rules,
        )
        self._tools = self._build_tools()

    def get_available_tools(self) -> List[MCPTool]:
        return self._tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        handlers = {
            "discover_polygon_options_fields": self._handle_discover_fields,
            "discover_polygon_options_technical_fields": self._handle_discover_technical_fields,
            "list_polygon_options_datasets": self._handle_list_datasets,
            "get_polygon_options_dataset": self._handle_get_dataset,
            "get_fields": self._handle_get_fields,  # Proper handler for object_data_service compatibility
            "get_polygon_options_aggregates": self._handle_get_aggregates,
            "get_option_chain": self._handle_get_option_chain,
            "get_polygon_options_snapshot": self._handle_get_snapshot,
            "list_polygon_options_cached_fields": self._handle_list_cached_fields,
            "get_polygon_options_market_status": self._handle_get_market_status,
        }

        handler = handlers.get(name)
        if handler is None:
            return self._error(f"Unknown tool: {name}")

        try:
            result = await handler(arguments)
            if name == "get_fields" and arguments.get("_bh_raw"):
                return self._success(result, label=name, raw=True)
            return self._success(result, label=name)
        except Exception as exc:
            return self._error(f"Error executing {name}: {exc}")

    def _build_tools(self) -> List[MCPTool]:
        dataset_class_enum = [item.value for item in PolygonDatasetClass]

        return [
            MCPTool(
                name="discover_polygon_options_fields",
                description="Probes Polygon endpoints to discover available fields for an options ticker (O:AAPL250117C00150000). Returns field catalog with required params and cache settings. Use before fetching data to see what's available. Default probes 6 datasets, configurable via max_datasets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Options ticker to probe."},
                        "datasets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of dataset identifiers to probe.",
                        },
                        "max_datasets": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 6,
                            "description": "Maximum number of datasets to probe during discovery.",
                        },
                    },
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="discover_polygon_options_technical_fields",
                description="Probes technical options datasets to discover derived metrics: implied volatility (IV) ranks, Greeks (delta, gamma, theta, vega), probability metrics. Returns field catalog from technical endpoints. Default probes 4 datasets.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Options ticker to probe."},
                        "max_datasets": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 4,
                        },
                    },
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="list_polygon_options_datasets",
                description="Lists all Polygon options catalog datasets with class (raw, technical, reference), required params, rate limits, and notes. Filter by dataset_class or discoverable_only. Use to browse available endpoints.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset_class": {
                            "type": "string",
                            "enum": dataset_class_enum,
                            "description": "Optional dataset class filter.",
                        },
                        "discoverable_only": {
                            "type": "boolean",
                            "default": False,
                            "description": "Limit results to datasets marked discoverable.",
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polygon_options_dataset",
                description="Fetches specific Polygon options dataset by catalog name. Provide ticker and dataset identifier with optional params. Unsupported params auto-ignored. Response includes catalog notes showing required fields if incomplete.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Ticker to query."},
                        "dataset": {"type": "string", "description": "Dataset identifier from the catalog."},
                        "params": {
                            "type": "object",
                            "description": "Optional query parameters to include. Unsupported keys are ignored.",
                        },
                    },
                    "required": ["ticker", "dataset"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polygon_options_aggregates",
                description="Fetches OHLCV bars for options contracts. Provide ticker (O:AAPL250117C00150000) and bar size via multiplier+timespan (e.g., 1 day, 5 minute, 1 hour). Optional from/to dates (auto-generates 30-day range if omitted). Supports adjusted data, limit, and sort.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "multiplier": {"type": "integer", "minimum": 1, "default": 1},
                        "timespan": {
                            "type": "string",
                            "enum": ["minute", "hour", "day", "week", "month", "quarter", "year"],
                            "default": "day",
                        },
                        "from": {"type": "string", "description": "Start date (YYYY-MM-DD). Defaults to 30 days ago."},
                        "to": {"type": "string", "description": "End date (YYYY-MM-DD). Defaults to today."},
                        "adjusted": {"type": "boolean", "description": "Whether to request adjusted data when supported."},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50000,
                            "description": "Maximum number of aggregate bars to return.",
                        },
                        "sort": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "Sort order for aggregates (ascending or descending).",
                        },
                    },
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_option_chain",
                description="Fetches full options chain for an underlying stock (e.g., AAPL). Returns all available options contracts with current snapshot data. Supports pagination via cursor and limit. Supports expiration date filtering to exclude 0-DTE or limit date range.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "underlying": {"type": "string", "description": "Underlying asset symbol, e.g. AAPL."},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 250},
                        "cursor": {"type": "string", "description": "Pagination cursor from a prior response."},
                        "expiration_date.gte": {
                            "type": "string",
                            "description": "Minimum expiration date (YYYY-MM-DD). Use to filter out 0-DTE options.",
                        },
                        "expiration_date.lte": {
                            "type": "string",
                            "description": "Maximum expiration date (YYYY-MM-DD). Use to limit expiration range.",
                        },
                        "contract_type": {
                            "type": "string",
                            "enum": ["call", "put"],
                            "description": "Filter by contract type (call or put).",
                        },
                        "strike_price.gte": {
                            "type": "number",
                            "description": "Minimum strike price filter.",
                        },
                        "strike_price.lte": {
                            "type": "number",
                            "description": "Maximum strike price filter.",
                        },
                    },
                    "required": ["underlying"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polygon_options_snapshot",
                description="Fetches unified snapshot for multiple options contracts. Provide tickers array or single ticker with optional market filter (options/forex/crypto). Returns current price, Greeks, IV. Supports pagination.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of tickers to include in the unified snapshot request.",
                        },
                        "ticker": {"type": "string", "description": "Convenience field for a single ticker."},
                        "market": {
                            "type": "string",
                            "enum": ["options", "forex", "crypto"],
                            "description": "Optional market filter supported by Polygon snapshot endpoint.",
                        },
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                        "cursor": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="list_polygon_options_cached_fields",
                description="Lists cached field discovery results for options with dataset names, timestamps, and notes. Returns previously discovered fields for faster reuse without re-probing endpoints.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_class": {
                            "type": "string",
                            "enum": [PolygonAssetClass.OPTIONS.value],
                        }
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polygon_options_market_status",
                description="Fetches current options market status (open/closed) for trading venues. Use include_upcoming=true to also get holiday schedule. Returns venue status and optional upcoming market closures.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_upcoming": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include upcoming market holiday schedule.",
                        }
                    },
                    "additionalProperties": False,
                },
            ),
        ]

    async def _handle_discover_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        datasets = args.get("datasets")
        max_datasets = args.get("max_datasets", 6)
        result = await self.field_discovery.discover_fields(
            args["ticker"],
            dataset_names=datasets,
            max_datasets=max_datasets,
        )
        return {"fields": result, "dataset_count": len(result)}

    async def _handle_discover_technical_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        max_datasets = args.get("max_datasets", 4)
        technical_datasets = [
            dataset.dataset
            for dataset in self.loader.list_datasets(
                asset_group=self._asset_group,
                dataset_class=PolygonDatasetClass.TECHNICAL,
            )
        ][:max_datasets]
        result = await self.field_discovery.discover_fields(
            args["ticker"],
            dataset_names=technical_datasets,
            max_datasets=max_datasets,
        )
        return {"fields": result, "dataset_count": len(result)}

    async def _handle_list_datasets(self, args: Dict[str, Any]) -> Dict[str, Any]:
        datasets = self._list_datasets(
            dataset_class=args.get("dataset_class"),
            discoverable_only=args.get("discoverable_only", False),
        )
        return {
            "datasets": [dataset.to_dict() for dataset in datasets],
            "count": len(datasets),
        }

    async def _handle_get_dataset(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset = self._ensure_dataset(args["dataset"])
        validation = self._validation_for_dataset(dataset, args["ticker"])
        params = args.get("params") or {}
        return await self._fetch_dataset(dataset, validation, query_params=params)

    async def _handle_get_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic dataset fetch for data workspace compatibility.
        Accepts 'datasets' (list) or 'dataset' (string), plus 'params' and identifier.
        
        Maps symbol/ticker to the appropriate parameter and iterates over datasets.
        Returns consistent {"datasets": {...}} format like UW/FMP servers.
        """
        import copy
        
        # Ticker-type identifier params that require a symbol
        TICKER_PARAMS = {'ticker', 'options_ticker', 'underlying', 'symbol'}
        # Non-ticker identifier params that should come from params dict
        NON_TICKER_PARAMS = {'date', 'direction', 'contract_ticker'}
        
        # Collect dataset names from both singular and plural args
        dataset_names: List[str] = []
        if args.get("dataset"):
            dataset_names.append(args["dataset"])
        if args.get("datasets"):
            dataset_names.extend(args["datasets"])
        
        if not dataset_names:
            return {"error": "No dataset(s) provided", "datasets": {}}
        
        # Get identifier from various possible keys (symbol, ticker, options_ticker, etc.)
        identifier = (
            args.get("ticker") or
            args.get("symbol") or
            args.get("options_ticker") or
            args.get("underlying")
        )
        
        base_params = dict(args.get("params", {}))
        results: Dict[str, Any] = {}
        
        for ds_name in dataset_names:
            try:
                # Look up dataset in catalog
                dataset = self.loader.get_dataset(ds_name)
                if dataset is None:
                    results[ds_name] = {"error": f"Dataset not found: {ds_name}"}
                    continue
                
                # Check if dataset is available for this asset group
                if self._asset_group not in dataset.asset_group:
                    results[ds_name] = {"error": f"Dataset '{ds_name}' not available for {self._asset_group.value}"}
                    continue
                
                # Check if identifier_param is a ticker-type or non-ticker-type
                id_param = dataset.identifier_param
                is_ticker_param = id_param in TICKER_PARAMS if id_param else False
                is_non_ticker_param = id_param in NON_TICKER_PARAMS if id_param else False
                
                # Determine if we have a valid ticker for this request
                has_valid_ticker = identifier and identifier not in ('_MARKET_', 'MARKET', '')
                
                # Determine if this is truly market-wide (no ticker required)
                is_market_wide = (
                    id_param is None or  # No identifier param at all
                    is_non_ticker_param  # Identifier is non-ticker (date, direction, etc.)
                )
                
                # For ticker-type params, require a ticker
                if is_ticker_param and not has_valid_ticker:
                    results[ds_name] = {
                        "error": "missing_required_params",
                        "required_params": [id_param],
                    }
                    continue
                
                # For non-ticker params, check if they're in base_params
                if is_non_ticker_param and id_param not in base_params:
                    results[ds_name] = {
                        "error": "missing_required_params",
                        "required_params": [id_param],
                        "hint": f"Provide '{id_param}' in params dict",
                    }
                    continue
                
                # Validate ticker or use default for market-wide endpoints
                if is_market_wide or not has_valid_ticker:
                    # Market-wide endpoint, use default validation
                    validation = self._default_validation()
                else:
                    try:
                        validation = self._validation_for_dataset(dataset, identifier)
                    except ValueError as ve:
                        results[ds_name] = {"error": str(ve)}
                        continue
                
                # Fetch data
                fetch_result = await self._fetch_dataset(dataset, validation, query_params=base_params)
                
                # Extract the actual data from the fetch result
                if isinstance(fetch_result, dict) and "data" in fetch_result:
                    results[ds_name] = copy.deepcopy(fetch_result["data"])
                else:
                    results[ds_name] = copy.deepcopy(fetch_result)
                    
            except Exception as e:
                results[ds_name] = {"error": str(e)}
        
        return {"datasets": results}

    async def _handle_get_aggregates(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return await self.historical_data.get_aggregates(
            ticker=args["ticker"],
            multiplier=args.get("multiplier", 1),
            timespan=args.get("timespan", "day"),
            start=args.get("from"),
            end=args.get("to"),
            adjusted=args.get("adjusted"),
            limit=args.get("limit"),
            sort=args.get("sort"),
        )

    async def _handle_get_option_chain(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset = self._ensure_dataset("options-snapshot-chain")
        validation = self._build_manual_validation(args["underlying"])
        query = {}
        
        # Pagination params
        if "limit" in args:
            query["limit"] = args["limit"]
        if "cursor" in args:
            query["cursor"] = args["cursor"]
        
        # Expiration date filters (critical for avoiding 0-DTE flood)
        if "expiration_date.gte" in args:
            query["expiration_date.gte"] = args["expiration_date.gte"]
        if "expiration_date.lte" in args:
            query["expiration_date.lte"] = args["expiration_date.lte"]
        
        # Contract type filter
        if "contract_type" in args:
            query["contract_type"] = args["contract_type"]
        
        # Strike price filters
        if "strike_price.gte" in args:
            query["strike_price.gte"] = args["strike_price.gte"]
        if "strike_price.lte" in args:
            query["strike_price.lte"] = args["strike_price.lte"]
        
        return await self._fetch_dataset(dataset, validation, query_params=query)

    async def _handle_get_snapshot(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset = self._ensure_dataset("snapshot-unified")
        raw_tickers: List[str] = []
        if "tickers" in args and args["tickers"]:
            raw_tickers.extend(args["tickers"])
        if "ticker" in args and args["ticker"]:
            raw_tickers.append(args["ticker"])

        normalized_tickers: List[str] = []
        for ticker in raw_tickers:
            validation = self.validator.normalize(ticker)
            if validation.asset_group is not self._asset_group:
                raise ValueError(f"Ticker '{ticker}' not supported by {self.name}")
            normalized_tickers.append(validation.normalized)

        query: Dict[str, Any] = {}
        validation_seed: Optional[str] = None
        if normalized_tickers:
            deduped = sorted(set(normalized_tickers))
            validation_seed = deduped[0]
            query["ticker.any_of"] = ",".join(deduped)
        if "market" in args:
            query["market"] = args["market"]
        if "limit" in args:
            query["limit"] = args["limit"]
        if "cursor" in args:
            query["cursor"] = args["cursor"]

        validation = self._resolve_validation(validation_seed)
        return await self._fetch_dataset(dataset, validation, query_params=query)

    async def _handle_list_cached_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        asset_class = args.get("asset_class")
        asset_enum = PolygonAssetClass(asset_class) if asset_class else None
        cached = self._list_cached_fields(asset_enum)
        return {"fields": cached, "count": len(cached)}

    async def _handle_get_market_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        include_upcoming = args.get("include_upcoming", False)
        current_dataset = self._ensure_dataset("marketstatus-now")
        validation = self._default_validation()
        current = await self._fetch_dataset(current_dataset, validation)

        if not include_upcoming:
            return {"current": current}

        upcoming_dataset = self._ensure_dataset("marketstatus-upcoming")
        upcoming = await self._fetch_dataset(upcoming_dataset, validation)
        return {"current": current, "upcoming": upcoming}

    def _default_validation(self) -> Any:
        return self._build_manual_validation("SPY")

    def _fallback_validation(self, ticker: str) -> Any:
        return self._build_manual_validation(ticker)
