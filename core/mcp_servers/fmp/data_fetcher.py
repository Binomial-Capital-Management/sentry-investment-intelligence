"""
FMP Data Fetcher - Handles data fetching, caching, and rate limiting
Following KISS principle - focused only on fetching and caching
"""

import aiohttp
import asyncio
import os
import redis.asyncio as redis
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from .ddc_loader import DatasetEntry
from .rate_limiter import DatasetRateLimiter
from core.ai.utils.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class FMPDataFetcher:
    """
    Handles all data fetching operations for FMP.
    Includes caching, rate limiting, and retry logic.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://financialmodelingprep.com"):
        """Initialize the data fetcher with API credentials"""
        self.api_key = api_key
        self.base_url = base_url
        
        # Cache settings
        self.cache_ttl = 300  # 5 minutes default
        self.memory_cache: Dict[str, Dict] = {}
        self.redis_client: Optional[redis.Redis] = None
        
        # Rate limiting
        self.rate_limiter = DatasetRateLimiter()
        
        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def connect(self):
        """Initialize connections (HTTP session and Redis)"""
        # Close existing session if reconnecting to prevent leaks
        if self.session and not self.session.closed:
            try:
                await self.session.close()
                if self.session.connector:
                    await self.session.connector.close()
            except Exception:
                pass  # Ignore errors during cleanup of old session
        
        # Create HTTP session with proper connector and timeout configuration
        # 90-second timeout for high production latency
        connector = aiohttp.TCPConnector(
            force_close=False,  # Keep connections alive for reuse
            enable_cleanup_closed=True  # Auto-cleanup closed connections
        )
        timeout = aiohttp.ClientTimeout(total=90, connect=10, sock_read=60)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        
        # Try to connect to Redis with enhanced configuration
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            logger.info(f"FMP DataFetcher connecting to Redis: {redis_url}")

            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            await self.redis_client.ping()
            logger.info("FMP DataFetcher: Redis connection successful")
        except redis.ConnectionError as e:
            logger.warning(f"FMP DataFetcher: Redis connection failed: {e}")
            self.redis_client = None
        except redis.TimeoutError as e:
            logger.warning(f"FMP DataFetcher: Redis connection timeout: {e}")
            self.redis_client = None
        except Exception as e:
            logger.warning(f"FMP DataFetcher: Redis not available, using memory cache: {e}")
            self.redis_client = None
    
    async def cleanup(self):
        """Cleanup connections"""
        if self.session:
            await self.session.close()
            # CRITICAL: Close connector to prevent resource leak
            if self.session.connector:
                await self.session.connector.close()

        if self.redis_client:
            await self.redis_client.close()

        self.memory_cache.clear()
    
    async def fetch_dataset(self, symbol: str, dataset: DatasetEntry,
                          historical_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fetch data from a single FMP endpoint with retry and rate limiting.

        Args:
            symbol: Stock symbol
            dataset: Dataset entry from DDC catalog
            historical_params: Optional params for historical data (period, limit)

        Returns:
            Fetched data as dictionary
        """
        # Build cache parameters
        cache_params = {
            "symbol": symbol,
            "dataset": dataset.dataset,
            "params": historical_params or {}
        }

        # Check cache first
        cached = cache_manager.get("market_data", "fetch_dataset", cache_params)
        if cached:
            logger.debug(f"Cache hit for {symbol}/{dataset.dataset}")
            return cached

        # Ensure session exists - fail fast if not connected
        if not self.session:
            raise RuntimeError("FMPDataFetcher not connected. Call connect() first.")

        # Apply rate limiting
        await self.rate_limiter.acquire(dataset.class_)
        
        # Build URL
        url = dataset.substitute_url(symbol=symbol)
        full_url = f"{self.base_url}{url}"

        # Build params (user-supplied first so reserved keys can overwrite afterward)
        params: Dict[str, Any] = {}
        
        # Add historical params if provided
        if historical_params:
            if dataset.allow_additional_params:
                for key, value in historical_params.items():
                    if value is not None:
                        params[key] = value
            # Only add params that the dataset accepts (check params_schema)
            elif dataset.params_schema:
                for key, value in historical_params.items():
                    if key in dataset.params_schema and value is not None:
                        params[key] = value
        
        # Enforce server-managed credentials
        params["apikey"] = self.api_key
    
        # Set identifier param from symbol, but only if:
        # 1. Dataset has an identifier_param defined
        # 2. That param wasn't already provided by the user (e.g., name=Nancy Pelosi)
        # 3. The symbol is a valid value (not empty or special marker)
        if dataset.identifier_param:
            identifier_already_set = dataset.identifier_param in params and params[dataset.identifier_param]
            symbol_is_valid = symbol and symbol not in ("", "_MARKET_", "MARKET")
            
            if symbol_is_valid and not identifier_already_set:
                params[dataset.identifier_param] = symbol
        
        # Simple retry - try 3 times
        for attempt in range(3):
            try:
                async with self.session.get(full_url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Handle different response formats
                        # For historical chart data, return the full list
                        if dataset.dataset == "historical-chart-1day":
                            result = data  # Return full list for charts
                        # For other endpoints, return full list when appropriate
                        elif isinstance(data, list) and len(data) > 0:
                            # For historical requests, return full list
                            if historical_params and historical_params.get("period"):
                                result = data
                            # For paginated endpoints (have 'limit' or 'page' in schema), return full array
                            elif dataset.params_schema and any(key in dataset.params_schema for key in ("limit", "page")):
                                result = data
                            # Many list endpoints omit identifier params (catalog/list feeds)
                            elif not dataset.identifier_param:
                                result = data
                            # Date-windowed requests should also return the full slice
                            elif historical_params and any(
                                key in historical_params for key in ("from", "to", "date", "year", "quarter")
                            ):
                                result = data
                            else:
                                first_item = data[0]
                                result = first_item if isinstance(first_item, dict) else {"data": data}
                        elif isinstance(data, dict):
                            result = data
                        else:
                            result = {"data": data}

                        # Cache the result before returning
                        if result:
                            cache_manager.set("market_data", "fetch_dataset", cache_params, result, ttl=dataset.cache_ttl)

                        return result
                    
                    elif response.status == 429:  # Rate limit
                        wait = int(response.headers.get('Retry-After', 5))
                        await asyncio.sleep(wait)
                        continue
                    else:
                        # Capture response text for debugging bad requests (e.g., missing entitlements/params)
                        error_text = await response.text()
                        logger.error(
                            "FMP API error %s for %s params=%s body=%s",
                            response.status,
                            full_url,
                            params,
                            error_text[:500],  # avoid flooding logs
                        )
                        raise Exception(f"HTTP {response.status}: {error_text}")
                        
            except asyncio.TimeoutError:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
                raise
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
                raise
        
        raise Exception(f"Failed after 3 attempts")
    
    async def get_cache(self, key: str) -> Optional[Dict]:
        """Get value from cache (Redis or memory)"""
        if self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # Fallback to memory cache
        if key in self.memory_cache:
            cached = self.memory_cache[key]
            # Check if not expired
            if cached["expires"] > datetime.now():
                return cached["data"]
            else:
                del self.memory_cache[key]
        
        return None
    
    async def set_cache(self, key: str, value: Dict, ttl: int = None):
        """Set value in cache (Redis or memory)"""
        if ttl is None:
            ttl = self.cache_ttl
            
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key, 
                    ttl, 
                    json.dumps(value)
                )
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        # Fallback to memory cache
        self.memory_cache[key] = {
            "data": value,
            "expires": datetime.now() + timedelta(seconds=ttl)
        }
