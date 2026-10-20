"""
Excel Agent API Router

Endpoints for the Sentry Excel Agent: workbook indexing, semantic search,
agent planning (SSE streaming), validation, and data feeds for custom functions.

Following CODING_RULES.md: KISS, DRY, no hardcoding, <500 lines, <50 line functions.
Following NASA Power of 10: bounded loops, minimal scope, check returns.
"""

import asyncio
import json
import logging
import time
from typing import Optional, AsyncIterator, Any

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.models import (
    ExcelIndexRequest,
    ExcelIndexResponse,
    ExcelDiffRequest,
    ExcelDiffResponse,
    ExcelReindexSheetRequest,
    ExcelSearchRequest,
    ExcelSearchResponse,
    ExcelPlanRequest,
    ExcelPlanSupplementRequest,
    ExcelValidateRequest,
    ExcelChatThreadCreate,
    ExcelChatThreadSummary,
    ExcelChatMessageCreate,
    ExcelChatMessageOut,
    ExcelChatBulkSave,
    ExcelChatBulkDeleteRequest,
    ExcelReadResponseBody,
    ExcelApprovalResponseBody,
)
from core.services.workbook_indexer import get_workbook_indexer
from core.database.postgres_client import get_postgres_rls_client
from core.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/excel", tags=["excel-agent"])

# Cancellation registry: tracks active Excel agent streams with asyncio.Event for signaling
_active_excel_streams: dict[str, dict[str, Any]] = {}
_excel_streams_lock = asyncio.Lock()


async def _register_excel_stream(request_id: str, user_id: str) -> asyncio.Event:
    """Register a new Excel stream and return its cancel event."""
    cancel_event = asyncio.Event()
    async with _excel_streams_lock:
        _active_excel_streams[request_id] = {
            "user_id": user_id,
            "cancel_event": cancel_event,
            "created_at": time.time(),
        }
    return cancel_event


async def _mark_excel_cancelled(request_id: str, requester_id: str) -> bool:
    """Mark an Excel stream as cancelled. Returns True if found and cancelled."""
    async with _excel_streams_lock:
        entry = _active_excel_streams.get(request_id)
        if entry:
            if entry["user_id"] != requester_id:
                raise PermissionError("Not authorized to cancel this request")
            entry["cancel_event"].set()
            # Cancel the SDK streaming run to stop in-flight MCP tool calls
            rs = entry.get("result_streaming")
            if rs and not getattr(rs, "is_complete", True):
                rs.cancel()
            return True
    return False


async def _set_result_streaming(request_id: str, result_streaming) -> None:
    """Store the SDK RunResultStreaming object for direct cancellation."""
    async with _excel_streams_lock:
        entry = _active_excel_streams.get(request_id)
        if entry:
            entry["result_streaming"] = result_streaming


async def _cleanup_excel_stream(request_id: str) -> None:
    """Remove an Excel stream from the registry."""
    async with _excel_streams_lock:
        _active_excel_streams.pop(request_id, None)


def _sse_event(event: str, data: dict, seq: int = 0) -> str:
    """Format a single SSE event."""
    lines = [f"id: {seq}", f"event: {event}", f"data: {json.dumps(data)}"]
    return "\n".join(lines) + "\n\n"


