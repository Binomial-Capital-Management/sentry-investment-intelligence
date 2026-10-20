from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse, Response, JSONResponse
from typing import Dict, Any, Optional, AsyncIterator, Set
from datetime import datetime, date
from contextlib import suppress
from dataclasses import dataclass
import asyncio
import json
import uuid
import re
import logging

import numpy as np


class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime, date, and numpy types."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if hasattr(obj, 'item') and callable(obj.item):
            try:
                return obj.item()
            except (ValueError, AttributeError):
                pass
        return super().default(obj)


def safe_json_dumps(obj: Any) -> str:
    """JSON dumps with datetime/numpy support."""
    return json.dumps(obj, cls=SafeJSONEncoder)

from core.config import get_config
from core.streaming.checkpoints import create_checkpoint_store, CheckpointStore
from core.streaming.run_state import create_run_state_store, RunStateStore
from api.models import ChatRequest, ChatResponse, TransformRequest, ClassifyRequest, ExportPdfRequest
from api.orchestrator import get_v6_orchestrator
from api.db import load_recent_history, get_last_user_message, insert_message
from api.utils import resolve_session_id, is_recall_query
from core.database.postgres_client import get_postgres_rls_client
from core.ai.response_processor import extract_structured_response
from core.charts.storage import get_chart
from core.ai.utils.message_compactor import get_provider_from_model
from core.ai.langgraph_utils import trim_sqlite_session_history
from core.integrations.gamma_client import get_gamma_client, build_instructions_from_settings
from api.routers.user_settings import fetch_user_export_style
from core.database.hybrid_session import get_hybrid_session_manager
from core.services.integration_service import get_drive_credential, build_authorized_credentials
from core.integrations.google_drive import get_metadata as drive_get_metadata
from agents import SQLiteSession

config = get_config()
router = APIRouter(prefix="/v6")
logger = logging.getLogger(__name__)

# Track active streaming sessions (session_id -> {"user_id": str | None, "cancel_event": asyncio.Event})
_active_streams: Dict[str, Dict[str, Any]] = {}
_streams_lock = asyncio.Lock()

# Track pending cancellations for sessions that haven't started streaming yet
# (session_id -> {"user_id": str | None, "requested_at": float})
_pending_cancellations: Dict[str, Dict[str, Any]] = {}
_pending_cancel_lock = asyncio.Lock()

# Track cancel flags by session_id - persists even after SSE connection drops
# This allows cancellation to work even if the user refreshes the page mid-request
# (session_id -> {"cancel_event": asyncio.Event, "created_at": float})
_session_cancel_flags: Dict[str, Dict[str, Any]] = {}
_cancel_flags_lock = asyncio.Lock()

# Track active runs by assistant message id (resume support)
_active_run_state: Dict[str, Dict[str, Any]] = {}
_run_state_lock = asyncio.Lock()

# Controllers manage background streaming tasks and live listeners per assistant message.
_run_controllers: Dict[str, "RunController"] = {}


async def _set_run_active(session_id: str, message_id: str) -> None:
    async with _run_state_lock:
        _active_run_state[message_id] = {
            "session_id": session_id,
            "done": False,
            "updated_at": datetime.now().timestamp(),
        }


async def _mark_run_done(message_id: str) -> None:
    async with _run_state_lock:
        state = _active_run_state.get(message_id)
        if state:
            state["done"] = True
            state["updated_at"] = datetime.now().timestamp()


async def _get_run_state(message_id: str) -> Optional[Dict[str, Any]]:
    async with _run_state_lock:
        state = _active_run_state.get(message_id)
        return dict(state) if state else None


def _schedule_run_cleanup(message_id: str, delay_seconds: int) -> None:
    async def _cleanup() -> None:
        try:
            await asyncio.sleep(max(1, delay_seconds))
            async with _run_state_lock:
                _active_run_state.pop(message_id, None)
                _run_controllers.pop(message_id, None)
        except Exception:
            pass

    asyncio.create_task(_cleanup())


@dataclass
class FormattedEvent:
    seq: int
    chunk: str
    payload: Dict[str, Any]
    sse_event: Optional[str] = None


class RunController:
    """Manages background streaming tasks and live listeners."""

    def __init__(self, session_id: str, message_id: str, *, is_remote: bool = False):
        self.session_id = session_id
        self.message_id = message_id
        self.listeners: Set[asyncio.Queue[FormattedEvent]] = set()
        self._listeners_lock = asyncio.Lock()
        self.background_task: Optional[asyncio.Task] = None
        self.done = asyncio.Event()
        self.error: Optional[str] = None
        self.last_seq = 0
        self.is_remote = is_remote

    async def add_listener(self) -> asyncio.Queue[FormattedEvent]:
        queue: asyncio.Queue[FormattedEvent] = asyncio.Queue()
        async with self._listeners_lock:
            self.listeners.add(queue)
        return queue

    async def remove_listener(self, queue: asyncio.Queue[FormattedEvent]) -> None:
        async with self._listeners_lock:
            self.listeners.discard(queue)

    async def broadcast(self, event: FormattedEvent) -> None:
        self.last_seq = max(self.last_seq, event.seq)
        async with self._listeners_lock:
            for listener in tuple(self.listeners):
                listener.put_nowait(event)


async def _register_run_controller(controller: RunController) -> None:
    async with _run_state_lock:
        _run_controllers[controller.message_id] = controller


async def _get_run_controller(message_id: str) -> Optional[RunController]:
    async with _run_state_lock:
        return _run_controllers.get(message_id)


async def _remove_run_controller(message_id: str) -> None:
    async with _run_state_lock:
        _run_controllers.pop(message_id, None)

# Initialize checkpoint store (Redis or in-memory)
checkpoint_store: CheckpointStore = create_checkpoint_store(config)
run_state_store: RunStateStore = create_run_state_store(config)

# Log which store implementations are active (critical for debugging multi-worker resume)
logger.info(
    f"[STREAMING] Store types: checkpoint={type(checkpoint_store).__name__}, "
    f"run_state={type(run_state_store).__name__}"
)


async def register_stream(session_id: str, user_id: Optional[str], is_resume: bool = False) -> asyncio.Event:
    """Register an active stream and return its cancellation flag.
    
    If a cancellation was requested before the stream started (pending cancellation),
    the cancel flag will be pre-set so the stream knows to abort immediately.
    
    NOTE: Pending cancellations expire after 3 seconds to prevent a cancelled message
    from accidentally killing a subsequent NEW message in the same session.
    
    CRITICAL: For resume requests (is_resume=True), we REUSE the existing cancel_flag
    if one exists. This ensures that cancelling a resumed stream also cancels the
    underlying orchestrator task, which is still watching the original cancel_flag.
    """
    import time
    
    # First check if there's an existing cancel_flag for this session (from a dropped connection)
    # This is critical for cancellation to work after page refresh
    async with _cancel_flags_lock:
        existing_flag = _session_cancel_flags.get(session_id)
        if existing_flag and is_resume:
            cancel_flag = existing_flag["cancel_event"]
            logger.info("[stream] Reusing cancel_flag from _session_cancel_flags for session %s (already set=%s)", session_id, cancel_flag.is_set())
            # Update timestamp to keep it alive
            existing_flag["created_at"] = time.time()
            # Also update _active_streams
            async with _streams_lock:
                _active_streams[session_id] = {"user_id": user_id, "cancel_event": cancel_flag}
            return cancel_flag
    
    async with _streams_lock:
        existing = _active_streams.get(session_id)
        if existing and is_resume:
            # REUSE existing cancel_flag for resume requests - the orchestrator is still watching it!
            cancel_flag = existing["cancel_event"]
            logger.info("[stream] Reusing existing cancel_flag for resumed session %s (already set=%s)", session_id, cancel_flag.is_set())
            # Update user_id in case it changed (unlikely but safe)
            existing["user_id"] = user_id
            return cancel_flag
        else:
            # Create new cancel_flag for new requests (not resumes)
            cancel_flag = asyncio.Event()
    
    # Check for pending cancellation before registering
    # Only apply if the pending cancellation is fresh (< 3 seconds old)
    # This prevents a cancelled message from killing a new message sent later
    async with _pending_cancel_lock:
        pending = _pending_cancellations.pop(session_id, None)
        if pending:
            age = time.time() - pending.get("requested_at", 0)
            if age < 3.0:
                logger.info("[cancel] Found fresh pending cancellation for session %s (age=%.2fs), pre-setting cancel flag", session_id, age)
                cancel_flag.set()
            else:
                logger.info("[cancel] Ignoring stale pending cancellation for session %s (age=%.2fs > 3s) - new message likely started", session_id, age)
    
    # Store cancel_flag in both _active_streams and _session_cancel_flags
    # _session_cancel_flags persists even after SSE connection drops (for cancellation during refresh)
    async with _streams_lock:
        _active_streams[session_id] = {"user_id": user_id, "cancel_event": cancel_flag}
        logger.info("[stream] Registered stream for session %s. Total active streams: %d", session_id, len(_active_streams))
    
    async with _cancel_flags_lock:
        _session_cancel_flags[session_id] = {"cancel_event": cancel_flag, "created_at": time.time()}
    
    return cancel_flag


async def mark_stream_cancelled(session_id: str, requester_id: Optional[str]) -> bool:
    """
    Mark the stream as cancelled if the requester owns it.
    Returns True when a stream was cancelled or pending cancellation was registered.
    Returns False only if the session doesn't exist and pending cancellation couldn't be set.
    
    If the stream hasn't started yet, registers a pending cancellation that will
    be applied when the stream starts.
    """
    # First, try to find and cancel an active stream
    async with _streams_lock:
        entry = _active_streams.get(session_id)
        if entry:
            owner_id = entry.get("user_id")
            if owner_id and requester_id != owner_id:
                raise PermissionError("stream ownership mismatch")

            entry["cancel_event"].set()
            logger.info("[cancel] cancellation event set for session %s (from _active_streams)", session_id)
            return True
    
    # Stream not in _active_streams (maybe SSE connection dropped) - check _session_cancel_flags
    # This handles the case where user refreshed the page but orchestrator is still running
    async with _cancel_flags_lock:
        flag_entry = _session_cancel_flags.get(session_id)
        if flag_entry:
            flag_entry["cancel_event"].set()
            logger.info("[cancel] cancellation event set for session %s (from _session_cancel_flags - SSE dropped)", session_id)
            return True
    
    # Stream not found anywhere - register a pending cancellation for when it starts
    async with _pending_cancel_lock:
        import time
        _pending_cancellations[session_id] = {
            "user_id": requester_id,
            "requested_at": time.time()
        }
        logger.info("[cancel] registered pending cancellation for session %s (stream not found)", session_id)
    return True


