"""
Error handling utilities for production-ready API calls.
Includes retry with exponential backoff and circuit breaker pattern.
"""
import time
import random
import logging
from functools import wraps
from typing import Optional, Tuple, Type, Union
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Track circuit breaker states
circuit_breaker_states = defaultdict(lambda: {"failures": 0, "last_failure": None, "state": "closed"})


class RetryableError(Exception):
    """Base class for errors that should trigger retry"""
    pass


class RateLimitError(RetryableError):
    """API rate limit exceeded"""
    pass


class TimeoutError(RetryableError):
    """Request timeout"""
    pass


class NetworkError(RetryableError):
    """Network connectivity issues"""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    max_delay: float = 16.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (RetryableError,)
):
    """
    Decorator for exponential backoff retry with jitter.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        max_delay: Maximum delay between retries in seconds
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exceptions that trigger retry
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    # Check circuit breaker
                    if not _check_circuit_breaker(func.__name__):
                        raise NetworkError(f"Circuit breaker open for {func.__name__}")
                    
                    # Try the function
                    result = await func(*args, **kwargs)
                    
                    # Reset circuit breaker on success
                    _reset_circuit_breaker(func.__name__)
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Update circuit breaker
                    _update_circuit_breaker(func.__name__)
                    
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(backoff_factor ** attempt, max_delay)
                    
                    # Add jitter if enabled
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s. Error: {e}"
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    # Check circuit breaker
                    if not _check_circuit_breaker(func.__name__):
                        raise NetworkError(f"Circuit breaker open for {func.__name__}")
                    
                    # Try the function
                    result = func(*args, **kwargs)
                    
                    # Reset circuit breaker on success
                    _reset_circuit_breaker(func.__name__)
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Update circuit breaker
                    _update_circuit_breaker(func.__name__)
                    
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(backoff_factor ** attempt, max_delay)
                    
                    # Add jitter if enabled
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s. Error: {e}"
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def _check_circuit_breaker(func_name: str, threshold: int = 5, timeout: int = 60) -> bool:
    """
    Check if circuit breaker allows the call.
    
    Args:
        func_name: Name of the function
        threshold: Number of failures before opening circuit
        timeout: Seconds before attempting to close circuit
    
    Returns:
        True if call is allowed, False if circuit is open
    """
    state = circuit_breaker_states[func_name]
    
    if state["state"] == "open":
        # Check if timeout has passed
        if state["last_failure"] and \
           datetime.now() - state["last_failure"] > timedelta(seconds=timeout):
            # Try to close the circuit
            state["state"] = "half-open"
            logger.info(f"Circuit breaker for {func_name} moving to half-open")
            return True
        return False
    
    return True


def _update_circuit_breaker(func_name: str, threshold: int = 5):
    """Update circuit breaker state on failure"""
    state = circuit_breaker_states[func_name]
    state["failures"] += 1
    state["last_failure"] = datetime.now()
    
    if state["failures"] >= threshold and state["state"] != "open":
        state["state"] = "open"
        logger.error(f"Circuit breaker opened for {func_name} after {threshold} failures")


def _reset_circuit_breaker(func_name: str):
    """Reset circuit breaker on success"""
    state = circuit_breaker_states[func_name]
    if state["state"] == "half-open":
        logger.info(f"Circuit breaker for {func_name} closed after successful call")
    state["failures"] = 0
    state["state"] = "closed"
    state["last_failure"] = None