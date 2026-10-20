"""
Simple rate limiter for FMP API - Following KISS principle
No complex libraries, just basic token bucket algorithm
"""

import asyncio
import time
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class SimpleRateLimiter:
    """
    Simple token bucket rate limiter
    No complex patterns, just track API calls per second
    """
    
    def __init__(self, calls_per_second: int = 5):
        """Initialize with calls per second limit"""
        self.calls_per_second = calls_per_second
        self.last_call_time = 0
        self.min_interval = 1.0 / calls_per_second  # Minimum time between calls
        
    async def acquire(self):
        """Wait if necessary to respect rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_call_time
        
        if time_since_last < self.min_interval:
            # Need to wait
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)
            
        self.last_call_time = time.time()


class DatasetRateLimiter:
    """
    Rate limiter per dataset class (market vs documents)
    Simple implementation following KISS principle
    """
    
    def __init__(self):
        """Initialize with default limits"""
        self.limiters = {
            "market": SimpleRateLimiter(calls_per_second=10),    # 10 calls/sec for market data
            "document": SimpleRateLimiter(calls_per_second=3),   # 3 calls/sec for documents (singular to match DDC)
            "documents": SimpleRateLimiter(calls_per_second=3),  # Keep plural for backward compatibility
            "market-data": SimpleRateLimiter(calls_per_second=10), # Market data alias
            "economic": SimpleRateLimiter(calls_per_second=5),   # Economic data
            "default": SimpleRateLimiter(calls_per_second=5)     # 5 calls/sec default
        }
        
    async def acquire(self, dataset_class: str = "default"):
        """Acquire permission to make an API call"""
        limiter = self.limiters.get(dataset_class, self.limiters["default"])
        await limiter.acquire()
        
    def get_status(self) -> Dict[str, float]:
        """Get current rate limiter status"""
        return {
            name: limiter.calls_per_second 
            for name, limiter in self.limiters.items()
        }