async def clear_stream(session_id: str) -> None:
    """Remove a stream from tracking."""
    async with _streams_lock:
        removed = _active_streams.pop(session_id, None)
        if removed:
            logger.debug("[stream] Cleared stream for session %s. Remaining active streams: %d", session_id, len(_active_streams))
    # Also clear any pending cancellation for this session
    async with _pending_cancel_lock:
        _pending_cancellations.pop(session_id, None)


async def cleanup_stale_pending_cancellations(max_age_seconds: int = 300) -> int:
    """Remove pending cancellations older than max_age_seconds. Returns count removed."""
    import time
    now = time.time()
    removed = 0
    async with _pending_cancel_lock:
        stale_keys = [
            k for k, v in _pending_cancellations.items()
            if now - v.get("requested_at", 0) > max_age_seconds
        ]
        for k in stale_keys:
            _pending_cancellations.pop(k, None)
            removed += 1
    if removed:
        logger.debug("[cancel] Cleaned up %d stale pending cancellations", removed)
    return removed


async def cleanup_stale_session_cancel_flags(max_age_seconds: int = 300) -> int:
    """Remove session cancel flags older than max_age_seconds. Returns count removed."""
    import time
    now = time.time()
    removed = 0
    async with _cancel_flags_lock:
        stale_keys = [
            k for k, v in _session_cancel_flags.items()
            if now - v.get("created_at", 0) > max_age_seconds
        ]
        for k in stale_keys:
            _session_cancel_flags.pop(k, None)
            removed += 1
    if removed:
        logger.debug("[cancel] Cleaned up %d stale session cancel flags", removed)
    return removed


class EventFormatter:
    """Formats events as SSE with automatic persistence."""

    def __init__(
        self,
        message_id: str,
        checkpoint_store: CheckpointStore,
        run_state: Optional[RunStateStore],
        start_seq: int = 0,
    ):
        self.msg_id = message_id
        self.checkpoint = checkpoint_store
        self.run_state = run_state
        self.seq = start_seq

    async def format(self, payload: Dict[str, Any], *, sse_event: Optional[str] = None) -> FormattedEvent:
        """Format event as SSE, persist checkpoint, and publish run state."""
        self.seq += 1
        record = {
            'id': self.seq,
            'type': payload.get('type'),
            'data': payload,
            'sse_event': sse_event,
        }
        await self.checkpoint.append(self.msg_id, record)
        if self.run_state:
            await self.run_state.mark_progress(self.msg_id, self.seq, payload, sse_event)

        parts = [f"id: {self.msg_id}_{self.seq}"]
        if sse_event:
            parts.append(f"event: {sse_event}")
        parts.append(f"data: {safe_json_dumps(payload)}")
        chunk = "\n".join(parts) + "\n\n"
        return FormattedEvent(seq=self.seq, chunk=chunk, payload=payload, sse_event=sse_event)


def parse_resume_request(request: Request) -> Optional[dict]:
    """Parse resume information from request headers/params."""
    # Try Last-Event-ID header first (browser sends automatically)
    last_event_id = request.headers.get("Last-Event-ID")
    logger.info("[SSE Resume Debug] Last-Event-ID header: %s", last_event_id)
    logger.info("[SSE Resume Debug] All headers: %s", dict(request.headers))

    # Fallback to query params (for manual resume)
    if not last_event_id:
        last_event_id = request.query_params.get("last_event_id")
        logger.info("[SSE Resume Debug] Last-Event-ID from query params: %s", last_event_id)

    resume_message_id = request.query_params.get("resume_message_id")
    resume_last_seq_param = (
        request.query_params.get("resume_last_seq")
        or request.query_params.get("last_seq")
        or request.query_params.get("resume_last_event_seq")
    )

    if last_event_id:
        try:
            parts = last_event_id.rsplit('_', 1)
            if len(parts) == 2:
                return {
                    "msg_id": parts[0],
                    "last_seq": int(parts[1]),
                }
            # If the value is just the message_id, fall back to explicit param or 0
            if len(parts) == 1 and parts[0]:
                seq = 0
                if resume_last_seq_param:
                    try:
                        seq = max(0, int(resume_last_seq_param))
                    except (TypeError, ValueError):
                        seq = 0
                return {
                    "msg_id": parts[0],
                    "last_seq": seq,
                }
        except (ValueError, IndexError):
            logger.warning(f"Invalid Last-Event-ID format: {last_event_id}")

    if resume_message_id:
        seq = 0
        if resume_last_seq_param:
            try:
                seq = max(0, int(resume_last_seq_param))
            except (TypeError, ValueError):
                seq = 0
        return {
            "msg_id": resume_message_id,
            "last_seq": seq,
        }

    return None


async def stream_resume_events(
    checkpoint_store: CheckpointStore,
    run_state_store: RunStateStore,
    message_id: str,
    last_seq: int,
    cancel_flag: Optional[asyncio.Event],
    enable_live: bool = True,
) -> AsyncIterator[FormattedEvent]:
    """Replay checkpoints and stream live events across workers."""
    current_seq = max(0, last_seq)

    async for event in checkpoint_store.replay(message_id, current_seq):
        payload = event.get("data")
        seq_val = event.get("id")
        if payload is None or seq_val is None:
            continue
        try:
            seq_int = int(seq_val)
        except (TypeError, ValueError):
            continue
        if seq_int <= current_seq:
            continue
        current_seq = seq_int
        sse_event = event.get("sse_event")
        lines = [f"id: {message_id}_{seq_int}"]
        if sse_event:
            lines.append(f"event: {sse_event}")
        lines.append(f"data: {safe_json_dumps(payload)}")
        chunk = "\n".join(lines) + "\n\n"
        yield FormattedEvent(seq=seq_int, chunk=chunk, payload=payload, sse_event=sse_event)

    state = await run_state_store.get_state(message_id)
    if not enable_live:
        return
    if state and state.get("status") in {"completed", "cancelled", "error"}:
        return

    async for published in run_state_store.listen(message_id, current_seq, cancel_flag):
        if cancel_flag and cancel_flag.is_set():
            break
        if published.get("type") == "run_done":
            break
        payload = published.get("data")
        if payload is None:
            continue
        try:
            seq_int = int(published.get("id", 0))
        except (TypeError, ValueError):
            continue
        if seq_int <= current_seq:
            continue
        current_seq = seq_int
        sse_event = published.get("sse_event")
        lines = [f"id: {message_id}_{seq_int}"]
        if sse_event:
            lines.append(f"event: {sse_event}")
        lines.append(f"data: {safe_json_dumps(payload)}")
        chunk = "\n".join(lines) + "\n\n"
        yield FormattedEvent(seq=seq_int, chunk=chunk, payload=payload, sse_event=sse_event)
        if payload.get("type") == "done":
            break


