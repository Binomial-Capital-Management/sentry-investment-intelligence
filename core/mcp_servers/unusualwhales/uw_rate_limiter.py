"""
Simple rate limiter for Unusual Whales API.
Token bucket algorithm with per-class limits.
Dynamically discovers rate limits from catalog.
"""

import asyncio
import time
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SimpleRateLimiter:
    """
    Simple token bucket rate limiter.
    Tracks API calls per second with burst capacity.
    """
    
    def __init__(self, calls_per_second: int = 5, burst: int = 15):
        """
        Initialize with rate limit configuration.
        
        Args:
            calls_per_second: Sustained rate limit
            burst: Maximum burst capacity
        """
        self.calls_per_second = calls_per_second
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        async with self._lock:
            current_time = time.time()
            time_passed = current_time - self.last_update
            
            # Refill tokens based on time passed
            self.tokens = min(
                self.burst,
                self.tokens + time_passed * self.calls_per_second
            )
            self.last_update = current_time
            
            if self.tokens < 1:
                # Need to wait for a token
                wait_time = (1 - self.tokens) / self.calls_per_second
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_update = time.time()
            else:
                self.tokens -= 1


class UWRateLimiter:
    """
    Rate limiter per dataset class for Unusual Whales API.
    Dynamically discovers classes from catalog and creates limiters.
    """
    
    def __init__(self, catalog=None):
        """
        Initialize rate limiters dynamically from catalog.
        
        Args:
            catalog: Optional UWCatalog instance. If None, discovers from loader.
        """
        self.limiters: Dict[str, SimpleRateLimiter] = {}
        self._default_rps = 5
        self._default_burst = 15
        
        # Always have a default fallback
        self.limiters["default"] = SimpleRateLimiter(
            calls_per_second=self._default_rps, 
            burst=self._default_burst
        )
        
        # Dynamically discover classes and their rate limits from catalog
        self._init_from_catalog(catalog)
    
    def _init_from_catalog(self, catalog=None):
        """
        Initialize rate limiters by discovering classes from catalog.
        Uses rate_limit config from each dataset.
        """
        if catalog is None:
            try:
                from .uw_ddc_loader import get_default_loader
                loader = get_default_loader()
                catalog = loader.catalog
            except Exception as e:
                logger.warning(f"Could not load catalog for rate limiter init: {e}")
                return
        
        if not catalog or not catalog.datasets:
            return
        
        # Discover all unique classes and their rate limits
        # Use the first dataset's rate_limit for each class
        class_limits: Dict[str, tuple] = {}
        for dataset in catalog.datasets:
            cls = dataset.class_
            if cls not in class_limits:
                # Get rate limit from dataset config
                rps = dataset.rate_limit.rps if dataset.rate_limit else self._default_rps
                burst = dataset.rate_limit.burst if dataset.rate_limit else self._default_burst
                class_limits[cls] = (rps, burst)
        
        # Create limiters for each discovered class
        for cls, (rps, burst) in class_limits.items():
            self.limiters[cls] = SimpleRateLimiter(calls_per_second=rps, burst=burst)
        
        logger.debug(f"UWRateLimiter initialized with {len(self.limiters)} classes from catalog")
        
    async def acquire(self, dataset_class: str = "default"):
        """
        Acquire permission to make an API call.
        
        Args:
            dataset_class: The class of dataset being accessed
        """
        limiter = self.limiters.get(dataset_class, self.limiters["default"])
        await limiter.acquire()
        
    def get_status(self) -> Dict[str, Dict[str, int]]:
        """Get current rate limiter configuration."""
        return {
            name: {
                "rps": limiter.calls_per_second,
                "burst": limiter.burst,
                "tokens": int(limiter.tokens)
            }
            for name, limiter in self.limiters.items()
        }
    
    def update_limits(self, dataset_class: str, rps: int, burst: int):
        """
        Update rate limits for a dataset class.
        
        Args:
            dataset_class: Class to update
            rps: New requests per second
            burst: New burst capacity
        """
        if dataset_class in self.limiters:
            self.limiters[dataset_class] = SimpleRateLimiter(rps, burst)
        else:
            logger.warning(f"Unknown dataset class: {dataset_class}")

