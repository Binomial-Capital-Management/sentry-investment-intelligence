"""
TTL-based cache utilities for the prediction markets MCP server.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class TTLCache:
    """Thread-safe in-memory cache with TTL semantics."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        """
        Args:
            ttl_seconds: Duration (in seconds) before entries expire.
        """
        self.ttl = ttl_seconds
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value if present and not expired."""
        async with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None

            value, expires_at = entry
            if datetime.now() >= expires_at:
                del self._cache[key]
                return None

            return value

    async def set(self, key: str, value: Any) -> None:
        """Store a value with the configured TTL."""
        async with self._lock:
            expires_at = datetime.now() + timedelta(seconds=self.ttl)
            self._cache[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Remove a specific entry if it exists."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()

    async def get_stats(self) -> Dict[str, int]:
        """Return basic cache statistics."""
        async with self._lock:
            now = datetime.now()
            total = len(self._cache)
            active = sum(1 for _, expires_at in self._cache.values() if expires_at > now)
            return {
                "total_entries": total,
                "active_entries": active,
                "expired_entries": total - active,
            }
