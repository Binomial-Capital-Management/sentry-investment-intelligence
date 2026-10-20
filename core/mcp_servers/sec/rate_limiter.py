"""
Rate limiter for SEC API requests
Following SEC EDGAR rate limit requirements
"""

import asyncio
import time
import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for SEC API requests"""
    
    def __init__(self, requests_per_second: float = 3.0):
        self.rate = requests_per_second
        self.last_request = 0
        self.backoff_until = 0
        
    async def acquire(self):
        """Wait if needed to respect rate limit"""
        now = time.time()
        
        # Handle backoff from 429
        if now < self.backoff_until:
            await asyncio.sleep(self.backoff_until - now)
            
        # Normal rate limiting
        time_since_last = now - self.last_request
        if time_since_last < (1.0 / self.rate):
            await asyncio.sleep((1.0 / self.rate) - time_since_last)
            
        self.last_request = time.time()
        
    def handle_429(self, response_headers: Dict):
        """Respect Retry-After header (supports both delta-seconds and HTTP-date), fallback to 60s"""
        retry_after = response_headers.get('Retry-After', '60')
        
        # Try to parse as integer (delta-seconds)
        try:
            retry_seconds = int(retry_after)
        except ValueError:
            # Try to parse as HTTP-date (RFC 7231)
            try:
                from email.utils import parsedate_to_datetime
                retry_time = parsedate_to_datetime(retry_after)
                retry_seconds = max(0, (retry_time - datetime.now(retry_time.tzinfo)).total_seconds())
            except (ImportError, TypeError, ValueError):
                # Fallback to 60 seconds if we can't parse
                retry_seconds = 60
                logger.debug(f"Could not parse Retry-After header: {retry_after}, using 60s fallback")
            
        self.backoff_until = time.time() + retry_seconds
        logger.warning(f"Rate limited, backing off for {retry_seconds} seconds")