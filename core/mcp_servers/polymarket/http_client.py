"""
Async HTTP client wrappers for Polymarket Gamma and CLOB endpoints.
"""

from __future__ import annotations

import asyncio
import json
import math
from typing import Any, Dict, Optional

import httpx


class PolymarketHTTPError(RuntimeError):
    """Raised when remote Polymarket endpoints fail."""

    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class PolymarketHTTPClient:
    """Shared HTTP plumbing for Gamma and CLOB calls with retry/backoff."""

    def __init__(
        self,
        gamma_base_url: str,
        clob_base_url: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.75,
    ) -> None:
        self.gamma_base_url = gamma_base_url.rstrip("/")
        self.clob_base_url = clob_base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._backoff = max(0.1, backoff_seconds)
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_gamma(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        url = f"{self.gamma_base_url}{path}"
        return await self._request("GET", url, params=params)

    async def get_clob(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        url = f"{self.clob_base_url}{path}"
        return await self._request("GET", url, params=params)

    async def post_clob(self, path: str, json_body: Any) -> httpx.Response:
        url = f"{self.clob_base_url}{path}"
        return await self._request("POST", url, json=json_body)

    async def get_market(self, slug: str) -> Dict[str, Any]:
        """Convenience wrapper for `/markets/slug/{slug}`."""
        response = await self.get_gamma(f"/markets/slug/{slug}")
        return response.json()

    async def _request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None, json: Any = None) -> httpx.Response:
        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(method, url, params=params, json=json)
                if response.status_code >= 400:
                    raise PolymarketHTTPError(
                        f"Polymarket request failed ({response.status_code}) for {url}",
                        status_code=response.status_code,
                        payload=_safe_json(response),
                    )
                return response
            except (httpx.TimeoutException, httpx.NetworkError, PolymarketHTTPError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._backoff * math.pow(2, attempt))

        if isinstance(last_error, PolymarketHTTPError):
            raise last_error

        raise PolymarketHTTPError(f"Polymarket request failed for {url}: {last_error}")


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text

