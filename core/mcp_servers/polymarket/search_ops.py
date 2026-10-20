"""Search utilities for Polymarket MCP server.

This module now prefers the Gamma `public-search` endpoint to retrieve canonical
market slugs and then enriches the matches via `/markets`. When public search
does not return candidates (or fails), we fall back to the historical tag
harvest approach so existing workflows continue to function.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence

from .market_ops import DEFAULT_MIN_VOLUME_24H
from .utils import ensure_list, prune_nones, utc_now_iso

DEFAULT_TAG_SLUGS = (
    "crypto",
    "bitcoin",
    "finance",
    "world",
    "economy",
    "tech",
    "earnings",
    "politics",
)

MAX_PUBLIC_SEARCH_CANDIDATES = 48
MAX_MARKET_DETAIL_LOOKUP = 24
DETAIL_BATCH_MIN = 4
DETAIL_BATCH_MAX = 12
DETAIL_REFRESH_CONCURRENCY = 4
TAG_HARVEST_CONCURRENCY = 3

logger = logging.getLogger(__name__)


def _normalize_slug(value: Any) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    return None


def _normalize_text(value: Any) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    return None


def _collect_strings(source: Any) -> List[str]:
    results: List[str] = []
    for entry in ensure_list(source):
        if isinstance(entry, str):
            candidate = entry.strip()
            if candidate and candidate not in results:
                results.append(candidate)
        elif isinstance(entry, dict):
            for key in ("slug", "label", "title", "name"):
                value = entry.get(key)
                if isinstance(value, str):
                    candidate = value.strip()
                    if candidate and candidate not in results:
                        results.append(candidate)
    return results


def _build_candidate(slug: str, market: Dict[str, Any], event: Optional[Dict[str, Any]], rank: int) -> Dict[str, Any]:
    tags = _collect_strings(market.get("tags"))
    categories = _collect_strings(market.get("categories"))
    event_tags = _collect_strings(event.get("tags")) if event else []
    event_categories = _collect_strings(event.get("categories")) if event else []
    category = (
        _normalize_text(market.get("category"))
        or (categories[0] if categories else None)
        or (_normalize_text(event.get("category")) if event else None)
    )
    question = _normalize_text(market.get("question") or market.get("title"))
    title = _normalize_text(market.get("title")) or question or slug.replace("-", " ").title()

    return {
        "slug": slug,
        "title": title,
        "question": question,
        "tags": tags,
        "categories": categories,
        "category": category,
        "event_slug": _normalize_slug(event.get("slug")) if event else None,
        "event_title": _normalize_text(event.get("title") or event.get("name")) if event else None,
        "event_tags": event_tags,
        "event_categories": event_categories,
        "rank": rank,
        "raw_market": market,
        "raw_event": event,
    }


def _collect_public_search_candidates(payload: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _add_candidate(market: Dict[str, Any], event: Optional[Dict[str, Any]]) -> None:
        slug = _normalize_slug(market.get("slug") or market.get("marketSlug"))
        if not slug or slug in seen:
            return
        seen.add(slug)
        candidates.append(_build_candidate(slug, market, event, len(candidates)))

    for market in ensure_list(payload.get("markets")):
        if isinstance(market, dict):
            _add_candidate(market, None)
            if len(candidates) >= limit:
                return candidates

    for event in ensure_list(payload.get("events")):
        if not isinstance(event, dict):
            continue
        for market in ensure_list(event.get("markets")):
            if isinstance(market, dict):
                _add_candidate(market, event)
                if len(candidates) >= limit:
                    return candidates

    for series in ensure_list(payload.get("series")):
        if not isinstance(series, dict):
            continue
        for market in ensure_list(series.get("markets")):
            if isinstance(market, dict):
                _add_candidate(market, series)
                if len(candidates) >= limit:
                    return candidates

    return candidates


def _detail_batch_size(limit: int) -> int:
    return max(DETAIL_BATCH_MIN, min(DETAIL_BATCH_MAX, max(limit, DETAIL_BATCH_MIN)))


async def _batch_fetch_market_details(
    service,
    slugs: Sequence[str],
    stats: Dict[str, int],
) -> Dict[str, Dict[str, Any]]:
    unique_slugs = []
    for slug in slugs:
        normalized = _normalize_slug(slug)
        if normalized and normalized not in unique_slugs:
            unique_slugs.append(normalized)

    if not unique_slugs:
        return {}

    params = {"slug": unique_slugs[:MAX_MARKET_DETAIL_LOOKUP], "limit": len(unique_slugs[:MAX_MARKET_DETAIL_LOOKUP])}
    raw_payload = None
    try:
        response = await service.client.get_gamma("/markets", params=params)
        raw_payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Polymarket market batch lookup failed for %s: %s", unique_slugs, exc)

    markets: List[Dict[str, Any]] = []
    if isinstance(raw_payload, list):
        markets = [entry for entry in raw_payload if isinstance(entry, dict)]
    elif isinstance(raw_payload, dict):
        markets_field = raw_payload.get("markets")
        if isinstance(markets_field, list):
            markets = [entry for entry in markets_field if isinstance(entry, dict)]
        elif raw_payload.get("slug") in unique_slugs:
            markets = [raw_payload]

    stats["detail_batch_fetches"] = stats.get("detail_batch_fetches", 0) + 1
    stats["detail_batch_slug_lookups"] = stats.get("detail_batch_slug_lookups", 0) + len(unique_slugs)

    details: Dict[str, Dict[str, Any]] = {}
    for entry in markets:
        slug_value = _normalize_slug(entry.get("slug"))
        if not slug_value:
            continue
        cached_payload = await service.cache_market_detail(
            slug_value,
            market=entry,
            source="public_search_batch",
        )
        if cached_payload:
            details[slug_value] = cached_payload

    return details


async def _refresh_missing_details(
    service,
    slugs: Sequence[str],
    stats: Dict[str, int],
) -> Dict[str, Dict[str, Any]]:
    if not slugs:
        return {}

    semaphore = asyncio.Semaphore(DETAIL_REFRESH_CONCURRENCY)

    async def _fetch_single(slug: str) -> Optional[tuple[str, Dict[str, Any]]]:
        async with semaphore:
            detail = await service.get_market_detail(slug, refresh=True)
            if detail:
                return slug, detail
            logger.debug("Unable to resolve Polymarket detail for slug %s via refresh", slug)
            return None

    tasks = [_fetch_single(slug) for slug in slugs]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    mapping: Dict[str, Dict[str, Any]] = {}
    successes = 0
    for result in results:
        if result is None:
            continue
        slug, detail = result
        mapping[slug] = detail
        successes += 1

    if successes:
        stats["detail_single_fetches"] = stats.get("detail_single_fetches", 0) + successes

    return mapping


async def _resolve_detail_for_candidate(
    service,
    candidates: Sequence[Dict[str, Any]],
    index: int,
    detail_map: Dict[str, Dict[str, Any]],
    batch_size: int,
    stats: Dict[str, int],
) -> Optional[Dict[str, Any]]:
    slug = candidates[index]["slug"]
    if slug in detail_map:
        return detail_map[slug]

    cached = await service.peek_market_detail(slug)
    if cached:
        detail_map[slug] = cached
        stats["detail_cache_hits"] = stats.get("detail_cache_hits", 0) + 1
        return cached

    lookahead: List[str] = [slug]
    total = len(candidates)
    pointer = index + 1
    while pointer < total and len(lookahead) < batch_size:
        next_slug = candidates[pointer]["slug"]
        if next_slug in lookahead or next_slug in detail_map:
            pointer += 1
            continue
        cached_candidate = await service.peek_market_detail(next_slug)
        if cached_candidate:
            detail_map[next_slug] = cached_candidate
            stats["detail_cache_hits"] = stats.get("detail_cache_hits", 0) + 1
        else:
            lookahead.append(next_slug)
        pointer += 1

    fetched = await _batch_fetch_market_details(service, lookahead, stats)
    if fetched:
        detail_map.update(fetched)

    missing = [slug_value for slug_value in lookahead if slug_value not in detail_map]
    if missing:
        refreshed = await _refresh_missing_details(service, missing, stats)
        if refreshed:
            detail_map.update(refreshed)

    detail = detail_map.get(slug)
    if detail:
        return detail

    logger.debug("Unable to resolve Polymarket detail for slug %s after refresh attempts", slug)
    return None


def _merge_candidate_with_details(
    candidate: Dict[str, Any],
    detail_entry: Optional[Dict[str, Any]],
    include_thin: bool,
) -> Optional[Dict[str, Any]]:
    summary = dict(detail_entry.get("summary") or {}) if detail_entry else {}
    metrics = detail_entry.get("metrics") if detail_entry else {}

    tags_joined: List[str] = []
    for collection in (candidate.get("tags"), summary.get("tags"), candidate.get("event_tags")):
        for item in ensure_list(collection):
            if isinstance(item, str) and item not in tags_joined:
                tags_joined.append(item)

    categories_joined: List[str] = []
    for collection in (candidate.get("categories"), summary.get("categories"), candidate.get("event_categories")):
        for item in ensure_list(collection):
            if isinstance(item, str) and item not in categories_joined:
                categories_joined.append(item)

    match = prune_nones(
        {
            "slug": candidate["slug"],
            "title": summary.get("question") or candidate.get("title") or candidate["slug"],
            "question": summary.get("question") or candidate.get("question"),
            "event_slug": candidate.get("event_slug"),
            "event_title": candidate.get("event_title"),
            "category": summary.get("category") or candidate.get("category"),
            "categories": categories_joined or None,
            "tags": tags_joined or None,
            "best_bid": summary.get("best_bid"),
            "best_ask": summary.get("best_ask"),
            "mid_price": summary.get("mid_price"),
            "last_trade_price": summary.get("last_trade_price"),
            "spread_pct": summary.get("spread_pct"),
            "volume_24h": summary.get("volume_24h"),
            "volume_7d": summary.get("volume_7d"),
            "liquidity": summary.get("liquidity"),
            "score": summary.get("score"),
            "token_ids": summary.get("token_ids"),
            "outcome_token_map": summary.get("outcome_token_map"),
            "closed": summary.get("closed"),
            "accepting_orders": summary.get("accepting_orders"),
            "end_date": summary.get("end_date"),
            "source": "public_search",
            "detail_source": detail_entry.get("source") if detail_entry else None,
            "search_rank": candidate.get("rank"),
        }
    )

    if not include_thin:
        volume = summary.get("volume_24h")
        if volume is None and isinstance(metrics, dict):
            volume = metrics.get("volume_24h")
        if volume is None or volume < DEFAULT_MIN_VOLUME_24H:
            return None

    if not match.get("title"):
        match["title"] = candidate["slug"]

    return match


async def _search_via_public_search(
    service,
    query: str,
    limit: int,
    include_closed: bool,
    include_thin: bool,
    tag_filters: Sequence[str],
    events_status: Optional[str],
    sort_field: Optional[str],
    ascending: Optional[bool],
    search_tags_flag: bool,
    search_profiles_flag: bool,
    refresh_requested: bool,
) -> Dict[str, Any]:
    request_limit = max(limit, min(MAX_PUBLIC_SEARCH_CANDIDATES, limit * 3))
    events_tag = list(dict.fromkeys(tag_filters)) if tag_filters else None

    params = prune_nones(
        {
            "q": query,
            "limit_per_type": request_limit,
            "keep_closed_markets": 1 if include_closed else 0,
            "cache": not refresh_requested,
            "events_tag": events_tag,
            "events_status": events_status or None,
            "sort": sort_field or None,
            "ascending": ascending if sort_field else None,
            "search_tags": search_tags_flag,
            "search_profiles": search_profiles_flag,
            "optimized": True,
        }
    )

    try:
        response = await service.client.get_gamma("/public-search", params=params)
        payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Polymarket public-search failed for query '%s': %s", query, exc)
        return {"matches": [], "meta": {"error": str(exc)}}

    if not isinstance(payload, dict):
        return {"matches": [], "meta": {"error": f"unexpected_payload_type:{type(payload).__name__}"}}

    candidates = _collect_public_search_candidates(payload, request_limit)
    meta = {
        "public_search_candidates": len(candidates),
        "public_search_events": len([event for event in ensure_list(payload.get("events")) if isinstance(event, dict)]),
        "public_search_markets": len([market for market in ensure_list(payload.get("markets")) if isinstance(market, dict)]),
    }

    if not candidates:
        return {"matches": [], "meta": meta}

    matches: List[Dict[str, Any]] = []
    filtered_out = 0
    detail_map: Dict[str, Dict[str, Any]] = {}
    stats: Dict[str, int] = {}
    batch_size = _detail_batch_size(limit)

    for index, candidate in enumerate(candidates):
        detail_entry = await _resolve_detail_for_candidate(
            service,
            candidates,
            index,
            detail_map,
            batch_size,
            stats,
        )
        merged = _merge_candidate_with_details(candidate, detail_entry, include_thin)
        if merged is None:
            filtered_out += 1
            continue
        matches.append(merged)
        if len(matches) >= limit:
            break

    if matches:
        meta.update(
            {
                "detail_cache_hits": stats.get("detail_cache_hits", 0),
                "detail_batch_fetches": stats.get("detail_batch_fetches", 0),
                "detail_batch_slug_lookups": stats.get("detail_batch_slug_lookups", 0),
                "detail_single_fetches": stats.get("detail_single_fetches", 0),
                "filtered_out": filtered_out,
            }
        )
    else:
        meta["filtered_out"] = len(candidates)

    return {"matches": matches, "meta": meta}


async def _resolve_tag_id(service, slug: str) -> Optional[int]:
    try:
        discovery = await service.discover_tags({"slug": slug})
    except Exception:
        return None
    tag_payload = discovery.get("tag") or {}
    tag_id = tag_payload.get("id")
    try:
        return int(tag_id)
    except (TypeError, ValueError):
        return None


def _build_fallback_match(market_summary: Dict[str, Any], tag_slug: str, tag_id: int) -> Dict[str, Any]:
    tags = [tag for tag in ensure_list(market_summary.get("tags")) if isinstance(tag, str)]
    categories = [cat for cat in ensure_list(market_summary.get("categories")) if isinstance(cat, str)]

    enriched = dict(market_summary)
    enriched.setdefault("title", market_summary.get("question"))
    if tags:
        enriched["tags"] = tags
    if categories:
        enriched["categories"] = categories
    enriched["source"] = "tag_harvest"
    enriched["source_tag_slug"] = tag_slug
    enriched["source_tag_id"] = tag_id
    return prune_nones(enriched)


async def _search_via_tag_harvest(
    service,
    query: str,
    limit: int,
    include_closed: bool,
    include_thin: bool,
    tag_slugs: Sequence[str],
    refresh: bool,
) -> Dict[str, Any]:
    seen_slugs: set[str] = set()
    matches: List[Dict[str, Any]] = []
    used_tags: List[str] = []

    semaphore = asyncio.Semaphore(TAG_HARVEST_CONCURRENCY)

    async def _fetch_for_tag(slug: str) -> tuple[str, Optional[int], List[Dict[str, Any]]]:
        async with semaphore:
            tag_id = await _resolve_tag_id(service, slug)
            if tag_id is None:
                return slug, None, []
            try:
                request_kwargs = {
                    "tag_id": tag_id,
                    "closed": include_closed,
                    "search_text": query,
                    "max_results": limit,
                    "include_thin_markets": include_thin,
                    "limit_per_page": 50,
                    "max_pages": 3,
                    "include_tag_details": False,
                }
                payload = await service.get_markets_by_tag(request_kwargs)
                cache_hit = bool(payload.get("cache_hit"))
                needs_refresh = (refresh and cache_hit) or not payload.get("markets")
                if needs_refresh:
                    payload = await service.get_markets_by_tag({**request_kwargs, "refresh": True})
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Polymarket tag harvest failed for slug %s: %s", slug, exc)
                return slug, tag_id, []

            markets = [
                market
                for market in ensure_list(payload.get("markets"))
                if isinstance(market, dict)
            ]
            return slug, tag_id, markets

    fetch_tasks = [_fetch_for_tag(slug) for slug in tag_slugs]
    results = await asyncio.gather(*fetch_tasks, return_exceptions=False)
    result_map: Dict[str, tuple[int, List[Dict[str, Any]]]] = {
        slug: (tag_id, markets)
        for slug, tag_id, markets in results
        if tag_id is not None
    }

    for slug in tag_slugs:
        if slug not in result_map:
            continue
        tag_id, markets = result_map[slug]
        used_tags.append(slug)
        for market in markets:
            slug_value = _normalize_slug(market.get("slug"))
            if not slug_value or slug_value in seen_slugs:
                continue
            seen_slugs.add(slug_value)
            matches.append(_build_fallback_match(market, slug, tag_id))
            if len(matches) >= limit:
                break
        if len(matches) >= limit:
            break

    note = None
    if not matches:
        note = "No markets matched the query across the inspected tags."

    return {
        "matches": matches,
        "tag_slugs_used": used_tags,
        "note": note,
    }


def _normalize_filter_value(value: Any) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip().lower()
        return candidate or None
    return None


async def search_markets(service, params: Dict[str, Any]) -> Dict[str, Any]:
    query = str(params.get("query", "")).strip()
    if not query:
        raise ValueError("query is required and must be non-empty")

    limit_param = params.get("limit") or params.get("limit_per_type") or 10
    try:
        limit = int(limit_param)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))

    include_closed = bool(params.get("include_closed", False))
    include_thin = bool(params.get("include_thin_markets", True))
    refresh_requested = bool(params.get("refresh", False))

    category_primary = _normalize_filter_value(params.get("category"))
    categories_param = [
        value
        for value in (
            _normalize_filter_value(item)
            for item in ensure_list(params.get("categories"))
        )
        if value is not None
    ]

    tag_slugs_param = [
        value
        for value in (
            _normalize_filter_value(item)
            for item in ensure_list(params.get("tag_slugs"))
        )
        if value is not None
    ]

    category_filters: List[str] = []
    if category_primary:
        category_filters.append(category_primary)
    for value in categories_param:
        if value not in category_filters:
            category_filters.append(value)

    tag_filters_public: List[str] = []
    for value in category_filters + tag_slugs_param:
        if value not in tag_filters_public:
            tag_filters_public.append(value)

    fallback_tag_slugs: List[str] = []
    if category_filters:
        fallback_tag_slugs.extend(category_filters)
    if tag_slugs_param:
        for value in tag_slugs_param:
            if value not in fallback_tag_slugs:
                fallback_tag_slugs.append(value)
    if not fallback_tag_slugs:
        fallback_tag_slugs = list(DEFAULT_TAG_SLUGS)

    if not tag_filters_public:
        tag_filters_public = list(dict.fromkeys(fallback_tag_slugs))

    events_status_raw = _normalize_filter_value(params.get("events_status"))
    if events_status_raw not in {None, "active", "closed", "all"}:
        events_status_raw = None

    sort_field = _normalize_text(params.get("sort"))
    ascending = params.get("ascending") if sort_field else None
    search_tags_flag = bool(params.get("search_tags", True))
    search_profiles_flag = bool(params.get("search_profiles", False))

    public_result = await _search_via_public_search(
        service,
        query=query,
        limit=limit,
        include_closed=include_closed,
        include_thin=include_thin,
        tag_filters=tag_filters_public,
        events_status=events_status_raw,
        sort_field=sort_field,
        ascending=bool(ascending) if ascending is not None else None,
        search_tags_flag=search_tags_flag,
        search_profiles_flag=search_profiles_flag,
        refresh_requested=refresh_requested,
    )

    timestamp = utc_now_iso()
    diagnostics = public_result.get("meta") or None

    if public_result.get("matches"):
        return prune_nones(
            {
                "query": query,
                "limit_requested": limit,
                "include_closed": include_closed,
                "category_filters": category_filters or None,
                "tag_slugs_used": tag_filters_public or None,
                "search_strategy": "public_search",
                "market_matches": public_result["matches"],
                "note": None,
                "diagnostics": diagnostics,
                "timestamp": timestamp,
            }
        )

    fallback_result = await _search_via_tag_harvest(
        service,
        query=query,
        limit=limit,
        include_closed=include_closed,
        include_thin=include_thin,
        tag_slugs=fallback_tag_slugs,
        refresh=refresh_requested,
    )

    fallback_note = fallback_result.get("note")
    if fallback_note:
        blended_note = f"Public search returned no matches; {fallback_note}"
    else:
        blended_note = "Public search returned no matches; used tag harvest fallback."

    return prune_nones(
        {
            "query": query,
            "limit_requested": limit,
            "include_closed": include_closed,
            "category_filters": category_filters or None,
            "tag_slugs_used": fallback_result.get("tag_slugs_used") or None,
            "search_strategy": "tag_harvest",
            "market_matches": fallback_result.get("matches") or [],
            "note": blended_note,
            "diagnostics": diagnostics,
            "timestamp": timestamp,
        }
    )
