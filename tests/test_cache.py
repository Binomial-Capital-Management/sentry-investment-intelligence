"""
Unit tests for cache.py - Redis cache with in-memory fallback.

Tests cover:
- Cache class (sync interface)
- Async wrappers (cache_set, cache_get, cache_delete)
- In-memory fallback when Redis unavailable
- TTL expiration
- JSON serialization
"""
import pytest
import time
import json
from unittest.mock import patch, MagicMock

from core.cache import (
    Cache,
    cache_set,
    cache_get,
    cache_delete,
    _memory_cache,
    _memory_get,
    _memory_set,
    _memory_delete,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clear_memory_cache():
    """Clear in-memory cache before and after each test."""
    _memory_cache.clear()
    yield
    _memory_cache.clear()


# =============================================================================
# In-Memory Cache Tests
# =============================================================================

class TestMemoryCache:
    """Tests for the in-memory fallback cache."""

    def test_memory_set_and_get(self):
        """Test basic set and get operations."""
        _memory_set("test_key", {"data": "value"}, ttl=60)
        
        result = _memory_get("test_key")
        assert result == {"data": "value"}

    def test_memory_get_nonexistent(self):
        """Test getting a key that doesn't exist."""
        result = _memory_get("nonexistent_key")
        assert result is None

    def test_memory_ttl_expiry(self):
        """Test that items expire after TTL."""
        _memory_set("expiring_key", "value", ttl=1)  # 1 second TTL
        
        # Should exist immediately
        assert _memory_get("expiring_key") == "value"
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be expired
        assert _memory_get("expiring_key") is None

    def test_memory_delete(self):
        """Test deleting a key."""
        _memory_set("delete_me", "value", ttl=60)
        assert _memory_get("delete_me") == "value"
        
        _memory_delete("delete_me")
        assert _memory_get("delete_me") is None

    def test_memory_delete_nonexistent(self):
        """Test deleting a nonexistent key (should not error)."""
        _memory_delete("nonexistent")  # Should not raise

    def test_memory_complex_values(self):
        """Test storing complex nested data structures."""
        complex_data = {
            "symbol": "AAPL",
            "data": [
                {"date": "2024-01-01", "close": 185.5},
                {"date": "2024-01-02", "close": 186.0},
            ],
            "metadata": {
                "source": "fmp",
                "fetched_at": 1704067200,
            }
        }
        
        _memory_set("complex", complex_data, ttl=60)
        result = _memory_get("complex")
        
        assert result == complex_data
        assert result["data"][0]["close"] == 185.5


# =============================================================================
# Cache Class Tests (Sync Interface)
# =============================================================================

class TestCacheClass:
    """Tests for the Cache class."""

    def test_cache_without_redis(self):
        """Test Cache falls back to memory when Redis unavailable."""
        with patch.dict('os.environ', {'REDIS_URL': ''}):
            cache = Cache()
            
            assert cache.enabled is False
            
            cache.set("key", "value", ttl=60)
            assert cache.get("key") == "value"

    def test_cache_with_invalid_redis_url(self):
        """Test Cache with invalid Redis URL."""
        with patch.dict('os.environ', {'REDIS_URL': 'not-a-valid-url'}):
            cache = Cache()
            
            assert cache.enabled is False

    def test_cache_json_serialization(self):
        """Test that values are JSON serialized."""
        with patch.dict('os.environ', {'REDIS_URL': ''}):
            cache = Cache()
            
            data = {"key": "value", "number": 42, "list": [1, 2, 3]}
            cache.set("json_test", data, ttl=60)
            
            result = cache.get("json_test")
            assert result == data

    def test_cache_zero_ttl_ignored(self):
        """Test that TTL <= 0 is ignored."""
        with patch.dict('os.environ', {'REDIS_URL': ''}):
            cache = Cache()
            
            cache.set("zero_ttl", "value", ttl=0)
            # Should not be stored
            assert cache.get("zero_ttl") is None

    def test_cache_delete(self):
        """Test cache delete operation."""
        with patch.dict('os.environ', {'REDIS_URL': ''}):
            cache = Cache()
            
            cache.set("to_delete", "value", ttl=60)
            assert cache.get("to_delete") == "value"
            
            cache.delete("to_delete")
            assert cache.get("to_delete") is None


# =============================================================================
# Async Wrapper Tests
# =============================================================================

class TestAsyncWrappers:
    """Tests for async cache_set, cache_get, cache_delete."""

    @pytest.mark.asyncio
    async def test_async_cache_set_get(self):
        """Test async set and get."""
        await cache_set("async_key", {"async": "data"}, ttl=60)
        
        result = await cache_get("async_key")
        assert result == {"async": "data"}

    @pytest.mark.asyncio
    async def test_async_cache_get_nonexistent(self):
        """Test async get for nonexistent key."""
        result = await cache_get("nonexistent_async")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_cache_delete(self):
        """Test async delete."""
        await cache_set("to_delete_async", "value", ttl=60)
        await cache_delete("to_delete_async")
        
        result = await cache_get("to_delete_async")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_cache_ttl(self):
        """Test async TTL expiration."""
        await cache_set("expiring_async", "value", ttl=1)
        
        # Should exist
        assert await cache_get("expiring_async") == "value"
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be gone
        assert await cache_get("expiring_async") is None


# =============================================================================
# Redis Fallback Tests
# =============================================================================

class TestRedisFallback:
    """Tests for Redis -> memory fallback behavior."""

    def test_fallback_on_redis_error_get(self):
        """Test fallback to memory on Redis get error."""
        with patch.dict('os.environ', {'REDIS_URL': 'redis://localhost:6379'}):
            cache = Cache()
            
            # Force enabled but mock Redis to fail
            cache.enabled = True
            cache.redis = MagicMock()
            cache.redis.get.side_effect = Exception("Connection lost")
            
            # Set in memory first
            _memory_set("fallback_key", "value", ttl=60)
            
            # Should fall back to memory
            result = cache.get("fallback_key")
            assert result == "value"

    def test_fallback_on_redis_error_set(self):
        """Test fallback to memory on Redis set error."""
        with patch.dict('os.environ', {'REDIS_URL': 'redis://localhost:6379'}):
            cache = Cache()
            
            # Force enabled but mock Redis to fail
            cache.enabled = True
            cache.redis = MagicMock()
            cache.redis.setex.side_effect = Exception("Connection lost")
            
            # Should fall back to memory
            cache.set("fallback_set", "value", ttl=60)
            
            # Should be in memory
            assert _memory_get("fallback_set") == "value"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_large_payload(self):
        """Test caching large data payloads."""
        # Create a large dataset (simulating FMP response)
        large_data = {
            "symbol": "AAPL",
            "data": [{"date": f"2020-{m:02d}-{d:02d}", "close": 100 + (m * 31 + d) * 0.5} 
                     for m in range(1, 13) for d in range(1, 29)]  # ~336 records
        }
        
        await cache_set("large_payload", large_data, ttl=60)
        result = await cache_get("large_payload")
        
        assert result == large_data
        assert len(result["data"]) == 336

    @pytest.mark.asyncio
    async def test_unicode_values(self):
        """Test caching Unicode strings."""
        unicode_data = {
            "company": "日本株式会社",
            "symbol": "7203.T",
            "notes": "トヨタ自動車 🚗",
        }
        
        await cache_set("unicode", unicode_data, ttl=60)
        result = await cache_get("unicode")
        
        assert result == unicode_data

    @pytest.mark.asyncio
    async def test_special_key_characters(self):
        """Test keys with special characters."""
        await cache_set("dataset_cache:abc-123-def", "value", ttl=60)
        result = await cache_get("dataset_cache:abc-123-def")
        
        assert result == "value"

    @pytest.mark.asyncio
    async def test_null_values(self):
        """Test caching None/null values."""
        await cache_set("null_value", None, ttl=60)
        result = await cache_get("null_value")
        
        assert result is None  # Note: This is indistinguishable from "not found"

    @pytest.mark.asyncio
    async def test_boolean_values(self):
        """Test caching boolean values."""
        await cache_set("bool_true", True, ttl=60)
        await cache_set("bool_false", False, ttl=60)
        
        assert await cache_get("bool_true") is True
        assert await cache_get("bool_false") is False

    @pytest.mark.asyncio
    async def test_numeric_values(self):
        """Test caching numeric values."""
        await cache_set("int_val", 42, ttl=60)
        await cache_set("float_val", 3.14159, ttl=60)
        
        assert await cache_get("int_val") == 42
        assert await cache_get("float_val") == 3.14159
