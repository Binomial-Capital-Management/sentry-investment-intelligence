"""
Market-oriented operations for the Polymarket service.
"""

from __future__ import annotations

import numbers
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

import logging

from .utils import (
    extract_outcomes,
    extract_token_ids,
    pair_outcomes_and_tokens,
    prune_nones,
    ensure_list,
    utc_now_iso,
)
from .http_client import PolymarketHTTPError

MAX_OUTCOMES = 6
MAX_QUESTION_LENGTH = 240
DEFAULT_MAX_RESULTS = 40
MAX_RESULTS_CAP = 120
DEFAULT_MIN_VOLUME_24H = 2500.0
THIN_SAMPLE_SIZE = 5
MISSING_TOKEN_SAMPLE_SIZE = 3
DEFAULT_CATEGORY_WHITELIST = ("crypto", "finance", "economy", "world", "tech", "earnings")
PRICE_ROUND = 4
SPREAD_PCT_ROUND = 4
VOLUME_ROUND = 2
SCORE_ROUND = 2
MAX_CATEGORY_ITEMS = 6
MAX_TAG_ITEMS = 8


logger = logging.getLogger(__name__)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, numbers.Number):
        if isinstance(value, bool):
            return float(int(value))
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace(",", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _round_if_not_none(value: Optional[float], digits: int) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def _clip_text(value: Any, limit: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    truncated = text[:limit].rstrip()
    excess = len(text) - len(truncated)
    return f"{truncated}… (+{excess} chars)"


def _tokenize_search_terms(text: str) -> List[str]:
    normalized = text.strip().lower()
    if not normalized:
        return []
    return [token for token in re.split(r"\s+", normalized) if token]


def _build_search_blob(parts: Sequence[Optional[str]]) -> str:
    return " ".join(part for part in parts if part).lower()


def _matches_search(search_blob: str, terms: Sequence[str]) -> bool:
    if not terms:
        return True
    return all(term in search_blob for term in terms)


def _compute_mid_spread(
    best_bid: Optional[float], best_ask: Optional[float]
) -> Tuple[Optional[float], Optional[float]]:
    if best_bid is None or best_ask is None:
        return None, None
    mid = (best_bid + best_ask) / 2
    if mid <= 0:
        return mid, None
    spread = abs(best_ask - best_bid)
    spread_pct = spread / mid if mid else None
    return mid, spread_pct


def _score_market(volume_24h: Optional[float], liquidity: Optional[float], volume_7d: Optional[float]) -> float:
    candidates = []
    for value in (volume_24h, liquidity):
        if value is not None and value > 0:
            candidates.append(value)
    if volume_7d is not None and volume_7d > 0:
        candidates.append(volume_7d / 7.0)
    if not candidates:
        return 0.0
    return max(candidates)


def _summarize_market(market: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    tokens = extract_token_ids(market.get("clobTokenIds"))
    outcomes_full = extract_outcomes(market.get("outcomes"))
    outcome_map = pair_outcomes_and_tokens(outcomes_full, tokens)

    question_full = str(market.get("question") or "").strip()
    question_display = _clip_text(question_full, MAX_QUESTION_LENGTH)
    slug_value = str(market.get("slug") or "").strip() or None

    volume_candidates = (
        market.get("volume24hr"),
        market.get("volume24hrNum"),
        market.get("volume24hrAmm"),
        market.get("volume24hrClob"),
    )
    volume_24h: Optional[float] = None
    for candidate in volume_candidates:
        value = _coerce_float(candidate)
        if value is not None:
            volume_24h = value
            break

    volume_7d = _coerce_float(market.get("volume1wk"))

    liquidity_candidates = (
        market.get("liquidityNum"),
        market.get("liquidity"),
    )
    liquidity: Optional[float] = None
    for candidate in liquidity_candidates:
        value = _coerce_float(candidate)
        if value is not None:
            liquidity = value
            break

    best_bid = _coerce_float(market.get("bestBid"))
    best_ask = _coerce_float(market.get("bestAsk"))
    last_trade_price = _coerce_float(market.get("lastTradePrice"))
    mid_price, spread_pct = _compute_mid_spread(best_bid, best_ask)

    score = _score_market(volume_24h, liquidity, volume_7d)

    summary: Dict[str, Any] = {}

    market_id = market.get("id")
    if market_id is not None:
        summary["id"] = market_id
    if slug_value:
        summary["slug"] = slug_value
    if question_display:
        summary["question"] = question_display
    if outcomes_full:
        summary["outcomes"] = outcomes_full[:MAX_OUTCOMES]
        if len(outcomes_full) > MAX_OUTCOMES:
            summary["outcome_count"] = len(outcomes_full)
    if outcome_map:
        summary["outcome_token_map"] = outcome_map
    if tokens:
        summary["token_ids"] = tokens

    if best_bid is not None:
        summary["best_bid"] = _round_if_not_none(best_bid, PRICE_ROUND)
    if best_ask is not None:
        summary["best_ask"] = _round_if_not_none(best_ask, PRICE_ROUND)
    if last_trade_price is not None:
        summary["last_trade_price"] = _round_if_not_none(last_trade_price, PRICE_ROUND)
    if mid_price is not None:
        summary["mid_price"] = _round_if_not_none(mid_price, PRICE_ROUND)
    if spread_pct is not None:
        summary["spread_pct"] = _round_if_not_none(spread_pct, SPREAD_PCT_ROUND)

    if volume_24h is not None:
        summary["volume_24h"] = _round_if_not_none(volume_24h, VOLUME_ROUND)
    if volume_7d is not None:
        summary["volume_7d"] = _round_if_not_none(volume_7d, VOLUME_ROUND)
    if liquidity is not None:
        summary["liquidity"] = _round_if_not_none(liquidity, VOLUME_ROUND)
    if score > 0:
        summary["score"] = _round_if_not_none(score, SCORE_ROUND)

    closed = market.get("closed")
    if isinstance(closed, bool):
        summary["closed"] = closed
    elif closed is not None:
        summary["closed"] = bool(closed)

    accepting = market.get("acceptingOrders")
    if isinstance(accepting, bool):
        summary["accepting_orders"] = accepting
    elif accepting is not None:
        summary["accepting_orders"] = bool(accepting)

    end_date = market.get("endDateIso") or market.get("endDate")
    if end_date:
        summary["end_date"] = end_date

    category = market.get("category")
    if isinstance(category, str) and category.strip():
        summary["category"] = category.strip()

    market_type = market.get("marketType")
    if isinstance(market_type, str) and market_type.strip():
        summary["market_type"] = market_type

    categories_field = ensure_list(market.get("categories"))
    categories_list: List[str] = []
    if categories_field:
        for item in categories_field:
            if isinstance(item, str):
                candidate = item.strip()
                if candidate and candidate not in categories_list:
                    categories_list.append(candidate)
            elif isinstance(item, dict):
                for key in ("name", "label", "title", "slug"):
                    value = item.get(key)
                    if isinstance(value, str):
                        candidate = value.strip()
                        if candidate and candidate not in categories_list:
                            categories_list.append(candidate)
        if categories_list:
            summary["categories"] = categories_list[:MAX_CATEGORY_ITEMS]

    tags_field = ensure_list(market.get("tags"))
    tags_list: List[str] = []
    if tags_field:
        for item in tags_field:
            if isinstance(item, str):
                candidate = item.strip()
                if candidate and candidate not in tags_list:
                    tags_list.append(candidate)
            elif isinstance(item, dict):
                for key in ("name", "label", "title", "slug"):
                    value = item.get(key)
                    if isinstance(value, str):
                        candidate = value.strip()
                        if candidate and candidate not in tags_list:
                            tags_list.append(candidate)
        if tags_list:
            summary["tags"] = tags_list[:MAX_TAG_ITEMS]

    outcomes_blob = " ".join(outcomes_full) if outcomes_full else None
    search_blob = _build_search_blob(
        [slug_value, question_full, outcomes_blob, str(category or ""), str(market_type or "")]
    )

    metrics = {
        "volume_24h": volume_24h,
        "volume_7d": volume_7d,
        "liquidity": liquidity,
        "score": score,
        "search_blob": search_blob,
    }

    return summary, metrics


def summarize_market_payload(market: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Public wrapper that returns the summary/metrics tuple for a raw market payload."""

    return _summarize_market(market)


def _sample_entries(
    items: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]],
    limit: int,
) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    for summary, _ in items[:limit]:
        preview.append(
            prune_nones(
                {
                    "slug": summary.get("slug"),
                    "question": summary.get("question"),
                    "volume_24h": summary.get("volume_24h"),
                    "liquidity": summary.get("liquidity"),
                    "score": summary.get("score"),
                }
            )
        )
    return preview


async def get_markets_by_tag(service, params: Dict[str, Any]) -> Dict[str, Any]:
    tag_id = params.get("tag_id")
    if tag_id is None:
        raise ValueError("tag_id is required")

    closed = params.get("closed", False)
    limit = params.get("limit_per_page", 100)
    max_pages = params.get("max_pages", 5)
    order = params.get("order")
    ascending = params.get("ascending")
    include_tag_details = params.get("include_tag_details", False)
    include_related_tag_markets = params.get("include_related_tag_markets", False)
    refresh = params.get("refresh", False)

    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit_per_page must be an integer") from exc
    if limit < 1 or limit > 200:
        raise ValueError("limit_per_page must be between 1 and 200")

    try:
        max_pages = int(max_pages)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_pages must be an integer") from exc
    if max_pages < 1 or max_pages > 40:
        raise ValueError("max_pages must be between 1 and 40")

    search_text = str(params.get("search_text") or "").strip()
    search_terms = _tokenize_search_terms(search_text)

    include_thin = bool(params.get("include_thin_markets", False))

    category_whitelist_param = params.get("category_whitelist")
    if category_whitelist_param is not None:
        normalized_categories = []
        for item in ensure_list(category_whitelist_param):
            if isinstance(item, str):
                candidate = item.strip().lower()
                if candidate and candidate not in normalized_categories:
                    normalized_categories.append(candidate)
        allowed_categories = normalized_categories
    else:
        allowed_categories = [cat.lower() for cat in DEFAULT_CATEGORY_WHITELIST]
    allowed_category_set = {cat for cat in allowed_categories if cat}

    min_volume_param = params.get("min_volume_24hr")
    min_volume = _coerce_float(min_volume_param) if min_volume_param is not None else None
    if min_volume_param is not None and min_volume is None:
        raise ValueError("min_volume_24hr must be numeric")
    if min_volume is None:
        min_volume = 0.0 if include_thin else DEFAULT_MIN_VOLUME_24H

    min_liquidity_param = params.get("min_liquidity_usd")
    min_liquidity = _coerce_float(min_liquidity_param) if min_liquidity_param is not None else None
    if min_liquidity_param is not None and min_liquidity is None:
        raise ValueError("min_liquidity_usd must be numeric")
    if min_liquidity is None:
        min_liquidity = 0.0

    max_results_param = params.get("max_results", DEFAULT_MAX_RESULTS)
    try:
        max_results = int(max_results_param)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_results must be an integer") from exc
    if max_results < 1:
        raise ValueError("max_results must be >= 1")
    max_results = min(max_results, MAX_RESULTS_CAP)

    harvest_threshold = max(max_results * 3, max_results + limit)

    cache_key = service.scoped_cache_key(
        "markets",
        tag_id,
        closed,
        limit,
        max_pages,
        order,
        ascending,
        include_tag_details,
        include_related_tag_markets,
        search_text.lower(),
        round(min_volume, 4),
        round(min_liquidity, 4),
        include_thin,
        max_results,
        tuple(sorted(allowed_category_set)) if allowed_category_set else None,
    )
    if not refresh:
        cached = await service.market_cache.get(cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

    summaries: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    fields_seen: set[str] = set()
    pages_retrieved = 0

    for page in range(max_pages):
        params_page = prune_nones(
            {
                "tag_id": tag_id,
                "closed": closed,
                "limit": limit,
                "offset": page * limit,
                "order": order,
                "ascending": ascending,
                "include_tag": include_tag_details or None,
                "related_tags": include_related_tag_markets or None,
            }
        )
        response = await service.client.get_gamma("/markets", params=params_page)
        page_data = response.json()

        if not isinstance(page_data, list) or not page_data:
            break

        pages_retrieved += 1

        for market in page_data:
            if not isinstance(market, dict):
                continue
            fields_seen.update(str(key) for key in market.keys())
            summary, metrics = _summarize_market(market)
            slug_value = summary.get("slug")
            if slug_value:
                await service.cache_market_detail(
                    slug_value,
                    market=market,
                    summary=summary,
                    metrics=metrics,
                    source="tag_harvest",
                )
            summaries.append((summary, metrics))
            if len(summaries) >= harvest_threshold:
                break

        if len(summaries) >= harvest_threshold:
            break

        if len(page_data) < limit:
            break

    search_filtered: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    missing_token: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    volume_filtered: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    liquidity_filtered: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    category_filtered: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    eligible_candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

    for summary, metrics in summaries:
        search_blob = metrics.get("search_blob", "")
        if not _matches_search(search_blob, search_terms):
            search_filtered.append((summary, metrics))
            continue

        if allowed_category_set:
            category_candidates = []
            primary_category = summary.get("category")
            if isinstance(primary_category, str) and primary_category.strip():
                category_candidates.append(primary_category.strip())
            additional_categories = summary.get("categories") or []
            for entry in additional_categories:
                if isinstance(entry, str) and entry.strip():
                    category_candidates.append(entry.strip())
            if not category_candidates:
                category_filtered.append((summary, metrics))
                continue

            normalized_hits = [
                value.lower()
                for value in category_candidates
                if isinstance(value, str)
            ]

            def _category_matches() -> bool:
                for value in normalized_hits:
                    for allowed in allowed_category_set:
                        if allowed and allowed in value:
                            return True
                return False

            if not _category_matches():
                category_filtered.append((summary, metrics))
                continue

        if not summary.get("token_ids"):
            missing_token.append((summary, metrics))
            continue

        if not include_thin:
            volume_value = metrics.get("volume_24h")
            if volume_value is None or volume_value < min_volume:
                volume_filtered.append((summary, metrics))
                continue

        if min_liquidity > 0:
            liquidity_value = metrics.get("liquidity")
            if liquidity_value is None or liquidity_value < min_liquidity:
                liquidity_filtered.append((summary, metrics))
                continue

        eligible_candidates.append((summary, metrics))

    filters_relaxed: Dict[str, bool] = {}
    final_candidates = eligible_candidates

    if not final_candidates and not include_thin and volume_filtered:
        final_candidates = volume_filtered
        filters_relaxed["min_volume_24h"] = True

    if not final_candidates and min_liquidity > 0 and liquidity_filtered:
        final_candidates = liquidity_filtered
        filters_relaxed["min_liquidity_usd"] = True

    if not final_candidates and missing_token:
        final_candidates = missing_token
        filters_relaxed["token_ids_required"] = True

    if not final_candidates and search_filtered:
        final_candidates = search_filtered
        filters_relaxed["search_terms"] = True

    def _sort_key(item: Tuple[Dict[str, Any], Dict[str, Any]]) -> Tuple[float, float, float]:
        metrics = item[1]
        return (
            metrics.get("score") or 0.0,
            metrics.get("volume_24h") or 0.0,
            metrics.get("liquidity") or 0.0,
        )

    final_sorted = sorted(final_candidates, key=_sort_key, reverse=True)
    candidate_pool_count = len(final_sorted)
    markets = [dict(item[0]) for item in final_sorted[:max_results]]

    token_ids = sorted(
        {
            token
            for market in markets
            for token in (market.get("token_ids") or [])
            if isinstance(token, str)
        }
    )

    volume_filtered_sorted = sorted(
        volume_filtered, key=lambda item: item[1].get("volume_24h") or 0.0, reverse=True
    )
    liquidity_filtered_sorted = sorted(
        liquidity_filtered, key=lambda item: item[1].get("liquidity") or 0.0, reverse=True
    )
    missing_token_sorted = sorted(
        missing_token, key=lambda item: item[1].get("score") or 0.0, reverse=True
    )
    search_filtered_sorted = sorted(
        search_filtered, key=lambda item: item[1].get("score") or 0.0, reverse=True
    )

    excluded_samples: Dict[str, List[Dict[str, Any]]] = {}
    if volume_filtered_sorted and not include_thin:
        excluded_samples["below_min_volume"] = _sample_entries(volume_filtered_sorted, THIN_SAMPLE_SIZE)
    if min_liquidity > 0 and liquidity_filtered_sorted:
        excluded_samples["below_min_liquidity"] = _sample_entries(
            liquidity_filtered_sorted, THIN_SAMPLE_SIZE
        )
    if missing_token_sorted:
        excluded_samples["missing_token_ids"] = _sample_entries(
            missing_token_sorted, MISSING_TOKEN_SAMPLE_SIZE
        )
    if category_filtered:
        excluded_samples["category_filtered"] = _sample_entries(
            sorted(category_filtered, key=lambda item: item[1].get("score") or 0.0, reverse=True),
            THIN_SAMPLE_SIZE,
        )
    if search_terms and search_filtered_sorted:
        excluded_samples["search_filtered"] = _sample_entries(search_filtered_sorted, THIN_SAMPLE_SIZE)
    excluded_samples = {key: value for key, value in excluded_samples.items() if value}

    filters: Dict[str, Any] = {
        "include_thin_markets": include_thin,
        "max_results": max_results,
        "min_volume_24h": _round_if_not_none(min_volume, VOLUME_ROUND),
        "min_liquidity_usd": _round_if_not_none(min_liquidity, VOLUME_ROUND),
    }
    if allowed_category_set:
        filters["category_whitelist"] = sorted(allowed_category_set)
    if search_terms:
        filters["search_terms"] = search_terms
    if filters_relaxed:
        filters["filters_relaxed"] = filters_relaxed

    counts = {
        "total_markets_seen": len(summaries),
        "search_filtered": len(search_filtered),
        "missing_token": len(missing_token),
        "below_min_volume": len(volume_filtered),
        "below_min_liquidity": len(liquidity_filtered),
        "category_filtered": len(category_filtered),
        "eligible_before_limit": len(eligible_candidates),
        "candidate_pool": candidate_pool_count,
        "returned_markets": len(markets),
    }

    result = {
        "tag_id": tag_id,
        "closed_requested": bool(closed),
        "markets": markets,
        "market_count": len(markets),
        "total_markets_seen": len(summaries),
        "fields_seen": sorted(fields_seen),
        "token_ids": token_ids,
        "pages_retrieved": pages_retrieved,
        "timestamp": utc_now_iso(),
        "cache_hit": False,
        "filters": filters,
        "counts": counts,
        "truncation_notice": {
            "max_results": max_results,
            "max_outcomes": MAX_OUTCOMES,
            "question_char_limit": MAX_QUESTION_LENGTH,
        },
    }

    if excluded_samples:
        result["excluded_samples"] = excluded_samples

    if include_tag_details:
        try:
            tag_metadata = await service.client.get_gamma(f"/tags/{tag_id}")
            payload = tag_metadata.json()
            if isinstance(payload, dict):
                result["tag"] = payload
        except PolymarketHTTPError:
            pass

    await service.market_cache.set(cache_key, result)
    return result


async def discover_market_fields(service, params: Dict[str, Any]) -> Dict[str, Any]:
    market_slug = params.get("market_slug")
    tag_id = params.get("tag_id")
    closed = params.get("closed", False)

    if not market_slug and tag_id is None:
        raise ValueError("Provide either market_slug or tag_id for sampling.")

    sample_market: Optional[Dict[str, Any]] = None
    data_source = ""

    if market_slug:
        try:
            payload = await service.client.get_gamma(f"/markets/slug/{market_slug}")
            market_json = payload.json()
            if isinstance(market_json, dict):
                sample_market = market_json
                data_source = f"/markets/slug/{market_slug}"
        except PolymarketHTTPError as exc:
            if exc.status_code == 404:
                logger.warning(
                    "Polymarket slug not found: %s. Prompting caller to use search tool.",
                    market_slug,
                )
                return {
                    "slug": market_slug,
                    "error": "market_slug_not_found",
                    "message": (
                        "Polymarket did not return a market for the supplied slug. "
                        "Use search_polymarket_markets or tag harvest results to obtain canonical slugs."
                    ),
                }
            raise
    else:
        query = prune_nones({"tag_id": tag_id, "closed": closed, "limit": 1})
        payload = await service.client.get_gamma("/markets", params=query)
        markets_json = payload.json()
        if isinstance(markets_json, list) and markets_json:
            candidate = markets_json[0]
            if isinstance(candidate, dict):
                sample_market = candidate
                query_str = urlencode(query, doseq=True)
                data_source = f"/markets?{query_str}" if query_str else "/markets"

    if not sample_market:
        raise ValueError("Unable to locate a market sample for field discovery.")

    if isinstance(sample_market, dict):
        summary, metrics = _summarize_market(sample_market)
        slug_value = summary.get("slug")
        if slug_value:
            await service.cache_market_detail(
                slug_value,
                market=sample_market,
                summary=summary,
                metrics=metrics,
                source="market_fields",
            )

    fields = sorted({str(key) for key in sample_market.keys()})
    tokens = extract_token_ids(sample_market.get("clobTokenIds"))
    outcomes = extract_outcomes(sample_market.get("outcomes"))

    return {
        "fields": fields,
        "token_ids": tokens,
        "outcomes": outcomes,
        "outcome_token_map": pair_outcomes_and_tokens(outcomes, tokens),
        "data_source": data_source,
        "timestamp": utc_now_iso(),
    }
