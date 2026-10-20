"""
Quote retrieval logic for Polymarket service.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Set

from .utils import extract_token_ids, utc_now_iso

DETAIL_FETCH_CONCURRENCY = 4


async def _resolve_tokens_for_slug(service, slug: str) -> Set[str]:
    tokens: Set[str] = set()
    detail = await service.peek_market_detail(slug)
    if not detail:
        detail = await service.get_market_detail(slug)
    if not detail:
        detail = await service.get_market_detail(slug, refresh=True)

    if detail:
        summary_tokens = detail.get("summary", {}).get("token_ids") or []
        for token in summary_tokens:
            if isinstance(token, str):
                normalized = token.strip()
                if normalized:
                    tokens.add(normalized)
        if not summary_tokens:
            market_payload = detail.get("market")
            if isinstance(market_payload, dict):
                tokens.update(extract_token_ids(market_payload.get("clobTokenIds")))

    return tokens


async def get_quotes(service, params: Dict[str, Any]) -> Dict[str, Any]:
    token_ids: Set[str] = set()
    raw_tokens = params.get("token_ids") or []
    if isinstance(raw_tokens, list):
        token_ids.update(str(item).strip() for item in raw_tokens if str(item).strip())

    market_slugs = params.get("market_slugs") or []
    unique_slugs: List[str] = []
    for slug in market_slugs:
        slug_str = str(slug).strip()
        if slug_str and slug_str not in unique_slugs:
            unique_slugs.append(slug_str)

    if unique_slugs:
        semaphore = asyncio.Semaphore(DETAIL_FETCH_CONCURRENCY)

        async def _bounded_resolve(slug: str) -> Set[str]:
            async with semaphore:
                return await _resolve_tokens_for_slug(service, slug)

        slug_results = await asyncio.gather(*(_bounded_resolve(slug) for slug in unique_slugs), return_exceptions=False)
        for slug_tokens in slug_results:
            token_ids.update(slug_tokens)

    if not token_ids:
        raise ValueError("At least one token_id or market_slug is required.")

    sides = params.get("sides") or ["BUY", "SELL"]
    sides = [side for side in sides if side in {"BUY", "SELL"}]
    if not sides:
        raise ValueError("sides must include BUY and/or SELL.")

    cache_key = service.scoped_cache_key("quotes", tuple(sorted(token_ids)), tuple(sorted(sides)))
    cached = await service.quote_cache.get(cache_key)
    if cached is not None and not params.get("refresh", False):
        cached["cache_hit"] = True
        return cached

    payload = [{"token_id": token, "side": side} for token in sorted(token_ids) for side in sides]
    response = await service.client.post_clob("/prices", json_body=payload)
    quotes = response.json()

    normalized = {}
    for token in sorted(token_ids):
        entry = quotes.get(token, {})
        normalized[token] = {side: entry.get(side) for side in sides}

    result = {
        "quotes": normalized,
        "requested_sides": sides,
        "requested_tokens": sorted(token_ids),
        "timestamp": utc_now_iso(),
        "fields_seen": sorted({side for entry in quotes.values() for side in entry.keys()}),
        "cache_hit": False,
    }

    await service.quote_cache.set(cache_key, result)
    return result
