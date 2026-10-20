"""
Polymarket service facade delegating to operation modules.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from agents.mcp.server import MCPTool

from .cache import TTLCache
from .http_client import PolymarketHTTPClient, PolymarketHTTPError
from .tag_ops import discover_tags as _discover_tags
from .market_ops import (
    get_markets_by_tag as _get_markets_by_tag,
    discover_market_fields as _discover_market_fields,
    DEFAULT_CATEGORY_WHITELIST,
    summarize_market_payload,
)
from .quote_ops import get_quotes as _get_quotes
from .history_ops import get_price_history as _get_price_history
from .search_ops import search_markets as _search_markets
from .utils import ensure_list, prune_nones, utc_now_iso


logger = logging.getLogger(__name__)

class PolymarketService:
    """Encapsulates shared state and delegates to operation modules."""

    def __init__(
        self,
        gamma_base_url: Optional[str] = None,
        clob_base_url: Optional[str] = None,
        *,
        default_cache_ttl: int = 180,
    ) -> None:
        self.gamma_base_url = gamma_base_url or os.getenv(
            "POLYMARKET_GAMMA_BASE_URL", "https://gamma-api.polymarket.com"
        )
        self.clob_base_url = clob_base_url or os.getenv(
            "POLYMARKET_CLOB_BASE_URL", "https://clob.polymarket.com"
        )

        timeout = _safe_float(os.getenv("POLYMARKET_HTTP_TIMEOUT_SECONDS", "12.0"), 12.0)
        retries = _safe_int(os.getenv("POLYMARKET_HTTP_MAX_RETRIES", "2"), 2)
        backoff = _safe_float(os.getenv("POLYMARKET_HTTP_BACKOFF_SECONDS", "0.75"), 0.75)

        self.client = PolymarketHTTPClient(
            gamma_base_url=self.gamma_base_url,
            clob_base_url=self.clob_base_url,
            timeout_seconds=timeout,
            max_retries=retries,
            backoff_seconds=backoff,
        )

        ttl = _safe_int(os.getenv("POLYMARKET_CACHE_TTL_SECONDS", str(default_cache_ttl)), default_cache_ttl)
        self.tag_cache = TTLCache(ttl)
        self.market_cache = TTLCache(ttl)
        self.quote_cache = TTLCache(ttl // 2 if ttl > 30 else ttl)
        detail_ttl = ttl if ttl <= 30 else int(ttl * 1.5)
        self.search_cache = TTLCache(ttl // 2 if ttl > 30 else ttl)
        self.market_detail_cache = TTLCache(detail_ttl)

        self._tenant_id: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Context & caching helpers
    # ------------------------------------------------------------------ #

    def set_tenant(self, tenant_id: str) -> None:
        """Namespace caches per tenant."""
        self._tenant_id = tenant_id or ""

    def scoped_cache_key(self, prefix: str, *parts: Any) -> str:
        tenant = self._tenant_id or "global"
        serialized = "::".join(json.dumps(part, sort_keys=True, default=str) for part in parts)
        return f"{tenant}::{prefix}::{serialized}"

    async def close(self) -> None:
        await self.client.close()
        await self.tag_cache.clear()
        await self.market_cache.clear()
        await self.quote_cache.clear()
        await self.search_cache.clear()
        await self.market_detail_cache.clear()
        self._tenant_id = None

    async def cache_market_detail(
        self,
        slug: str,
        *,
        market: Optional[Dict[str, Any]] = None,
        summary: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Persist a normalized market detail payload for re-use across tools."""

        slug_norm = str(slug or "").strip()
        if not slug_norm:
            return None

        market_payload = dict(market) if isinstance(market, dict) else None
        summary_payload = dict(summary) if isinstance(summary, dict) else None
        metrics_payload = dict(metrics) if isinstance(metrics, dict) else None

        if market_payload is not None and (summary_payload is None or metrics_payload is None):
            summary_payload, metrics_payload = summarize_market_payload(market_payload)

        if summary_payload is None and metrics_payload is None and market_payload is None:
            return None

        detail_payload = prune_nones(
            {
                "slug": slug_norm,
                "summary": summary_payload,
                "metrics": metrics_payload,
                "market": market_payload,
                "source": source,
                "timestamp": utc_now_iso(),
            }
        )

        await self.market_detail_cache.set(
            self.scoped_cache_key("market_detail", slug_norm),
            detail_payload,
        )
        return detail_payload

    async def peek_market_detail(self, slug: str) -> Optional[Dict[str, Any]]:
        slug_norm = str(slug or "").strip()
        if not slug_norm:
            return None
        return await self.market_detail_cache.get(self.scoped_cache_key("market_detail", slug_norm))

    async def get_market_detail(self, slug: str, *, refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Return cached market detail (summary+metrics+raw) or fetch and store it."""

        slug_norm = str(slug or "").strip()
        if not slug_norm:
            return None

        cache_key = self.scoped_cache_key("market_detail", slug_norm)
        if not refresh:
            cached = await self.market_detail_cache.get(cache_key)
            if cached is not None:
                return cached

        market_payload = await self._fetch_market_payload(slug_norm)
        if not isinstance(market_payload, dict):
            return None

        return await self.cache_market_detail(
            slug_norm,
            market=market_payload,
            source="gamma_single",
        )

    async def _fetch_market_payload(self, slug: str) -> Optional[Dict[str, Any]]:
        """Retrieve a market payload using the most reliable available endpoint."""

        if hasattr(self.client, "get_market"):
            try:
                payload = await self.client.get_market(slug)  # type: ignore[attr-defined]
                if isinstance(payload, dict):
                    return payload
            except PolymarketHTTPError as exc:
                if exc.status_code == 404:
                    return None
                logger.debug("Polymarket get_market failed for %s: %s", slug, exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Polymarket get_market unexpected failure for %s: %s", slug, exc)

        try:
            response = await self.client.get_gamma("/markets", params={"slug": [slug], "limit": 1})
            payload = response.json()
            if isinstance(payload, list) and payload:
                candidate = payload[0]
                if isinstance(candidate, dict):
                    return candidate
            if isinstance(payload, dict):
                markets_field = payload.get("markets")
                if isinstance(markets_field, list) and markets_field:
                    candidate = markets_field[0]
                    if isinstance(candidate, dict):
                        return candidate
                if payload.get("slug") == slug:
                    return payload
        except PolymarketHTTPError as exc:
            if exc.status_code == 404:
                return None
            logger.debug("Polymarket /markets slug lookup failed for %s: %s", slug, exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Polymarket /markets unexpected failure for %s: %s", slug, exc)

        try:
            response = await self.client.get_gamma(f"/markets/slug/{slug}")
            payload = response.json()
            if isinstance(payload, dict):
                return payload
        except PolymarketHTTPError as exc:
            if exc.status_code == 404:
                return None
            logger.debug("Polymarket /markets/slug lookup failed for %s: %s", slug, exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Polymarket /markets/slug unexpected failure for %s: %s", slug, exc)

        return None

    # ------------------------------------------------------------------ #
    # Tool definitions
    # ------------------------------------------------------------------ #

    def build_tools(self) -> List[MCPTool]:
        return [
            MCPTool(
                name="discover_polymarket_tags",
                description="Discover tag metadata by slug, optionally including related tags.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["active", "closed", "all"],
                            "default": "active",
                        },
                        "include_related": {"type": "boolean", "default": False},
                        "omit_empty_related": {"type": "boolean", "default": True},
                        "include_template": {"type": "boolean", "default": False},
                        "refresh": {"type": "boolean", "default": False},
                    },
                    "required": ["slug"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polymarket_markets_by_tag",
                description="List Polymarket markets for a tag id with agent-friendly filtering and summaries.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tag_id": {"type": "integer"},
                        "closed": {"type": "boolean", "default": False},
                        "limit_per_page": {"type": "integer", "minimum": 1, "maximum": 200, "default": 100},
                        "max_pages": {"type": "integer", "minimum": 1, "maximum": 40, "default": 5},
                        "order": {"type": "string"},
                        "ascending": {"type": "boolean"},
                        "include_tag_details": {"type": "boolean", "default": False},
                        "include_related_tag_markets": {"type": "boolean", "default": False},
                        "category_whitelist": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Restrict markets to these categories (case-insensitive, substring match).",
                            "default": list(DEFAULT_CATEGORY_WHITELIST),
                        },
                        "search_text": {
                            "type": "string",
                            "description": "Case-insensitive keyword filter applied to slug, question, and outcomes.",
                        },
                        "min_volume_24hr": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Minimum 24h volume in USD required to keep a market. Defaults to 2,500 unless include_thin_markets is true.",
                        },
                        "min_liquidity_usd": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Minimum liquidity in USD to keep a market in the primary result set.",
                        },
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 120,
                            "default": 40,
                            "description": "Maximum markets to return after filtering and scoring.",
                        },
                        "include_thin_markets": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include thin/low volume markets instead of applying the default min volume filter.",
                        },
                        "refresh": {"type": "boolean", "default": False},
                    },
                    "required": ["tag_id"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="discover_polymarket_market_fields",
                description="Inspect market payloads dynamically by slug or tag sample.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "market_slug": {"type": "string"},
                        "tag_id": {"type": "integer"},
                        "closed": {"type": "boolean", "default": False},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="search_polymarket_markets",
                description="Search Polymarket markets by keyword and return candidate slugs and metadata.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "description": "Maximum markets to return after filtering. Defaults to 10 when omitted.",
                        },
                        "limit_per_type": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 10,
                            "description": "Deprecated alias for limit; retained for backward compatibility.",
                        },
                        "include_closed": {"type": "boolean", "default": False},
                        "include_thin_markets": {
                            "type": "boolean",
                            "default": True,
                            "description": "If false, thin/low-volume markets are filtered from the final results.",
                        },
                        "category": {
                            "type": "string",
                            "description": "Primary Polymarket tag/category slug to focus search (e.g., 'crypto').",
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional tag/category slugs considered during public search and fallback harvest.",
                        },
                        "tag_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Explicit set of tag slugs for fallback harvesting (defaults to a curated list when omitted).",
                        },
                        "events_status": {
                            "type": "string",
                            "enum": ["active", "closed", "all"],
                            "description": "Optional event status filter applied to public search queries.",
                        },
                        "sort": {
                            "type": "string",
                            "description": "Optional sort field for the public search endpoint (e.g., 'volume').",
                        },
                        "ascending": {
                            "type": "boolean",
                            "description": "When sort is provided, choose ascending instead of descending order.",
                        },
                        "search_tags": {
                            "type": "boolean",
                            "default": True,
                            "description": "When false, disable tag matching within the public search endpoint.",
                        },
                        "search_profiles": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include profile results in the public search payload (typically unnecessary).",
                        },
                        "refresh": {"type": "boolean", "default": False},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polymarket_quotes",
                description="Fetch live Polymarket quotes for token ids or market slugs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "token_ids": {"type": "array", "items": {"type": "string"}},
                        "market_slugs": {"type": "array", "items": {"type": "string"}},
                        "sides": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["BUY", "SELL"]},
                            "default": ["BUY", "SELL"],
                        },
                        "refresh": {"type": "boolean", "default": False},
                    },
                    "additionalProperties": False,
                },
            ),
            MCPTool(
                name="get_polymarket_price_history",
                description="Retrieve price history for a token id via the CLOB API. Provide either token_id OR market_slug (optionally with outcome/outcome_index).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "token_id": {"type": "string", "description": "Direct token ID (preferred if known)"},
                        "market_slug": {"type": "string", "description": "Market slug to resolve token ID from"},
                        "outcome": {"type": "string", "description": "Outcome label when using market_slug"},
                        "outcome_index": {"type": "integer", "minimum": 0, "description": "Outcome index when using market_slug"},
                        "interval": {
                            "type": "string",
                            "enum": ["1m", "1h", "6h", "1d", "1w", "max"],
                            "description": "Time interval for history"
                        },
                        "start_ts": {"type": "number", "description": "Start Unix timestamp (mutually exclusive with interval)"},
                        "end_ts": {"type": "number", "description": "End Unix timestamp (mutually exclusive with interval)"},
                        "fidelity": {"type": "integer", "minimum": 1, "description": "Resolution in minutes"},
                    },
                    "additionalProperties": False,
                },
            ),
        ]

    # ------------------------------------------------------------------ #
    # Delegated operations
    # ------------------------------------------------------------------ #

    async def discover_tags(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return await _discover_tags(self, params)

    async def get_markets_by_tag(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return await _get_markets_by_tag(self, params)

    async def discover_market_fields(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return await _discover_market_fields(self, params)

    async def get_quotes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return await _get_quotes(self, params)

    async def get_price_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return await _get_price_history(self, params)

    async def search_markets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        refresh = bool(params.get("refresh", False))
        query_norm = str(params.get("query", "")).strip().lower()
        include_closed = bool(params.get("include_closed", False))
        include_thin = bool(params.get("include_thin_markets", True))

        limit_param = params.get("limit") or params.get("limit_per_type") or 10
        try:
            limit_value = int(limit_param)
        except (TypeError, ValueError):
            limit_value = 10
        limit_value = max(1, min(limit_value, 50))

        category_tokens: List[str] = []
        for raw in [params.get("category"), *ensure_list(params.get("categories"))]:
            token = _normalize_cache_token(raw)
            if token and token not in category_tokens:
                category_tokens.append(token)

        tag_tokens: List[str] = []
        for raw in ensure_list(params.get("tag_slugs")):
            token = _normalize_cache_token(raw)
            if token and token not in tag_tokens:
                tag_tokens.append(token)

        events_status_norm = _normalize_cache_token(params.get("events_status"))
        if events_status_norm not in {None, "active", "closed", "all"}:
            events_status_norm = None

        sort_field_norm = _normalize_cache_token(params.get("sort"))
        ascending_norm = bool(params.get("ascending")) if sort_field_norm else None
        search_tags_flag = bool(params.get("search_tags", True))
        search_profiles_flag = bool(params.get("search_profiles", False))

        cache_key = self.scoped_cache_key(
            "search",
            query_norm,
            include_closed,
            include_thin,
            limit_value,
            tuple(category_tokens) or None,
            tuple(tag_tokens) or None,
            events_status_norm,
            sort_field_norm,
            ascending_norm,
            search_tags_flag,
            search_profiles_flag,
        )

        if not refresh:
            cached = await self.search_cache.get(cache_key)
            if cached is not None:
                cached["cache_hit"] = True
                return cached

        result = await _search_markets(self, params)
        result["cache_hit"] = False
        await self.search_cache.set(cache_key, dict(result))
        return result


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _normalize_cache_token(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip().lower()
        return cleaned or None
    return None


def _safe_int(value: str, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: str, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
