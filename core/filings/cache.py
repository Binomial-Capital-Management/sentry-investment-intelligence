"""Simple in-memory cache for SEC filings data."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class FilingsCache:
    """Thread-safe in-memory cache with TTL support."""
    
    # Default TTLs
    METADATA_TTL = 7200  # 2 hours for FMP metadata
    CONTENT_TTL = 3600   # 1 hour for SEC content
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry["expires"]:
                return entry["data"]
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, data: Any, ttl: int) -> None:
        """Set value in cache with TTL in seconds."""
        self._cache[key] = {
            "data": data,
            "expires": datetime.now() + timedelta(seconds=ttl)
        }
    
    def delete(self, key: str) -> bool:
        """Delete a cache entry. Returns True if existed."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    def size(self) -> int:
        """Return number of cached items."""
        return len(self._cache)


# Global cache instance
_cache = FilingsCache()


def get_cache() -> FilingsCache:
    """Get the global cache instance."""
    return _cache
