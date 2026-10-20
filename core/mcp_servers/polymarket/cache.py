"""
Lightweight async TTL cache for Polymarket MCP workflows.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class TTLCache:
    """Simple in-memory cache with per-entry expiry."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._entries: Dict[str, tuple[Any, datetime]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value if present and not expired."""
        async with self._lock:
            item = self._entries.get(key)
            if item is None:
                return None

            value, expires_at = item
            if datetime.now() >= expires_at:
                self._entries.pop(key, None)
                return None

            return value

    async def set(self, key: str, value: Any) -> None:
        """Store a value for the configured TTL."""
        async with self._lock:
            expires_at = datetime.now() + timedelta(seconds=self._ttl)
            self._entries[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Remove a cached entry."""
        async with self._lock:
            self._entries.pop(key, None)

    async def clear(self) -> None:
        """Remove all entries."""
        async with self._lock:
            self._entries.clear()

    async def stats(self) -> Dict[str, int]:
        """Return basic counts for observability."""
        async with self._lock:
            now = datetime.now()
            total = len(self._entries)
            active = sum(1 for _, expires_at in self._entries.values() if expires_at > now)
            return {
                "total": total,
                "active": active,
                "expired": total - active,
            }

