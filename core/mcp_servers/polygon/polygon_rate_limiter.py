"""
Asynchronous token bucket rate limiter tailored for Polygon.io constraints.

Polygon's free tier permits five requests per minute. Token buckets let us
apply back-pressure across concurrent coroutines while still supporting dataset
specific overrides from the catalog metadata.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional

from .polygon_ddc_loader import PolygonDatasetEntry


@dataclass
class _Bucket:
    capacity: int
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float
    cooldown_until: float = 0.0
    lock: asyncio.Lock = None

    def __post_init__(self):
        if self.lock is None:
            self.lock = asyncio.Lock()


class PolygonRateLimiter:
    """Token bucket rate limiter with simple 429 back-off integration."""

    def __init__(self, default_per_minute: int = 5, default_burst: int = 5) -> None:
        self._default_per_minute = default_per_minute
        self._default_burst = default_burst
        self._buckets: Dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, dataset: Optional[PolygonDatasetEntry] = None) -> None:
        """
        Acquire a token for the dataset. Await until a token becomes available.
        """

        key = dataset.dataset if dataset else "__global__"

        # Only lock during bucket initialization, not during token wait
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                per_minute = (
                    dataset.rate_limit.per_minute if dataset else self._default_per_minute
                )
                burst = dataset.rate_limit.burst if dataset else self._default_burst
                bucket = _Bucket(
                    capacity=burst,
                    tokens=float(burst),
                    refill_rate=per_minute / 60.0,
                    last_refill=time.monotonic(),
                )
                self._buckets[key] = bucket

        # Wait for token WITHOUT holding the global lock - allows parallel requests per endpoint
        await self._wait_for_token(bucket)

    async def _wait_for_token(self, bucket: _Bucket) -> None:
        """Wait until a token is available in the bucket."""

        while True:
            await asyncio.sleep(0)
            # Use per-bucket lock instead of global lock - allows different endpoints to run in parallel
            async with bucket.lock:
                self._refill(bucket)

                if bucket.cooldown_until > time.monotonic():
                    sleep_for = max(0.0, bucket.cooldown_until - time.monotonic())
                elif bucket.tokens >= 1:
                    bucket.tokens -= 1
                    return
                else:
                    sleep_for = max(0.0, (1 - bucket.tokens) / bucket.refill_rate)

            if sleep_for > 0:
                await asyncio.sleep(min(sleep_for, 5))

    def _refill(self, bucket: _Bucket) -> None:
        """Refill tokens based on elapsed time."""

        now = time.monotonic()
        elapsed = now - bucket.last_refill
        if elapsed <= 0:
            return
        bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_rate)
        bucket.last_refill = now

    def register_cooldown(
        self,
        dataset: Optional[PolygonDatasetEntry],
        retry_after: Optional[float],
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Register a cooldown after receiving an HTTP 429 response.

        Args:
            dataset: Dataset entry associated with the request.
            retry_after: Value from Retry-After header if present.
            headers: Additional headers for parsing rate limit resets.
        """

        key = dataset.dataset if dataset else "__global__"
        bucket = self._buckets.get(key)
        if bucket is None:
            return

        wait_seconds = retry_after or 0.0
        if wait_seconds <= 0 and headers:
            reset = headers.get("X-RateLimit-Reset")
            remaining = headers.get("X-RateLimit-Remaining")
            if reset and remaining == "0":
                try:
                    reset_ts = float(reset)
                    wait_seconds = max(0.0, reset_ts - time.time())
                except ValueError:
                    wait_seconds = 0.0

        if wait_seconds <= 0:
            wait_seconds = 5.0  # Default fallback

        bucket.cooldown_until = max(bucket.cooldown_until, time.monotonic() + wait_seconds)


__all__ = ["PolygonRateLimiter"]