async def load_portfolio_context(portfolio_id: Optional[str], user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load portfolio from database and convert to context format."""
    logger.info(f"[load_portfolio_context] Called with portfolio_id={portfolio_id}, user_id={user_id}, enable_postgres={config.enable_postgres}")
    if not user_id or not config.enable_postgres:
        logger.warning(f"[load_portfolio_context] Returning None: user_id={user_id}, enable_postgres={config.enable_postgres}")
        return None

    try:
        pg = await get_postgres_rls_client()
        # If no explicit portfolio_id, try default portfolio
        if portfolio_id:
            portfolio_data = await pg.get_portfolio_by_id(user_id=user_id, portfolio_id=portfolio_id)
            logger.info(f"[load_portfolio_context] get_portfolio_by_id returned: {portfolio_data}")
            if not portfolio_data:
                logger.warning(f"[load_portfolio_context] Portfolio {portfolio_id} not found for user {user_id}")
                return None
        else:
            # Fetch default portfolio
            rows = await pg.get_user_portfolios(user_id)
            default_row = next((r for r in rows if r.get("is_default")), None) if rows else None
            portfolio_data = default_row or (rows[0] if rows else None)
        
        if portfolio_data:
            # Convert to orchestrator format - use config default for portfolio value
            holdings_data = portfolio_data.get("holdings", [])

            # Parse holdings if it's a JSON string (from PostgreSQL JSONB)
            if isinstance(holdings_data, str):
                try:
                    import json
                    holdings_data = json.loads(holdings_data)
                except Exception:
                    holdings_data = []

            # Aggregate lots into summary lines to reduce context bloat
            # Instead of sending all individual lots, we send:
            # - totalQuantity: sum of lot quantities
            # - avgCostBasis: weighted average purchase price
            # - lotCount: number of lots (for reference)
            if holdings_data:
                aggregated_holdings = []
                for h in holdings_data:
                    ticker = h.get("ticker")
                    lots = h.get("lots", [])
                    if lots:
                        total_qty = 0.0
                        total_cost = 0.0
                        for lot in lots:
                            qty = float(lot.get("quantity", 0) or 0)
                            price = float(lot.get("purchasePrice", 0) or 0)
                            total_qty += qty
                            total_cost += qty * price
                        avg_cost = total_cost / total_qty if total_qty > 0 else 0
                        aggregated_holdings.append({
                            "ticker": ticker,
                            "totalQuantity": round(total_qty, 4),
                            "avgCostBasis": round(avg_cost, 2),
                            "lotCount": len(lots),
                        })
                    else:
                        aggregated_holdings.append({"ticker": ticker})
                holdings_data = aggregated_holdings

            # Adjust weights to include cash balance in calculations
            stored_weights = portfolio_data.get("weights", [])
            cash_balance = float(portfolio_data.get("cash_balance", 0) or 0)
            stocks_value = float(portfolio_data.get("value", config.portfolio_value) or 0)
            total_value = stocks_value + cash_balance

            # Stored weights sum to 1.0 (stocks only). Adjust for total portfolio value (stocks + cash)
            if cash_balance > 0 and total_value > 0 and stored_weights:
                adjusted_weights = [w * (stocks_value / total_value) for w in stored_weights]
            else:
                adjusted_weights = stored_weights

            return {
                "tickers": portfolio_data.get("tickers", []),
                "weights": adjusted_weights,
                "value": total_value,  # Already converted to float above
                "cash_balance": cash_balance,  # Already converted to float above
                "holdings": holdings_data if holdings_data else None,
            }
    except Exception as e:
        logger.error(f"Failed to load portfolio {portfolio_id}: {e}")
    
    return None

@router.get("/health")
async def v6_health_check():
    orchestrator = get_v6_orchestrator()
    streaming_ready = (
        getattr(checkpoint_store, "supports_cross_worker", False)
        and getattr(run_state_store, "supports_pubsub", False)
    )
    # Opportunistically clean up stale pending cancellations and cancel flags on health check
    await cleanup_stale_pending_cancellations(max_age_seconds=300)
    await cleanup_stale_session_cancel_flags(max_age_seconds=300)
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "orchestrator": "initialized" if orchestrator else "not initialized",
        "event_loop": "running",
        "streaming": {
            "checkpoint_store": type(checkpoint_store).__name__,
            "run_state_store": type(run_state_store).__name__,
            "require_redis": getattr(config, "require_redis_for_streaming", False),
            "multi_worker_ready": streaming_ready,
        },
    }

@router.get("/metrics")
async def get_metrics():
    orchestrator = get_v6_orchestrator()
    if hasattr(orchestrator, 'get_performance_metrics'):
        return orchestrator.get_performance_metrics()
    return {"message": "Metrics not available"}

@router.post("/classify")
async def v6_classify(request: ClassifyRequest):
    text = (request.message or "").strip().lower()
    if not text:
        return {"type": "search"}
    simple_tokens = config.classify_simple_tokens
    search_tokens = config.classify_search_tokens
    calc_tokens = config.classify_calc_tokens
    if any(tok in text for tok in calc_tokens):
        return {"type": "calculation"}
    if any(tok in text for tok in search_tokens):
        return {"type": "search"}
    if any(tok in text for tok in simple_tokens):
        return {"type": "simple"}
    return {"type": "search"}

@router.post("/transform", response_model=ChatResponse)
async def v6_transform(req: TransformRequest, raw_request: Request):
    session_id = resolve_session_id(req.session_id, dict(raw_request.headers))
    content: Optional[str] = None
    msg_id = req.message_id

    # Fetch content: prefer explicit message_id, else last assistant for session
    from aiosqlite import connect as aiosqlite_connect
    async with aiosqlite_connect(config.conversation_db_path) as db:
        if msg_id:
            async with db.execute("SELECT content FROM messages WHERE id = ? AND role = 'assistant'", (msg_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    content = row[0]
        if content is None:
            async with db.execute(
                "SELECT content FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                content = row[0] if row else None

    if not content:
        raise HTTPException(status_code=400, detail="No assistant content found to transform")

    op = (req.operation or "to_table").lower()
    if op == "to_table":
        lines = [ln.strip(" -\t") for ln in content.splitlines() if ln.strip()]
        rows = []
        for ln in lines:
            if ":" in ln:
                left, right = ln.split(":", 1)
                rows.append((left.strip(), right.strip()))
        if not rows:
            rows = [(str(i+1), ln) for i, ln in enumerate(lines)]
        header = "| Key | Value |\n|---|---|\n"
        body = "\n".join([f"| {k} | {v} |" for k, v in rows])
        transformed = header + body
    else:
        transformed = content

    assistant_msg_id = uuid.uuid4().hex
    await insert_message(assistant_msg_id, session_id, 'assistant', transformed, datetime.now().isoformat())

    return ChatResponse(
        response=transformed,
        sources=None,
        charts=None,
        metrics=None,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        message_id=assistant_msg_id,
    )

@router.post("/chat", response_model=ChatResponse)
async def v6_chat(
    request: ChatRequest,
    raw_request: Request
):
    orchestrator = get_v6_orchestrator()

    session_id = resolve_session_id(request.session_id, dict(raw_request.headers))

    # Use user_id from RLS middleware (handles both dev and real auth)
    user_id = getattr(raw_request.state, 'user_id', None)

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(raw_request.state, 'org_id', None)

    user_msg_id = uuid.uuid4().hex

    # Save user message to PostgreSQL with RLS
    if config.enable_postgres and user_id:
        try:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                await conn.execute(
                    """
                    INSERT INTO chat_messages (id, session_id, user_id, org_id, role, content, created_at)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
                    """,
                    uuid.UUID(user_msg_id), uuid.UUID(session_id), user_id, org_id, 'user', request.message, datetime.now()
                )
        except Exception as e:
            logger.error(f"Failed to save user message to PostgreSQL: {e}")
            # Fallback to SQLite
            await insert_message(user_msg_id, session_id, 'user', request.message, datetime.now().isoformat())
    else:
        await insert_message(user_msg_id, session_id, 'user', request.message, datetime.now().isoformat())

    # Ensure a chat_sessions row exists for this session_id (so it appears on refresh)
    if config.enable_postgres and user_id and session_id:
        try:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                try:
                    # Create session with client-provided UUID if missing
                    await conn.execute(
                        """
                        INSERT INTO chat_sessions (id, user_id, org_id, title)
                        VALUES ($1::uuid, $2, $3, $4)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        uuid.UUID(session_id), user_id, org_id, request.title if hasattr(request, 'title') else 'New Chat'
                    )
                except Exception:
                    # If provided id is not a valid UUID, skip upsert
                    pass
        except Exception as e:
            logger.debug(f"Session ensure failed (non-fatal): {e}")

    # Save file associations if files are attached and PostgreSQL is enabled
    if request.file_ids and config.enable_postgres:
        user_id = getattr(raw_request.state, 'user_id', None) if raw_request and hasattr(raw_request, 'state') else None
        if user_id:
            try:
                pg = await get_postgres_rls_client()
                # Save message with file associations
                await pg.save_chat_message(
                    user_id=user_id,
                    session_id=session_id,
                    role='user',
                    content=request.message,
                    file_ids=request.file_ids,
                    org_id=org_id
                )
                logger.info(f"Saved user message with {len(request.file_ids)} file associations")
            except Exception as e:
                logger.warning(f"Failed to save file associations: {e}")
    
    # No command parsing needed - commands are just text the LLM understands
    # Agent mode routing is handled by the orchestrator based on agent_mode parameter
    
    if is_recall_query(request.message):
        prev_user = await get_last_user_message(session_id)
        response_text = (
            f"Your previous user message was: \"{prev_user}\"" if prev_user
            else "I couldn't find a previous user message in this conversation."
        )
        assistant_msg_id = uuid.uuid4().hex
        await insert_message(assistant_msg_id, session_id, 'assistant', response_text, datetime.now().isoformat())
        return ChatResponse(
            response=response_text,
            sources=None,
            charts=None,
            metrics=None,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            message_id=assistant_msg_id,
        )

    # Read from Postgres when enabled, fallback to SQLite
    if config.enable_postgres and user_id:
        try:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                messages = await conn.fetch("""
                    SELECT role, content, created_at
                    FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at ASC
                    LIMIT 50
                """, session_id)
                backend_hist = [{"role": msg['role'], "content": msg['content']} for msg in messages]
        except Exception as e:
            logger.warning(f"Failed to read history from Postgres, falling back to SQLite: {e}")
            backend_hist = await load_recent_history(session_id)
    else:
        backend_hist = await load_recent_history(session_id)
    if request.history and isinstance(request.history, list):
        seen = set((h.get("role"), h.get("content")) for h in backend_hist)
        merged = backend_hist[:]
        for item in request.history:
            r = str(item.get("role", "user"))
            c = str(item.get("content", ""))
            if c and (r, c) not in seen:
                merged.append({"role": r, "content": c})
        history = merged
    else:
        history = backend_hist

    # Use provided portfolio or load from DB
    portfolio_context = request.portfolio
    if request.portfolio_id and not portfolio_context:
        clerk_user_id = user_id
        loaded_portfolio = await load_portfolio_context(request.portfolio_id, clerk_user_id)
        if loaded_portfolio:
            portfolio_context = loaded_portfolio
    
    # Build workflow context with file attachments (uploads + Drive)
    workflow_context: Dict[str, Any] = {}
    attachments: list[Dict[str, Any]] = []

    if request.file_ids and config.enable_postgres:
        user_id = getattr(raw_request.state, 'user_id', None) if raw_request and hasattr(raw_request, 'state') else None
        logger.info(f"File validation: user_id={user_id}, file_ids={request.file_ids}")
        if user_id:
            try:
                pg = await get_postgres_rls_client()
                async with pg.acquire_with_org_context(user_id, org_id) as conn:
                    validated_file_ids: list[str] = []
                    for file_id in request.file_ids[:10]:  # Limit to 10 files
                        try:
                            file_record = await conn.fetchrow(
                                "SELECT id, original_name, content_type, size_bytes FROM files WHERE id = $1",
                                uuid.UUID(file_id)
                            )
                            if file_record:
                                record = {
                                    "id": str(file_record['id']),
                                    "name": file_record['original_name'],
                                    "type": file_record['content_type'],
                                    "size": file_record['size_bytes'],
                                    "source": "upload",
                                }
                                attachments.append(record)
                                validated_file_ids.append(str(file_record['id']))
                                logger.info(f"Validated file {file_id}: {file_record['original_name']}")
                        except Exception as e:
                            logger.warning(f"Invalid file_id {file_id}: {e}")

                    if validated_file_ids:
                        workflow_context["file_ids"] = validated_file_ids
            except Exception as e:
                logger.warning(f"Failed to load file contexts: {e}")
        else:
            logger.warning("No user_id found for file validation, skipping file attachment")

    if request.drive_file_ids:
        drive_user_id = getattr(raw_request.state, 'user_id', None) if raw_request and hasattr(raw_request, 'state') else None
        if drive_user_id:
            try:
                drive_credential = await get_drive_credential(drive_user_id)
                if drive_credential:
                    google_credentials = await build_authorized_credentials(drive_credential)
                    drive_files: list[Dict[str, Any]] = []
                    for drive_id in request.drive_file_ids[:10]:
                        try:
                            metadata = await drive_get_metadata(google_credentials, drive_id)
                            drive_files.append({
                                "id": metadata.get("id", drive_id),
                                "name": metadata.get("name", drive_id),
                                "type": metadata.get("mimeType"),
                                "size": metadata.get("size"),
                                "source": "google_drive",
                                "last_modified": metadata.get("modifiedTime"),
                            })
                        except Exception as exc:
                            logger.warning(f"Failed to load Google Drive metadata for {drive_id}: {exc}")
                    if drive_files:
                        attachments.extend(drive_files)
                        workflow_context.setdefault("drive", {})
                        workflow_context["drive"]["file_ids"] = [
                            item.get("id") for item in drive_files if item.get("id")
                        ]
                else:
                    logger.warning("User requested Google Drive files but no credential linked")
            except Exception as exc:
                logger.warning(f"Failed to prepare Google Drive context: {exc}")
        else:
            logger.warning("Missing user context for Google Drive attachments")

    if attachments:
        workflow_context["attachments"] = attachments

    # Register cancel event for non-streaming requests (allows cancel to work)
    cancel_flag = await register_stream(session_id, user_id)
    
    # Check for pre-set cancellation before starting
    if cancel_flag.is_set():
        logger.info("[chat] Session %s was cancelled before processing started", session_id)
        await clear_stream(session_id)
        return ChatResponse(
            response="Request was cancelled.",
            sources=None,
            charts=None,
            metrics=None,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            message_id=uuid.uuid4().hex,
        )

    try:
        result = await orchestrator.process_query(
            query=request.message,
            session_id=session_id,
            user_id=(getattr(raw_request.state, 'user_id', None) if hasattr(raw_request, 'state') else None),
            portfolio_context=portfolio_context,
            history=history,
            agent_mode=request.agent_mode,  # Pass agent mode from request
            workflow_context=workflow_context,  # Pass workflow context with attachments
            selected_model=request.selected_model,  # Pass selected model from request
            cancel_event=cancel_flag,  # Pass cancel event for cooperative cancellation
        )
    except asyncio.CancelledError:
        logger.info("[chat] Session %s was cancelled during processing", session_id)
        return ChatResponse(
            response="Request was cancelled.",
            sources=None,
            charts=None,
            metrics=None,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            message_id=uuid.uuid4().hex,
        )
    finally:
        await clear_stream(session_id)

    # Clear any compaction metadata (non-streaming path)
    orchestrator.pop_last_compaction_stats(session_id)
    
    # Track user activity if authenticated (generic tracking, no hardcoding)
    if user_id and config.enable_postgres:
        try:
            # Get tickers from portfolio context if available
            tickers = request.portfolio.get('tickers', []) if request.portfolio else []

            # Track as generic chat activity
            # The orchestrator should provide analysis_type in result if it ran calculations
            analysis_type = "chat"
            if isinstance(result, dict):
                analysis_type = result.get('analysis_type', 'chat')

            hybrid_manager = get_hybrid_session_manager()
            await hybrid_manager.track_user_activity(
                clerk_user_id=user_id,
                analysis_type=analysis_type,
                tickers=tickers
            )
        except Exception as e:
            # Don't fail the request if tracking fails
            logger.debug(f"Failed to track user activity: {e}")

    # Process the response to extract structured data
    logger.info(f"[CHART DEBUG v6_chat] Result type: {type(result)}")
    if isinstance(result, dict):
        logger.info(f"[CHART DEBUG v6_chat] Result keys: {result.keys()}")
        logger.info(f"[CHART DEBUG v6_chat] Charts in result: {len(result.get('charts', []))}")
        if result.get('charts'):
            logger.info(f"[CHART DEBUG v6_chat] First chart: {result['charts'][0].get('id') if result['charts'] else 'N/A'}")
    
    if isinstance(result, str):
        # Extract any embedded sources from markdown
        response_text, extracted_sources, extracted_charts = extract_structured_response(result)
        sources = extracted_sources
        charts = extracted_charts
        metrics: Dict[str, Any] = {}
    elif isinstance(result, dict):
        response_text = result.get("content") or result.get("response") or json.dumps(result)
        sources = result.get("sources") or []
        charts = result.get("charts") or []
        metrics = result.get("metrics") or {}

        # Extract full charts from _full_charts (new pattern to avoid context overflow)
        full_charts = result.get("_full_charts") or []
        if full_charts:
            logger.info(f"[CHART DEBUG v6_chat] Found {len(full_charts)} full charts in _full_charts")
            # Use full charts for database storage and frontend rendering
            charts = full_charts

        logger.info(f"[CHART DEBUG v6_chat] Extracted {len(charts)} charts from result")
        
        # If no sources but content has markdown links, extract them
        if not sources and response_text:
            _, extracted_sources, _ = extract_structured_response(response_text)
            if extracted_sources:
                sources = extracted_sources
    else:
        response_text = str(result)
        _, sources, charts = extract_structured_response(response_text)
        metrics = {}

    # Hydrate chart handles to ensure Plotly payloads reach the frontend
    if charts:
        hydrated_charts = []
        for chart in charts:
            if isinstance(chart, dict) and not chart.get("plotly"):
                chart_id = chart.get("chart_id") or chart.get("id")
                stored = get_chart(str(chart_id)) if chart_id else None
                if stored and isinstance(stored, dict):
                    # Merge stored payload into chart handle
                    merged = dict(stored)
                    merged.update({k: v for k, v in chart.items() if v is not None})
                    hydrated_charts.append(merged)
                    continue
            hydrated_charts.append(chart)
        charts = hydrated_charts

    # Extract code execution data and charts for metadata
    extras = {}

    # Add charts to metadata if present
    if charts:
        extras["charts"] = charts
        logger.info(f"[CHART DEBUG v6_chat] Added {len(charts)} charts to metadata")

    # Add sources to metadata if present
    if sources:
        extras["sources"] = sources

    # Check if result contains code execution data from quant_coding agent
    logger.info(f"[DEBUG] Result type: {type(result)}")
    logger.info(f"[DEBUG] Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")

    if isinstance(result, dict):
        # Extract code_execution_data from orchestrator result
        code_execution_data = result.get("code_execution_data")
        logger.info(f"[DEBUG] code_execution_data: {code_execution_data}")

        if code_execution_data and isinstance(code_execution_data, dict):
            # Extract the nested data from code_execution_data
            generated_files = code_execution_data.get("generated_files", [])
            container_id = code_execution_data.get("container_id")
            code_blocks = code_execution_data.get("code_blocks", [])

            logger.info(f"[DEBUG] Extracted - Files: {len(generated_files)}, Container: {container_id}, Blocks: {len(code_blocks)}")

            if generated_files or container_id or code_blocks:
                extras.update({
                    "generated_files": generated_files,
                    "container_id": container_id,
                    "code_blocks": code_blocks
                })
                logger.info(f"[CODE EXECUTION] Added {len(generated_files)} files and {len(code_blocks)} code blocks to extras")
                logger.info(f"[DEBUG] Full extras content: {extras}")

    assistant_msg_id = uuid.uuid4().hex

    # Save assistant message to PostgreSQL with RLS (include extras for code_blocks)
    if config.enable_postgres and user_id:
        try:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                await conn.execute(
                    """
                    INSERT INTO chat_messages (id, session_id, user_id, org_id, role, content, metadata, created_at)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb, $8)
                    """,
                    uuid.UUID(assistant_msg_id), uuid.UUID(session_id), user_id, org_id, 'assistant', response_text,
                    json.dumps(extras) if extras else '{}',
                    datetime.now()
                )
        except Exception as e:
            logger.error(f"Failed to save assistant message to PostgreSQL: {e}")
            # Fallback to SQLite
            await insert_message(assistant_msg_id, session_id, 'assistant', response_text, datetime.now().isoformat())
    else:
        await insert_message(assistant_msg_id, session_id, 'assistant', response_text, datetime.now().isoformat())

    # Debug logging for extras field
    if extras:
        logger.info(f"[V6_ROUTER] Returning extras with keys: {list(extras.keys())}")
        if 'generated_files' in extras:
            logger.info(f"[V6_ROUTER] Generated files count: {len(extras['generated_files'])}")
        if 'container_id' in extras:
            logger.info(f"[V6_ROUTER] Container ID: {extras['container_id']}")

    return ChatResponse(
        response=response_text,
        sources=sources,
        charts=charts,
        metrics=metrics,
        extras=extras if extras else None,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        message_id=assistant_msg_id,
    )


