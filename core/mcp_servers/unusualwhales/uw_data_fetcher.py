"""
Unusual Whales Data Fetcher - Handles data fetching, caching, and rate limiting.
Uses Bearer token authentication (different from FMP's query param auth).
"""

import aiohttp
import asyncio
import os
import json
import logging
import re
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta, date

from .uw_models import UWDatasetEntry
from .uw_rate_limiter import UWRateLimiter

logger = logging.getLogger(__name__)

# OCC option symbol format: SYMBOL + YYMMDD + C/P + STRIKE*1000
# Example: AAPL230120C00150000 -> AAPL, 2023-01-20, call, 150.00
OPTION_SYMBOL_RE = re.compile(r'^([A-Z]{1,5})(\d{6})([CP])(\d{8})$')


def parse_option_symbol(symbol: str) -> Dict[str, Any]:
    """
    Parse OCC-format option symbol into components.
    
    Args:
        symbol: Option symbol like "AAPL230120C00150000"
        
    Returns:
        Dict with parsed_ticker, parsed_expiry, parsed_type, parsed_strike
        or empty dict if parsing fails
    """
    if not symbol or not isinstance(symbol, str):
        return {}
    
    # Handle symbols with numbers in ticker (e.g., SPX, SPXW, VIX)
    # Try progressively shorter ticker matches
    for ticker_len in range(min(5, len(symbol)), 0, -1):
        potential_ticker = symbol[:ticker_len]
        remainder = symbol[ticker_len:]
        
        # Check if remainder matches the expected pattern
        if len(remainder) >= 15:  # YYMMDD + C/P + 8 digits = 15 chars
            expiry_str = remainder[:6]
            opt_type = remainder[6:7]
            strike_str = remainder[7:15]
            
            # Validate components
            if (expiry_str.isdigit() and 
                opt_type in ('C', 'P') and 
                strike_str.isdigit()):
                try:
                    # Parse expiry: YYMMDD -> YYYY-MM-DD
                    expiry_date = datetime.strptime(expiry_str, "%y%m%d")
                    parsed_expiry = expiry_date.strftime("%Y-%m-%d")
                    
                    # Parse strike: divide by 1000
                    parsed_strike = int(strike_str) / 1000
                    
                    return {
                        "parsed_ticker": potential_ticker,
                        "parsed_expiry": parsed_expiry,
                        "parsed_type": "call" if opt_type == "C" else "put",
                        "parsed_strike": parsed_strike
                    }
                except ValueError:
                    continue
    
    return {}


def get_last_business_day(from_date: Optional[date] = None) -> date:
    """
    Get the most recent business day (Mon-Fri).
    
    Args:
        from_date: Starting date (defaults to today)
        
    Returns:
        Most recent business day
    """
    check_date = from_date or date.today()
    
    # Walk backwards until we find a weekday
    while check_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        check_date = check_date - timedelta(days=1)
    
    return check_date


def get_last_business_day_str(from_date: Optional[date] = None) -> str:
    """Get last business day as YYYY-MM-DD string."""
    return get_last_business_day(from_date).isoformat()


