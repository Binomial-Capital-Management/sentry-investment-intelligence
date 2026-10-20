"""
FinFeed Prediction Markets MCP server wiring.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Type, TypeVar
import logging

from dotenv import load_dotenv

load_dotenv()

from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult
from mcp.types import TextContent
from pydantic import BaseModel

from .cache import TTLCache
from .catalog import MarketCatalog
from .http_client import FinFeedHTTPClient
from .schemas import (
    ConsensusProbability,
    ErrorEnvelope,
    Exchange,
    MarketHistory,
    MarketPrices,
    MarketResolved,
    OHLCVRecord,
    OutcomeInfo,
    Period,
    ToolCatalog,
    ToolMetadata,
)
from .utils import build_cache_key, create_outcome_slug, parse_iso_datetime

# Environment configuration -------------------------------------------------
FINFEED_BASE_URL = os.getenv("FINFEED_PREDICTION_BASE_URL")
FINFEED_API_KEY = os.getenv("FINFEED_PREDICTION_API_KEY")
FINFEED_JWT_KID = os.getenv("FINFEED_PREDICTION_JWT_KID")
FINFEED_JWT_SUB = os.getenv("FINFEED_PREDICTION_JWT_SUB", "finfeed-client")
FINFEED_JWT_ISS = os.getenv("FINFEED_PREDICTION_JWT_ISS", "finfeed-client")
FINFEED_JWT_TTL = int(os.getenv("FINFEED_PREDICTION_JWT_TTL_SEC", "240"))
FINFEED_JWT_PRIVATE_KEY = os.getenv("FINFEED_PREDICTION_JWT_PRIVATE_KEY")
FINFEED_RPS = int(os.getenv("FINFEED_PREDICTION_RPS", "10"))
FINFEED_CACHE_TTL = int(os.getenv("FINFEED_PREDICTION_CACHE_TTL_SEC", "300"))

ModelT = TypeVar("ModelT", bound=BaseModel)

logger = logging.getLogger(__name__)


class FinFeedPredictionMarketsServer(MCPServer):
    """Prediction markets MCP server following the FMP discovery pattern."""

    def __init__(self) -> None:
        super().__init__()
        for name, value in [
            ("FINFEED_PREDICTION_BASE_URL", FINFEED_BASE_URL),
            ("FINFEED_PREDICTION_API_KEY", FINFEED_API_KEY),
            ("FINFEED_PREDICTION_JWT_PRIVATE_KEY", FINFEED_JWT_PRIVATE_KEY),
            ("FINFEED_PREDICTION_JWT_KID", FINFEED_JWT_KID),
        ]:
            if not value:
                raise ValueError(f"Missing required env vars: {name}")

        private_key = FINFEED_JWT_PRIVATE_KEY.strip().strip('"')
        self._name = "FinFeedPredictionMarketsServer"
        self.use_structured_content = False  # Required by openai-agents SDK

        sub = (FINFEED_JWT_SUB or "finfeed-client").strip().strip('"')
        iss = (FINFEED_JWT_ISS or "finfeed-client").strip().strip('"')
        ttl = FINFEED_JWT_TTL
        try:
            ttl = int(ttl)
        except (TypeError, ValueError):
            ttl = 240

        self.client = FinFeedHTTPClient(
            base_url=FINFEED_BASE_URL,
            api_key=FINFEED_API_KEY,
            rps=FINFEED_RPS,
            private_key=private_key,
            kid=FINFEED_JWT_KID,
            sub=sub,
            iss=iss,
            ttl_seconds=ttl,
        )
        logger.info(
            "FinFeedPredictionMarketsServer initialized (kid=%s, sub=%s, ttl=%s)",
            FINFEED_JWT_KID,
            sub,
            ttl,
        )
        self.catalog = MarketCatalog(self.client)
        self.cache = TTLCache(FINFEED_CACHE_TTL)

        self._initialized = False
        self._tenant_id: Optional[str] = None

    @property
    def name(self) -> str:
        """Server name for MCP"""
        return self._name

    # ------------------------------------------------------------------ #
    # Lifecycle helpers
    # ------------------------------------------------------------------ #

    def set_tenant(self, tenant_id: str) -> None:
        """Set tenant identifier for cache key isolation."""
        self._tenant_id = tenant_id

    async def initialize(self) -> None:
        """Mark as initialized without loading markets (lazy loading on first search)."""
        if not self._initialized:
            # Don't pre-load markets on startup - search will trigger lazy loading
            self._initialized = True

    async def connect(self):
        """Initialize connections"""
        await self.initialize()

    async def cleanup(self) -> None:
        """Close network resources and clear cache."""
        await self.client.close()
        await self.cache.clear()

    # ------------------------------------------------------------------ #
    # MCP Abstract Methods
    # ------------------------------------------------------------------ #

    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        """MCP method: List available tools"""
        return self.get_tools()

    async def list_prompts(self, run_context, agent) -> List[str]:
        """List available prompts (none for this server)"""
        return []

    async def get_prompt(self, name: str, arguments: Dict, run_context, agent) -> str:
        """MCP method: Get a prompt (not implemented for this server)"""
        raise NotImplementedError(f"No prompts available for {self.name}")

    async def call_tool(self, tool_name: str, arguments: Dict) -> CallToolResult:
        """MCP method: Call a tool by name"""
        await self.initialize()

        # Map tool names to methods
        tool_methods = {
            "list_exchanges": self.list_exchanges,
            "list_periods": self.list_periods,
            "discover_prediction_fields": self.discover_prediction_fields,
            "refresh_catalog": self.refresh_catalog,
            "search_catalog": self.search_catalog,
            "resolve_market": self.resolve_market,
            "get_market_prices": self.get_market_prices,
            "get_market_history": self.get_market_history,
            "get_market_prices_smart": self.get_market_prices_smart,
            "get_market_history_smart": self.get_market_history_smart,
            "get_consensus_probability": self.get_consensus_probability,
        }

        if tool_name not in tool_methods:
            return CallToolResult(
                content=[{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                isError=True
            )

        try:
            result = await tool_methods[tool_name](arguments)
            return CallToolResult(
                content=[{"type": "text", "text": item.text} for item in result],
                isError=False
            )
        except Exception as e:
            return CallToolResult(
                content=[{"type": "text", "text": f"Error calling {tool_name}: {str(e)}"}],
                isError=True
            )

    # ------------------------------------------------------------------ #
    # Tool registration
    # ------------------------------------------------------------------ #

    def get_tools(self) -> List[MCPTool]:
        """Expose the tools supported by this MCP server."""
        return [
            MCPTool(
                name="list_exchanges",
                description="List available prediction market exchanges",
                inputSchema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="list_periods",
                description="List supported OHLCV periods",
                inputSchema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="discover_prediction_fields",
                description="Return metadata for all prediction market tools",
                inputSchema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="refresh_catalog",
                description="Refresh the in-memory catalog from the FinFeed API",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "exchanges": {"type": "array", "items": {"type": "string"}},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 1000,
                            "default": 100,
                            "description": "Page size per request (1-1000, default 100)",
                        },
                        "max_pages": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Optional maximum number of pages to fetch per exchange",
                        },
                        "page": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 1,
                            "description": "Starting page number (1-based)",
                        },
                    },
                },
            ),
            MCPTool(
                name="search_catalog",
                description="Fuzzy search prediction market catalog",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "exchanges": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="resolve_market",
                description="Resolve a query to a canonical market_id",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "exchanges": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="get_market_prices",
                description="Fetch current probabilities/prices for a market",
                inputSchema={
                    "type": "object",
                    "properties": {"market_id": {"type": "string"}},
                    "required": ["market_id"],
                },
            ),
            MCPTool(
                name="get_market_history",
                description="Fetch historical OHLCV data for a market",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "market_id": {"type": "string"},
                        "period_id": {"type": "string"},
                        "time_start": {"type": "string"},
                        "time_end": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["market_id", "period_id"],
                },
            ),
            MCPTool(
                name="get_market_prices_smart",
                description="Search, resolve, and fetch prices in one call",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "exchanges": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="get_market_history_smart",
                description="Search, resolve, and fetch history in one call",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "period_id": {"type": "string"},
                        "time_start": {"type": "string"},
                        "time_end": {"type": "string"},
                        "limit": {"type": "integer"},
                        "exchanges": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["query", "period_id"],
                },
            ),
            MCPTool(
                name="get_consensus_probability",
                description="Aggregate probabilities across platforms using cached prices",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "market_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["market_ids"],
                },
            ),
        ]

    # ------------------------------------------------------------------ #
    # Discovery tools
    # ------------------------------------------------------------------ #

    async def list_exchanges(self, arguments: Dict) -> List[TextContent]:
        data = await self.client.get("/v1/exchanges")
        if isinstance(data, dict):
            raw_exchanges = data.get("exchanges", [])
        else:
            raw_exchanges = data or []

        # Handle both dict and string formats
        exchanges = []
        for item in raw_exchanges:
            if isinstance(item, dict):
                # Standard dict format
                exchanges.append(
                    Exchange(
                        exchange_id=item.get("exchange_id"),
                        market_name_institution_description=item.get("market_name_institution_description"),
                        website=item.get("website"),
                        additional_properties={
                            key: value
                            for key, value in item.items()
                            if key not in {"exchange_id", "market_name_institution_description", "website"}
                        },
                    ).model_dump()
                )
            elif isinstance(item, str):
                # String format (just exchange IDs)
                exchanges.append(
                    Exchange(
                        exchange_id=item,
                        market_name_institution_description=None,
                        website=None,
                        additional_properties={},
                    ).model_dump()
                )

        return [TextContent(type="text", text=json.dumps({"exchanges": exchanges}, indent=2))]

    async def list_periods(self, arguments: Dict) -> List[TextContent]:
        data = await self.client.get("/v1/ohlcv/periods")
        raw_periods = data if isinstance(data, list) else data.get("periods", [])
        periods = [
            Period(
                period_id=item.get("period_id"),
                length_seconds=item.get("length_seconds"),
                length_months=item.get("length_months"),
                unit_count=item.get("unit_count"),
                unit_name=item.get("unit_name"),
                display_name=item.get("display_name"),
            ).model_dump()
            for item in raw_periods
        ]
        return [TextContent(type="text", text=json.dumps({"periods": periods}, indent=2))]

    async def discover_prediction_fields(self, arguments: Dict) -> List[TextContent]:
        metadata: List[ToolMetadata] = []
        for tool in self.get_tools():
            schema = tool.inputSchema or {}
            required = schema.get("required", [])
            optional = [
                key for key in schema.get("properties", {}).keys() if key not in required
            ]
            metadata.append(
                ToolMetadata(
                    name=tool.name,
                    description=tool.description or "",
                    required_params=required,
                    optional_params=optional,
                    notes=self._tool_notes(tool.name),
                    examples=self._tool_examples(tool.name),
                )
            )
        catalog = ToolCatalog(server=self.name, version="1.0", tools=metadata)
        return [TextContent(type="text", text=catalog.model_dump_json(indent=2))]

    async def refresh_catalog(self, arguments: Dict) -> List[TextContent]:
        limit = self._get_int_argument(arguments, "limit", minimum=1, maximum=1000, default=100)
        max_pages = self._get_int_argument(arguments, "max_pages", minimum=1, default=None)
        page_start = self._get_int_argument(arguments, "page", minimum=1, default=1)

        await self.catalog.refresh(
            arguments.get("exchanges"),
            limit=limit,
            max_pages=max_pages,
            page_start=page_start,
        )
        markets = await self.catalog.list_markets(limit=1_000_000)
        return [
            TextContent(
                type="text",
                text=json.dumps({"status": "ok", "markets_loaded": len(markets)}, indent=2),
            )
        ]

    def _require_text_argument(self, arguments: Dict, field: str) -> str:
        """Extract and validate a required string argument."""
        raw_value = arguments.get(field)
        if raw_value is None:
            raise ValueError(f"Missing required argument: {field}")
        if not isinstance(raw_value, str):
            raw_value = str(raw_value)
        value = raw_value.strip()
        if not value:
            raise ValueError(f"Argument '{field}' cannot be empty")
        return value

    def _get_int_argument(
        self,
        arguments: Dict,
        field: str,
        *,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
        default: Optional[int] = None,
    ) -> Optional[int]:
        """Parse an optional integer argument with bounds checking."""
        if field not in arguments or arguments[field] is None:
            return default

        try:
            value = int(arguments[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Argument '{field}' must be an integer") from exc

        if minimum is not None and value < minimum:
            raise ValueError(f"Argument '{field}' must be >= {minimum}")
        if maximum is not None and value > maximum:
            raise ValueError(f"Argument '{field}' must be <= {maximum}")

        return value

    async def search_catalog(self, arguments: Dict) -> List[TextContent]:
        await self.initialize()
        query = self._require_text_argument(arguments, "query")
        exchanges = arguments.get("exchanges")
        limit = arguments.get("limit", 10)

        # Lazy loading: Load markets on-demand only for requested exchanges
        # This avoids slow startup and only loads what's needed
        logger.info("Searching for: '%s' in exchanges: %s", query, exchanges or "all")

        # Conservative loading: Load 2-3 pages per exchange (~200-300 markets) to avoid rate limits
        # User can call refresh_catalog explicitly if they need full catalog
        await self.catalog.refresh(exchanges=exchanges, max_pages=3, limit=100)

        # Search the catalog
        results = await self.catalog.search(query, exchanges=exchanges, limit=limit)

        payload = [
            {"market": entry.model_dump(), "score": score} for entry, score in results
        ]
        return [TextContent(type="text", text=json.dumps({"results": payload}, indent=2))]

    async def resolve_market(self, arguments: Dict) -> List[TextContent]:
        await self.initialize()
        resolved = await self._resolve_market_internal(
            self._require_text_argument(arguments, "query"),
            exchanges=arguments.get("exchanges"),
        )
        return [TextContent(type="text", text=resolved.model_dump_json(indent=2))]

    # ------------------------------------------------------------------ #
    # Retrieval tools
    # ------------------------------------------------------------------ #

    async def get_market_prices(self, arguments: Dict) -> List[TextContent]:
        await self.initialize()
        try:
            prices = await self._fetch_market_prices(arguments["market_id"])
        except ValueError as exc:
            return [self._error_text("get_market_prices", str(exc))]
        return [TextContent(type="text", text=prices.model_dump_json(indent=2))]

    async def get_market_history(self, arguments: Dict) -> List[TextContent]:
        await self.initialize()
        try:
            history = await self._fetch_market_history(
                market_id=arguments["market_id"],
                period_id=arguments["period_id"],
                time_start=arguments.get("time_start"),
                time_end=arguments.get("time_end"),
                limit=arguments.get("limit"),
            )
        except ValueError as exc:
            return [self._error_text("get_market_history", str(exc))]
        return [TextContent(type="text", text=history.model_dump_json(indent=2))]

    async def get_market_prices_smart(self, arguments: Dict) -> List[TextContent]:
        await self.initialize()
        query = self._require_text_argument(arguments, "query")
        market_id = await self._resolve_with_cache(query, arguments.get("exchanges"))
        if market_id is None:
            return [
                self._error_text("get_market_prices_smart", "No markets found for supplied query")
            ]
        return await self.get_market_prices({"market_id": market_id})

    async def get_market_history_smart(self, arguments: Dict) -> List[TextContent]:
        await self.initialize()
        query = self._require_text_argument(arguments, "query")
        market_id = await self._resolve_with_cache(query, arguments.get("exchanges"))
        if market_id is None:
            return [
                self._error_text(
                    "get_market_history_smart", "No markets found for supplied query"
                )
            ]
        history_args = {
            "market_id": market_id,
            "period_id": arguments["period_id"],
            "time_start": arguments.get("time_start"),
            "time_end": arguments.get("time_end"),
            "limit": arguments.get("limit"),
        }
        return await self.get_market_history(history_args)

    async def get_consensus_probability(self, arguments: Dict) -> List[TextContent]:
        await self.initialize()
        market_ids = arguments.get("market_ids") or []
        if not market_ids:
            return [self._error_text("get_consensus_probability", "No market_ids supplied")]

        probabilities: List[float] = []
        platforms: List[Dict[str, object]] = []
        weighted_total = 0.0
        total_weight = 0.0

        for market_id in market_ids:
            try:
                prices = await self._fetch_market_prices(market_id)
            except ValueError:
                continue

            if not prices.outcomes:
                continue

            probability = prices.outcomes[0].probability
            if probability is None:
                continue

            entry = await self.catalog.get(market_id)
            weight = entry.volume_24h if entry and entry.volume_24h else 1.0

            probabilities.append(probability)
            weighted_total += probability * weight
            total_weight += weight
            platforms.append(
                {
                    "market_id": market_id,
                    "platform": entry.platform if entry else None,
                    "probability": probability,
                    "weight": weight,
                    "volume": entry.volume_24h if entry else None,
                }
            )

        if total_weight == 0:
            return [
                self._error_text(
                    "get_consensus_probability", "No valid probability data found", retriable=False
                )
            ]

        consensus_value = weighted_total / total_weight
        disagreement = 0.0
        if len(probabilities) > 1:
            mean = sum(probabilities) / len(probabilities)
            disagreement = (sum((p - mean) ** 2 for p in probabilities) / len(probabilities)) ** 0.5

        consensus = ConsensusProbability(
            consensus_probability=consensus_value,
            platforms=platforms,
            disagreement_score=disagreement,
            notes=[f"Aggregated across {len(platforms)} platforms"],
        )
        return [TextContent(type="text", text=consensus.model_dump_json(indent=2))]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _resolve_with_cache(
        self, query: str, exchanges: Optional[List[str]]
    ) -> Optional[str]:
        cache_key = build_cache_key(
            "resolved",
            self._tenant_id,
            query=query,
            exchanges=",".join(exchanges) if exchanges else None,
        )
        cached = await self.cache.get(cache_key)
        if cached:
            return str(cached)

        try:
            resolved = await self._resolve_market_internal(query, exchanges)
        except ValueError:
            return None

        await self.cache.set(cache_key, resolved.market_id)
        return resolved.market_id

    async def _resolve_market_internal(
        self, query: str, exchanges: Optional[List[str]]
    ) -> MarketResolved:
        if query is None or not str(query).strip():
            raise ValueError("Query cannot be empty")
        results = await self.catalog.search(query, exchanges=exchanges, limit=5)
        if not results:
            raise ValueError(f"No markets found for query: {query}")

        top_entry, top_score = results[0]
        alternatives = []
        needs_disambiguation = False

        if len(results) > 1:
            runner_score = results[1][1]
            if top_score < 2 * runner_score:
                needs_disambiguation = True
            for entry, score in results[1:4]:
                alternatives.append(
                    {
                        "market_id": entry.market_id,
                        "platform": entry.platform,
                        "score": score,
                        "title": entry.title,
                    }
                )

        notes = []
        if needs_disambiguation:
            notes.append("Ambiguous match – consider refining the query.")
        if alternatives:
            notes.append("Alternatives available on other platforms.")

        return MarketResolved(
            market_id=top_entry.market_id,
            exchange_id=top_entry.exchange_id,
            title=top_entry.title,
            platform=top_entry.platform,
            outcome_type=top_entry.outcome_type,
            outcomes=top_entry.outcomes,
            status=top_entry.status,
            close_date=top_entry.close_date,
            score=top_score,
            required_params=["period_id"],
            notes=notes,
            needs_disambiguation=needs_disambiguation,
            alternatives=alternatives,
            quality_score=top_entry.quality_score,
        )

    async def _fetch_market_prices(self, market_id: str) -> MarketPrices:
        cache_key = build_cache_key("prices", self._tenant_id, market_id=market_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return self._load_model_from_cache(MarketPrices, cached)

        entry = await self.catalog.get(market_id)
        if not entry:
            raise ValueError(f"Market not found: {market_id}")

        # Use activity/current endpoint per API spec for latest prices
        payload = await self.client.get(
            f"/v1/activity/{entry.exchange_id}/{entry.api_market_id}/current",
            params={},
        )

        trade = payload.get("trade") or {}
        quote = payload.get("quote") or {}

        price_value = trade.get("price")
        ask = quote.get("ask") if isinstance(quote, dict) else None
        bid = quote.get("bid") if isinstance(quote, dict) else None
        if price_value is None:
            if isinstance(ask, (int, float)) and isinstance(bid, (int, float)):
                price_value = (ask + bid) / 2
            elif isinstance(ask, (int, float)):
                price_value = ask
            elif isinstance(bid, (int, float)):
                price_value = bid

        volume = trade.get("quantity")
        if volume is None and isinstance(quote, dict):
            ask_volume = quote.get("ask_volume")
            bid_volume = quote.get("bid_volume")
            if isinstance(ask_volume, (int, float)) and isinstance(bid_volume, (int, float)):
                volume = max(ask_volume, bid_volume)
            else:
                volume = ask_volume or bid_volume

        timestamp = (
            parse_iso_datetime(trade.get("timestamp"))
            or parse_iso_datetime(quote.get("entry_time"))
            or parse_iso_datetime(quote.get("recv_time"))
            or datetime.now()
        )

        base_outcomes = entry.outcomes or [
            OutcomeInfo(
                outcome_id=f"{market_id}:primary",
                outcome_name=entry.title,
                probability=None,
                price=None,
                volume_24h=None,
                additional_properties={},
            )
        ]

        outcomes: List[OutcomeInfo] = []
        for base in base_outcomes:
            additional = dict(base.additional_properties)
            if trade:
                additional.update({
                    "latest_trade_price": trade.get("price"),
                    "latest_trade_quantity": trade.get("quantity"),
                    "latest_trade_timestamp": trade.get("timestamp"),
                })
            if quote:
                additional.update({
                    "latest_quote_ask": quote.get("ask"),
                    "latest_quote_bid": quote.get("bid"),
                    "latest_quote_ask_volume": quote.get("ask_volume"),
                    "latest_quote_bid_volume": quote.get("bid_volume"),
                    "latest_quote_timestamp": quote.get("entry_time") or quote.get("recv_time"),
                })

            probability = base.probability
            if probability is None and isinstance(price_value, (int, float)) and 0.0 <= price_value <= 1.0:
                probability = price_value

            outcomes.append(
                OutcomeInfo(
                    outcome_id=base.outcome_id,
                    outcome_name=base.outcome_name,
                    probability=probability,
                    price=price_value if price_value is not None else base.price,
                    volume_24h=volume if isinstance(volume, (int, float)) else base.volume_24h,
                    additional_properties=additional,
                )
            )

        prices = MarketPrices(
            market_id=market_id,
            outcomes=outcomes,
            last_updated=timestamp,
            notes=["Activity endpoint: latest trade/quote applied"],
            quality_score=entry.quality_score,
        )
        await self.cache.set(cache_key, prices.model_dump_json())
        return prices

    async def _fetch_market_history(
        self,
        market_id: str,
        period_id: str,
        time_start: Optional[str],
        time_end: Optional[str],
        limit: Optional[int],
    ) -> MarketHistory:
        entry = await self.catalog.get(market_id)
        if not entry:
            raise ValueError(f"Market not found: {market_id}")

        cache_key = build_cache_key(
            "history",
            self._tenant_id,
            market_id=market_id,
            period_id=period_id,
            time_start=time_start,
            time_end=time_end,
            limit=limit,
        )
        cached = await self.cache.get(cache_key)
        if cached:
            return self._load_model_from_cache(MarketHistory, cached)

        params = {
            "period_id": period_id,
        }
        if time_start:
            params["time_start"] = time_start
        if time_end:
            params["time_end"] = time_end
        if limit:
            params["limit"] = limit

        payload = await self.client.get(
            f"/v1/ohlcv/{entry.exchange_id}/{entry.api_market_id}/history",
            params=params,
        )
        outcome_lookup = {o.outcome_name: o for o in entry.outcomes}
        default_outcome = entry.outcomes[0] if entry.outcomes else None
        records: List[OHLCVRecord] = []

        existing_slugs: set[str] = set()
        raw_records = payload if isinstance(payload, list) else payload.get("data") or payload.get("results") or []
        for index, record_raw in enumerate(raw_records):
            outcome_name = record_raw.get("outcome")
            base = outcome_lookup.get(outcome_name) if outcome_name else default_outcome
            slug = create_outcome_slug(outcome_name, index, existing_slugs)
            existing_slugs.add(slug)

            additional = {
                key: value
                for key, value in record_raw.items()
                if key
                not in {
                    "time_period_start",
                    "time_period_end",
                    "time_open",
                    "time_close",
                    "price_open",
                    "price_high",
                    "price_low",
                    "price_close",
                    "volume_traded",
                    "outcome",
                }
            }

            records.append(
                OHLCVRecord(
                    timestamp=parse_iso_datetime(record_raw.get("time_period_start")),
                    outcome_id=base.outcome_id if base else f"{market_id}:{slug}",
                    open=record_raw.get("price_open"),
                    high=record_raw.get("price_high"),
                    low=record_raw.get("price_low"),
                    close=record_raw.get("price_close"),
                    volume=record_raw.get("volume_traded"),
                    additional_properties=additional,
                )
            )

        history = MarketHistory(
            market_id=market_id,
            period_id=period_id,
            data=records,
            last_updated=datetime.now(),
            notes=[f"{len(records)} records returned"],
        )
        await self.cache.set(cache_key, history.model_dump_json())
        return history

    def _tool_notes(self, name: str) -> str:
        return {
            "resolve_market": "Call before requesting prices or history to get a canonical market_id.",
            "get_consensus_probability": "Provide market_ids for the same event across platforms.",
            "get_market_prices_smart": "Convenience wrapper; resolves ID automatically.",
            "get_market_history_smart": "Convenience wrapper; resolves ID automatically.",
        }.get(name, "")

    def _tool_examples(self, name: str) -> List[str]:
        return {
            "resolve_market": ['{"query": "Fed rate cuts March 2025"}'],
            "get_consensus_probability": [
                '{"market_ids": ["pm:kalshi:fed-cut-2025", "pm:polymarket:fed-cut-2025"]}'
            ],
        }.get(name, [])

    def _error_text(self, tool_name: str, message: str, retriable: bool = False) -> TextContent:
        error = ErrorEnvelope(
            code="TOOL_ERROR",
            message=message,
            retriable=retriable,
            status=None,
            source=tool_name,
        )
        return TextContent(type="text", text=error.model_dump_json(indent=2))

    def _load_model_from_cache(self, model_cls: Type[ModelT], payload: str) -> ModelT:
        """Load a Pydantic model from cached JSON, supporting both v1/v2."""
        try:
            return model_cls.model_validate_json(payload)  # type: ignore[attr-defined]
        except AttributeError:
            return model_cls.parse_raw(payload)  # type: ignore[call-arg]


# Singleton helper ----------------------------------------------------------- #
_SERVER_INSTANCE: Optional[FinFeedPredictionMarketsServer] = None


def get_finfeed_prediction_server() -> Optional[FinFeedPredictionMarketsServer]:
    """Return a singleton instance of the prediction markets server."""
    global _SERVER_INSTANCE  # pylint: disable=global-statement

    if not all([
        FINFEED_BASE_URL,
        FINFEED_API_KEY,
        FINFEED_JWT_PRIVATE_KEY,
        FINFEED_JWT_KID,
    ]):
        return None

    if _SERVER_INSTANCE is None:
        _SERVER_INSTANCE = FinFeedPredictionMarketsServer()

    return _SERVER_INSTANCE


__all__ = ["FinFeedPredictionMarketsServer", "get_finfeed_prediction_server"]
