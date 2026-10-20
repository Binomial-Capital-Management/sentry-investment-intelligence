"""
Price history logic for Polymarket service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .utils import (
    ensure_list,
    extract_outcomes,
    extract_token_ids,
    pair_outcomes_and_tokens,
    prune_nones,
    utc_now_iso,
)
from .http_client import PolymarketHTTPError

ALLOWED_INTERVALS = ("1m", "1h", "6h", "1d", "1w", "max")
INTERVAL_DEFAULT_FIDELITY = {
    "1m": 1,
    "1h": 5,
    "6h": 15,
    "1d": 60,
    "1w": 360,
    "max": 1440,
}


async def get_price_history(service, params: Dict[str, Any]) -> Dict[str, Any]:
    token_id = str(params.get("token_id", "")).strip()
    market_slug = str(params.get("market_slug", "")).strip()
    outcome_label = params.get("outcome")
    outcome_index = params.get("outcome_index")

    if not token_id and not market_slug:
        raise ValueError("Provide a token_id or market_slug to retrieve history.")

    if market_slug and not token_id:
        detail = await service.peek_market_detail(market_slug)
        if not detail:
            detail = await service.get_market_detail(market_slug)
        if not detail:
            detail = await service.get_market_detail(market_slug, refresh=True)

        summary = detail.get("summary") if detail else None
        market_payload = detail.get("market") if detail else None

        if not isinstance(market_payload, dict):
            market_payload = await service.client.get_market(market_slug)
            if isinstance(market_payload, dict):
                await service.cache_market_detail(
                    market_slug,
                    market=market_payload,
                    source="history_fallback",
                )

        token_id = _resolve_token_id(summary, market_payload, outcome_label, outcome_index)
        if not token_id:
            raise ValueError(
                "Unable to resolve token_id from market_slug; specify outcome or outcome_index."
            )

    interval = params.get("interval")
    start_ts = params.get("start_ts")
    end_ts = params.get("end_ts")
    fidelity = params.get("fidelity")

    if interval and (start_ts or end_ts):
        raise ValueError("interval is mutually exclusive with start_ts/end_ts.")

    query = prune_nones(
        {
            "market": token_id,
            "interval": interval,
            "startTs": start_ts,
            "endTs": end_ts,
            "fidelity": fidelity,
        }
    )

    requested_query = dict(query)
    note: Optional[str] = None

    if interval and fidelity is None:
        default_fidelity = INTERVAL_DEFAULT_FIDELITY.get(interval)
        if default_fidelity is not None:
            query["fidelity"] = default_fidelity
            requested_query["fidelity"] = default_fidelity

    body, error = await _fetch_history_payload(service, query)
    final_query = dict(query)

    if error and interval:
        fallback_interval = _fallback_interval(interval)
        if fallback_interval:
            fallback_query = dict(query)
            fallback_query["interval"] = fallback_interval
            fallback_query.pop("fidelity", None)
            default_fidelity = INTERVAL_DEFAULT_FIDELITY.get(fallback_interval)
            if default_fidelity is not None:
                fallback_query["fidelity"] = default_fidelity
            body, error = await _fetch_history_payload(service, fallback_query)
            final_query = fallback_query
            if not error:
                note = (
                    f"Polymarket rejected interval '{interval}'; "
                    f"used fallback interval '{fallback_interval}'."
                )
        else:
            note = f"Polymarket rejected interval '{interval}'."

    if error:
        return _build_history_response(
            token_id=token_id,
            history_payload={},
            query=requested_query,
            final_query=requested_query,
            note=note,
            error={
                "type": "unsupported_interval",
                "message": "Polymarket rejected the requested price history interval.",
                "status_code": error.status_code if isinstance(error, PolymarketHTTPError) else None,
            },
        )

    history_payload = body if isinstance(body, dict) else {}
    return _build_history_response(
        token_id=token_id,
        history_payload=history_payload,
        query=requested_query,
        final_query=final_query,
        note=note,
        error=None,
    )


def _fallback_interval(interval: Optional[str]) -> Optional[str]:
    if not interval:
        return None
    try:
        idx = ALLOWED_INTERVALS.index(interval)
    except ValueError:
        return None
    if idx == 0:
        return None
    # Prefer the next more granular interval.
    return ALLOWED_INTERVALS[idx - 1]


async def _fetch_history_payload(service, query: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[PolymarketHTTPError]]:
    try:
        response = await service.client.get_clob("/prices-history", params=query)
        return response.json(), None
    except PolymarketHTTPError as exc:
        if exc.status_code == 400:
            return None, exc
        raise


def _build_history_response(
    *,
    token_id: str,
    history_payload: Dict[str, Any],
    query: Dict[str, Any],
    final_query: Dict[str, Any],
    note: Optional[str],
    error: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    history = history_payload.get("history", []) if isinstance(history_payload, dict) else []
    timestamps = [entry.get("t") for entry in history if isinstance(entry, dict) and "t" in entry]
    prices = [entry.get("p") for entry in history if isinstance(entry, dict) and "p" in entry]

    result = {
        "token_id": token_id,
        "requested_parameters": query,
        "parameters": final_query,
        "history": history,
        "points": len(history),
        "timestamp_range": {
            "min": min(timestamps) if timestamps else None,
            "max": max(timestamps) if timestamps else None,
        },
        "price_range": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
        },
        "fields_seen": sorted({key for entry in history if isinstance(entry, dict) for key in entry.keys()}),
        "retrieved_at": utc_now_iso(),
        "supported_intervals": list(ALLOWED_INTERVALS),
    }
    if note:
        result["note"] = note
    if error:
        result["error"] = error
    return result


def _resolve_token_id(
    summary: Optional[Dict[str, Any]],
    market: Optional[Dict[str, Any]],
    outcome_label: Optional[str],
    outcome_index: Optional[int],
) -> Optional[str]:
    mapping = []
    tokens: List[str] = []

    if isinstance(summary, dict):
        for entry in ensure_list(summary.get("outcome_token_map")):
            if isinstance(entry, dict):
                mapping.append(entry)
        for token in ensure_list(summary.get("token_ids")):
            if isinstance(token, str) and token.strip():
                tokens.append(token.strip())

    if not mapping and isinstance(market, dict):
        tokens = extract_token_ids(market.get("clobTokenIds"))
        outcomes = extract_outcomes(market.get("outcomes"))
        mapping = pair_outcomes_and_tokens(outcomes, tokens)
    elif not tokens:
        tokens = [entry.get("token_id") for entry in mapping if isinstance(entry, dict) and entry.get("token_id")]

    if outcome_label:
        label_lower = outcome_label.strip().lower()
        for entry in mapping:
            outcome = (entry.get("outcome") or "").strip().lower()
            if outcome and outcome == label_lower:
                return entry.get("token_id")

    if outcome_index is not None:
        if 0 <= outcome_index < len(mapping):
            return mapping[outcome_index].get("token_id")

    for entry in mapping:
        token = (entry.get("token_id") or "").strip()
        if token:
            return token

    return tokens[0] if tokens else None
