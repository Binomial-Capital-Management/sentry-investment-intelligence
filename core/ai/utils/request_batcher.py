"""
Request batching for efficient API calls at scale.
Groups similar requests within time windows to reduce API calls.
"""
import asyncio
import time
from typing import Dict, List, Any, Callable, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RequestBatcher:
    """
    Batches similar requests within a time window to reduce API calls.
    Future-proofing for high-volume scenarios.
    """
    
    def __init__(self, 
                 batch_window: float = 0.1,  # 100ms window
                 max_batch_size: int = 10):
        """
        Initialize request batcher.
        
        Args:
            batch_window: Time window to collect requests (seconds)
            max_batch_size: Maximum requests per batch
        """
        self.batch_window = batch_window
        self.max_batch_size = max_batch_size
        self.pending_requests = defaultdict(list)
        self.batch_tasks = {}
        self.metrics = {
            "batches_created": 0,
            "requests_batched": 0,
            "requests_individual": 0,
        }
    
    async def batch_request(self,
                           batch_key: str,
                           request_params: Dict[str, Any],
                           fetch_func: Callable) -> Any:
        """
        Add request to batch and wait for result.
        
        Args:
            batch_key: Key to group similar requests (e.g., "market_data")
            request_params: Parameters for this specific request
            fetch_func: Function to call for batch processing
        
        Returns:
            Result for this specific request
        """
        # Create a future for this request
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        # Add to pending requests
        self.pending_requests[batch_key].append((request_params, future))
        
        # Check if we need to start a batch task
        if batch_key not in self.batch_tasks or self.batch_tasks[batch_key].done():
            # Start new batch task
            self.batch_tasks[batch_key] = asyncio.create_task(
                self._process_batch(batch_key, fetch_func)
            )
        
        # Check if batch is full
        if len(self.pending_requests[batch_key]) >= self.max_batch_size:
            # Trigger immediate processing
            if batch_key in self.batch_tasks:
                self.batch_tasks[batch_key].cancel()
            self.batch_tasks[batch_key] = asyncio.create_task(
                self._process_batch(batch_key, fetch_func, immediate=True)
            )
        
        # Wait for result
        try:
            result = await future
            return result
        except Exception as e:
            logger.error(f"Batch request failed: {e}")
            raise
    
    async def _process_batch(self, 
                            batch_key: str, 
                            fetch_func: Callable,
                            immediate: bool = False):
        """Process a batch of requests"""
        if not immediate:
            # Wait for batch window
            await asyncio.sleep(self.batch_window)
        
        # Get all pending requests
        requests = self.pending_requests[batch_key]
        if not requests:
            return
        
        # Clear pending requests
        self.pending_requests[batch_key] = []
        
        # Update metrics
        self.metrics["batches_created"] += 1
        self.metrics["requests_batched"] += len(requests)
        
        logger.info(f"Processing batch of {len(requests)} requests for {batch_key}")
        
        try:
            # Extract all parameters
            all_params = [req[0] for req in requests]
            
            # Call batch function
            results = await fetch_func(all_params)
            
            # Distribute results
            for i, (_, future) in enumerate(requests):
                if i < len(results):
                    future.set_result(results[i])
                else:
                    future.set_exception(Exception("No result returned for request"))
                    
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Set exception for all futures
            for _, future in requests:
                future.set_exception(e)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get batching metrics"""
        total_requests = self.metrics["requests_batched"] + self.metrics["requests_individual"]
        batch_rate = (self.metrics["requests_batched"] / total_requests * 100) \
                    if total_requests > 0 else 0
        
        return {
            **self.metrics,
            "batch_rate": f"{batch_rate:.1f}%",
            "avg_batch_size": (self.metrics["requests_batched"] / self.metrics["batches_created"]) 
                            if self.metrics["batches_created"] > 0 else 0,
        }


# Example batch functions for MCP servers
async def batch_market_data(requests: List[Dict[str, Any]]) -> List[Any]:
    """
    Example: Batch market data requests.
    In reality, this would call Yahoo Finance batch API.
    """
    # Extract all tickers
    tickers = [req.get("ticker") for req in requests]
    
    # Simulated batch API call
    # results = await yahoo_finance.get_batch(tickers)
    
    # For now, return placeholder
    return [{"ticker": ticker, "price": 100.0} for ticker in tickers]


async def batch_economic_data(requests: List[Dict[str, Any]]) -> List[Any]:
    """
    Example: Batch economic data requests.
    In reality, this would call FRED batch API.
    """
    # Extract all series
    series_ids = [req.get("series_id") for req in requests]
    
    # Simulated batch API call
    # results = await fred.get_batch(series_ids)
    
    # For now, return placeholder
    return [{"series_id": sid, "value": 2.5} for sid in series_ids]


# Global instance
request_batcher = RequestBatcher()