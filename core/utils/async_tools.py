"""
Async Utilities for Parallel Execution
Status: Production
Created: October 2025

PURPOSE: Shared async helpers for concurrent task execution with fallback.
Accepts callables (task factories) to enable sequential retry on failure.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# Try to get default concurrency limit from config at import time
_default_limit: Optional[int] = None
try:
    from core.config import get_config
    _default_limit = get_config().async_concurrency_limit
except Exception:
    # Config not initialized yet - fall back to unlimited
    _default_limit = None


async def run_parallel(
    task_factories: Iterable[Callable[[], Awaitable[Any]]],
    *,
    concurrency_limit: Optional[int] = None,
    on_error: Optional[Callable[[BaseException], Awaitable[None]]] = None,
) -> List[Any]:
    """
    Execute async tasks in parallel with optional concurrency limit and sequential fallback.

    Args:
        task_factories: Iterable of callables that return awaitables (task factories).
                       Using factories allows sequential retry if parallel execution fails.
        concurrency_limit: Maximum concurrent tasks. None uses config default or unlimited.
        on_error: Optional async callback for error handling.

    Returns:
        List of results in original order.

    Raises:
        Exception: If all tasks fail or sequential fallback fails.

    Example:
        >>> async def fetch_data(url: str):
        ...     return await client.get(url)
        >>> factories = [lambda u=url: fetch_data(u) for url in urls]
        >>> results = await run_parallel(factories, concurrency_limit=5)
    """
    # Convert to list immediately for reuse in fallback
    factories = list(task_factories)

    if not factories:
        return []

    # Use provided limit, or fall back to config default, or unlimited
    limit = concurrency_limit if concurrency_limit is not None else _default_limit

    # Try parallel execution with concurrency limit
    tasks: List[asyncio.Task] = []
    try:
        if limit and limit > 0:
            # Use semaphore to limit concurrency
            semaphore = asyncio.Semaphore(limit)

            async def limited_task(factory: Callable[[], Awaitable[Any]]) -> Any:
                async with semaphore:
                    return await factory()

            tasks = [asyncio.create_task(limited_task(f)) for f in factories]
        else:
            # No limit - execute all in parallel
            tasks = [asyncio.create_task(f()) for f in factories]

        results = await asyncio.gather(*tasks)
        logger.debug(f"Parallel execution completed: {len(results)} tasks")
        return results

    except Exception as e:
        logger.warning(f"Parallel execution failed: {e}. Cancelling in-flight tasks and falling back to sequential.")

        # Cancel any in-flight tasks to prevent lingering coroutines
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for all cancellations to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Call error handler if provided
        if on_error:
            try:
                await on_error(e)
            except Exception as handler_error:
                logger.error(f"Error handler failed: {handler_error}")

        # Sequential fallback - call each factory fresh to get new coroutines
        results = []
        for i, factory in enumerate(factories):
            try:
                result = await factory()
                results.append(result)
            except Exception as task_error:
                logger.error(f"Task {i} failed in sequential fallback: {task_error}")
                # Call error handler for each task failure
                if on_error:
                    try:
                        await on_error(task_error)
                    except Exception as handler_error:
                        logger.error(f"Error handler failed: {handler_error}")
                raise  # Re-raise to fail fast

        logger.debug(f"Sequential fallback completed: {len(results)} tasks")
        return results


async def gather_dict(
    task_dict: Dict[str, Callable[[], Awaitable[Any]]],
    *,
    concurrency_limit: Optional[int] = None,
    on_error: Optional[Callable[[BaseException], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """
    Execute dict of async task factories in parallel, returning dict of results.

    Args:
        task_dict: Dict mapping keys to task factory callables.
        concurrency_limit: Maximum concurrent tasks. None uses config default or unlimited.
        on_error: Optional async callback for error handling.

    Returns:
        Dict mapping keys to results in original key order.

    Example:
        >>> factories = {
        ...     "profile": lambda: fetch_profile(user_id),
        ...     "orders": lambda: fetch_orders(user_id),
        ...     "settings": lambda: fetch_settings(user_id),
        ... }
        >>> results = await gather_dict(factories, concurrency_limit=3)
        >>> print(results["profile"], results["orders"])
    """
    if not task_dict:
        return {}

    # Extract keys and factories in order
    keys = list(task_dict.keys())
    factories = [task_dict[k] for k in keys]

    # Run parallel execution with same on_error for consistent logging/fallback
    results = await run_parallel(
        factories,
        concurrency_limit=concurrency_limit,
        on_error=on_error,
    )

    # Zip keys back to results
    return dict(zip(keys, results))