@router.post("/chat/cancel")
async def v6_chat_cancel(raw_request: Request, session_id: str = Query(..., min_length=1)):
    """Cancel an active streaming chat session."""
    orchestrator = get_v6_orchestrator()
    user_id = getattr(raw_request.state, 'user_id', None)

    # Resolve the canonical session ID exactly the same way as /chat/stream
    headers = dict(raw_request.headers) if raw_request else {}
    query_params = dict(raw_request.query_params) if raw_request else {}
    resolved_session_id = resolve_session_id(session_id, headers, query_params)

    try:
        logger.info("[cancel] request received for session %s user=%s", resolved_session_id, user_id)
        cancelled = await mark_stream_cancelled(resolved_session_id, user_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this session")

    orchestrator_cancelled = await orchestrator.cancel_active_run(resolved_session_id)

    status = "cancelled" if (cancelled or orchestrator_cancelled) else "not_found"
    logger.info(
        "[cancel] result for session %s -> %s (registry=%s orchestrator=%s)",
        resolved_session_id,
        status,
        cancelled,
        orchestrator_cancelled,
    )
    origin = raw_request.headers.get("origin")
    headers = {}
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse({"status": status, "session_id": resolved_session_id}, headers=headers)


@router.get("/chat/stream")
async def v6_chat_stream(
    message: str,
    session_id: Optional[str] = None,
    agent_mode: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    file_ids: Optional[str] = None,  # Comma-separated file IDs
    drive_file_ids: Optional[str] = None,  # Comma-separated Google Drive file IDs
    selected_model: Optional[str] = None,  # Model selection from UI
    deep_analysis_mode: Optional[str] = None,  # Deep analysis mode flag
    prioritized_tools: Optional[str] = None,  # Comma-separated tools to prioritize
    raw_request: Request = None
):
    orchestrator = get_v6_orchestrator()
    heartbeat_seconds = config.stream_heartbeat_seconds
    logger.info(
        "[CONFIG DEBUG] enable_true_token_streaming=%s enable_stream_events=%s",
        getattr(config, "enable_true_token_streaming", None),
        getattr(config, "enable_stream_events", None),
    )
    seen_stream_events: set[str] = set()

    # Define user_id at function level for proper scoping
    user_id = getattr(raw_request.state, 'user_id', None) if raw_request and hasattr(raw_request, 'state') else None

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(raw_request.state, 'org_id', None) if raw_request and hasattr(raw_request, 'state') else None

    async def event_generator():
        sid: Optional[str] = None
        cancel_flag: Optional[asyncio.Event] = None
        stream_state = {"content_chunks": []}
        cancel_recorded = False
        run_registered = False
        controller: Optional[RunController] = None
        listener_queue: Optional[asyncio.Queue[FormattedEvent]] = None
        assistant_msg_id: Optional[str] = None
        formatter: Optional[EventFormatter] = None
        run_status = "completed"

        async def persist_cancelled_message(reason: str = "user_request") -> None:
            nonlocal cancel_recorded, run_status
            if cancel_recorded or not sid:
                return
            cancel_recorded = True
            run_status = "cancelled"

            # Set cancel flag to unblock other checks (consume_live_events, orchestrator, etc.)
            if cancel_flag:
                cancel_flag.set()

            note = "_[Cancelled by user]_"
            if reason == "disconnect":
                note = "_[Stream cancelled: connection lost]_"

            partial = ''.join(stream_state.get("content_chunks") or []).strip()
            if partial:
                if not partial.endswith('\n'):
                    partial = partial.rstrip()
                payload = f"{partial}\n\n{note}"
            else:
                payload = note

            normalized_reason = "user" if reason == "user_request" else ("disconnect" if reason == "disconnect" else "backend")
            metadata = {
                "status": "cancelled",
                "reason": normalized_reason,
                "timestamp": datetime.now().isoformat(),
                "partialContent": partial or None,
                "note": note,
            }

            if config.enable_postgres and user_id:
                try:
                    pg = await get_postgres_rls_client()
                    await pg.save_chat_message(
                        user_id=user_id,
                        session_id=sid,
                        role='assistant',
                        content=payload,
                        metadata=metadata,
                        org_id=org_id
                    )
                    logger.info("[stream] Persisted cancellation message to Postgres for session %s", sid)
                    return
                except Exception as e:
                    logger.warning(f"[stream] Persist cancellation in Postgres failed: {e}")

            cancel_msg_id = uuid.uuid4().hex
            try:
                await insert_message(cancel_msg_id, sid, 'assistant', payload, datetime.now().isoformat())
                logger.info("[stream] Persisted cancellation message to SQLite for session %s", sid)
            except Exception as e:
                logger.warning(f"[stream] Persist cancellation in SQLite failed: {e}")

        async def consume_live_events(controller: RunController, queue: asyncio.Queue[FormattedEvent], start_seq: int, request: Request) -> AsyncIterator[FormattedEvent]:
            current_seq = start_seq
            consecutive_timeouts = 0
            max_timeouts = 1200  # Exit after 20 minutes of no activity if client disconnected

            while True:
                # Check if client disconnected (e.g., page refresh)
                if await request.is_disconnected():
                    logger.info("[stream] Client disconnected, exiting stream")
                    break

                if controller.done.is_set() and queue.empty():
                    break
                try:
                    formatted = await asyncio.wait_for(queue.get(), timeout=1)
                    consecutive_timeouts = 0  # Reset on successful get
                except asyncio.TimeoutError:
                    consecutive_timeouts += 1
                    # Exit if too many consecutive timeouts (client likely gone)
                    if consecutive_timeouts >= max_timeouts:
                        logger.warning("[stream] Max timeouts reached, client likely disconnected")
                        break
                    # Send heartbeat every 10 seconds to keep connection alive during agent reasoning
                    if consecutive_timeouts % 10 == 0:
                        current_seq += 1
                        heartbeat = FormattedEvent(
                            seq=current_seq,
                            chunk="event: status\ndata: {\"message\": \"processing...\"}\n\n",
                            payload={"type": "status", "message": "processing..."},
                            sse_event="status"
                        )
                        yield heartbeat
                    continue
                if formatted.seq <= current_seq:
                    continue
                current_seq = formatted.seq
                yield formatted

        try:
            headers = dict(raw_request.headers) if raw_request else {}
            query_params = dict(raw_request.query_params) if raw_request else {}
            sid = resolve_session_id(session_id, headers, query_params)
            
            # Detect resume BEFORE registering stream so we can reuse existing cancel_flag
            if raw_request:
                logger.debug(
                    "[SSE Resume] Incoming request headers Last-Event-ID=%s query resume_message_id=%s resume_last_seq=%s",
                    raw_request.headers.get("Last-Event-ID"),
                    raw_request.query_params.get("resume_message_id"),
                    raw_request.query_params.get("resume_last_seq") or raw_request.query_params.get("last_seq"),
                )
            resume_info = parse_resume_request(raw_request) if raw_request else None
            is_resume = resume_info is not None
            
            # Register stream - for resumes, reuse existing cancel_flag so cancellation works correctly
            cancel_flag = await register_stream(sid, user_id, is_resume=is_resume)

            # Check for pre-set cancellation (from pending cancellation before stream started)
            if cancel_flag.is_set():
                logger.info("[stream] Session %s was cancelled before streaming started", sid)
                await persist_cancelled_message("pre_cancelled")
                yield "event: cancelled\ndata: {\"type\": \"cancelled\", \"reason\": \"pre_cancelled\"}\n\n"
                return
            if resume_info:
                assistant_msg_id = resume_info['msg_id']
                last_seq = max(0, int(resume_info.get('last_seq', 0)))
                logger.info("[SSE Resume] Resuming session %s at event %s", assistant_msg_id, last_seq)

                controller = await _get_run_controller(assistant_msg_id)
                if controller:
                    listener_queue = await controller.add_listener()
                    try:
                        current_seq = last_seq
                        async for replay_evt in stream_resume_events(
                            checkpoint_store,
                            run_state_store,
                            assistant_msg_id,
                            last_seq,
                            cancel_flag,
                            enable_live=False,
                        ):
                            if replay_evt.seq <= current_seq:
                                continue
                            current_seq = replay_evt.seq
                            yield replay_evt.chunk

                        async for live_evt in consume_live_events(controller, listener_queue, current_seq, raw_request):
                            yield live_evt.chunk
                    finally:
                        await controller.remove_listener(listener_queue)
                    return

                # Cross-worker resume requires Redis-backed stores
                if "Memory" in type(checkpoint_store).__name__ or "Memory" in type(run_state_store).__name__:
                    logger.warning(
                        f"[STREAMING] Cross-worker resume attempted with in-memory stores "
                        f"(checkpoint={type(checkpoint_store).__name__}, "
                        f"run_state={type(run_state_store).__name__}). "
                        f"Configure REDIS_URL to enable multi-worker streaming."
                    )

                relay_controller = RunController(sid or "remote", assistant_msg_id, is_remote=True)
                await _register_run_controller(relay_controller)

                async def relay_existing_run() -> None:
                    try:
                        async for formatted in stream_resume_events(
                            checkpoint_store,
                            run_state_store,
                            assistant_msg_id,
                            last_seq,
                            cancel_flag,
                            enable_live=getattr(run_state_store, "supports_pubsub", False),
                        ):
                            await relay_controller.broadcast(formatted)
                    finally:
                        relay_controller.done.set()
                        await _remove_run_controller(assistant_msg_id)

                relay_task = asyncio.create_task(relay_existing_run())
                relay_controller.background_task = relay_task
                listener_queue = await relay_controller.add_listener()
                try:
                    async for formatted in consume_live_events(relay_controller, listener_queue, last_seq, raw_request):
                        yield formatted.chunk
                finally:
                    await relay_controller.remove_listener(listener_queue)
                    relay_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await relay_task
                return

            client_message_id = None
            if raw_request:
                client_candidate = raw_request.query_params.get("client_message_id")
                if client_candidate:
                    candidate = client_candidate.strip()
                    if re.fullmatch(r"[0-9a-fA-F]{24,}", candidate):
                        client_message_id = candidate.lower()
                    else:
                        logger.debug("[stream] Ignoring invalid client_message_id: %s", client_candidate)

            assistant_msg_id = client_message_id or uuid.uuid4().hex
            
            # DEDUPLICATION: Check if this message is already being processed
            # This prevents duplicate execution when frontend reconnects without proper resume params
            existing_controller = await _get_run_controller(assistant_msg_id)
            if existing_controller and not existing_controller.done.is_set():
                logger.info("[stream] DEDUP: Run already active for message %s, joining as listener instead of re-executing", assistant_msg_id)
                listener_queue = await existing_controller.add_listener()
                try:
                    # Replay any checkpointed events first
                    async for replay_evt in stream_resume_events(
                        checkpoint_store,
                        run_state_store,
                        assistant_msg_id,
                        0,  # Start from beginning
                        cancel_flag,
                        enable_live=False,
                    ):
                        yield replay_evt.chunk
                    # Then consume live events
                    async for live_evt in consume_live_events(existing_controller, listener_queue, 0, raw_request):
                        yield live_evt.chunk
                finally:
                    await existing_controller.remove_listener(listener_queue)
                return
            
            formatter = EventFormatter(assistant_msg_id, checkpoint_store, run_state_store)
            controller = RunController(sid, assistant_msg_id)
            await _register_run_controller(controller)
            await _set_run_active(sid, assistant_msg_id)
            await run_state_store.mark_active(assistant_msg_id, sid)
            run_registered = True

            async def ensure_session_row() -> None:
                if not (config.enable_postgres and user_id and sid):
                    return
                try:
                    pg = await get_postgres_rls_client()
                    async with pg.acquire_with_org_context(user_id, org_id) as conn:
                        try:
                            await conn.execute(
                                """
                                INSERT INTO chat_sessions (id, user_id, org_id, title)
                                VALUES ($1::uuid, $2, $3, $4)
                                ON CONFLICT (id) DO NOTHING
                                """,
                                uuid.UUID(sid), user_id, org_id, 'New Chat'
                            )
                        except Exception:
                            pass
                except Exception as exc:
                    logger.debug(f"[stream] Session ensure failed (non-fatal): {exc}")

            async def save_user_message() -> None:
                user_msg_id = uuid.uuid4().hex
                saved = False
                if config.enable_postgres and user_id and sid:
                    try:
                        pg = await get_postgres_rls_client()
                        await pg.save_chat_message(
                            user_id=user_id,
                            session_id=sid,
                            role='user',
                            content=message,
                            metadata={"portfolio_id": portfolio_id} if portfolio_id else None,
                            org_id=org_id
                        )
                        saved = True
                    except Exception as exc:
                        logger.warning(f"Failed to save streaming user message to Postgres: {exc}")
                if not saved:
                    await insert_message(user_msg_id, sid, 'user', message, datetime.now().isoformat())
                if file_ids and config.enable_postgres and user_id:
                    try:
                        pg = await get_postgres_rls_client()
                        file_id_list = [fid.strip() for fid in file_ids.split(',')[:10] if fid.strip()]
                        if file_id_list:
                            await pg.save_chat_message(
                                user_id=user_id,
                                session_id=sid,
                                role='user',
                                content=message,
                                file_ids=file_id_list,
                                org_id=org_id
                            )
                            logger.info("[stream] Saved streaming user message with %d file associations", len(file_id_list))
                    except Exception as exc:
                        logger.warning(f"Failed to save file associations in streaming: {exc}")

            async def build_context() -> tuple[Dict[str, Any], Dict[str, Any], bool, bool, Optional[str], Optional[str], Dict[str, bool]]:
                if config.enable_postgres and user_id:
                    try:
                        pg = await get_postgres_rls_client()
                        async with pg.acquire_with_org_context(user_id, org_id) as conn:
                            messages = await conn.fetch(
                                """
                                SELECT role, content, created_at
                                FROM chat_messages
                                WHERE session_id = $1
                                ORDER BY created_at ASC
                                LIMIT 50
                                """,
                                sid,
                            )
                            history = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
                    except Exception as exc:
                        logger.warning(f"Failed to read streaming history from Postgres, falling back to SQLite: {exc}")
                        history = await load_recent_history(sid)
                else:
                    history = await load_recent_history(sid)

                orchestrator_kwargs: Dict[str, Any] = {
                    "query": message,
                    "session_id": sid,
                    "user_id": user_id,
                    "history": history,
                }

                if agent_mode and agent_mode != 'auto':
                    orchestrator_kwargs["agent_mode"] = agent_mode

                if selected_model:
                    orchestrator_kwargs["selected_model"] = selected_model

                orchestrator_kwargs["deep_analysis_mode"] = bool(deep_analysis_mode and deep_analysis_mode.lower() == 'true')

                # Parse prioritized tools if provided
                if prioritized_tools:
                    tools_list = [t.strip() for t in prioritized_tools.split(',') if t.strip()]
                    if tools_list:
                        orchestrator_kwargs["prioritized_tools"] = tools_list
                        logger.info(f"[PRIORITIZED TOOLS] User requested priority for: {tools_list}")

                if portfolio_id:
                    logger.info(f"[PORTFOLIO DEBUG] Loading portfolio {portfolio_id} for user {user_id}")
                    portfolio_context = await load_portfolio_context(portfolio_id, user_id)
                    logger.info(f"[PORTFOLIO DEBUG] Loaded context: {portfolio_context}")
                    if portfolio_context:
                        orchestrator_kwargs["portfolio_context"] = portfolio_context
                        logger.info(f"[PORTFOLIO DEBUG] Added to orchestrator_kwargs")
                    else:
                        logger.warning(f"[PORTFOLIO DEBUG] load_portfolio_context returned None")
                else:
                    logger.warning(f"[PORTFOLIO DEBUG] No portfolio_id provided in stream request")

                workflow_context: Dict[str, Any] = {}
                attachments: list[Dict[str, Any]] = []

                if file_ids and config.enable_postgres and user_id:
                    try:
                        pg = await get_postgres_rls_client()
                        async with pg.acquire_with_org_context(user_id, org_id) as conn:
                            cap = getattr(config, 'max_file_attachments', 10)
                            file_id_list = [fid.strip() for fid in file_ids.split(',')[:cap] if fid.strip()]
                            validated_files: list[Dict[str, Any]] = []
                            validated_file_ids: list[str] = []
                            for file_id in file_id_list:
                                try:
                                    record = await conn.fetchrow(
                                        "SELECT id, original_name, content_type, size_bytes FROM files WHERE id = $1",
                                        uuid.UUID(file_id),
                                    )
                                    if record:
                                        validated_files.append({
                                            "id": str(record['id']),
                                            "name": record['original_name'],
                                            "type": record['content_type'],
                                            "size": record['size_bytes'],
                                            "source": "upload",
                                        })
                                        validated_file_ids.append(str(record['id']))
                                except Exception as exc:
                                    logger.warning(f"Invalid file_id {file_id}: {exc}")
                            if validated_file_ids:
                                attachments.extend(validated_files)
                                workflow_context["file_ids"] = validated_file_ids
                    except Exception as exc:
                        logger.warning(f"Failed to load file contexts: {exc}")

                if drive_file_ids and user_id:
                    try:
                        drive_credential = await get_drive_credential(user_id)
                        if drive_credential:
                            google_credentials = await build_authorized_credentials(drive_credential)
                            drive_ids = [fid.strip() for fid in drive_file_ids.split(',') if fid.strip()]
                            drive_records: list[Dict[str, Any]] = []
                            for drive_id in drive_ids[:10]:
                                try:
                                    metadata = await drive_get_metadata(google_credentials, drive_id)
                                    drive_records.append({
                                        "id": metadata.get("id", drive_id),
                                        "name": metadata.get("name", drive_id),
                                        "type": metadata.get("mimeType"),
                                        "size": metadata.get("size"),
                                        "source": "google_drive",
                                        "last_modified": metadata.get("modifiedTime"),
                                    })
                                except Exception as exc:
                                    logger.warning(f"Failed to load Drive metadata for {drive_id}: {exc}")
                            if drive_records:
                                attachments.extend(drive_records)
                                workflow_context.setdefault("drive", {})
                                workflow_context["drive"]["file_ids"] = [
                                    item.get("id") for item in drive_records if item.get("id")
                                ]
                    except Exception as exc:
                        logger.warning(f"Failed to prepare Google Drive context for streaming: {exc}")

                if attachments:
                    workflow_context["attachments"] = attachments

                if workflow_context:
                    orchestrator_kwargs["workflow_context"] = workflow_context

                stream_kwargs = dict(orchestrator_kwargs)
                if cancel_flag:
                    orchestrator_kwargs["cancel_event"] = cancel_flag
                    stream_kwargs["cancel_event"] = cancel_flag

                compaction_sse = config.cross_provider_compaction_sse_enabled
                prev_provider = orchestrator.get_last_provider(sid) if compaction_sse else None
                new_provider = get_provider_from_model(selected_model) if selected_model is not None else get_provider_from_model(None)
                provider = get_provider_from_model(selected_model) if selected_model else "openai"

                provider_flags = {
                    "use_true_stream": getattr(config, 'enable_true_token_streaming', False) and provider not in {"anthropic", "gemini", "bedrock", "xai"},
                    "anthropic": provider == "anthropic",
                    "gemini": provider == "gemini",
                    "bedrock": provider == "bedrock",
                    "xai": provider == "xai",
                }

                compaction_started = bool(compaction_sse and prev_provider and prev_provider != new_provider)

                return orchestrator_kwargs, stream_kwargs, compaction_sse, compaction_started, prev_provider, new_provider, provider_flags

            async def save_assistant_message(content: str, extras: Optional[Dict[str, Any]]) -> None:
                metadata: Dict[str, Any] = {"portfolio_id": portfolio_id} if portfolio_id else {}
                if extras and isinstance(extras, dict):
                    metadata.update(extras)
                if config.enable_postgres and user_id:
                    try:
                        pg = await get_postgres_rls_client()
                        await pg.save_chat_message(
                            user_id=user_id,
                            session_id=sid,
                            role='assistant',
                            content=content,
                            metadata=metadata,
                            org_id=org_id
                        )
                        return
                    except Exception as exc:
                        logger.warning(f"Failed to save assistant message to Postgres: {exc}")
                await insert_message(assistant_msg_id, sid, 'assistant', content, datetime.now().isoformat())

            async def finalize_assistant(content: str, extras: Optional[Dict[str, Any]], compaction_sse: bool, compaction_started: bool, prev_provider: Optional[str], new_provider: Optional[str]) -> AsyncIterator[FormattedEvent]:
                stats = orchestrator.pop_last_compaction_stats(sid)
                if compaction_sse and (stats or compaction_started):
                    effective_stats = stats or {}
                    payload = {
                        "status": "complete",
                        "tokens": max(0, int(effective_stats.get("tokens", 0)) // 4),
                        "from_provider": effective_stats.get("from_provider") or prev_provider,
                        "to_provider": effective_stats.get("to_provider") or new_provider,
                        "original_tokens": int(effective_stats.get("original_tokens", 0)),
                        "summary_tokens": int(effective_stats.get("summary_tokens", 0)),
                        "summary_model": effective_stats.get("summary_model"),
                        "summary_used": bool(effective_stats.get("summary_used", False)),
                        "summary_preview": effective_stats.get("summary_preview"),
                    }
                    yield await formatter.format(payload, sse_event='compaction')
                await save_assistant_message(content, extras if isinstance(extras, dict) else None)
                yield await formatter.format({'type': 'done'}, sse_event='done')

            async def stream_fallback(existing_sources: list[Any], existing_charts: list[Any], orchestrator_kwargs: Dict[str, Any]) -> AsyncIterator[FormattedEvent]:
                # ✅ CHECK CANCELLATION: Skip fallback if request was cancelled
                if cancel_flag and cancel_flag.is_set():
                    logger.info("[STREAM] Fallback skipped - request cancelled")
                    yield await formatter.format({'type': 'cancelled'})
                    return
                try:
                    result_fallback = await orchestrator.process_query(**orchestrator_kwargs)
                except Exception as exc:
                    logger.warning(f"[STREAM] Fallback response generation failed: {exc}")
                    return

                if isinstance(result_fallback, str):
                    content_fb = result_fallback
                    sources_fb: list[Any] = []
                    charts_fb: list[Any] = []
                elif isinstance(result_fallback, dict):
                    content_fb = result_fallback.get("content") or result_fallback.get("response") or json.dumps(result_fallback)
                    sources_fb = result_fallback.get("sources", [])
                    charts_fb = result_fallback.get("charts", [])
                else:
                    content_fb = str(result_fallback)
                    sources_fb = []
                    charts_fb = []

                if not existing_sources and sources_fb:
                    yield await formatter.format({'type': 'sources', 'sources': sources_fb})
                if not existing_charts and charts_fb:
                    yield await formatter.format({'type': 'charts', 'charts': charts_fb})

                import re as _re
                tokens_fb = _re.findall(r'\S+|\n', content_fb)
                fallback_chunks: list[str] = []
                stream_state["content_chunks"] = fallback_chunks
                for idx, tok in enumerate(tokens_fb):
                    if tok == '\n':
                        chunk = tok
                    else:
                        if idx < len(tokens_fb) - 1 and tokens_fb[idx + 1] != '\n':
                            chunk = tok + " "
                        else:
                            chunk = tok
                    fallback_chunks.append(chunk)
                    yield await formatter.format({'type': 'content', 'content': chunk})

            async def true_stream(orchestrator_kwargs: Dict[str, Any], stream_kwargs: Dict[str, Any], compaction_sse: bool, compaction_started: bool, prev_provider: Optional[str], new_provider: Optional[str]) -> AsyncIterator[FormattedEvent]:
                acc_content: list[str] = []
                stream_state["content_chunks"] = acc_content
                acc_sources: list[Any] = []
                acc_charts: list[Any] = []
                acc_extras: Optional[Dict[str, Any]] = None

                async for event in orchestrator.process_query_stream(**stream_kwargs):
                    et = event.get('type')
                    if et == 'content':
                        chunk = event.get('content') or ''
                        if chunk:
                            acc_content.append(chunk)
                    elif et == 'sources' and not acc_sources:
                        acc_sources = event.get('sources') or []
                    elif et == 'charts' and not acc_charts:
                        acc_charts = event.get('charts') or []
                    elif et == 'extras':
                        acc_extras = event.get('extras')
                    elif et == 'cancelled':
                        await persist_cancelled_message()
                        yield await formatter.format(event)
                        return
                    elif et == 'done':
                        break
                    elif et == 'stream_event' and getattr(config, 'enable_stream_events', False):
                        evt_payload = event.get('event') or {}
                        evt_type = evt_payload.get("type")
                        if isinstance(evt_type, str) and evt_type not in seen_stream_events:
                            seen_stream_events.add(evt_type)
                            logger.info("[STREAM] First structured event forwarded: %s", evt_type)

                    yield await formatter.format(event)

                if acc_extras:
                    yield await formatter.format({'type': 'extras', 'extras': acc_extras})

                full_content = ''.join(acc_content)
                if not full_content.strip():
                    # ✅ CHECK CANCELLATION: Skip fallback if request was cancelled
                    if cancel_flag and cancel_flag.is_set():
                        logger.info("[STREAM] true_stream skipping fallback - request cancelled")
                        await persist_cancelled_message()
                        yield await formatter.format({'type': 'cancelled'})
                        return
                    async for fallback_event in stream_fallback(acc_sources, acc_charts, orchestrator_kwargs):
                        yield fallback_event
                    full_content = ''.join(stream_state.get("content_chunks") or [])

                # Merge charts into extras for database persistence
                extras_payload = acc_extras if isinstance(acc_extras, dict) else {}
                if acc_charts:
                    if not extras_payload:
                        extras_payload = {}
                    extras_payload["charts"] = acc_charts
                    logger.info(f"[CHART PERSISTENCE] Added {len(acc_charts)} charts to extras for database storage")

                async for final_event in finalize_assistant(full_content, extras_payload if extras_payload else None, compaction_sse, compaction_started, prev_provider, new_provider):
                    yield final_event

            async def simulated_stream(orchestrator_kwargs: Dict[str, Any], compaction_sse: bool, compaction_started: bool, prev_provider: Optional[str], new_provider: Optional[str]) -> AsyncIterator[FormattedEvent]:
                task = asyncio.create_task(orchestrator.process_query(**orchestrator_kwargs))
                cancel_waiter: Optional[asyncio.Task] = asyncio.create_task(cancel_flag.wait()) if cancel_flag else None
                try:
                    while True:
                        wait_set = [task]
                        if cancel_waiter:
                            wait_set.append(cancel_waiter)
                        done, _ = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED, timeout=heartbeat_seconds)
                        if cancel_waiter and cancel_waiter in done:
                            task.cancel()
                            with suppress(asyncio.CancelledError):
                                await task
                            await orchestrator.cancel_active_run(sid)
                            await persist_cancelled_message()
                            yield await formatter.format({'type': 'cancelled'})
                            return
                        if task in done:
                            break
                        yield await formatter.format({'type': 'status', 'message': 'working...'})
                    try:
                        result = await task
                    except asyncio.CancelledError:
                        await persist_cancelled_message()
                        yield await formatter.format({'type': 'cancelled'})
                        return
                finally:
                    if cancel_waiter:
                        cancel_waiter.cancel()
                        with suppress(asyncio.CancelledError):
                            await cancel_waiter

                if isinstance(result, str):
                    content = result
                    sources: list[Any] = []
                    charts: list[Any] = []
                    extras: Optional[Dict[str, Any]] = None
                elif isinstance(result, dict):
                    content = result.get("content") or result.get("response") or json.dumps(result)
                    sources = result.get("sources", [])
                    charts = result.get("charts", [])
                    extras = None
                    code_execution_data = result.get("code_execution_data")
                    if code_execution_data and isinstance(code_execution_data, dict):
                        extras = {
                            "generated_files": code_execution_data.get("generated_files"),
                            "container_id": code_execution_data.get("container_id"),
                            "code_blocks": code_execution_data.get("code_blocks"),
                        }
                else:
                    content = str(result)
                    sources = []
                    charts = []
                    extras = None

                if sources:
                    yield await formatter.format({'type': 'sources', 'sources': sources})
                if charts:
                    yield await formatter.format({'type': 'charts', 'charts': charts})

                import re as _re
                tokens = _re.findall(r'\S+|\n', content)
                content_chunks: list[str] = []
                stream_state["content_chunks"] = content_chunks
                for idx, tok in enumerate(tokens):
                    if tok == '\n':
                        chunk = tok
                    else:
                        if idx < len(tokens) - 1 and tokens[idx + 1] != '\n':
                            chunk = tok + " "
                        else:
                            chunk = tok
                    content_chunks.append(chunk)
                    yield await formatter.format({'type': 'content', 'content': chunk})
                    await asyncio.sleep(getattr(config, 'stream_typing_delay_seconds', 0))
                if extras:
                    yield await formatter.format({'type': 'extras', 'extras': extras})

                final_content = ''.join(content_chunks) or content

                # Merge charts into extras for database persistence
                extras_payload = extras if isinstance(extras, dict) else {}
                if charts:
                    if not extras_payload:
                        extras_payload = {}
                    extras_payload["charts"] = charts
                    logger.info(f"[CHART PERSISTENCE] Added {len(charts)} charts to extras for database storage (simulated stream)")

                async for final_event in finalize_assistant(final_content, extras_payload if extras_payload else None, compaction_sse, compaction_started, prev_provider, new_provider):
                    yield final_event

            async def generate_events() -> AsyncIterator[FormattedEvent]:
                nonlocal run_status
                yield await formatter.format({'type': 'start', 'message_id': assistant_msg_id})
                await ensure_session_row()
                await save_user_message()
                orchestrator_kwargs, stream_kwargs, compaction_sse, compaction_started, prev_provider, new_provider, provider_flags = await build_context()
                if compaction_started:
                    start_payload = {
                        "status": "start",
                        "from_provider": prev_provider,
                        "to_provider": new_provider,
                    }
                    yield await formatter.format(start_payload, sse_event='compaction')
                initial_payload = {
                    "type": "initial_update",
                    "agent_mode": agent_mode,
                    "session_id": sid,
                    "selected_model": selected_model,
                    "portfolio_id": portfolio_id,
                    "file_ids": file_ids,
                    "drive_file_ids": drive_file_ids,
                    "started_at": datetime.now().isoformat(),
                    "stream_payload_version": 2 if getattr(config, 'enable_stream_events', False) else 1,
                }
                try:
                    yield await formatter.format(initial_payload)
                except Exception:
                    pass
                try:
                    if provider_flags.get("use_true_stream"):
                        async for event in true_stream(orchestrator_kwargs, stream_kwargs, compaction_sse, compaction_started, prev_provider, new_provider):
                            yield event
                    else:
                        # Preflight: trim/compact the provider-scoped SQLiteSession history so the UI can
                        # surface a "Compacting..." status even when we simulate streaming (Claude/Gemini/etc).
                        try:
                            sdk_session_id = f"{sid}::{new_provider}"
                            sqlite_session = SQLiteSession(sdk_session_id, config.openai_sessions_db_path)
                            trim_result = await trim_sqlite_session_history(
                                sqlite_session,
                                selected_model,
                                "stream_preflight",
                            )
                            if isinstance(trim_result, dict) and trim_result.get("did_trim"):
                                yield await formatter.format(
                                    {"type": "status", "message": "Compacting conversation history..."},
                                    sse_event="status",
                                )
                        except Exception as exc:
                            logger.warning("[stream] Preflight session trim failed: %s", exc)
                        async for event in simulated_stream(orchestrator_kwargs, compaction_sse, compaction_started, prev_provider, new_provider):
                            yield event
                except Exception as exc:
                    logger.error(f"[STREAM] Streaming error: {exc}")
                    run_status = "error"
                    yield await formatter.format({'type': 'error', 'error': str(exc)})

            async def run_stream() -> None:
                try:
                    async for formatted_event in generate_events():
                        await controller.broadcast(formatted_event)
                finally:
                    controller.done.set()
                    if run_registered:
                        await _mark_run_done(assistant_msg_id)
                        # Mark run complete in Redis only when background task actually finishes
                        last_seq = formatter.seq if formatter else 0
                        with suppress(Exception):
                            await run_state_store.mark_done(assistant_msg_id, run_status, last_seq)
                        with suppress(Exception):
                            await run_state_store.clear(assistant_msg_id)
                        cleanup_delay = getattr(config, 'stream_checkpoint_ttl_seconds', 300)
                        _schedule_run_cleanup(assistant_msg_id, cleanup_delay)

            controller.background_task = asyncio.create_task(run_stream())
            listener_queue = await controller.add_listener()
            async for formatted in consume_live_events(controller, listener_queue, 0, raw_request):
                yield formatted.chunk
            return

        finally:
            if listener_queue and controller:
                await controller.remove_listener(listener_queue)
            # DO NOT mark run as done here - let run_stream() finally block handle it
            # when the background task actually completes. Marking done here causes
            # stream_resume_events() to bail out early on reconnects.
            if sid:
                orchestrator.pop_last_compaction_stats(sid)
                await clear_stream(sid)
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.post("/export/pdf-legacy")  # Renamed to avoid conflict with exports router
async def v6_export_pdf_legacy(req: ExportPdfRequest, raw_request: Request):
    """Export either the latest assistant chat as PDF (mode=chat) or a structured risk analysis (mode=analysis)."""
    session_id = resolve_session_id(req.session_id, dict(raw_request.headers))

    # If chat mode: export the last assistant content or a specific message_id
    if (req.mode or "analysis").lower() == "chat":
        content: Optional[str] = None
        
        # First check if content was provided directly in the request
        if hasattr(req, 'content') and req.content:
            content = req.content
        else:
            # Otherwise try to fetch from database
            from aiosqlite import connect as aiosqlite_connect
            async with aiosqlite_connect(config.conversation_db_path) as db:
                if req.message_id:
                    async with db.execute("SELECT content FROM messages WHERE id = ? AND role = 'assistant'", (req.message_id,)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            content = row[0]
                if content is None:
                    async with db.execute(
                        "SELECT content FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
                        (session_id,),
                    ) as cursor:
                        row = await cursor.fetchone()
                        content = row[0] if row else None
        if not content:
            raise HTTPException(status_code=400, detail="No assistant content found to export")

        # Get user_id from request state (set by RLS middleware)
        user_id = getattr(raw_request.state, 'user_id', None) or "local-dev-user"

        # Fetch user export settings
        user_settings = await fetch_user_export_style(user_id)
        gamma_client = get_gamma_client()

        # Build natural language instructions from user settings
        final_instructions = build_instructions_from_settings(
            base_prompt=user_settings.custom_prompt,
            verbosity=user_settings.verbosity,
            tone=user_settings.tone,
            audience=user_settings.audience
        )

        # Build card options with logo from user settings
        card_options = None
        if user_settings.logo_source != "none":
            header_footer = {
                "bottomRight": {"type": "cardNumber"},
                "hideFromFirstCard": True
            }

            logo_config = {
                "type": "image",
                "source": user_settings.logo_source,
                "size": user_settings.logo_size
            }

            if user_settings.logo_source == "custom" and user_settings.logo_url:
                logo_config["src"] = user_settings.logo_url

            header_footer[user_settings.logo_position] = logo_config
            card_options = {"headerFooter": header_footer}

        # Generate PDF with Gamma API
        pdf_bytes = await gamma_client.generate_presentation(
            content=content,
            format="document",
            export_as="pdf",
            theme_id=user_settings.theme_id,
            text_options={"language": user_settings.language},
            additional_instructions=final_instructions,
            cardOptions=card_options
        )

        if pdf_bytes is None:
            raise HTTPException(status_code=500, detail="Failed to generate PDF export")

        return Response(content=pdf_bytes, media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=chat_export.pdf"
        })

    # analysis mode - convert analysis_data to content/extras format
    analysis_data = req.analysis_data or {}
    if not analysis_data:
        # Best-effort: build minimal analysis structure from recent context (optional)
        analysis_data = {
            "portfolio": {},
            "risk_metrics": {},
            "summary": "Generated report. Provide analysis_data for richer content.",
        }

    # Get user_id from request state (set by RLS middleware)
    user_id = getattr(raw_request.state, 'user_id', None) or "local-dev-user"

    # Fetch user export settings
    user_settings = await fetch_user_export_style(user_id)
    gamma_client = get_gamma_client()

    # Build natural language instructions from user settings
    final_instructions = build_instructions_from_settings(
        base_prompt=user_settings.custom_prompt,
        verbosity=user_settings.verbosity,
        tone=user_settings.tone,
        audience=user_settings.audience
    )

    # Build card options with logo from user settings
    card_options = None
    if user_settings.logo_source != "none":
        header_footer = {
            "bottomRight": {"type": "cardNumber"},
            "hideFromFirstCard": True
        }

        logo_config = {
            "type": "image",
            "source": user_settings.logo_source,
            "size": user_settings.logo_size
        }

        if user_settings.logo_source == "custom" and user_settings.logo_url:
            logo_config["src"] = user_settings.logo_url

        header_footer[user_settings.logo_position] = logo_config
        card_options = {"headerFooter": header_footer}

    content = analysis_data.get("summary", "Generated report. Provide analysis_data for richer content.")

    # Generate PDF with Gamma API
    pdf_bytes = await gamma_client.generate_presentation(
        content=content,
        format="document",
        export_as="pdf",
        theme_id=user_settings.theme_id,
        text_options={"language": user_settings.language},
        additional_instructions=final_instructions,
        cardOptions=card_options
    )

    if pdf_bytes is None:
        raise HTTPException(status_code=500, detail="Failed to generate PDF export")

    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=risk_report.pdf"
    })


