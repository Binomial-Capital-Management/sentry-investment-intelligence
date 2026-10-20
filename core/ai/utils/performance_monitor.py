"""
Performance monitoring utilities for tracking execution times and metrics.
Simple decorators for timing and logging slow operations.
"""
import time
import functools
import logging
from typing import Dict, Any, Callable, List
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Track performance metrics across the application.
    """
    
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0,
            "slow_queries": [],
        })
        self.slow_threshold = 2.0  # seconds
    
    def record_timing(self, 
                     operation: str, 
                     elapsed: float,
                     context: Dict[str, Any] = None):
        """Record timing for an operation"""
        metric = self.metrics[operation]
        
        # Update basic metrics
        metric["count"] += 1
        metric["total_time"] += elapsed
        metric["min_time"] = min(metric["min_time"], elapsed)
        metric["max_time"] = max(metric["max_time"], elapsed)
        
        # Track slow queries
        if elapsed > self.slow_threshold:
            slow_entry = {
                "elapsed": elapsed,
                "timestamp": time.time(),
                "context": context or {}
            }
            metric["slow_queries"].append(slow_entry)
            
            # Keep only last 10 slow queries
            if len(metric["slow_queries"]) > 10:
                metric["slow_queries"] = metric["slow_queries"][-10:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics"""
        summary = {}
        
        for operation, metric in self.metrics.items():
            count = metric["count"]
            if count > 0:
                avg_time = metric["total_time"] / count
                summary[operation] = {
                    "count": count,
                    "avg_time": f"{avg_time:.3f}s",
                    "min_time": f"{metric['min_time']:.3f}s",
                    "max_time": f"{metric['max_time']:.3f}s",
                    "total_time": f"{metric['total_time']:.3f}s",
                    "slow_queries_count": len(metric["slow_queries"]),
                }
        
        return summary
    
    def get_slow_queries(self, operation: str = None) -> List[Dict[str, Any]]:
        """Get slow queries for specific operation or all operations"""
        if operation:
            return self.metrics[operation]["slow_queries"]
        
        # Get all slow queries
        all_slow = []
        for op, metric in self.metrics.items():
            for query in metric["slow_queries"]:
                all_slow.append({
                    "operation": op,
                    **query
                })
        
        # Sort by timestamp
        return sorted(all_slow, key=lambda x: x["timestamp"], reverse=True)


# Global instance
performance_monitor = PerformanceMonitor()


def time_operation(operation_name: str = None):
    """
    Decorator to time function execution.
    
    Args:
        operation_name: Name for the operation (defaults to function name)
    """
    def decorator(func: Callable):
        name = operation_name or func.__name__
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            context = {"args": str(args)[:100], "kwargs": str(kwargs)[:100]}
            
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                
                # Record timing
                performance_monitor.record_timing(name, elapsed, context)
                
                # Log if slow
                if elapsed > performance_monitor.slow_threshold:
                    logger.warning(f"Slow operation '{name}' took {elapsed:.2f}s")
                else:
                    logger.debug(f"Operation '{name}' completed in {elapsed:.2f}s")
                
                return result
                
            except Exception as e:
                elapsed = time.time() - start_time
                context["error"] = str(e)
                performance_monitor.record_timing(name, elapsed, context)
                logger.error(f"Operation '{name}' failed after {elapsed:.2f}s: {e}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            context = {"args": str(args)[:100], "kwargs": str(kwargs)[:100]}
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                
                # Record timing
                performance_monitor.record_timing(name, elapsed, context)
                
                # Log if slow
                if elapsed > performance_monitor.slow_threshold:
                    logger.warning(f"Slow operation '{name}' took {elapsed:.2f}s")
                else:
                    logger.debug(f"Operation '{name}' completed in {elapsed:.2f}s")
                
                return result
                
            except Exception as e:
                elapsed = time.time() - start_time
                context["error"] = str(e)
                performance_monitor.record_timing(name, elapsed, context)
                logger.error(f"Operation '{name}' failed after {elapsed:.2f}s: {e}")
                raise
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class Timer:
    """Context manager for timing code blocks"""
    
    def __init__(self, operation_name: str, context: Dict[str, Any] = None):
        self.operation_name = operation_name
        self.context = context or {}
        self.start_time = None
        self.elapsed = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time
        
        if exc_type:
            self.context["error"] = str(exc_val)
        
        performance_monitor.record_timing(
            self.operation_name,
            self.elapsed,
            self.context
        )
        
        if self.elapsed > performance_monitor.slow_threshold:
            logger.warning(f"Slow block '{self.operation_name}' took {self.elapsed:.2f}s")
        
        # Don't suppress exceptions
        return False


# Example usage functions
@time_operation("fetch_market_data")
async def example_fetch_data(ticker: str) -> Dict[str, Any]:
    """Example function showing decorator usage"""
    # Simulate API call
    await asyncio.sleep(0.1)
    return {"ticker": ticker, "price": 100.0}


def example_with_timer():
    """Example showing context manager usage"""
    with Timer("data_processing", {"size": 1000}) as timer:
        # Simulate processing
        time.sleep(0.05)
        # Can access elapsed time
        print(f"Processing took {timer.elapsed:.3f}s")