"""Simple Redis cache wrapper with enhanced connection handling.

Provides both sync (Cache class) and async (cache_set/cache_get) interfaces.
When Redis is unavailable, falls back to in-memory cache.
"""
import json
import redis
import os
import logging
import time
from typing import Any, Optional, Dict, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# In-Memory Fallback Cache
# =============================================================================

_memory_cache: Dict[str, Tuple[float, Any]] = {}


def _memory_get(key: str) -> Optional[Any]:
    """Get value from in-memory cache, respecting TTL."""
    if key in _memory_cache:
        expiry, value = _memory_cache[key]
        if time.time() < expiry:
            return value
        del _memory_cache[key]
    return None


def _memory_set(key: str, value: Any, ttl: int) -> None:
    """Set value in in-memory cache with TTL."""
    _memory_cache[key] = (time.time() + ttl, value)


def _memory_delete(key: str) -> None:
    """Delete value from in-memory cache."""
    _memory_cache.pop(key, None)


# =============================================================================
# Redis Cache Class (sync)
# =============================================================================

class Cache:
    def __init__(self):
        """Initialize Redis connection with proper error handling and configuration."""
        self.redis = None
        self.enabled = False
        
        # Get Redis URL - empty string means disabled
        redis_url = os.getenv('REDIS_URL', '').strip()
        
        # Skip if no valid Redis URL provided
        if not redis_url:
            logger.info("Redis disabled (REDIS_URL not set or empty) - using in-memory fallback")
            return
        
        # Validate URL has proper scheme
        if not redis_url.startswith(('redis://', 'rediss://', 'unix://')):
            logger.warning(f"Redis disabled (invalid URL scheme): {redis_url[:30]}... - using in-memory fallback")
            return
        
        try:
            logger.info(f"Attempting Redis connection...")

            # Enhanced connection configuration for ElastiCache
            self.redis = redis.from_url(
                redis_url,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Test connection
            self.redis.ping()
            self.enabled = True
            logger.info("Redis connection successful")

        except redis.ConnectionError as e:
            logger.warning(f"Redis unavailable (cache disabled): {e} - using in-memory fallback")
            self.enabled = False
        except redis.TimeoutError as e:
            logger.warning(f"Redis timeout (cache disabled): {e} - using in-memory fallback")
            self.enabled = False
        except Exception as e:
            logger.warning(f"Redis error (cache disabled): {e} - using in-memory fallback")
            self.enabled = False
    
    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return _memory_get(key)
        try:
            val = self.redis.get(key)
            return json.loads(val) if val else None
        except Exception:
            return _memory_get(key)
    
    def set(self, key: str, value: Any, ttl: float = 300):
        if not self.enabled:
            _memory_set(key, value, int(ttl))
            return
        try:
            if ttl <= 0:
                return
            if ttl < 1:
                millis = max(int(ttl * 1000), 1)
                self.redis.psetex(key, millis, json.dumps(value))
            else:
                self.redis.setex(key, int(ttl), json.dumps(value))
        except Exception:
            # Fallback to memory on Redis errors
            _memory_set(key, value, int(ttl))
    
    def delete(self, key: str):
        if not self.enabled:
            _memory_delete(key)
            return
        try:
            self.redis.delete(key)
        except Exception:
            _memory_delete(key)


# Global cache instance
cache = Cache()


# =============================================================================
# Async Interface (wraps sync for simplicity)
# =============================================================================

async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """
    Async wrapper to store value in cache with TTL.
    
    Uses Redis when available, falls back to in-memory cache.
    TTL is in seconds (default: 5 minutes).
    """
    cache.set(key, value, ttl)


async def cache_get(key: str) -> Optional[Any]:
    """
    Async wrapper to retrieve value from cache.
    
    Uses Redis when available, falls back to in-memory cache.
    Returns None if key doesn't exist or is expired.
    """
    return cache.get(key)


async def cache_delete(key: str) -> None:
    """
    Async wrapper to delete value from cache.
    """
    cache.delete(key)
