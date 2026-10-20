"""
Enhanced cache manager for V6 with different TTLs and compression.
Builds on top of the existing cache.py but adds production features.
"""
import hashlib
import json
import zlib
import logging
from typing import Any, Optional, Dict
from core.cache import cache as redis_cache

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Enhanced cache manager with:
    - Different TTLs for different data types
    - Compression for large responses
    - Cache metrics tracking
    - Structured key patterns
    """
    
    # TTL configurations (in seconds)
    TTL_CONFIG = {
        "market_data": 3600,        # 1 hour - volatile data
        "economic_data": 86400,     # 24 hours - updates daily
        "field_discovery": 604800,  # 7 days - rarely changes
        "series_search": 86400,     # 24 hours - FRED series list
        "failed_request": 300,      # 5 minutes - prevent hammering
    }
    
    # Compression threshold (bytes)
    COMPRESSION_THRESHOLD = 1024  # 1KB
    
    def __init__(self):
        self.cache = redis_cache
        self.metrics = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "compressed": 0,
        }
    
    def _make_key(self, service: str, operation: str, params: Dict[str, Any]) -> str:
        """
        Create cache key with pattern: {service}:{operation}:{hash}
        
        Args:
            service: Service name (market_data, economic_data)
            operation: Operation type (get_data, discover_fields, etc.)
            params: Parameters to hash
        
        Returns:
            Cache key string
        """
        # Sort params for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(sorted_params.encode()).hexdigest()[:8]
        
        return f"v6:{service}:{operation}:{param_hash}"
    
    def get(self, 
            service: str, 
            operation: str, 
            params: Dict[str, Any]) -> Optional[Any]:
        """
        Get value from cache with decompression if needed.
        
        Args:
            service: Service name
            operation: Operation type
            params: Parameters used for the operation
        
        Returns:
            Cached value or None if not found
        """
        if not self.cache.enabled:
            return None
        
        key = self._make_key(service, operation, params)
        
        try:
            cached_data = self.cache.get(key)
            
            if cached_data is None:
                self.metrics["misses"] += 1
                logger.debug(f"Cache miss for {key}")
                return None
            
            # Check if data is compressed
            if isinstance(cached_data, dict) and cached_data.get("_compressed"):
                # Decompress
                compressed_bytes = bytes.fromhex(cached_data["data"])
                decompressed = zlib.decompress(compressed_bytes)
                result = json.loads(decompressed)
                logger.debug(f"Cache hit (compressed) for {key}")
            else:
                result = cached_data
                logger.debug(f"Cache hit for {key}")
            
            self.metrics["hits"] += 1
            return result
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Cache get error for {key}: {e}")
            return None
    
    def set(self,
            service: str,
            operation: str,
            params: Dict[str, Any],
            value: Any,
            ttl: Optional[int] = None):
        """
        Set value in cache with compression if needed.
        
        Args:
            service: Service name
            operation: Operation type
            params: Parameters used for the operation
            value: Value to cache
            ttl: Override TTL (uses defaults if None)
        """
        if not self.cache.enabled:
            return
        
        key = self._make_key(service, operation, params)
        
        # Determine TTL
        if ttl is None:
            # Determine data type for TTL
            if "market" in service:
                ttl = self.TTL_CONFIG["market_data"]
            elif "economic" in service:
                ttl = self.TTL_CONFIG["economic_data"]
            elif "discover" in operation or "list" in operation:
                ttl = self.TTL_CONFIG["field_discovery"]
            elif "search" in operation:
                ttl = self.TTL_CONFIG["series_search"]
            else:
                ttl = self.TTL_CONFIG["market_data"]  # Default
        
        try:
            # Check if compression is needed
            value_str = json.dumps(value)
            
            if len(value_str) > self.COMPRESSION_THRESHOLD:
                # Compress the data
                compressed = zlib.compress(value_str.encode())
                cache_value = {
                    "_compressed": True,
                    "data": compressed.hex()
                }
                self.metrics["compressed"] += 1
                logger.debug(f"Caching compressed data for {key} "
                           f"({len(value_str)} -> {len(compressed)} bytes)")
            else:
                cache_value = value
                logger.debug(f"Caching data for {key} ({len(value_str)} bytes)")
            
            self.cache.set(key, cache_value, ttl)
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Cache set error for {key}: {e}")
    
    def set_failed(self,
                   service: str,
                   operation: str,
                   params: Dict[str, Any],
                   error: str):
        """Cache failed requests to prevent repeated failures"""
        self.set(
            service,
            operation,
            params,
            {"error": error, "cached_failure": True},
            ttl=self.TTL_CONFIG["failed_request"]
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics"""
        total_requests = self.metrics["hits"] + self.metrics["misses"]
        hit_rate = (self.metrics["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.metrics,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total_requests,
        }
    
    def clear_pattern(self, pattern: str):
        """Clear all keys matching a pattern (for testing/maintenance)"""
        # Note: This requires SCAN command support in Redis
        # For now, this is a placeholder
        logger.info(f"Would clear cache keys matching pattern: {pattern}")


# Global instance
cache_manager = CacheManager()