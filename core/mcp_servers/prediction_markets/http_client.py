"""
Async HTTP client with rate limiting and retry logic for FinFeed Prediction Markets.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional
import datetime

import jwt

import httpx
from urllib.parse import urljoin


class TokenBucketLimiter:
    """Simple token bucket rate limiter using perf_counter for accuracy."""

    def __init__(self, rate: int) -> None:
        """
        Args:
            rate: Maximum requests per second.
        """
        self.rate = float(max(rate, 1))
        self.tokens = self.rate
        self.last_refill = time.perf_counter()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a token is available."""
        async with self._lock:
            now = time.perf_counter()
            elapsed = now - self.last_refill
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class FinFeedHTTPClient:
    """Async HTTP client for FinFeed Prediction Markets API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        rps: int,
        private_key: str,
        kid: str,
        sub: str,
        iss: str,
        ttl_seconds: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._limiter = TokenBucketLimiter(rps)
        self._api_key = api_key
        self._private_key = private_key.replace("\\n", "\n")
        self._kid = kid
        self._sub = sub
        self._iss = iss
        self._ttl = ttl_seconds

        self._client = httpx.AsyncClient(
            headers={
                "X-API-Key": self._api_key,
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def get(self, endpoint: str, params: Optional[Dict[str, object]] = None) -> Dict:
        """
        Perform a GET request with retry logic.

        Retries:
            - Up to 3 times on 5xx responses or timeouts (exponential backoff).
            - No retries on 4xx errors.
        """
        await self._limiter.acquire()

        base = self.base_url.rstrip("/")

        # Normalize both base and endpoint so we never double-insert the API version.
        normalized_base = base.replace("/v1/v1", "/v1")
        normalized_endpoint = endpoint.lstrip("/")
        if normalized_endpoint.startswith("v1/") and normalized_base.endswith("/v1"):
            normalized_endpoint = normalized_endpoint[3:]

        url = urljoin(f"{normalized_base}/", normalized_endpoint)
        retry_count = 0
        max_retries = 3

        while True:
            try:
                headers = {"Authorization": f"Bearer {self._generate_jwt()}"}
                request_params = dict(params or {})
                request_params.setdefault("apikey", self._api_key)
                response = await self._client.get(url, params=request_params, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if 400 <= status < 500:
                    raise
                retry_count += 1
                if retry_count > max_retries:
                    raise
                await asyncio.sleep(2 ** retry_count)
            except httpx.TimeoutException:
                retry_count += 1
                if retry_count > max_retries:
                    raise
                await asyncio.sleep(2 ** retry_count)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def _generate_jwt(self) -> str:
        now = datetime.datetime.now(datetime.UTC)
        payload = {
            "sub": self._sub,
            "iss": self._iss,
            "iat": now,
            "exp": now + datetime.timedelta(seconds=self._ttl),
        }
        token = jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._kid},
        )
        return token