@router.post("/export/powerpoint")
async def v6_export_powerpoint(req: ExportPdfRequest, raw_request: Request):
    """Export PowerPoint-style PDF with 16:9 presentation format"""
    session_id = resolve_session_id(req.session_id, dict(raw_request.headers))

    if (req.mode or "analysis").lower() == "chat":
        content: Optional[str] = None

        if hasattr(req, 'content') and req.content:
            content = req.content
        else:
            from aiosqlite import connect as aiosqlite_connect
            async with aiosqlite_connect(config.conversation_db_path) as db:
                if req.message_id:
                    async with db.execute("SELECT content FROM messages WHERE id = ? AND role = 'assistant'", (req.message_id,)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            content = row[0]
                if content is None:
                    async with db.execute(
                        "SELECT content FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
                        (session_id,),
                    ) as cursor:
                        row = await cursor.fetchone()
                        content = row[0] if row else None
        if not content:
            raise HTTPException(status_code=400, detail="No assistant content found to export")

        # Get user_id from request state (set by RLS middleware)
        user_id = getattr(raw_request.state, 'user_id', None) or "local-dev-user"

        # Fetch user export settings
        user_settings = await fetch_user_export_style(user_id)
        gamma_client = get_gamma_client()

        # Build natural language instructions from user settings
        final_instructions = build_instructions_from_settings(
            base_prompt=user_settings.custom_prompt,
            verbosity=user_settings.verbosity,
            tone=user_settings.tone,
            audience=user_settings.audience
        )

        # Build card options with logo from user settings
        card_options = None
        if user_settings.logo_source != "none":
            header_footer = {
                "bottomRight": {"type": "cardNumber"},
                "hideFromFirstCard": True
            }

            logo_config = {
                "type": "image",
                "source": user_settings.logo_source,
                "size": user_settings.logo_size
            }

            if user_settings.logo_source == "custom" and user_settings.logo_url:
                logo_config["src"] = user_settings.logo_url

            header_footer[user_settings.logo_position] = logo_config
            card_options = {"headerFooter": header_footer}

        # Generate PPTX with Gamma API
        pptx_bytes = await gamma_client.generate_presentation(
            content=content,
            format="presentation",
            export_as="pptx",
            theme_id=user_settings.theme_id,
            text_options={"language": user_settings.language},
            additional_instructions=final_instructions,
            cardOptions=card_options
        )

        if pptx_bytes is None:
            raise HTTPException(status_code=500, detail="Failed to generate presentation export")

        return Response(content=pptx_bytes, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={
            "Content-Disposition": "attachment; filename=presentation_slides.pptx"
        })

    analysis_data = req.analysis_data or {}
    if not analysis_data:
        analysis_data = {
            "portfolio": {},
            "risk_metrics": {},
            "summary": "Generated report. Provide analysis_data for richer content.",
        }

    # Get user_id from request state (set by RLS middleware)
    user_id = getattr(raw_request.state, 'user_id', None) or "local-dev-user"

    # Fetch user export settings
    user_settings = await fetch_user_export_style(user_id)
    gamma_client = get_gamma_client()

    # Build natural language instructions from user settings
    final_instructions = build_instructions_from_settings(
        base_prompt=user_settings.custom_prompt,
        verbosity=user_settings.verbosity,
        tone=user_settings.tone,
        audience=user_settings.audience
    )

    # Build card options with logo from user settings
    card_options = None
    if user_settings.logo_source != "none":
        header_footer = {
            "bottomRight": {"type": "cardNumber"},
            "hideFromFirstCard": True
        }

        logo_config = {
            "type": "image",
            "source": user_settings.logo_source,
            "size": user_settings.logo_size
        }

        if user_settings.logo_source == "custom" and user_settings.logo_url:
            logo_config["src"] = user_settings.logo_url

        header_footer[user_settings.logo_position] = logo_config
        card_options = {"headerFooter": header_footer}

    content = analysis_data.get("summary", "Generated report. Provide analysis_data for richer content.")

    # Generate PPTX with Gamma API
    pptx_bytes = await gamma_client.generate_presentation(
        content=content,
        format="presentation",
        export_as="pptx",
        theme_id=user_settings.theme_id,
        text_options={"language": user_settings.language},
        additional_instructions=final_instructions,
        cardOptions=card_options
    )

    if pptx_bytes is None:
        raise HTTPException(status_code=500, detail="Failed to generate presentation export")

    return Response(content=pptx_bytes, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={
        "Content-Disposition": "attachment; filename=presentation_slides.pptx"
    })


@router.get("/containers/{container_id}/files/{file_id}")
async def download_container_file(
    container_id: str,
    file_id: str,
    request: Request,
    filename: str = Query(default="download.bin"),  # Accept filename as query parameter
    session_id: Optional[str] = Query(default=None)
):
    """Download file generated by code execution"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Basic session ownership verification (best-effort when Postgres is enabled)
    if config.enable_postgres:
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        try:
            pg = await get_postgres_rls_client()
            # Extract org_id from request state (set by RLS middleware)
            org_id = getattr(request.state, 'org_id', None)
            # Verify the session belongs to this user (RLS context)
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                row = await conn.fetchrow(
                    "SELECT id FROM chat_sessions WHERE id = $1::uuid AND user_id = $2",
                    uuid.UUID(session_id),
                    user_id,
                )
                if not row:
                    raise HTTPException(status_code=403, detail="Unauthorized session")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Session verification failed: {e}")
            raise HTTPException(status_code=500, detail="Verification failed")

    logger.info(f"User {user_id} requesting file {file_id} from container {container_id} (session={session_id})")

    # Download from OpenAI Container
    try:
        import httpx

        # Use the container files API endpoint
        headers = {"Authorization": f"Bearer {config.openai_api_key}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.openai.com/v1/containers/{container_id}/files/{file_id}/content",
                headers=headers
            )
            response.raise_for_status()

            # Use the filename from the query parameter (passed from frontend)
            return Response(
                content=response.content,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
    except Exception as e:
        logger.error(f"Failed to download file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="File download failed")