def _get_user_id(request: Request) -> str:
    """Extract user_id from request state (set by RLS middleware)."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


def _get_org_id(request: Request) -> Optional[str]:
    """Extract org_id from request state, None for personal workspace."""
    return getattr(request.state, "org_id", None) or None


# =============================================================================
# Vector Index Endpoints
# =============================================================================


@router.post("/index", response_model=ExcelIndexResponse)
async def index_workbook(request: Request, body: ExcelIndexRequest):
    """
    Full workbook index: chunk, embed, store in pgvector.

    Called by the add-in on first open or when no existing index is found.
    """
    user_id = _get_user_id(request)
    org_id = _get_org_id(request)
    indexer = get_workbook_indexer()

    result = await indexer.index_workbook(
        workbook_data=body.workbook_data,
        workbook_hash=body.workbook_hash,
        workbook_name=body.workbook_name,
        user_id=user_id,
        org_id=org_id,
    )
    return ExcelIndexResponse(**result)


@router.get("/index/lookup")
async def lookup_workbook(
    request: Request,
    workbook_hash: str = Query(..., description="Stable workbook identity hash"),
):
    """Check if a workbook is already indexed. Returns registry info or null."""
    user_id = _get_user_id(request)
    indexer = get_workbook_indexer()

    result = await indexer.lookup(workbook_hash, user_id)
    if not result:
        return {"indexed": False}
    return {"indexed": True, **result}


@router.post("/index/diff", response_model=ExcelDiffResponse)
async def diff_workbook(request: Request, body: ExcelDiffRequest):
    """Compare content hash to detect if the index is stale."""
    user_id = _get_user_id(request)
    indexer = get_workbook_indexer()

    result = await indexer.diff(body.workbook_id, body.current_hash, user_id)
    return ExcelDiffResponse(**result)


@router.post("/index/reindex-sheet")
async def reindex_sheet(request: Request, body: ExcelReindexSheetRequest):
    """
    Incremental re-index: delete + re-chunk + re-embed one sheet.

    Called after the agent writes to a sheet, or when diff detects staleness.
    """
    user_id = _get_user_id(request)
    org_id = _get_org_id(request)
    indexer = get_workbook_indexer()

    result = await indexer.reindex_sheet(
        workbook_id=body.workbook_id,
        sheet_name=body.sheet_name,
        sheet_data=body.sheet_data,
        user_id=user_id,
        org_id=org_id,
    )
    return result


# =============================================================================
# Search Endpoint
# =============================================================================


@router.post("/search", response_model=ExcelSearchResponse)
async def search_workbook(request: Request, body: ExcelSearchRequest):
    """
    Semantic search over workbook chunks using pgvector cosine similarity.

    The SpreadsheetAgent uses this to find relevant context before planning.
    """
    user_id = _get_user_id(request)
    indexer = get_workbook_indexer()

    chunks = await indexer.search(
        workbook_id=body.workbook_id,
        query=body.query,
        user_id=user_id,
        top_k=body.top_k,
    )
    return ExcelSearchResponse(chunks=chunks)


# =============================================================================
# Agent Endpoints (plan, supplement, validate)
# Placeholder — will delegate to SpreadsheetAgent via LangGraph once built.
# =============================================================================


@router.post("/plan")
async def create_plan_endpoint(request: Request, body: ExcelPlanRequest):
    """
    Create an execution plan for a user request — streamed via SSE.

    SSE events emitted:
      - status:    {stage, message}    — progress updates
      - tool_call: {tool}              — agent is calling a tool
      - tool_done: {tool, output}      — tool returned
      - thinking:  {text}              — reasoning delta
      - plan:      {plan payload}      — the completed plan
      - error:     {message, fatal}    — on failure
      - done:      {}                  — stream end

    Flow: embed(message) -> pgvector search -> SpreadsheetAgent streams plan
    """
    user_id = _get_user_id(request)

    async def event_generator() -> AsyncIterator[str]:
        seq = 0
        event_queue: list[dict] = []

        async def on_agent_event(event: dict) -> None:
            """Callback from SpreadsheetAgent streaming — queue events."""
            event_queue.append(event)

        try:
            seq += 1
            yield _sse_event("status", {"stage": "searching", "message": "Searching workbook context..."}, seq)

            indexer = get_workbook_indexer()
            chunks = await indexer.search(
                workbook_id=body.workbook_id,
                query=body.message,
                user_id=user_id,
            )

            seq += 1
            yield _sse_event("status", {
                "stage": "planning",
                "message": f"Found {len(chunks)} relevant chunks. Agent is planning...",
            }, seq)

            from core.agents.SpreadsheetAgent import create_plan_streamed

            # Run the streamed agent — it will call on_agent_event for each tool/text event.
            # Since SSE generators are synchronous yields, we collect events and flush after.
            import asyncio

            plan = None
            plan_future = asyncio.ensure_future(
                create_plan_streamed(
                    message=body.message,
                    context_chunks=chunks,
                    on_event=on_agent_event,
                )
            )

            # Poll for events while the agent runs
            while not plan_future.done():
                # Check for client disconnect
                if await request.is_disconnected():
                    plan_future.cancel()
                    logger.info("Client disconnected during plan generation, cancelling")
                    break
                
                await asyncio.sleep(0.3)
                # Flush queued events
                while event_queue:
                    ev = event_queue.pop(0)
                    seq += 1
                    ev_type = ev.get("type", "status")

                    if ev_type == "tool_call":
                        yield _sse_event("tool_call", {
                            "tool": ev.get("tool", "unknown"),
                            "message": f"Calling {ev.get('tool', 'tool')}...",
                        }, seq)
                    elif ev_type == "tool_output":
                        yield _sse_event("tool_done", {
                            "output": ev.get("output", "")[:2500],
                            "message": "Tool returned data.",
                        }, seq)
                    elif ev_type == "thinking":
                        yield _sse_event("thinking", {
                            "text": ev.get("text", ""),
                        }, seq)
                    elif ev_type == "text_delta":
                        # Skip raw text deltas — the plan JSON will come at the end
                        pass

            # Get the plan result (may raise)
            plan = plan_future.result()
            plan["workbook_id"] = body.workbook_id

            # Flush any remaining events
            while event_queue:
                ev = event_queue.pop(0)
                seq += 1
                ev_type = ev.get("type", "status")
                if ev_type == "tool_call":
                    yield _sse_event("tool_call", {
                        "tool": ev.get("tool", "unknown"),
                        "message": f"Calling {ev.get('tool', 'tool')}...",
                    }, seq)
                elif ev_type == "tool_output":
                    yield _sse_event("tool_done", {
                        "output": ev.get("output", "")[:2500],
                        "message": "Tool returned data.",
                    }, seq)

            seq += 1
            yield _sse_event("plan", plan, seq)

            seq += 1
            yield _sse_event("done", {}, seq)

        except Exception as e:
            logger.error(f"Plan generation failed: {e}", exc_info=True)
            seq += 1
            yield _sse_event("error", {"message": str(e), "fatal": True}, seq)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.post("/execute/cancel/{request_id}")
async def cancel_execution(request: Request, request_id: str):
    """
    Cancel an active Excel agent execution.
    
    Called by the frontend when the user clicks the stop button.
    Sets the cancel_event for the specified request_id, causing
    the streaming loop to break gracefully.
    """
    user_id = _get_user_id(request)
    try:
        cancelled = await _mark_excel_cancelled(request_id, user_id)
        status = "cancelled" if cancelled else "not_found"
        logger.info(f"[Excel] Cancel request for {request_id}: {status}")
        return {"status": status, "request_id": request_id}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this request")


@router.post("/execute/{request_id}/read-response")
async def read_response(request: Request, request_id: str, body: ExcelReadResponseBody):
    """
    Receive read response from frontend during active execution.
    
    Called by the add-in after reading a range requested by excel_read_range tool.
    The tool emits a read_range operation with a read_id, then waits for this
    endpoint to be called with the result.
    """
    from core.agents.excel_tools import resolve_pending_read
    
    user_id = _get_user_id(request)
    
    # Validate request_id is active and owned by this user
    async with _excel_streams_lock:
        entry = _active_excel_streams.get(request_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Request not found or expired")
        if entry["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    # Resolve the pending read (request_id identifies the agent execution context)
    resolved = await resolve_pending_read(request_id, body.read_id, {
        "success": body.success,
        "data": body.data,
        "error": body.error,
    })
    
    if not resolved:
        logger.warning(f"[Excel] Read response for unknown read_id: {body.read_id}")
        raise HTTPException(status_code=404, detail="Read request not found or already resolved")
    
    logger.debug(f"[Excel] Read response resolved: {body.read_id}, success={body.success}")
    return {"status": "ok"}


@router.post("/execute/{request_id}/approval-response")
async def approval_response(request: Request, request_id: str, body: ExcelApprovalResponseBody):
    """
    Receive approval/denial from frontend for a write operation.

    Called by the add-in when the user clicks Allow/Deny on the PermissionDialog.
    The backend tool is blocked on an asyncio.Future awaiting this response.
    """
    from core.agents.excel_tools import resolve_pending_approval

    user_id = _get_user_id(request)

    async with _excel_streams_lock:
        entry = _active_excel_streams.get(request_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Request not found or expired")
        if entry["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

    resolved = await resolve_pending_approval(request_id, body.approval_id, body.approved)

    if not resolved:
        logger.warning(f"[Excel] Approval response for unknown approval_id: {body.approval_id}")
        raise HTTPException(status_code=404, detail="Approval request not found or already resolved")

    logger.debug(f"[Excel] Approval resolved: {body.approval_id}, approved={body.approved}")
    return {"status": "ok"}


@router.post("/execute")
async def execute_endpoint(request: Request, body: ExcelPlanRequest):
    """
    Execute a user request via the SpreadsheetAgent (v2 — tool-calling architecture).

    The agent calls excel_* tools incrementally. Each tool call is streamed
    as an SSE event for the frontend to execute via Office.js.

    SSE events:
      - status:    {stage, message}     — progress update
      - tool_call: {tool, message}      — agent is calling a data/excel tool
      - tool_done: {output}             — tool returned
      - thinking:  {text}               — reasoning delta
      - operation: {action, sheet, ...} — EXECUTE THIS in Office.js
      - summary:   {text, count}        — agent finished, summary text
      - error:     {message, fatal}     — on failure
      - done:      {}                   — stream end

    The key difference from /plan: operations stream one at a time for
    immediate execution, instead of a batch plan at the end.
    """
    user_id = _get_user_id(request)

    # ── Resolve portfolio context ──
    portfolio_context = body.portfolio
    if body.portfolio_id and not portfolio_context:
        try:
            from api.routers.v6 import load_portfolio_context
            loaded = await load_portfolio_context(body.portfolio_id, user_id)
            if loaded:
                portfolio_context = loaded
        except Exception as e:
            logger.warning(f"Failed to load portfolio {body.portfolio_id}: {e}")

    # ── Validate file IDs and detect images for vision ──
    validated_file_ids: list[str] = []
    image_attachments: list[dict] = []  # [{file_id, content_type, stored_key}]
    if body.file_ids:
        try:
            import uuid as _uid
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                for fid in body.file_ids[:10]:
                    try:
                        row = await conn.fetchrow(
                            "SELECT id, content_type, stored_key FROM files WHERE id = $1",
                            _uid.UUID(fid),
                        )
                        if row:
                            fid_str = str(row["id"])
                            validated_file_ids.append(fid_str)
                            ct = row.get("content_type") or ""
                            if ct.startswith("image/"):
                                image_attachments.append({
                                    "file_id": fid_str,
                                    "content_type": ct,
                                    "stored_key": row.get("stored_key", ""),
                                })
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"File validation failed: {e}")

    # ── Load image bytes as base64 for vision ──
    image_b64_list: list[dict] = []
    if image_attachments:
        import base64 as _b64
        import os as _os
        _upload_dir = _os.getenv("UPLOAD_DIR", "/tmp/uploads")
        for img_info in image_attachments[:5]:
            try:
                fpath = _os.path.join(_upload_dir, img_info["stored_key"].replace("/", "_"))
                if _os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        raw = f.read()
                    data_url = f"data:{img_info['content_type']};base64,{_b64.b64encode(raw).decode()}"
                    image_b64_list.append({"file_id": img_info["file_id"], "data_url": data_url})
                    logger.info(f"[Excel] Loaded image for vision: {img_info['file_id']} ({len(raw)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to load image {img_info['file_id']}: {e}")

    # ── Load conversation history if thread_id provided ──
    conversation_history: list[dict[str, str]] = []
    logger.info(f"[Excel] Execute request - thread_id: {body.thread_id}, message: '{body.message[:50]}...'")
    if body.thread_id:
        try:
            import uuid as _uid
            org_id = _get_org_id(request)
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                rows = await conn.fetch("""
                    SELECT role, content FROM excel_chat_messages
                    WHERE thread_id = $1
                    ORDER BY created_at ASC
                    LIMIT 20
                """, _uid.UUID(body.thread_id))
                conversation_history = [{"role": r["role"], "content": r["content"]} for r in rows]
                logger.info(f"[Excel] Loaded {len(conversation_history)} messages from thread {body.thread_id}")
                if conversation_history:
                    logger.info(f"[Excel] First message: {conversation_history[0].get('role')}: {conversation_history[0].get('content', '')[:100]}...")
        except Exception as e:
            logger.warning(f"Failed to load conversation history: {e}")
    else:
        logger.info("[Excel] No thread_id provided - conversation history will be empty")

    async def event_generator() -> AsyncIterator[str]:
        import uuid as _uuid

        seq = 0
        event_queue: asyncio.Queue = asyncio.Queue()
        request_id = str(_uuid.uuid4())  # Unique ID for cancellation
        cancel_event: asyncio.Event | None = None
        agent_task: asyncio.Task | None = None

        async def on_agent_event(event: dict) -> None:
            """Callback — push events to the async queue (non-blocking)."""
            await event_queue.put(event)

        try:
            # Register this stream for explicit cancellation
            cancel_event = await _register_excel_stream(request_id, user_id)

            msg_id = str(_uuid.uuid4())[:8]

            seq += 1
            # Include request_id so frontend can call /cancel/{request_id}
            yield _sse_event("start", {"message_id": msg_id, "request_id": request_id}, seq)

            # Tool-first vs RAG path
            indexer = None  # avoid UnboundLocalError when skip_context=True
            if body.skip_context:
                # TOOL-FIRST PATH: Skip RAG search, agent will read on-demand
                chunks = []
                seq += 1
                yield _sse_event("status", {
                    "stage": "executing",
                    "message": "Agent is analyzing workbook...",
                }, seq)
                logger.info(f"[Excel] Tool-first mode: skipping RAG search for workbook {body.workbook_id}")
            else:
                # EXISTING RAG PATH: Search for relevant chunks
                seq += 1
                yield _sse_event("status", {
                    "stage": "searching",
                    "message": "Analyzing workbook...",
                }, seq)

                # Search workbook context
                indexer = get_workbook_indexer()
                chunks = await indexer.search(
                    workbook_id=body.workbook_id,
                    query=body.message,
                    user_id=user_id,
                    top_k=15,
                )

                seq += 1
                yield _sse_event("status", {
                    "stage": "executing",
                    "message": f"Found {len(chunks)} context chunks. Agent is working...",
                }, seq)

            # Build blueprint if available
            blueprint = body.blueprint if hasattr(body, "blueprint") else None

            from core.agents.SpreadsheetAgent import execute_streamed

            # Run agent in background — events flow through the queue
            non_image_file_ids = [
                fid for fid in validated_file_ids
                if fid not in {img["file_id"] for img in image_b64_list}
            ]

            agent_task = asyncio.ensure_future(
                execute_streamed(
                    message=body.message,
                    context_chunks=chunks,
                    conversation_history=conversation_history or None,
                    blueprint=blueprint,
                    on_event=on_agent_event,
                    selected_model=body.model,
                    portfolio_context=portfolio_context,
                    file_ids=non_image_file_ids or None,
                    user_id=user_id,
                    bloomberg=body.bloomberg,
                    cancel_event=cancel_event,
                    request_id=request_id,
                    selection=body.selection,
                    edit_approval_mode=body.edit_approval_mode,
                    on_stream_created=lambda rs: _set_result_streaming(request_id, rs),
                    images=image_b64_list or None,
                )
            )

            # Drain events from the queue as they arrive
            cancelled = False
            while True:
                # Check explicit cancellation (primary mechanism)
                if cancel_event.is_set():
                    logger.info(f"[Excel] Cancel event set for {request_id}, stopping execution")
                    # Cancel SDK streaming run first to stop in-flight MCP tool calls
                    async with _excel_streams_lock:
                        entry = _active_excel_streams.get(request_id)
                        rs = entry.get("result_streaming") if entry else None
                    if rs and not getattr(rs, "is_complete", True):
                        rs.cancel()
                    agent_task.cancel()
                    try:
                        await agent_task
                    except asyncio.CancelledError:
                        pass
                    cancelled = True
                    break

                # Check for client disconnect (fallback mechanism)
                if await request.is_disconnected():
                    logger.info(f"[Excel] Client disconnected for {request_id}, stopping execution")
                    cancel_event.set()
                    async with _excel_streams_lock:
                        entry = _active_excel_streams.get(request_id)
                        rs = entry.get("result_streaming") if entry else None
                    if rs and not getattr(rs, "is_complete", True):
                        rs.cancel()
                    agent_task.cancel()
                    try:
                        await agent_task
                    except asyncio.CancelledError:
                        pass
                    cancelled = True
                    break

                if agent_task.done() and event_queue.empty():
                    break

                try:
                    ev = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                seq += 1
                ev_type = ev.get("type", "status")

                if ev_type == "operation":
                    if ev.get("action") == "vba_code":
                        yield _sse_event("vba_code", {
                            "title": ev.get("title", ""),
                            "code": ev.get("code", ""),
                            "purpose": ev.get("purpose", ""),
                            "instructions": ev.get("instructions", ""),
                            "sheets_involved": ev.get("sheets_involved", []),
                        }, seq)
                    else:
                        yield _sse_event("operation", ev, seq)
                elif ev_type == "tool_call":
                    tool_event = {
                        "tool": ev.get("tool", "tool"),
                        "message": f"Calling {ev.get('tool', 'tool')}...",
                    }
                    if ev.get("parameters"):
                        tool_event["parameters"] = ev["parameters"]
                    if ev.get("call_id"):
                        tool_event["call_id"] = ev["call_id"]
                    yield _sse_event("tool_call", tool_event, seq)
                elif ev_type == "tool_done":
                    done_event = {
                        "output": ev.get("output", "")[:2500],
                    }
                    if ev.get("result"):
                        done_event["result"] = ev["result"]
                    if ev.get("call_id"):
                        done_event["call_id"] = ev["call_id"]
                    yield _sse_event("tool_done", done_event, seq)
                elif ev_type == "tool_server_done":
                    server_event: dict = {"tool": ev.get("tool", "")}
                    if ev.get("call_id"):
                        server_event["call_id"] = ev["call_id"]
                    if ev.get("server_duration_ms") is not None:
                        server_event["server_duration_ms"] = ev["server_duration_ms"]
                    yield _sse_event("tool_server_done", server_event, seq)
                elif ev_type == "model_params":
                    yield _sse_event("model_params", {
                        "model": ev.get("model", ""),
                        "params": ev.get("params", {}),
                    }, seq)
                elif ev_type == "thinking":
                    yield _sse_event("thinking", {
                        "text": ev.get("text", ""),
                    }, seq)
                elif ev_type == "token":
                    yield _sse_event("token", {
                        "text": ev.get("text", ""),
                    }, seq)
                elif ev_type == "ci_code_delta":
                    yield _sse_event("ci_code_delta", {
                        "delta": ev.get("delta", ""),
                        "call_id": ev.get("call_id"),
                    }, seq)
                elif ev_type == "ci_interpreting":
                    yield _sse_event("ci_interpreting", {
                        "call_id": ev.get("call_id"),
                    }, seq)
                elif ev_type == "api_usage":
                    yield _sse_event("api_usage", {
                        "index": ev.get("index", 0),
                        "timestamp": ev.get("timestamp", 0),
                        "input_tokens": ev.get("input_tokens", 0),
                        "output_tokens": ev.get("output_tokens", 0),
                        "cached_tokens": ev.get("cached_tokens", 0),
                        "cumulative_input_tokens": ev.get("cumulative_input_tokens", 0),
                        "tokens_per_min": ev.get("tokens_per_min", 0),
                    }, seq)

            # Handle cancelled state
            if cancelled:
                seq += 1
                yield _sse_event("summary", {
                    "text": "Cancelled by user.",
                    "count": 0,
                }, seq)
                seq += 1
                yield _sse_event("done", {}, seq)
                return

            # Get result from completed agent task
            if agent_task.done():
                exc = agent_task.exception()
                if exc:
                    raise exc
            result = agent_task.result()

            # Log BH performance summary before teardown
            try:
                from core.agents.binomial_hash import get_binomial_hash
                get_binomial_hash().log_summary()
            except Exception:
                pass

            # Persist BinomialHash manifests as vector chunks (if workbook indexed)
            if body.workbook_id and indexer is not None:
                try:
                    bh_result = await indexer.index_bh_datasets(
                        workbook_id=body.workbook_id,
                        user_id=user_id,
                    )
                    if bh_result.get("bh_chunks", 0) > 0:
                        logger.info("Persisted %d BH chunks", bh_result["bh_chunks"])
                except Exception as bh_err:
                    logger.warning("BH chunk indexing failed (non-fatal): %s", bh_err)

            seq += 1
            yield _sse_event("summary", {
                "text": result.get("summary", ""),
                "count": result.get("operations_count", 0),
            }, seq)

            seq += 1
            yield _sse_event("done", {}, seq)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            seq += 1
            yield _sse_event("error", {"message": str(e), "fatal": True}, seq)

        finally:
            # Always cleanup the stream registration
            await _cleanup_excel_stream(request_id)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.post("/plan/supplement")
async def supplement_plan(request: Request, body: ExcelPlanSupplementRequest):
    """
    Provide surgical read data to refine an in-progress plan.

    The add-in reads specific ranges requested by the agent's data_requests,
    then posts them here so the agent can refine its plan.
    """
    user_id = _get_user_id(request)
    indexer = get_workbook_indexer()

    from core.agents.SpreadsheetAgent import create_plan as agent_create_plan

    workbook_id = body.workbook_id
    original_message = body.message
    supplemental_data = body.data

    chunks = await indexer.search(
        workbook_id=workbook_id,
        query=original_message,
        user_id=user_id,
    )

    plan = await agent_create_plan(
        message=original_message,
        context_chunks=chunks,
        supplemental_data=supplemental_data,
    )
    plan["workbook_id"] = workbook_id
    return plan


@router.post("/validate")
async def validate_step_endpoint(request: Request, body: ExcelValidateRequest):
    """Validate a completed agent step against expected results."""
    user_id = _get_user_id(request)
    indexer = get_workbook_indexer()

    from core.agents.SpreadsheetAgent import validate_step as agent_validate

    # Get context for dependency checking
    chunks = await indexer.search(
        workbook_id=body.workbook_id,
        query=body.step.get("description", ""),
        user_id=user_id,
        top_k=5,
    )

    result = await agent_validate(
        step=body.step,
        actual=body.actual,
        context_chunks=chunks,
        attempt=body.attempt,
    )
    return result


# =============================================================================
# Data Endpoints (for =SENTRY.* custom Excel functions)
# Placeholder — will wrap existing MCP servers.
# =============================================================================


@router.get("/data/price")
async def get_price_endpoint(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
):
    """Get current stock price for =SENTRY.PRICE() custom function."""
    _get_user_id(request)

    from core.services.excel_data_service import get_price
    return await get_price(ticker)


@router.get("/data/metric")
async def get_metric_endpoint(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
    metric: str = Query(..., description="Metric name (e.g. marketCap, pe)"),
):
    """Get a financial metric for =SENTRY.METRIC() custom function."""
    _get_user_id(request)

    from core.services.excel_data_service import get_metric
    return await get_metric(ticker, metric)


@router.get("/data/fred")
async def get_fred_endpoint(
    request: Request,
    series: str = Query(..., description="FRED series ID (e.g. UNRATE, GDP)"),
):
    """Get FRED economic data for =SENTRY.FRED() custom function."""
    _get_user_id(request)

    from core.services.excel_data_service import get_fred
    return await get_fred(series)


# =============================================================================
# Workbook Chat Endpoints (save / load / delete)
# Separate from main chat_sessions — uses excel_chat_threads + excel_chat_messages.
# =============================================================================


@router.get("/chats", response_model=list[ExcelChatThreadSummary])
async def list_workbook_chats(
    request: Request,
    workbook_id: str = Query(None, description="Filter by workbook (optional)"),
):
    """List all excel chat threads for the current user, optionally filtered by workbook."""
    user_id = _get_user_id(request)
    org_id = _get_org_id(request) or ""

    if not config.enable_postgres:
        return []

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        if workbook_id:
            # workbook_id param is actually workbook_hash — join to filter correctly
            rows = await conn.fetch("""
                SELECT t.id, r.workbook_hash, t.title, t.model, t.created_at, t.updated_at,
                       (SELECT COUNT(*) FROM excel_chat_messages m WHERE m.thread_id = t.id) AS message_count
                FROM excel_chat_threads t
                JOIN workbook_registry r ON r.id = t.workbook_id
                WHERE r.workbook_hash = $1
                ORDER BY t.updated_at DESC
                LIMIT 50
            """, workbook_id)
        else:
            rows = await conn.fetch("""
                SELECT t.id, r.workbook_hash, t.title, t.model, t.created_at, t.updated_at,
                       (SELECT COUNT(*) FROM excel_chat_messages m WHERE m.thread_id = t.id) AS message_count
                FROM excel_chat_threads t
                JOIN workbook_registry r ON r.id = t.workbook_id
                ORDER BY t.updated_at DESC
                LIMIT 50
            """)

    return [
        ExcelChatThreadSummary(
            id=str(r["id"]),
            workbook_id=r["workbook_hash"],  # Return hash for frontend consistency
            title=r["title"],
            model=r["model"],
            created_at=str(r["created_at"]) if r["created_at"] else None,
            updated_at=str(r["updated_at"]) if r["updated_at"] else None,
            message_count=r["message_count"],
        )
        for r in rows
    ]


@router.get("/chats/{thread_id}/messages", response_model=list[ExcelChatMessageOut])
async def load_workbook_chat(request: Request, thread_id: str):
    """Load all messages for a specific excel chat thread."""
    user_id = _get_user_id(request)
    org_id = _get_org_id(request) or ""

    if not config.enable_postgres:
        return []

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        rows = await conn.fetch("""
            SELECT id, role, content, metadata, created_at
            FROM excel_chat_messages
            WHERE thread_id = $1
            ORDER BY created_at ASC
            LIMIT 500
        """, thread_id)

    return [
        ExcelChatMessageOut(
            id=str(r["id"]),
            role=r["role"],
            content=r["content"],
            metadata=json.loads(r["metadata"]) if r["metadata"] else None,
            created_at=str(r["created_at"]) if r["created_at"] else None,
        )
        for r in rows
    ]


@router.post("/chats", response_model=ExcelChatThreadSummary)
async def save_workbook_chat(request: Request, body: ExcelChatBulkSave):
    """
    Save an entire chat history for a workbook.

    Creates a new thread and bulk-inserts all messages.
    Called by the add-in when the user explicitly saves or when the session ends.
    """
    user_id = _get_user_id(request)
    org_id = _get_org_id(request) or ""

    if not config.enable_postgres:
        raise HTTPException(status_code=503, detail="Database not available")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        # Resolve workbook_hash -> workbook_registry.id (body.workbook_id is actually the hash)
        registry_row = await conn.fetchrow(
            "SELECT id FROM workbook_registry WHERE workbook_hash = $1",
            body.workbook_id,
        )
        if registry_row:
            workbook_registry_id = registry_row["id"]
        else:
            # Create minimal registry entry (not indexed yet, just identity for chat FK)
            registry_row = await conn.fetchrow("""
                INSERT INTO workbook_registry (user_id, org_id, workbook_hash, workbook_name)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, user_id, org_id, body.workbook_id, body.title or "Untitled")
            workbook_registry_id = registry_row["id"]

        # Create thread with the resolved registry ID
        thread_row = await conn.fetchrow("""
            INSERT INTO excel_chat_threads (workbook_id, user_id, org_id, title, model)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, workbook_id, title, model, created_at, updated_at
        """, workbook_registry_id, user_id, org_id, body.title, body.model)

        thread_id = thread_row["id"]

        # Bulk insert messages
        if body.messages:
            values = []
            for msg in body.messages:
                meta_json = json.dumps(msg.metadata) if msg.metadata else None
                values.append((thread_id, user_id, org_id, msg.role, msg.content, meta_json))

            await conn.executemany("""
                INSERT INTO excel_chat_messages (thread_id, user_id, org_id, role, content, metadata)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """, values)

    return ExcelChatThreadSummary(
        id=str(thread_row["id"]),
        workbook_id=body.workbook_id,  # Return the original hash for frontend consistency
        title=thread_row["title"],
        model=thread_row["model"],
        created_at=str(thread_row["created_at"]) if thread_row["created_at"] else None,
        updated_at=str(thread_row["updated_at"]) if thread_row["updated_at"] else None,
        message_count=len(body.messages),
    )


