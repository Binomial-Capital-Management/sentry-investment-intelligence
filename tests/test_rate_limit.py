"""
Unit tests for rate_limit.py - Sliding window rate limiter.

Tests cover:
- RateLimiter class behavior
- Sliding window algorithm
- check_rate_limit helper function
- Edge cases: window expiry, multiple users
"""
import pytest
import time
from unittest.mock import patch

from core.utils.rate_limit import (
    RateLimiter,
    check_rate_limit,
    get_rate_limit_info,
    _limiters,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clear_limiters():
    """Clear global limiters before each test."""
    _limiters.clear()
    yield
    _limiters.clear()


# =============================================================================
# RateLimiter Class Tests
# =============================================================================

class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.is_allowed("user1") is True

    def test_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # Use up the limit
        for _ in range(3):
            assert limiter.is_allowed("user1") is True
        
        # 4th request should be blocked
        assert limiter.is_allowed("user1") is False

    def test_separate_keys_have_separate_limits(self):
        """Test that different keys have independent limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # User1 uses up limit
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False
        
        # User2 should still have full limit
        assert limiter.is_allowed("user2") is True
        assert limiter.is_allowed("user2") is True

    def test_sliding_window_expiry(self):
        """Test that old requests expire from the window."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)  # 1 second window
        
        # Use up limit
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again
        assert limiter.is_allowed("user1") is True

    def test_get_remaining_full(self):
        """Test get_remaining when no requests made."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        assert limiter.get_remaining("new_user") == 5

    def test_get_remaining_partial(self):
        """Test get_remaining after some requests."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        
        assert limiter.get_remaining("user1") == 3

    def test_get_remaining_empty(self):
        """Test get_remaining when limit exhausted."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        
        assert limiter.get_remaining("user1") == 0

    def test_get_reset_time_no_requests(self):
        """Test get_reset_time when no requests made."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        assert limiter.get_reset_time("new_user") == 0

    def test_get_reset_time_with_requests(self):
        """Test get_reset_time after requests."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        limiter.is_allowed("user1")
        
        reset_time = limiter.get_reset_time("user1")
        # Should be close to 60 seconds (window size)
        assert 59 <= reset_time <= 60


# =============================================================================
# check_rate_limit Helper Tests
# =============================================================================

class TestCheckRateLimit:
    """Tests for the check_rate_limit helper function."""

    def test_creates_limiter_on_first_call(self):
        """Test that limiter is created for new action."""
        assert "new_action" not in _limiters
        
        result = check_rate_limit("user1", "new_action", limit=5, window=60)
        
        assert result is True
        assert "new_action" in _limiters

    def test_respects_limit_parameter(self):
        """Test that limit parameter is respected."""
        # Set limit to 2
        assert check_rate_limit("user1", "action1", limit=2, window=60) is True
        assert check_rate_limit("user1", "action1", limit=2, window=60) is True
        assert check_rate_limit("user1", "action1", limit=2, window=60) is False

    def test_user_id_scoping(self):
        """Test that user_id creates separate rate limit buckets."""
        # User1 exhausts limit
        check_rate_limit("user1", "action1", limit=1, window=60)
        assert check_rate_limit("user1", "action1", limit=1, window=60) is False
        
        # User2 should have separate limit
        assert check_rate_limit("user2", "action1", limit=1, window=60) is True

    def test_action_scoping(self):
        """Test that different actions have separate limits."""
        # Exhaust limit for action1
        check_rate_limit("user1", "action1", limit=1, window=60)
        assert check_rate_limit("user1", "action1", limit=1, window=60) is False
        
        # action2 should have separate limit
        assert check_rate_limit("user1", "action2", limit=1, window=60) is True


# =============================================================================
# get_rate_limit_info Tests
# =============================================================================

class TestGetRateLimitInfo:
    """Tests for the get_rate_limit_info function."""

    def test_info_for_new_action(self):
        """Test info when no limiter exists."""
        info = get_rate_limit_info("user1", "nonexistent_action")
        
        assert info["remaining"] == 10  # default
        assert info["reset_in"] == 0

    def test_info_after_requests(self):
        """Test info after making some requests."""
        check_rate_limit("user1", "test_action", limit=5, window=60)
        check_rate_limit("user1", "test_action", limit=5, window=60)
        
        info = get_rate_limit_info("user1", "test_action")
        
        assert info["remaining"] == 3
        assert info["reset_in"] > 0


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_limit(self):
        """Test behavior with zero limit (always blocked)."""
        limiter = RateLimiter(max_requests=0, window_seconds=60)
        
        assert limiter.is_allowed("user1") is False

    def test_very_short_window(self):
        """Test with very short window (100ms)."""
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False
        
        time.sleep(0.15)
        
        assert limiter.is_allowed("user1") is True

    def test_rapid_requests(self):
        """Test rapid sequential requests."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        
        # Make 100 rapid requests
        for _ in range(100):
            assert limiter.is_allowed("user1") is True
        
        # 101st should be blocked
        assert limiter.is_allowed("user1") is False

    def test_limiter_reuse(self):
        """Test that limiter is reused for same action."""
        check_rate_limit("user1", "reuse_test", limit=5, window=60)
        
        limiter1_id = id(_limiters["reuse_test"])
        
        check_rate_limit("user1", "reuse_test", limit=5, window=60)
        
        limiter2_id = id(_limiters["reuse_test"])
        
        assert limiter1_id == limiter2_id  # Same object

    def test_concurrent_users_stress(self):
        """Test with many concurrent users."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # 100 users each making 3 requests
        for user_num in range(100):
            user_key = f"user_{user_num}"
            for _ in range(3):
                assert limiter.is_allowed(user_key) is True
            # 4th request should fail
            assert limiter.is_allowed(user_key) is False
