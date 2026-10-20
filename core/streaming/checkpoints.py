"""
SSE checkpoint storage for stream resumption.

Provides Redis-backed and in-memory implementations with a common interface.
"""
from abc import ABC, abstractmethod
from collections import deque
from typing import AsyncIterator, Any
import json
import time
import logging

import numpy as np

logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert numpy arrays, datetime, and other non-JSON types to JSON-serializable format.
    Prevents 'Object of type ndarray/datetime is not JSON serializable' errors.
    """
    from datetime import datetime, date
    
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif hasattr(obj, 'item') and callable(obj.item):  # numpy scalar
        try:
            return obj.item()
        except (ValueError, AttributeError):
            return obj
    elif isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    return obj


class CheckpointStore(ABC):
    """Abstract base for SSE checkpoint storage."""

    supports_cross_worker: bool = False

    @abstractmethod
    async def append(self, message_id: str, event: dict) -> None:
        """Store an event for potential replay."""
        pass

    @abstractmethod
    async def replay(self, message_id: str, after_seq: int) -> AsyncIterator[dict]:
        """Yield events after the given sequence number."""
        pass

    @abstractmethod
    async def clear(self, message_id: str) -> None:
        """Remove all checkpoints for a message."""
        pass


class RedisCheckpointStore(CheckpointStore):
    """Redis-backed checkpoint storage with TTL and size limits."""

    supports_cross_worker = True

    def __init__(self, redis_url: str, ttl_seconds: int, max_events: int, *, strict: bool = False):
        self._redis = None
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._limit = max_events
        self._init_attempted = False
        self._strict = strict
        self._last_failure_ts: float | None = None

    async def _ensure_redis(self):
        """Lazy initialization of Redis connection with graceful degradation."""
        if self._redis is not None:
            return True

        if self._init_attempted and self._last_failure_ts is not None:
            # Allow retries after a short backoff to recover from transient outages
            if time.time() - self._last_failure_ts < 5:
                return False
            self._init_attempted = False

        self._init_attempted = True
        try:
            import redis.asyncio as aioredis

            # AWS ElastiCache TLS configuration
            # For rediss:// URLs, pass ssl_cert_reqs as parameter (not ssl context)
            ssl_params = {}
            if self._redis_url.startswith('rediss://'):
                # AWS ElastiCache doesn't require client certificates
                # Pass ssl_cert_reqs as string parameter per redis-py docs
                ssl_params['ssl_cert_reqs'] = 'none'

            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                **ssl_params
            )
            await self._redis.ping()
            logger.info("Redis checkpoint store initialized successfully")
            self._last_failure_ts = None
            return True
        except Exception as e:
            message = f"Redis unavailable, checkpoints disabled: {e}"
            if self._strict:
                logger.error(message)
                raise RuntimeError(message) from e
            logger.warning(message)
            self._last_failure_ts = time.time()
            return False

    async def append(self, message_id: str, event: dict) -> None:
        try:
            if not await self._ensure_redis():
                return  # Gracefully degrade - no checkpointing

            key = f"checkpoint:{message_id}"

            # Store event with metadata (convert numpy arrays to lists)
            event_data = json.dumps(_make_json_serializable({
                "id": event.get("id", 0),
                "type": event.get("type"),
                "data": event.get("data"),
                "sse_event": event.get("sse_event"),
                "timestamp": time.time()
            }))

            # Append to list
            await self._redis.rpush(key, event_data)

            # Set TTL (refreshes on each append)
            await self._redis.expire(key, self._ttl)

            # Trim to max size (keep most recent)
            await self._redis.ltrim(key, -self._limit, -1)

        except Exception as e:
            logger.warning(f"Failed to append checkpoint to Redis: {e}")

    async def replay(self, message_id: str, after_seq: int) -> AsyncIterator[dict]:
        try:
            if not await self._ensure_redis():
                return  # No replay data available

            key = f"checkpoint:{message_id}"

            # Fetch all events
            events_raw = await self._redis.lrange(key, 0, -1)

            # Filter and yield events after sequence
            for event_str in events_raw:
                event = json.loads(event_str)
                if event.get("id", 0) > after_seq:
                    yield event

        except Exception as e:
            logger.warning(f"Failed to replay from Redis: {e}")

    async def clear(self, message_id: str) -> None:
        try:
            if not await self._ensure_redis():
                return  # Nothing to clear

            key = f"checkpoint:{message_id}"
            await self._redis.delete(key)
        except Exception as e:
            logger.warning(f"Failed to clear Redis checkpoint: {e}")


class MemoryCheckpointStore(CheckpointStore):
    """In-memory checkpoint storage with automatic expiration."""

    def __init__(self, ttl_seconds: int, max_events: int):
        self._store: dict[str, dict] = {}
        self._ttl = ttl_seconds
        self._limit = max_events
        logger.info("Memory checkpoint store initialized")

    def _cleanup_expired(self):
        """Remove expired checkpoints."""
        now = time.time()
        expired = [
            msg_id for msg_id, data in self._store.items()
            if now - data.get("timestamp", 0) > self._ttl
        ]
        for msg_id in expired:
            del self._store[msg_id]

    async def append(self, message_id: str, event: dict) -> None:
        self._cleanup_expired()

        if message_id not in self._store:
            self._store[message_id] = {
                "events": deque(maxlen=self._limit),
                "timestamp": time.time()
            }

        # Add event (convert numpy arrays to lists for consistency)
        self._store[message_id]["events"].append(_make_json_serializable({
            "id": event.get("id", 0),
            "type": event.get("type"),
            "data": event.get("data"),
            "sse_event": event.get("sse_event"),
            "timestamp": time.time()
        }))

        # Update timestamp
        self._store[message_id]["timestamp"] = time.time()

    async def replay(self, message_id: str, after_seq: int) -> AsyncIterator[dict]:
        self._cleanup_expired()

        data = self._store.get(message_id)
        if not data:
            return

        for event in data["events"]:
            if event.get("id", 0) > after_seq:
                yield event

    async def clear(self, message_id: str) -> None:
        self._store.pop(message_id, None)


def create_checkpoint_store(config) -> CheckpointStore:
    """
    Factory function to create appropriate checkpoint store.

    Returns Redis-backed store if redis_url is configured,
    otherwise returns in-memory store.
    """
    ttl = getattr(config, 'stream_checkpoint_ttl_seconds', 300)
    limit = getattr(config, 'stream_checkpoint_limit', 100)

    redis_url = getattr(config, 'redis_url', None)
    require_redis = getattr(config, 'require_redis_for_streaming', False)

    if redis_url:
        try:
            logger.info(f"Creating Redis checkpoint store (TTL={ttl}s, limit={limit})")
            return RedisCheckpointStore(redis_url, ttl, limit, strict=require_redis)
        except Exception as e:
            if require_redis:
                raise
            logger.warning(f"Redis unavailable, falling back to memory: {e}")

    if require_redis:
        raise RuntimeError("REDIS_URL is required for streaming resume in this environment")

    logger.info(f"Creating memory checkpoint store (TTL={ttl}s, limit={limit})")
    return MemoryCheckpointStore(ttl, limit)
