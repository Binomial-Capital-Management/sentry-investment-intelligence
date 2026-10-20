"""
Simple in-memory rate limiter using sliding window algorithm.

This is a per-instance limiter suitable for single-instance deployments.
For multi-instance deployments (e.g., ECS with multiple tasks), upgrade to
a Redis-backed implementation.

Usage:
    from core.utils.rate_limit import check_rate_limit
    
    if not check_rate_limit(user_id, "workspace_actions", limit=10, window=60):
        return {"status": "error", "message": "Rate limit exceeded"}
"""
import time
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter with sliding window algorithm.
    
    Tracks request timestamps per key and enforces limits within
    a rolling time window.
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Size of the sliding window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, key: str) -> bool:
        """
        Check if a request is allowed for the given key.
        
        If allowed, records the request timestamp.
        
        Args:
            key: Identifier for rate limiting (e.g., "user_123:add_dataset")
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = time.time()
        
        # Initialize key if not seen before
        if key not in self._requests:
            self._requests[key] = []
        
        # Clean up old requests outside the window
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
        
        # Check if limit exceeded
        if len(self._requests[key]) >= self.max_requests:
            logger.debug(f"Rate limit exceeded for {key}: {len(self._requests[key])}/{self.max_requests} in {self.window_seconds}s")
            return False
        
        # Record this request
        self._requests[key].append(now)
        return True
    
    def get_remaining(self, key: str) -> int:
        """Get remaining requests allowed for a key."""
        now = time.time()
        cutoff = now - self.window_seconds
        
        if key not in self._requests:
            return self.max_requests
        
        # Count requests in current window
        current_count = len([t for t in self._requests[key] if t > cutoff])
        return max(0, self.max_requests - current_count)
    
    def get_reset_time(self, key: str) -> float:
        """Get seconds until the rate limit resets (oldest request expires)."""
        now = time.time()
        cutoff = now - self.window_seconds
        
        if key not in self._requests:
            return 0
        
        # Find oldest request still in window
        in_window = [t for t in self._requests[key] if t > cutoff]
        if not in_window:
            return 0
        
        oldest = min(in_window)
        return max(0, oldest + self.window_seconds - now)


# =============================================================================
# Global limiters by action type
# =============================================================================

_limiters: Dict[str, RateLimiter] = {}


def check_rate_limit(
    user_id: str,
    action: str,
    limit: int = 10,
    window: int = 60
) -> bool:
    """
    Check if user is within rate limit for an action.
    
    Creates a limiter for the action if one doesn't exist.
    
    Args:
        user_id: User identifier
        action: Action name (e.g., "workspace_actions", "add_dataset")
        limit: Max requests per window (default: 10)
        window: Window size in seconds (default: 60)
    
    Returns:
        True if allowed, False if rate limit exceeded
    
    Example:
        if not check_rate_limit(user_id, "workspace_actions", limit=10, window=60):
            return {"status": "error", "message": "Rate limit exceeded. Wait 60 seconds."}
    """
    # Get or create limiter for this action
    limiter_key = action
    if limiter_key not in _limiters:
        _limiters[limiter_key] = RateLimiter(limit, window)
    
    # Check rate limit using user-specific key
    user_key = f"{user_id}:{action}"
    return _limiters[limiter_key].is_allowed(user_key)


def get_rate_limit_info(user_id: str, action: str) -> Dict:
    """
    Get rate limit information for a user/action.
    
    Returns:
        Dict with remaining requests and reset time
    """
    limiter_key = action
    if limiter_key not in _limiters:
        return {"remaining": 10, "reset_in": 0}
    
    limiter = _limiters[limiter_key]
    user_key = f"{user_id}:{action}"
    
    return {
        "remaining": limiter.get_remaining(user_key),
        "reset_in": round(limiter.get_reset_time(user_key), 1),
    }
