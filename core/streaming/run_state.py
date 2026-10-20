"""
Shared run state storage for SSE streaming.

Provides Redis-backed and in-memory implementations so multiple workers can
publish and consume streaming events consistently.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from contextlib import suppress
from datetime import datetime, date
from typing import Any, AsyncIterator, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """Convert non-JSON types (datetime, numpy) to serializable format."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif hasattr(obj, 'item') and callable(obj.item):
        try:
            return obj.item()
        except (ValueError, AttributeError):
            return obj
    elif isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    return obj


class RunStateStore(ABC):
    """Abstract base for run state storage."""

    supports_pubsub: bool = False

    @abstractmethod
    async def mark_active(self, message_id: str, session_id: Optional[str]) -> None:
        """Persist that a run has started."""

    @abstractmethod
    async def mark_progress(
        self,
        message_id: str,
        seq: int,
        payload: Dict[str, Any],
        sse_event: Optional[str],
    ) -> None:
        """Record last sequence and publish the payload."""

    @abstractmethod
    async def mark_done(self, message_id: str, status: str, seq: int) -> None:
        """Mark the run as finished."""

    @abstractmethod
    async def get_state(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Fetch stored state."""

    @abstractmethod
    async def clear(self, message_id: str) -> None:
        """Remove run state."""

    @abstractmethod
    async def listen(
        self,
        message_id: str,
        starting_seq: int,
        cancel_flag: Optional[asyncio.Event],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream published events with sequence greater than starting_seq."""


class RedisRunStateStore(RunStateStore):
    """Redis-backed run state and pub/sub."""

    def __init__(self, redis_url: str, ttl_seconds: int, *, strict: bool = False):
        self.supports_pubsub = True
        self._redis = None
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._init_attempted = False
        self._strict = strict
        self._last_failure_ts: float | None = None

    async def _ensure(self) -> bool:
        if self._redis is not None:
            return True
        if self._init_attempted and self._last_failure_ts is not None:
            if time.time() - self._last_failure_ts < 5:
                return False
            self._init_attempted = False
        self._init_attempted = True
        try:
            import redis.asyncio as aioredis  # noqa: WPS433

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
            logger.info("Redis run-state store initialised successfully")
            self._last_failure_ts = None
            return True
        except Exception as exc:  # noqa: BLE001
            message = f"Redis unavailable for run-state store: {exc}"
            if self._strict:
                logger.error(message)
                raise RuntimeError(message) from exc
            logger.warning(message)
            self._last_failure_ts = time.time()
            return False

    def _state_key(self, message_id: str) -> str:
        return f"runstate:{message_id}"

    def _channel(self, message_id: str) -> str:
        return f"stream:{message_id}"

    async def mark_active(self, message_id: str, session_id: Optional[str]) -> None:
        if not await self._ensure():
            return
        state = {
            "status": "running",
            "session_id": session_id,
            "last_seq": 0,
            "updated_at": time.time(),
        }
        try:
            await self._redis.set(
                self._state_key(message_id),
                json.dumps(state),
                ex=self._ttl,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to write run state: %s", exc)

    async def mark_progress(
        self,
        message_id: str,
        seq: int,
        payload: Dict[str, Any],
        sse_event: Optional[str],
    ) -> None:
        if not await self._ensure():
            return
        try:
            current = await self._redis.get(self._state_key(message_id))
            state = json.loads(current) if current else {}
            state.update(
                {
                    "last_seq": seq,
                    "status": state.get("status", "running"),
                    "updated_at": time.time(),
                },
            )
            await self._redis.set(
                self._state_key(message_id),
                json.dumps(state),
                ex=self._ttl,
            )
            event = {
                "id": seq,
                "data": _make_json_serializable(payload),
                "sse_event": sse_event,
            }
            await self._redis.publish(self._channel(message_id), json.dumps(event))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to publish run event: %s", exc)

    async def mark_done(self, message_id: str, status: str, seq: int) -> None:
        if not await self._ensure():
            return
        try:
            current = await self._redis.get(self._state_key(message_id))
            state = json.loads(current) if current else {}
            state.update(
                {
                    "status": status,
                    "done": True,
                    "last_seq": seq,
                    "updated_at": time.time(),
                },
            )
            await self._redis.set(
                self._state_key(message_id),
                json.dumps(state),
                ex=self._ttl,
            )
            await self._redis.publish(
                self._channel(message_id),
                json.dumps({"type": "run_done", "status": status, "id": seq}),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to mark run done: %s", exc)

    async def get_state(self, message_id: str) -> Optional[Dict[str, Any]]:
        if not await self._ensure():
            return None
        try:
            data = await self._redis.get(self._state_key(message_id))
            return json.loads(data) if data else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read run state: %s", exc)
            return None

    async def clear(self, message_id: str) -> None:
        if not await self._ensure():
            return
        try:
            await self._redis.delete(self._state_key(message_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to clear run state: %s", exc)

    async def listen(
        self,
        message_id: str,
        starting_seq: int,
        cancel_flag: Optional[asyncio.Event],
    ) -> AsyncIterator[Dict[str, Any]]:
        if not await self._ensure():
            return
        pubsub = self._redis.pubsub()
        channel = self._channel(message_id)
        await pubsub.subscribe(channel)
        try:
            last_seq = starting_seq
            while True:
                if cancel_flag and cancel_flag.is_set():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue
                try:
                    data = json.loads(message["data"])
                except Exception:  # noqa: BLE001
                    continue
                seq = int(data.get("id", 0))
                if seq <= last_seq and data.get("type") != "run_done":
                    continue
                last_seq = seq or last_seq
                yield data
                if data.get("type") == "run_done":
                    break
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe(channel)
            with suppress(Exception):
                await pubsub.close()


class MemoryRunStateStore(RunStateStore):
    """In-process fallback run state store."""

    def __init__(self, ttl_seconds: int):
        self.supports_pubsub = False
        self._ttl = ttl_seconds
        self._state: Dict[str, Dict[str, Any]] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def mark_active(self, message_id: str, session_id: Optional[str]) -> None:
        async with self._lock:
            self._state[message_id] = {
                "status": "running",
                "session_id": session_id,
                "last_seq": 0,
                "updated_at": time.time(),
            }
            self._queues.setdefault(message_id, asyncio.Queue())

    async def mark_progress(
        self,
        message_id: str,
        seq: int,
        payload: Dict[str, Any],
        sse_event: Optional[str],
    ) -> None:
        async with self._lock:
            state = self._state.get(message_id, {})
            state.update(
                {
                    "status": state.get("status", "running"),
                    "last_seq": seq,
                    "updated_at": time.time(),
                },
            )
            self._state[message_id] = state
            queue = self._queues.setdefault(message_id, asyncio.Queue())
            await queue.put({"id": seq, "data": payload, "sse_event": sse_event})

    async def mark_done(self, message_id: str, status: str, seq: int) -> None:
        async with self._lock:
            state = self._state.get(message_id, {})
            state.update(
                {"status": status, "done": True, "last_seq": seq, "updated_at": time.time()},
            )
            self._state[message_id] = state
            queue = self._queues.setdefault(message_id, asyncio.Queue())
            await queue.put({"type": "run_done", "status": status, "id": seq})

    async def get_state(self, message_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            state = self._state.get(message_id)
            return dict(state) if state else None

    async def clear(self, message_id: str) -> None:
        async with self._lock:
            self._state.pop(message_id, None)
            self._queues.pop(message_id, None)

    async def listen(
        self,
        message_id: str,
        starting_seq: int,
        cancel_flag: Optional[asyncio.Event],
    ) -> AsyncIterator[Dict[str, Any]]:
        queue = self._queues.setdefault(message_id, asyncio.Queue())
        last_seq = starting_seq
        while True:
            if cancel_flag and cancel_flag.is_set():
                break
            try:
                data = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            seq = int(data.get("id", 0))
            if seq <= last_seq and data.get("type") != "run_done":
                continue
            last_seq = seq or last_seq
            yield data
            if data.get("type") == "run_done":
                break


def create_run_state_store(config) -> RunStateStore:
    ttl = getattr(config, "runstate_ttl_seconds", 3600)
    redis_url = getattr(config, "runstate_redis_url", None) or getattr(config, "redis_url", None)
    require_redis = getattr(config, "require_redis_for_streaming", False)
    if redis_url:
        try:
            return RedisRunStateStore(redis_url, ttl, strict=require_redis)
        except Exception as exc:  # noqa: BLE001
            if require_redis:
                raise
            logger.warning("Falling back to in-memory run-state store: %s", exc)
    if require_redis:
        raise RuntimeError("REDIS_URL is required for streaming run state in this environment")
    logger.info("Using in-memory run-state store (TTL=%s)", ttl)
    return MemoryRunStateStore(ttl)
