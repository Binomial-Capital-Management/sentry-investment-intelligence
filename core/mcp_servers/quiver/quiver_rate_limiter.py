"""
Simple Quiver Quant rate limiter.
"""

import asyncio
import time


class SimpleRateLimiter:
    """Token bucket limiter for provider APIs with soft, per-second caps."""

    def __init__(self, calls_per_second: int = 5, burst: int = 10):
        self.calls_per_second = calls_per_second
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.calls_per_second)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.calls_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_update = time.time()
            else:
                self.tokens -= 1


class QuiverRateLimiter(SimpleRateLimiter):
    """Provider-specific alias to keep parity with other MCP packages."""