class UWDataFetcher:
    """
    Handles all data fetching operations for Unusual Whales API.
    Includes caching, rate limiting, and retry logic.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.unusualwhales.com"):
        """
        Initialize the data fetcher with API credentials.
        
        Args:
            api_key: Unusual Whales API key (Bearer token)
            base_url: API base URL
        """
        self.api_key = api_key
        self.base_url = base_url
        
        # Cache settings
        self.cache_ttl = 300  # 5 minutes default
        self.memory_cache: Dict[str, Dict] = {}
        self.max_cache_size = 1000  # Prevent unbounded growth
        self.redis_client = None  # Optional Redis support
        
        # Rate limiting
        self.rate_limiter = UWRateLimiter()
        
        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Request tracking for debugging
        self._request_count = 0
        self._error_count = 0
        
    async def connect(self):
        """Initialize HTTP session and optional Redis connection."""
        # Create HTTP session with proper connector and timeout
        connector = aiohttp.TCPConnector(
            force_close=False,
            enable_cleanup_closed=True,
            limit=20  # Connection pool limit
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=45)
        
        # Default headers for all requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "SentryInvestmentPlatform/1.0"
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        
        # Try to connect to Redis (optional)
        try:
            import redis.asyncio as redis
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                await self.redis_client.ping()
                logger.info("UW DataFetcher: Redis connection successful")
        except Exception as e:
            logger.debug(f"UW DataFetcher: Redis not available, using memory cache: {e}")
            self.redis_client = None
            
        logger.info("UW DataFetcher connected")
    
    async def cleanup(self):
        """Cleanup connections."""
        if self.session:
            await self.session.close()
            if self.session.connector:
                await self.session.connector.close()

        if self.redis_client:
            await self.redis_client.close()

        self.memory_cache.clear()
        logger.info(f"UW DataFetcher cleaned up (requests: {self._request_count}, errors: {self._error_count})")
    
    def _build_cache_key(self, dataset_name: str, params: Dict[str, Any]) -> str:
        """Build a cache key from dataset name and parameters."""
        # Sort params for consistent key
        sorted_params = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params if v is not None)
        return f"uw:{dataset_name}:{param_str}"
    
    async def get_cache(self, key: str) -> Optional[Dict]:
        """Get value from cache (Redis or memory)."""
        if self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.debug(f"Redis get failed: {e}")
        
        # Fallback to memory cache
        if key in self.memory_cache:
            cached = self.memory_cache[key]
            if cached["expires"] > datetime.now():
                return cached["data"]
            else:
                del self.memory_cache[key]
        
        return None
    
    async def set_cache(self, key: str, value: Any, ttl: int = None):
        """Set value in cache (Redis or memory)."""
        if ttl is None:
            ttl = self.cache_ttl
            
        if self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, json.dumps(value))
                return
            except Exception as e:
                logger.debug(f"Redis set failed: {e}")
        
        # Fallback to memory cache with size limit
        # Evict expired entries first
        now = datetime.now()
        expired_keys = [k for k, v in self.memory_cache.items() if v["expires"] <= now]
        for k in expired_keys:
            del self.memory_cache[k]
        
        # If still over limit, evict oldest entries (simple LRU approximation)
        if len(self.memory_cache) >= self.max_cache_size:
            # Remove 10% of oldest entries
            sorted_keys = sorted(self.memory_cache.keys(), 
                                key=lambda k: self.memory_cache[k]["expires"])
            for k in sorted_keys[:max(1, len(sorted_keys) // 10)]:
                del self.memory_cache[k]
        
        self.memory_cache[key] = {
            "data": value,
            "expires": now + timedelta(seconds=ttl)
        }
    
    def _apply_date_defaults(self, params: Dict[str, Any], dataset: UWDatasetEntry) -> Dict[str, Any]:
        """
        Apply smart defaults for date parameters.
        
        UW API endpoints that accept 'date' parameter default to "last trading day"
        on their side, but weekends/holidays may return empty data. We proactively
        set date to last business day if not provided.
        
        Args:
            params: Input parameters
            dataset: Dataset entry with schema info
            
        Returns:
            Updated params dict with date defaults applied
        """
        result = dict(params)
        schema = dataset.params_schema or {}
        
        # Check if 'date' is in the schema and not already provided
        if 'date' in schema and 'date' not in result:
            # Default to last business day
            result['date'] = get_last_business_day_str()
            logger.debug(f"Applied date default {result['date']} for {dataset.dataset}")
        
        return result
    
    async def fetch_dataset(
        self, 
        dataset: UWDatasetEntry,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch data from an Unusual Whales endpoint.

        Args:
            dataset: Dataset entry from UW catalog
            params: Parameters for the request (path params + query params)
            use_cache: Whether to use caching

        Returns:
            Fetched data as dictionary
        """
        params = params or {}
        
        # Apply business day fallback for date params if not provided
        # This ensures we don't request data for weekends/holidays which return empty
        params = self._apply_date_defaults(params, dataset)
        
        # Validate and apply defaults
        try:
            validated_params = dataset.validate_params(params)
        except ValueError as e:
            return {"error": str(e), "dataset": dataset.dataset}
        
        # Build cache key
        cache_key = self._build_cache_key(dataset.dataset, validated_params)
        
        # Check cache first
        if use_cache:
            cached = await self.get_cache(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {dataset.dataset}")
                return cached
        
        # Ensure session exists
        if not self.session:
            raise RuntimeError("UWDataFetcher not connected. Call connect() first.")
        
        # Apply rate limiting
        await self.rate_limiter.acquire(dataset.class_)
        
        # Build URL with path parameters substituted
        path_params = dataset.get_path_params()
        path_values = {k: validated_params.pop(k) for k in path_params if k in validated_params}
        url = dataset.substitute_url(**path_values)
        full_url = f"{self.base_url}{url}"
        
        # Remaining params go as query params
        # Convert booleans to lowercase strings for URL encoding
        query_params = {}
        for k, v in validated_params.items():
            if v is None:
                continue
            elif isinstance(v, bool):
                query_params[k] = str(v).lower()  # True -> "true", False -> "false"
            else:
                query_params[k] = v
        
        # Retry logic
        last_error = None
        for attempt in range(3):
            try:
                self._request_count += 1
                
                async with self.session.get(full_url, params=query_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Normalize response format
                        result = self._normalize_response(data, dataset)
                        
                        # Cache the result
                        if use_cache and result:
                            await self.set_cache(cache_key, result, dataset.cache_ttl)
                        
                        return result
                    
                    elif response.status == 429:  # Rate limit
                        self._error_count += 1
                        wait = int(response.headers.get('Retry-After', 5))
                        logger.warning(f"Rate limited on {dataset.dataset}, waiting {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    
                    elif response.status == 401:
                        self._error_count += 1
                        return {
                            "error": "Authentication failed - check API key",
                            "status": 401,
                            "dataset": dataset.dataset
                        }
                    
                    elif response.status == 404:
                        self._error_count += 1
                        return {
                            "error": f"Endpoint not found: {url}",
                            "status": 404,
                            "dataset": dataset.dataset
                        }
                    
                    else:
                        self._error_count += 1
                        text = await response.text()
                        last_error = f"HTTP {response.status}: {text[:200]}"
                        logger.warning(f"HTTP error on {dataset.dataset}: {last_error}")
                        
            except asyncio.TimeoutError:
                self._error_count += 1
                last_error = "Request timeout"
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                    
            except aiohttp.ClientError as e:
                self._error_count += 1
                last_error = str(e)
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                    
            except Exception as e:
                self._error_count += 1
                last_error = str(e)
                logger.error(f"Unexpected error fetching {dataset.dataset}: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
        
        return {
            "error": f"Failed after 3 attempts: {last_error}",
            "dataset": dataset.dataset
        }
    
    def _normalize_response(self, data: Any, dataset: UWDatasetEntry) -> Dict[str, Any]:
        """
        Normalize API response to consistent format.
        
        Args:
            data: Raw API response
            dataset: Dataset entry for context
            
        Returns:
            Normalized response dict
        """
        # UW API typically returns {"data": [...]} or direct arrays
        if isinstance(data, dict):
            if "data" in data:
                result = data  # Already has data wrapper
            else:
                result = {"data": data}  # Single object response
        elif isinstance(data, list):
            result = {"data": data}
        else:
            result = {"data": data}
        
        # Auto-parse option_symbol columns if present
        # This adds parsed_ticker, parsed_expiry, parsed_type, parsed_strike
        if isinstance(result.get("data"), list):
            for row in result["data"]:
                if isinstance(row, dict):
                    # Check for option_symbol field (various possible names)
                    symbol = (
                        row.get("option_symbol") or 
                        row.get("contract_symbol") or 
                        row.get("symbol") or
                        row.get("option_chain")
                    )
                    if symbol and isinstance(symbol, str) and len(symbol) >= 15:
                        parsed = parse_option_symbol(symbol)
                        if parsed:
                            # Only add parsed fields if they don't already exist
                            for key, value in parsed.items():
                                if key not in row:
                                    row[key] = value
        
        return result
    
    async def fetch_multiple(
        self,
        requests: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        Fetch multiple datasets concurrently.
        
        Args:
            requests: List of {"dataset": UWDatasetEntry, "params": {...}}
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dict mapping dataset names to results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(req: Dict) -> tuple:
            async with semaphore:
                result = await self.fetch_dataset(req["dataset"], req.get("params"))
                return req["dataset"].dataset, result
        
        tasks = [fetch_with_semaphore(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            name: result if not isinstance(result, Exception) else {"error": str(result)}
            for name, result in results
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get fetcher statistics."""
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "cache_size": len(self.memory_cache),
            "rate_limiter_status": self.rate_limiter.get_status()
        }