@router.post("/chats/{thread_id}/messages", response_model=ExcelChatMessageOut)
async def append_message(request: Request, thread_id: str, body: ExcelChatMessageCreate):
    """Append a single message to an existing excel chat thread."""
    user_id = _get_user_id(request)
    org_id = _get_org_id(request) or ""

    if not config.enable_postgres:
        raise HTTPException(status_code=503, detail="Database not available")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        meta_json = json.dumps(body.metadata) if body.metadata else None
        row = await conn.fetchrow("""
            INSERT INTO excel_chat_messages (thread_id, user_id, org_id, role, content, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING id, role, content, metadata, created_at
        """, thread_id, user_id, org_id, body.role, body.content, meta_json)

        # Touch the thread's updated_at
        await conn.execute("""
            UPDATE excel_chat_threads SET updated_at = NOW() WHERE id = $1
        """, thread_id)

    return ExcelChatMessageOut(
        id=str(row["id"]),
        role=row["role"],
        content=row["content"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


@router.delete("/chats/{thread_id}")
async def delete_workbook_chat(request: Request, thread_id: str):
    """Delete a single excel chat thread and all its messages (cascade)."""
    user_id = _get_user_id(request)
    org_id = _get_org_id(request) or ""

    if not config.enable_postgres:
        raise HTTPException(status_code=503, detail="Database not available")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        result = await conn.execute("""
            DELETE FROM excel_chat_threads WHERE id = $1
        """, thread_id)

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Thread not found")

    return {"deleted": True, "thread_id": thread_id}


@router.post("/chats/bulk-delete")
async def bulk_delete_workbook_chats(request: Request, body: ExcelChatBulkDeleteRequest):
    """Delete multiple excel chat threads at once."""
    user_id = _get_user_id(request)
    org_id = _get_org_id(request) or ""

    if not config.enable_postgres:
        raise HTTPException(status_code=503, detail="Database not available")

    if not body.thread_ids:
        return {"deleted_count": 0}

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        # Convert list to array for IN clause
        result = await conn.execute("""
            DELETE FROM excel_chat_threads WHERE id = ANY($1::uuid[])
        """, body.thread_ids)

    # Parse "DELETE N" to get count
    count = 0
    if result and result.startswith("DELETE"):
        try:
            count = int(result.split(" ")[1])
        except (IndexError, ValueError):
            pass

    return {"deleted_count": count}
