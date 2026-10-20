"""Canvas Chat Router.

Thin router that delegates to CanvasChatService for all business logic.
Uses FastAPI dependency injection for auth and database access.
"""

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import logging

from core.exceptions import ThreadNotFoundError, DatabaseError
from ...types import CreateThreadRequest, UpdateThreadRequest, ActionResultRequest, WorkspaceSnapshotRequest
from ..dependencies import DB, CurrentUser, OrgId

logger = logging.getLogger(__name__)

router = APIRouter(tags=["canvas-chat"])


# =============================================================================
# CANVAS CHAT THREAD MANAGEMENT
# =============================================================================


@router.get("/chat/threads")
async def get_chat_threads(user_id: CurrentUser, org_id: OrgId, db: DB):
    """Get all Canvas chat threads for the user."""
    threads = await db.get_canvas_chat_threads(
        user_id=user_id,
        org_id=org_id,
    )
    return {"threads": threads}


@router.post("/chat/threads")
async def create_chat_thread(body: CreateThreadRequest, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Create a new Canvas chat thread."""
    thread = await db.create_canvas_chat_thread(
        user_id=user_id,
        org_id=org_id,
        title=body.title,
    )

    if not thread:
        raise DatabaseError("Failed to create thread")

    return thread


@router.get("/chat/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Get messages for a Canvas chat thread."""
    messages = await db.get_canvas_chat_messages(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
    )
    return {"messages": messages}


@router.delete("/chat/threads/{thread_id}")
async def delete_chat_thread(thread_id: str, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Delete a Canvas chat thread."""
    success = await db.delete_canvas_chat_thread(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
    )

    if not success:
        raise ThreadNotFoundError(thread_id)

    return {"status": "success"}


@router.patch("/chat/threads/{thread_id}")
async def update_chat_thread(thread_id: str, body: UpdateThreadRequest, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Update a Canvas chat thread (rename or pin/unpin)."""
    thread = await db.update_canvas_chat_thread(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
        title=body.title,
        pinned=body.pinned,
    )

    if not thread:
        raise ThreadNotFoundError(thread_id)

    return thread


# =============================================================================
# WORKSPACE SNAPSHOT (Chat-Workspace Binding)
# =============================================================================


@router.get("/chat/threads/{thread_id}/workspace")
async def get_workspace_snapshot(thread_id: str, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Get workspace snapshot for a chat thread.
    
    Returns stored tab configurations for restoring workspace state
    when loading a chat from history.
    """
    snapshot = await db.get_canvas_workspace_snapshot(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
    )
    return {"snapshot": snapshot}


@router.patch("/chat/threads/{thread_id}/workspace")
async def save_workspace_snapshot(
    thread_id: str, 
    body: WorkspaceSnapshotRequest, 
    user_id: CurrentUser, 
    org_id: OrgId, 
    db: DB
):
    """Save workspace snapshot for a chat thread.
    
    Stores tab configurations (not data) that can be restored when loading
    a chat from history. Called after each AI action that modifies tabs.
    """
    snapshot = {
        "captured_at": body.captured_at,
        "tabs": body.tabs,
        "activeTabId": body.activeTabId,
    }
    
    success = await db.save_canvas_workspace_snapshot(
        thread_id=thread_id,
        user_id=user_id,
        snapshot=snapshot,
        org_id=org_id,
    )
    
    if not success:
        raise DatabaseError("Failed to save workspace snapshot")
    
    return {"status": "success"}


@router.delete("/chat/threads/{thread_id}/workspace")
async def clear_workspace_snapshot(thread_id: str, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Clear workspace snapshot for a chat thread.
    
    Called when all chat-linked tabs are deleted.
    """
    success = await db.clear_canvas_workspace_snapshot(
        thread_id=thread_id,
        user_id=user_id,
        org_id=org_id,
    )
    
    if not success:
        raise DatabaseError("Failed to clear workspace snapshot")
    
    return {"status": "success"}


# =============================================================================
# ACTION RESULT FEEDBACK (for AI feedback loop)
# =============================================================================


@router.post("/chat/action-result")
async def report_action_result(body: ActionResultRequest, user_id: CurrentUser, org_id: OrgId, db: DB):
    """
    Report the result of an agent action execution.
    
    Called by frontend after executing (or failing to execute) an AI-initiated action.
    Results are stored and injected into the AI's context on the next turn.
    
    Args:
        body: Action result details (thread_id, action_id, success, error, etc.)
    """
    try:
        await db.store_canvas_action_result(
            thread_id=body.thread_id,
            action_id=body.action_id,
            action_type=body.action_type,
            symbol=body.symbol,
            success=body.success,
            error=body.error,
            cancelled=body.cancelled or False,
            data=body.data,
            user_id=user_id,
            org_id=org_id,
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to store action result: {e}")
        raise DatabaseError(f"Failed to store action result: {str(e)}")


# =============================================================================
# CANVAS AI CHAT STREAMING ENDPOINT
# =============================================================================


@router.get("/chat/stream")
async def canvas_chat_stream(
    message: str,
    user_id: CurrentUser,
    org_id: OrgId,
    process_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    selected_model: Optional[str] = Query(None, alias="model"),
    last_event_id: Optional[str] = None,
    data_context: Optional[str] = None,
):
    """
    Stream Canvas AI chat with SSE events.

    Args:
        message: User's message/question
        process_id: Optional Canvas process ID to provide context
        thread_id: Optional thread ID for conversation continuity
        selected_model: Optional model override
        last_event_id: Optional event ID for resume (skip thread creation if present)
        data_context: Optional JSON string with data context (for DataWorkspace, etc.)
    """
    # Import service and create request
    from core.services.canvas_chat_service import (
        get_canvas_chat_service, 
        ChatStreamRequest
    )
    
    service = await get_canvas_chat_service()
    
    stream_request = ChatStreamRequest(
        message=message,
        user_id=user_id,
        org_id=org_id,
        process_id=process_id,
        thread_id=thread_id,
        model=selected_model,
        last_event_id=last_event_id,
        data_context=data_context,
    )

    return StreamingResponse(
        service.stream_chat(stream_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )
