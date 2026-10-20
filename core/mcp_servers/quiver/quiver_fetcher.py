"""
Quiver Quant data fetcher with auth, retries, and tier-error detection.
"""

from __future__ import annotations

import aiohttp
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from .quiver_rate_limiter import QuiverRateLimiter

logger = logging.getLogger(__name__)

QUIVER_TIER_ERROR = "Upgrade your subscription plan to access this dataset."


class QuiverTierError(RuntimeError):
    """Raised when Quiver returns a subscription-tier error payload."""


class QuiverDataFetcher:
    """HTTP client for Quiver Quant endpoints."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.quiverquant.com",
        auth_scheme: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.auth_scheme = (auth_scheme or os.getenv("QUIVER_AUTH_SCHEME", "token")).lower()
        self.timeout_seconds = float(timeout_seconds or os.getenv("QUIVER_HTTP_TIMEOUT_SECONDS", "30"))
        self.rate_limiter = QuiverRateLimiter(
            calls_per_second=int(os.getenv("QUIVER_RATE_LIMIT_RPS", "5")),
            burst=int(os.getenv("QUIVER_RATE_LIMIT_BURST", "10")),
        )
        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        if self.session:
            return

        auth_prefix = "Bearer" if self.auth_scheme == "bearer" else "Token"
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds, connect=10, sock_read=self.timeout_seconds)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Authorization": f"{auth_prefix} {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "SentryInvestmentPlatform/1.0",
            },
        )

    async def cleanup(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        await self.rate_limiter.acquire()
        await self.connect()
        assert self.session is not None

        normalized_params = _prune_params(params)
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        logger.info("Quiver request: path=%s params=%s", path, normalized_params)

        for attempt in range(2):
            try:
                async with self.session.get(url, params=normalized_params) as response:
                    text = await response.text()
                    payload = self.parse_response_text(text, response.status)
                    self._log_response_shape(path, normalized_params, payload)
                    return payload
            except QuiverTierError:
                raise
            except aiohttp.ClientResponseError as exc:
                last_error = exc
                if exc.status < 500 or attempt == 1:
                    raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt == 1:
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("Quiver request failed without an explicit error")

    @staticmethod
    def parse_response_text(text: str, status_code: int) -> Any:
        payload = (text or "").strip()

        if payload == QUIVER_TIER_ERROR:
            raise QuiverTierError(QUIVER_TIER_ERROR)

        if status_code >= 400:
            raise RuntimeError(payload or f"HTTP {status_code}")

        if not payload:
            return []

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid Quiver response: {payload[:200]}") from exc

    def _log_response_shape(self, path: str, params: Dict[str, Any], payload: Any) -> None:
        if isinstance(payload, list):
            row_count = len(payload)
            first_keys = sorted(payload[0].keys())[:10] if payload and isinstance(payload[0], dict) else []
            logger.info(
                "Quiver response: path=%s type=list rows=%s first_keys=%s",
                path,
                row_count,
                first_keys,
            )
            requested_page_size = params.get("page_size")
            if requested_page_size is not None and row_count > int(requested_page_size):
                logger.warning(
                    "Quiver provider ignored or overrode page_size: path=%s requested_page_size=%s actual_rows=%s",
                    path,
                    requested_page_size,
                    row_count,
                )
        elif isinstance(payload, dict):
            logger.info(
                "Quiver response: path=%s type=dict keys=%s",
                path,
                sorted(payload.keys())[:15],
            )
        else:
            logger.info("Quiver response: path=%s type=%s", path, type(payload).__name__)


def normalize_quiver_payload(dataset_key: str, payload: Any) -> Any:
    """Normalize common Quiver response families into cleaner scalar/date types."""
    if not isinstance(payload, list):
        return payload

    normalizer = _NORMALIZERS.get(dataset_key)
    if normalizer is None:
        return payload

    normalized = [normalizer(row) if isinstance(row, dict) else row for row in payload]
    return normalized


def _normalize_congress_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for key in ("Amount", "ExcessReturn", "PriceChange", "SPYChange"):
        result[key] = _to_float_if_possible(result.get(key))
    for key in ("ReportDate", "TransactionDate", "Date", "last_modified", "Traded", "Filed", "Quiver_Upload_Time"):
        result[key] = _normalize_dateish(result.get(key))
    return result


def _normalize_insider_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for key in ("Shares", "PricePerShare", "SharesOwnedFollowing"):
        result[key] = _to_float_if_possible(result.get(key))
    for key in ("Date", "fileDate", "uploaded"):
        result[key] = _normalize_datetimeish(result.get(key))
    return result


def _normalize_offexchange_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for key in ("OTC_Short", "OTC_Total"):
        result[key] = _to_int_if_possible(result.get(key))
    result["DPI"] = _to_float_if_possible(result.get("DPI"))
    result["Date"] = _normalize_dateish(result.get("Date"))
    return result


def _normalize_13f_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    numeric_candidates = (
        "Shares",
        "Value",
        "Change",
        "Weight",
        "Ownership",
        "MarketValue",
        "SharesHeld",
        "PercentOfPortfolio",
    )
    for key in numeric_candidates:
        if key in result:
            result[key] = _to_float_if_possible(result.get(key))
    for key in ("Date", "ReportDate", "Period", "fileDate", "last_modified"):
        if key in result:
            result[key] = _normalize_dateish(result.get(key))
    return result


def _normalize_sentiment_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for key in ("Date", "date", "uploaded", "fileDate"):
        if key in result:
            result[key] = _normalize_datetimeish(result.get(key))
    for key in ("Count", "Mentions", "mentions", "count"):
        if key in result:
            result[key] = _to_int_if_possible(result.get(key))
    return result


def _normalize_alt_signal_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for key in ("Date", "date", "ReportDate", "action_date", "last_modified"):
        if key in result:
            result[key] = _normalize_dateish(result.get(key))
    for key in ("Amount", "DPI", "PatentMomentum", "PatentDrift", "Rating", "PriceTarget"):
        if key in result:
            result[key] = _to_float_if_possible(result.get(key))
    return result


def _to_float_if_possible(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        candidate = value.strip().replace(",", "")
        if not candidate:
            return value
        try:
            return float(candidate)
        except ValueError:
            return value
    return value


def _to_int_if_possible(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        candidate = value.strip().replace(",", "")
        try:
            number = float(candidate)
            return int(number) if number.is_integer() else number
        except ValueError:
            return value
    return value


def _normalize_dateish(value: Any) -> Any:
    if not value or not isinstance(value, str):
        return value
    parsed = _parse_datetime(value)
    if parsed is None:
        return value
    return parsed.date().isoformat()


def _normalize_datetimeish(value: Any) -> Any:
    if not value or not isinstance(value, str):
        return value
    parsed = _parse_datetime(value)
    if parsed is None:
        return value
    return parsed.isoformat(timespec="seconds")


def _parse_datetime(value: str) -> Optional[datetime]:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        candidate = candidate.replace("Z", "+00:00")
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


_NORMALIZERS = {
    "congresstrading": _normalize_congress_row,
    "senatetrading": _normalize_congress_row,
    "housetrading": _normalize_congress_row,
    "insiders": _normalize_insider_row,
    "offexchange": _normalize_offexchange_row,
    "sec13f": _normalize_13f_row,
    "sec13fchanges": _normalize_13f_row,
    "etfholdings": _normalize_13f_row,
    "wallstreetbets": _normalize_sentiment_row,
    "spacs": _normalize_sentiment_row,
    "twitter": _normalize_sentiment_row,
    "wsbcomments": _normalize_sentiment_row,
    "wsbcommentsfull": _normalize_sentiment_row,
    "cryptocomments": _normalize_sentiment_row,
    "cryptocommentsfull": _normalize_sentiment_row,
    "spaccomments": _normalize_sentiment_row,
    "redditcomments": _normalize_sentiment_row,
    "allpatents": _normalize_alt_signal_row,
    "patentdrift": _normalize_alt_signal_row,
    "patentmomentum": _normalize_alt_signal_row,
    "appratings": _normalize_alt_signal_row,
    "govcontracts": _normalize_alt_signal_row,
    "govcontractsall": _normalize_alt_signal_row,
    "flights": _normalize_alt_signal_row,
    "cnbc": _normalize_alt_signal_row,
    "eventsbeta": _normalize_alt_signal_row,
    "politicalbeta": _normalize_alt_signal_row,
    "lobbying": _normalize_alt_signal_row,
    "corporatedonors": _normalize_alt_signal_row,
}


def _prune_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not params:
        return {}
    return {key: value for key, value in params.items() if value is not None}
