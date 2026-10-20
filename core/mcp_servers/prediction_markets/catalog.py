"""
Market catalog management for the FinFeed Prediction Markets MCP server.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .http_client import FinFeedHTTPClient
from .schemas import MarketCatalogEntry, OutcomeInfo
from .utils import create_outcome_slug, parse_iso_datetime

logger = logging.getLogger(__name__)


class MarketCatalog:
    """In-memory catalog of prediction markets with fuzzy search support."""

    def __init__(self, client: FinFeedHTTPClient) -> None:
        self.client = client
        self._markets: Dict[str, MarketCatalogEntry] = {}
        self._search_index: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()
        self._last_refresh: Dict[str, datetime] = {}  # Track per-exchange refresh times
        self._refresh_ttl = 300  # 5 minutes staleness threshold

    async def refresh(
        self,
        exchanges: Optional[List[str]] = None,
        *,
        limit: int = 100,
        max_pages: Optional[int] = None,
        page_start: int = 1,
    ) -> None:
        """
        Rebuild the catalog from the FinFeed API.

        Args:
            exchanges: Optional list of exchange IDs to refresh. If omitted,
                all exchanges returned by list_exchanges are refreshed.
            limit: Page size per request (1-1000 per API docs).
            max_pages: Optional cap on number of pages to fetch per exchange.
            page_start: Starting page number (1-based).
        """
        async with self._lock:
            exchange_ids = exchanges

            if not exchange_ids:
                data = await self.client.get("/v1/exchanges")
                if isinstance(data, dict) and "exchanges" in data:
                    exchanges = data["exchanges"]
                elif isinstance(data, list):
                    exchanges = data
                else:
                    exchanges = []

                exchange_ids = [
                    entry.get("exchange_id")
                    for entry in exchanges
                    if isinstance(entry, dict) and entry.get("exchange_id")
                ]

            self._markets.clear()

            for exchange_id in exchange_ids or []:
                page = max(page_start, 1)
                pages_fetched = 0

                while True:
                    try:
                        payload = await self.client.get(
                            f"/v1/markets/{exchange_id}/history",
                            params={
                                "exchange_id": exchange_id,
                                "limit": limit,
                                "page": page,
                            },
                        )
                    except Exception as exc:
                        logger.error("Failed to fetch markets for %s (page %s): %s", exchange_id, page, exc)
                        break

                    markets_data = payload if isinstance(payload, list) else payload.get("markets", [])
                    if not markets_data:
                        break

                    for market_raw in markets_data:
                        try:
                            entry = self._build_entry(exchange_id, market_raw)
                        except Exception as exc:  # pylint: disable=broad-except
                            logger.warning("Skipping market on %s due to error: %s", exchange_id, exc)
                            continue
                        self._markets[entry.market_id] = entry

                    pages_fetched += 1
                    if limit and len(markets_data) < limit:
                        break
                    if max_pages is not None and pages_fetched >= max_pages:
                        break

                    page += 1

            self._rebuild_search_index()

    def _build_entry(self, exchange_id: str, raw: Dict) -> MarketCatalogEntry:
        """Create a MarketCatalogEntry from raw FinFeed payload."""
        api_market_id = raw.get("market_id") or raw.get("id") or raw.get("marketId")
        if not api_market_id:
            raise ValueError("Missing market identifier in payload")

        market_id = f"pm:{exchange_id}:{api_market_id}"

        outcomes: List[OutcomeInfo] = []
        existing_slugs: set[str] = set()

        for index, outcome_raw in enumerate(raw.get("outcomes", [])):
            outcome_name = (
                outcome_raw.get("name")
                or outcome_raw.get("label")
                or outcome_raw.get("title")
            )
            slug = create_outcome_slug(outcome_name, index, existing_slugs)
            existing_slugs.add(slug)

            outcomes.append(
                OutcomeInfo(
                    outcome_id=f"{market_id}:{slug}",
                    outcome_name=outcome_name or f"Outcome {index}",
                    probability=outcome_raw.get("probability"),
                    price=outcome_raw.get("price"),
                    volume_24h=outcome_raw.get("volume_24h") or outcome_raw.get("volume"),
                    additional_properties={
                        key: value
                        for key, value in outcome_raw.items()
                        if key
                        not in {
                            "name",
                            "label",
                            "title",
                            "probability",
                            "price",
                            "volume_24h",
                            "volume",
                        }
                    },
                )
            )

        if not outcomes:
            fallback_name = raw.get("outcome_name") or raw.get("title") or f"Outcome 0"
            slug = create_outcome_slug(fallback_name, 0, existing_slugs)
            existing_slugs.add(slug)
            price = raw.get("price")
            probability = raw.get("probability")
            if probability is None and isinstance(price, (int, float)):
                probability = price if 0.0 <= price <= 1.0 else None
            volume = raw.get("volume_24h") or raw.get("volume_traded") or raw.get("quantity")
            outcomes.append(
                OutcomeInfo(
                    outcome_id=f"{market_id}:{slug}",
                    outcome_name=fallback_name,
                    probability=probability,
                    price=price,
                    volume_24h=volume,
                    additional_properties={
                        key: value
                        for key, value in raw.items()
                        if key
                        not in {
                            "market_id",
                            "id",
                            "marketId",
                            "title",
                            "question",
                            "category",
                            "tag",
                            "status",
                            "close_date",
                            "endDate",
                            "outcome_type",
                            "outcomes",
                            "liquidity",
                            "volume_24h",
                            "volume",
                            "price",
                            "probability",
                            "volume_traded",
                            "quantity",
                            "outcome_name",
                        }
                    },
                )
            )

        close_date = parse_iso_datetime(raw.get("close_date") or raw.get("endDate"))

        return MarketCatalogEntry(
            market_id=market_id,
            exchange_id=exchange_id,
            api_market_id=str(api_market_id),
            title=raw.get("title") or raw.get("question") or "Untitled Market",
            platform=exchange_id,
            category=raw.get("category") or raw.get("tag"),
            status=raw.get("status", "active"),
            close_date=close_date,
            outcome_type=self._infer_outcome_type(outcomes, raw),
            outcomes=outcomes,
            liquidity=raw.get("liquidity"),
            volume_24h=raw.get("volume_24h") or raw.get("volume"),
            last_updated=datetime.now(),
            additional_properties={
                key: value
                for key, value in raw.items()
                if key
                not in {
                    "market_id",
                    "id",
                    "marketId",
                    "title",
                    "question",
                    "category",
                    "tag",
                    "status",
                    "close_date",
                    "endDate",
                    "outcome_type",
                    "outcomes",
                    "liquidity",
                    "volume_24h",
                    "volume",
                }
            },
            quality_score=self._calculate_quality_score(
                exchange_id=exchange_id,
                volume=raw.get("volume_24h") or raw.get("volume"),
                liquidity=raw.get("liquidity") or raw.get("bid_ask_spread"),
                close_date=close_date,
            ),
        )

    @staticmethod
    def _infer_outcome_type(outcomes: List[OutcomeInfo], raw: Dict) -> str:
        """Infer the outcome type if the payload omits it."""
        if raw.get("outcome_type"):
            return raw["outcome_type"]

        if len(outcomes) == 2:
            names = {outcome.outcome_name.lower() for outcome in outcomes}
            if names <= {"yes", "no", "true", "false", "1", "0"}:
                return "binary"

        return "categorical" if len(outcomes) > 2 else "binary"

    def _rebuild_search_index(self) -> None:
        """Rebuild inverted index for simple token-based searches."""
        self._search_index.clear()
        for market_id, entry in self._markets.items():
            tokens = entry.title.lower().split()
            if entry.category:
                tokens.extend(entry.category.lower().split())
            for token in set(tokens):
                self._search_index.setdefault(token, []).append(market_id)

    async def search(
        self,
        query: str,
        exchanges: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Tuple[MarketCatalogEntry, float]]:
        """
        Perform a fuzzy search across the catalog.

        Returns:
            List of (MarketCatalogEntry, score) sorted by relevance.
        """
        if not query.strip():
            return []

        query_tokens = set(query.lower().split())
        candidates: Dict[str, int] = {}

        async with self._lock:
            for token in query_tokens:
                for market_id in self._search_index.get(token, []):
                    entry = self._markets.get(market_id)
                    if entry is None:
                        continue
                    if exchanges and entry.exchange_id not in exchanges:
                        continue
                    candidates[market_id] = candidates.get(market_id, 0) + 1

            results: List[Tuple[MarketCatalogEntry, float]] = []
            for market_id, matches in candidates.items():
                entry = self._markets[market_id]
                score = min(0.8, matches / len(query_tokens))

                if entry.volume_24h and entry.volume_24h > 0:
                    volume_boost = min(0.2, 0.2 * (math.log10(entry.volume_24h) / 5))
                    score += volume_boost

                results.append((entry, min(1.0, score)))

            results.sort(key=lambda item: item[1], reverse=True)
            return results[:limit]

    async def get(self, market_id: str) -> Optional[MarketCatalogEntry]:
        """Retrieve a catalog entry by its canonical market ID."""
        async with self._lock:
            return self._markets.get(market_id)

    async def list_markets(
        self,
        exchanges: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 20,
        page: int = 0,
    ) -> List[MarketCatalogEntry]:
        """List markets with optional filters and pagination."""
        async with self._lock:
            markets = list(self._markets.values())

            if exchanges:
                markets = [entry for entry in markets if entry.exchange_id in exchanges]
            if status:
                markets = [entry for entry in markets if entry.status == status]

            start = page * limit
            end = start + limit
            return markets[start:end]

    def _calculate_quality_score(
        self,
        exchange_id: str,
        volume: Optional[float],
        liquidity: Optional[float],
        close_date: Optional[datetime],
    ) -> float:
        """
        Compute a simple quality score (0-100) for a market based on heuristics.

        Heuristic weights derived from design blockers document.
        """
        score = 0.0

        # Volume weight (40%)
        if volume:
            if volume > 5_000_000:
                score += 40
            elif volume > 1_000_000:
                score += 30
            elif volume > 100_000:
                score += 15
            elif volume > 10_000:
                score += 8
            else:
                score += 5

        # Liquidity / bid-ask spread weight (30%)
        if liquidity is not None:
            try:
                spread = float(liquidity)
            except (TypeError, ValueError):
                spread = None
            if spread is not None:
                if spread < 0.02:
                    score += 30
                elif spread < 0.05:
                    score += 20
                elif spread < 0.10:
                    score += 10
                else:
                    score += 5

        # Platform credibility (20%)
        platform_weights = {
            "kalshi": 20,
            "polymarket": 15,
            "predictit": 10,
        }
        score += platform_weights.get(exchange_id.lower(), 8)

        # Time to resolution (10%)
        if close_date:
            days_remaining = (close_date - datetime.now()).days
            if days_remaining < 0:
                score += 2
            elif days_remaining < 90:
                score += 10
            elif days_remaining < 180:
                score += 6
            else:
                score += 4

        return min(score, 100.0)
