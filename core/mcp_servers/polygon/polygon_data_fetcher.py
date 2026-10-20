"""
HTTP client utilities for interacting with Polygon.io.

Provides:
* Shared aiohttp session handling
* Rate limiter integration
* Resilient retry strategy with 429 back-off support
* URL template substitution tied to catalog definitions
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, Optional

import aiohttp

from .polygon_ddc_loader import PolygonDatasetEntry
from .polygon_rate_limiter import PolygonRateLimiter

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERN = re.compile(r"{([^{}]+)}")


class PolygonAPIError(Exception):
    """Raised when Polygon returns an error response."""

    def __init__(self, status: int, message: str, url: str) -> None:
        super().__init__(f"Polygon API error {status}: {message}")
        self.status = status
        self.message = message
        self.url = url


class PolygonDataFetcher:
    """Wrapper around aiohttp with rate limiting and retry awareness."""

    def __init__(
        self,
        api_key: Optional[str],
        rate_limiter: PolygonRateLimiter,
        base_url: str = "https://api.polygon.io",
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._rate_limiter = rate_limiter
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: Optional[aiohttp.ClientSession] = None
        self._max_retries = max_retries

    async def connect(self) -> None:
        """Create the aiohttp session if it does not exist."""

        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

    async def cleanup(self) -> None:
        """Close open resources."""

        if self._session is not None:
            await self._session.close()
            self._session = None

    async def fetch(
        self,
        dataset: PolygonDatasetEntry,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a request against the dataset definition.
        """

        await self.connect()
        assert self._session is not None  # mypy hint

        await self._rate_limiter.acquire(dataset)

        url = self._build_url(dataset.url, path_params or {})
        params = self._prepare_params(dataset, query_params or {})

        attempt = 0
        while attempt < self._max_retries:
            attempt += 1
            try:
                async with self._session.request(
                    dataset.method,
                    url,
                    params=params,
                ) as response:
                    if response.status == 429:
                        retry_after = self._parse_retry_after(response)
                        self._rate_limiter.register_cooldown(
                            dataset,
                            retry_after=retry_after,
                            headers=dict(response.headers),
                        )
                        await asyncio.sleep(retry_after or 5.0)
                        continue

                    if 500 <= response.status < 600:
                        await asyncio.sleep(min(2 ** attempt, 5))
                        continue

                    if response.status >= 400:
                        text = await response.text()
                        raise PolygonAPIError(response.status, text, url)

                    return await response.json(content_type=None)

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt >= self._max_retries:
                    raise PolygonAPIError(0, str(exc), url) from exc
                await asyncio.sleep(min(2 ** attempt, 5))

        raise PolygonAPIError(429, "Exceeded retry budget", url)

    def _build_url(self, template: str, path_params: Dict[str, Any]) -> str:
        """Replace placeholders in the dataset URL template."""

        missing = []
        url = template
        for placeholder in PLACEHOLDER_PATTERN.findall(template):
            if placeholder in path_params:
                url = url.replace(f"{{{placeholder}}}", str(path_params[placeholder]))
            else:
                missing.append(placeholder)

        if missing:
            raise ValueError(
                f"Missing path parameters for URL template '{template}': {missing}"
            )

        return f"{self._base_url}{url}"

    def _prepare_params(
        self,
        dataset: PolygonDatasetEntry,
        raw_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Filter query parameters using the catalog schema."""

        params: Dict[str, Any] = {}

        if dataset.params_schema:
            for key, value in raw_params.items():
                if key in dataset.params_schema and value is not None:
                    params[key] = value
        else:
            params.update({k: v for k, v in raw_params.items() if v is not None})

        if self._api_key and "apiKey" not in params:
            params["apiKey"] = self._api_key

        return params

    @staticmethod
    def _parse_retry_after(response: aiohttp.ClientResponse) -> Optional[float]:
        """Extract Retry-After header as float seconds."""

        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            return float(retry_after)
        except ValueError:
            return None


__all__ = ["PolygonDataFetcher", "PolygonAPIError"]
