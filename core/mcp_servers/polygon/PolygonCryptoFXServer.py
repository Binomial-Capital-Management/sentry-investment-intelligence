"""
Polygon Crypto & FX MCP server.

Provides Polygon tooling for foreign exchange and crypto datasets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.mcp.server import MCPTool

from .polygon_base_server import PolygonBaseServer
from .polygon_ddc_loader import PolygonAssetClass, PolygonAssetGroup, PolygonDatasetClass


class PolygonCryptoFXServer(PolygonBaseServer):
    """Expose Polygon FX and crypto datasets through MCP tools."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        placeholder_rules: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name="PolygonCryptoFXServer",
            asset_group=PolygonAssetGroup.CRYPTO_FX,
            api_key=api_key,
            placeholder_rules=placeholder_rules,
        )
        self._tools = self._build_tools()

    def get_available_tools(self) -> List[MCPTool]:
        return self._tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        handlers = {
            "discover_polygon_crypto_fields": self._handle_discover_fields,
            "discover_polygon_crypto_technical_fields": self._handle_discover_technical_fields,
            "list_polygon_crypto_datasets": self._handle_list_datasets,
            "get_polygon_crypto_dataset": self._handle_get_dataset,
            "get_fields": self._handle_get_fields,  # Proper handler for object_data_service compatibility
            "get_polygon_crypto_aggregates": self._handle_get_aggregates,
            "get_polygon_crypto_snapshot": self._handle_get_snapshot,
            "convert_currency": self._handle_convert_currency,
            "get_market_movers": self._handle_get_market_movers,
            "list_polygon_crypto_cached_fields": self._handle_list_cached_fields,
            "get_polygon_crypto_market_status": self._handle_get_market_status,
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
                name="discover_polygon_crypto_fields",
                description=(
                    "Probe the Polygon FX/crypto catalog for available fields, required parameters, notes, and "
                    "entitlement guidance for the supplied ticker."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "datasets": {"type": "array", "items": {"type": "string"}},
                        "max_datasets": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 6,
                        },
                    },
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="discover_polygon_crypto_technical_fields",
                description=(
                    "Discover Polygon technical/derived datasets for FX and crypto tickers (momentum, volatility, "
                    "rankings) with catalog notes and requirements."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "max_datasets": {"type": "integer", "minimum": 1, "maximum": 10, "default": 4},
                    },
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="list_polygon_crypto_datasets",
                description=(
                    "List Polygon FX/crypto catalog entries, including dataset class, supported asset classes, "
                    "required params, rate limits, and notes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset_class": {"type": "string", "enum": dataset_class_enum},
                        "discoverable_only": {"type": "boolean", "default": False},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polygon_crypto_dataset",
                description=(
                    "Fetch a Polygon FX/crypto dataset using catalog metadata. Unsupported params are ignored and "
                    "responses reflect catalog notes/requirements."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "dataset": {"type": "string"},
                        "params": {"type": "object"},
                    },
                    "required": ["ticker", "dataset"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polygon_crypto_aggregates",
                description=(
                    "Retrieve catalog-driven Polygon aggregate bars for FX or crypto tickers with automatic date "
                    "defaults and adjustment flags."
                ),
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
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                        "adjusted": {"type": "boolean"},
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
                name="get_polygon_crypto_snapshot",
                description=(
                    "Retrieve Polygon's FX/crypto unified snapshot (supports multiple tickers) incorporating catalog "
                    "notes and market filters."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {"type": "array", "items": {"type": "string"}},
                        "ticker": {"type": "string"},
                        "market": {"type": "string", "enum": ["forex", "crypto"]},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                        "cursor": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="convert_currency",
                description=(
                    "Convert between currencies using Polygon real-time FX quotes; catalog notes highlight precision "
                    "limits and supported pairs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "from_currency": {"type": "string", "description": "Base currency code (ISO-4217)."},
                        "to_currency": {"type": "string", "description": "Quote currency code (ISO-4217)."},
                        "amount": {"type": "number", "description": "Amount to convert."},
                        "precision": {"type": "integer", "minimum": 0, "maximum": 6},
                    },
                    "required": ["from_currency", "to_currency"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_market_movers",
                description=(
                    "Retrieve catalog-backed FX/crypto market movers (gainers/losers) with asset-class filtering and "
                    "rate-limit-aware defaults."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_class": {
                            "type": "string",
                            "enum": [PolygonAssetClass.FOREX.value, PolygonAssetClass.CRYPTO.value],
                            "default": PolygonAssetClass.FOREX.value,
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["gainers", "losers"],
                            "default": "gainers",
                        },
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="list_polygon_crypto_cached_fields",
                description=(
                    "List cached FX/crypto field discovery results persisted by the catalog, including dataset info "
                    "and timestamps."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_class": {
                            "type": "string",
                            "enum": [PolygonAssetClass.FOREX.value, PolygonAssetClass.CRYPTO.value],
                        }
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polygon_crypto_market_status",
                description=(
                    "Return Polygon status for FX and crypto venues and, when requested, the catalog-defined upcoming "
                    "schedule."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {"include_upcoming": {"type": "boolean", "default": False}},
                    "additionalProperties": False,
                },
            ),
        ]

    async def _handle_discover_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.field_discovery.discover_fields(
            args["ticker"],
            dataset_names=args.get("datasets"),
            max_datasets=args.get("max_datasets", 6),
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
        return {"datasets": [dataset.to_dict() for dataset in datasets], "count": len(datasets)}

    async def _handle_get_dataset(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset = self._ensure_dataset(args["dataset"])
        validation = self._validation_for_dataset(dataset, args["ticker"])
        params = args.get("params") or {}
        return await self._fetch_dataset(dataset, validation, query_params=params)

    def _dataset_needs_ticker_components(self, dataset_name: str) -> bool:
        """
        Check if a dataset's URL placeholders require ticker components.
        
        Some datasets have identifier_param=null but their URL uses placeholders
        like {from}/{to} that need to be extracted from ticker components
        (e.g., crypto-open-close: /v1/open-close/crypto/{from}/{to}/{date}).
        """
        # Check if there are dataset-specific placeholder rules that use 'component' source
        dataset_rules = self.field_discovery._dataset_placeholder_rules.get(dataset_name, {})
        for rule in dataset_rules.values():
            if isinstance(rule, dict) and rule.get("source") == "component":
                return True
        return False

    async def _handle_get_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic dataset fetch for data workspace compatibility.
        Accepts 'datasets' (list) or 'dataset' (string), plus 'params' and identifier.
        
        Maps symbol/ticker to the appropriate parameter and iterates over datasets.
        Returns consistent {"datasets": {...}} format like UW/FMP servers.
        """
        import copy
        
        # Ticker-type identifier params that require a symbol
        TICKER_PARAMS = {'ticker', 'crypto_ticker', 'fx_ticker', 'symbol', 'tickers'}
        # Non-ticker identifier params that should come from params dict (NOT component-based)
        NON_TICKER_PARAMS = {'date', 'direction'}
        
        # Collect dataset names from both singular and plural args
        dataset_names: List[str] = []
        if args.get("dataset"):
            dataset_names.append(args["dataset"])
        if args.get("datasets"):
            dataset_names.extend(args["datasets"])
        
        if not dataset_names:
            return {"error": "No dataset(s) provided", "datasets": {}}
        
        # Get identifier from various possible keys (symbol, ticker, etc.)
        identifier = (
            args.get("ticker") or
            args.get("symbol") or
            args.get("crypto_ticker") or
            args.get("fx_ticker")
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
                
                # Determine the default asset class from the dataset's supported asset_classes
                default_asset_class = None
                if dataset.asset_classes:
                    # Prefer crypto if available, else forex
                    if PolygonAssetClass.CRYPTO in dataset.asset_classes:
                        default_asset_class = PolygonAssetClass.CRYPTO
                    elif PolygonAssetClass.FOREX in dataset.asset_classes:
                        default_asset_class = PolygonAssetClass.FOREX
                
                # Check if identifier_param is a ticker-type or non-ticker-type
                id_param = dataset.identifier_param
                is_ticker_param = id_param in TICKER_PARAMS if id_param else False
                is_non_ticker_param = id_param in NON_TICKER_PARAMS if id_param else False
                
                # Check if URL placeholders need ticker components (even if identifier_param is null)
                needs_ticker_components = self._dataset_needs_ticker_components(ds_name)
                
                # Determine if we have a valid ticker for this request
                has_valid_ticker = identifier and identifier not in ('_MARKET_', 'MARKET', '')
                
                # Determine if this is truly market-wide (no ticker required)
                # NOT market-wide if URL placeholders need ticker components
                is_market_wide = (
                    (id_param is None and not needs_ticker_components) or  # No identifier AND no component needs
                    is_non_ticker_param  # Identifier is non-ticker (date, direction, etc.)
                )
                
                # For datasets needing ticker components, require a ticker
                if needs_ticker_components and not has_valid_ticker:
                    results[ds_name] = {
                        "error": "missing_required_params",
                        "required_params": ["ticker"],
                        "hint": f"Dataset '{ds_name}' requires a ticker to extract URL components",
                    }
                    continue
                
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
                if is_market_wide and not has_valid_ticker:
                    # Market-wide endpoint, use default validation with correct asset class
                    validation = self._default_validation(default_asset_class)
                elif has_valid_ticker:
                    try:
                        validation = self._validation_for_dataset(dataset, identifier)
                    except ValueError as ve:
                        results[ds_name] = {"error": str(ve)}
                        continue
                else:
                    # Fallback to default validation
                    validation = self._default_validation(default_asset_class)
                
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
        result = await self._fetch_dataset(dataset, validation, query_params=query)
        result["source"] = "Polygon.io"
        result["source_type"] = "market_data"
        return result

    async def _handle_convert_currency(self, args: Dict[str, Any]) -> Dict[str, Any]:
        base = args["from_currency"].strip().upper()
        quote = args["to_currency"].strip().upper()
        pair = f"C:{base}{quote}"

        dataset = self._ensure_dataset("forex-conversion")
        validation = self.validator.normalize(pair)
        query = {}
        if "amount" in args:
            query["amount"] = args["amount"]
        if "precision" in args:
            query["precision"] = args["precision"]
        result = await self._fetch_dataset(dataset, validation, query_params=query)
        result["source"] = "Polygon.io"
        result["source_type"] = "market_data"
        return result

    async def _handle_get_market_movers(self, args: Dict[str, Any]) -> Dict[str, Any]:
        asset_class = PolygonAssetClass(args.get("asset_class", PolygonAssetClass.FOREX.value))
        direction = args.get("direction", "gainers")
        limit = args.get("limit")

        if asset_class is PolygonAssetClass.FOREX:
            dataset = self._ensure_dataset("forex-snapshot-movers")
            validation = self._resolve_validation("C:EURUSD")
        else:
            dataset = self._ensure_dataset("crypto-snapshot-movers")
            validation = self._resolve_validation("X:BTCUSD")

        path_overrides = {"direction": direction}
        query = {}
        if limit:
            query["limit"] = limit

        result = await self._fetch_dataset(dataset, validation, path_overrides=path_overrides, query_params=query)
        result["source"] = "Polygon.io"
        result["source_type"] = "market_data"
        return result

    async def _handle_list_cached_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        asset_class = args.get("asset_class")
        asset_enum = PolygonAssetClass(asset_class) if asset_class else None
        cached = self._list_cached_fields(asset_enum)
        return {"fields": cached, "count": len(cached)}

    async def _handle_get_market_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        include_upcoming = args.get("include_upcoming", False)
        validation = self._default_validation()
        current = await self._fetch_dataset(self._ensure_dataset("marketstatus-now"), validation)

        if not include_upcoming:
            return {"current": current}

        upcoming = await self._fetch_dataset(self._ensure_dataset("marketstatus-upcoming"), validation)
        return {"current": current, "upcoming": upcoming}

    def _default_validation(self, asset_class: Optional[PolygonAssetClass] = None) -> Any:
        """Return a default validation for the given asset class or infer from context."""
        # If asset_class is provided, use it to determine the default ticker
        if asset_class == PolygonAssetClass.CRYPTO:
            return self.validator.normalize("X:BTCUSD")
        elif asset_class == PolygonAssetClass.FOREX:
            return self.validator.normalize("C:EURUSD")
        # Default to forex for backward compatibility
        return self.validator.normalize("C:EURUSD")

    def _fallback_validation(self, ticker: str) -> Any:
        upper = ticker.strip().upper()
        if len(upper) == 6 and upper.isalpha():
            return self.validator.normalize(f"C:{upper}")
        if "-" in upper or len(upper) >= 6:
            normalized = upper if upper.startswith("X:") else f"X:{upper}"
            return self.validator.normalize(normalized)
        raise ValueError(f"Unable to normalize ticker '{ticker}' for FX/crypto datasets")
