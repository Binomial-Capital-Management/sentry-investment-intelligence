from fastapi import APIRouter, HTTPException, Request, status
from typing import List, Optional, Dict, Any, Tuple
import uuid
import logging
from datetime import datetime

from api.models_dir.chat import ChatSessionCreate, ChatSessionSummary, ChatMessageCreate, ChatMessageResponse
from api.models import ChatResponse  # reuse existing response envelope
from core.database.postgres_client import get_postgres_rls_client
from api.utils import resolve_session_id
from api.db import load_recent_history, insert_message
from api.orchestrator import get_v6_orchestrator
from core.config import config

router = APIRouter(prefix="/api/chats", tags=["chats"])
logger = logging.getLogger(__name__)


def validate_session_id(session_id: str) -> Tuple[str, bool]:
    """
    Validate and normalize session_id.
    Returns (session_id, is_valid_uuid) tuple.
    
    Accepts both UUID format and legacy web_ format for backwards compatibility.
    For legacy IDs, returns (session_id, False) - caller should return empty results.
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Accept legacy web_ prefixed IDs (backwards compatibility) - return empty results
    if session_id.startswith("web_"):
        return session_id, False
    
    # Try to parse as UUID
    try:
        uuid.UUID(session_id)
        return session_id, True
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid session_id format: {session_id}")

@router.get("", response_model=List[ChatSessionSummary])
async def list_chats(
    request: Request,
):
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = getattr(request.state, 'org_id', None)

    # If PostgreSQL is disabled, return empty list (chats not persisted)
    if not config.enable_postgres:
        return []

    # Use PostgreSQL if enabled
    pg = await get_postgres_rls_client()
    sessions = await pg.get_user_sessions(user_id=user_id, org_id=org_id, limit=50)
    
    # Convert UUID and datetime to strings for Pydantic model
    return [ChatSessionSummary(
        id=str(s['id']),
        title=s.get('title'),
        created_at=s['created_at'].isoformat() if s.get('created_at') else None,
        updated_at=s['updated_at'].isoformat() if s.get('updated_at') else None
    ) for s in sessions]

@router.post("", response_model=ChatSessionSummary, status_code=status.HTTP_201_CREATED)
async def create_chat(
    payload: ChatSessionCreate,
    request: Request,
):
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = getattr(request.state, 'org_id', None)

    # If PostgreSQL is disabled, create a simple session without database
    if not config.enable_postgres:
        session_id = str(uuid.uuid4())
        return ChatSessionSummary(
            id=session_id,
            title=payload.title or "New Chat",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )

    # Use PostgreSQL if enabled
    pg = await get_postgres_rls_client()
    s = await pg.create_chat_session(user_id=user_id, title=payload.title, org_id=org_id)
    if not s:
        raise HTTPException(status_code=500, detail="Failed to create chat")
    
    # Convert UUID and datetime to strings for Pydantic model
    return ChatSessionSummary(
        id=str(s['id']),
        title=s.get('title'),
        created_at=s['created_at'].isoformat() if s.get('created_at') else None,
        updated_at=s['updated_at'].isoformat() if s.get('updated_at') else None
    )

@router.patch("/{session_id}", response_model=ChatSessionSummary)
async def update_chat(
    session_id: str,
    payload: ChatSessionCreate,
    request: Request,
):
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = getattr(request.state, 'org_id', None)

    if not config.enable_postgres:
        # Return mock response in dev mode
        return ChatSessionSummary(
            id=session_id,
            title=payload.title or "New Chat",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )

    pg = await get_postgres_rls_client()
    s = await pg.update_chat_session(
        user_id=user_id,
        session_id=session_id,
        org_id=org_id,
        title=payload.title
    )
    if not s:
        raise HTTPException(status_code=404, detail="Chat not found")

    return ChatSessionSummary(
        id=str(s['id']),
        title=s.get('title'),
        created_at=s['created_at'].isoformat() if s.get('created_at') else None,
        updated_at=s['updated_at'].isoformat() if s.get('updated_at') else None
    )

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    session_id: str,
    request: Request,
):
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = getattr(request.state, 'org_id', None)

    # If PostgreSQL is disabled, there is no persisted chat state to delete.
    # Return 204 to keep UX consistent in development.
    if not config.enable_postgres:
        return None

    pg = await get_postgres_rls_client()
    ok = await pg.delete_chat_session(user_id=user_id, session_id=session_id, org_id=org_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat not found or not deleted")
    return None


from pydantic import BaseModel


class BulkDeleteRequest(BaseModel):
    session_ids: List[str]


class BulkDeleteResponse(BaseModel):
    deleted_count: int


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_chats(
    payload: BulkDeleteRequest,
    request: Request,
):
    """Bulk delete multiple chat sessions at once."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = getattr(request.state, 'org_id', None)

    if not payload.session_ids:
        return BulkDeleteResponse(deleted_count=0)

    # Validate all session IDs are valid UUIDs
    for sid in payload.session_ids:
        try:
            uuid.UUID(sid)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid session_id format: {sid}")

    # If PostgreSQL is disabled, return 0 (nothing to delete)
    if not config.enable_postgres:
        return BulkDeleteResponse(deleted_count=len(payload.session_ids))

    pg = await get_postgres_rls_client()
    deleted_count = await pg.bulk_delete_chat_sessions(
        user_id=user_id,
        session_ids=payload.session_ids,
        org_id=org_id
    )
    
    return BulkDeleteResponse(deleted_count=deleted_count)

@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    request: Request,
):
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = getattr(request.state, 'org_id', None)

    # Normalize session ID from multiple sources: path param, header, or query param
    session_id = resolve_session_id(
        session_id,  # Path param takes priority
        dict(request.headers),
        dict(request.query_params)
    )

    # Validate session_id - accept legacy web_ IDs gracefully
    session_id, is_valid_uuid = validate_session_id(session_id)
    if not is_valid_uuid:
        # Legacy ID - return empty messages (local-only chat)
        # Must match expected response format: { session_id, messages: [] }
        return {"session_id": session_id, "messages": []}

    # Read from Postgres chat_messages with RLS context
    if config.enable_postgres:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # Get messages ordered by created_at ASC
            messages = await conn.fetch("""
                SELECT id, role, content, created_at, metadata
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT 200
            """, session_id)

            # Format messages for compatibility with existing frontend
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "id": str(msg['id']),
                    "role": msg['role'],
                    "content": msg['content'],
                    "timestamp": msg['created_at'].isoformat() if msg['created_at'] else None,
                    "metadata": msg.get('metadata')
                })

            return {"session_id": session_id, "messages": formatted_messages}
    else:
        # Fallback to SQLite for development
        history = await load_recent_history(session_id, limit=200)
        transformed = []
        from datetime import datetime as _dt
        for entry in history:
            content = entry.get("content", "")
            metadata: Dict[str, Any] | None = None
            lowered = content.strip().lower()
            user_note = lowered.endswith("_[cancelled by user]_".lower())
            backend_note = lowered.endswith("_[stream cancelled]_".lower()) or lowered.endswith("_[stream cancelled: connection lost]_".lower())
            if user_note or backend_note:
                reason = 'user' if user_note else 'backend'
                note_token = '_[Cancelled by user]_' if user_note else ('_[Stream cancelled: connection lost]_' if 'connection lost' in lowered else '_[Stream cancelled]_')
                partial = content.replace(note_token, '').strip() or None
                metadata = {
                    'status': 'cancelled',
                    'reason': reason,
                    'partialContent': partial,
                    'note': note_token,
                }
            created_at = entry.get('created_at')
            try:
                timestamp = _dt.fromisoformat(created_at) if created_at else None
            except Exception:
                timestamp = None
            transformed.append({
                'id': entry.get('id'),
                'role': entry.get('role', 'assistant'),
                'content': content,
                'timestamp': timestamp.isoformat() if timestamp else None,
                'metadata': metadata,
            })
        return {"session_id": session_id, "messages": transformed}

@router.post("/{session_id}/messages", response_model=ChatResponse)
async def send_message(
    session_id: str,
    payload: ChatMessageCreate,
    request: Request,
):
    orchestrator = get_v6_orchestrator()
    pg = await get_postgres_rls_client()

    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = getattr(request.state, 'org_id', None)

    # Normalize session ID from multiple sources: path param, body, header, or query param
    # Priority: body -> path param -> header -> query param -> generate new
    session_id = resolve_session_id(
        getattr(payload, 'session_id', None) or session_id,
        dict(request.headers),
        dict(request.query_params)
    )

    # Validate session_id - accept legacy web_ IDs gracefully
    session_id, is_valid_uuid = validate_session_id(session_id)
    if not is_valid_uuid:
        # For POST messages with legacy IDs, we need to convert to a proper UUID session
        # Generate a new UUID and use that instead
        session_id = str(uuid.uuid4())
        logger.info(f"Converted legacy session to UUID: {session_id}")

    # Optionally load referenced portfolio to pass as context
    portfolio_context: Optional[Dict[str, Any]] = None
    if payload.portfolio_id:
        p = await pg.get_portfolio_by_id(user_id=clerk_user_id, portfolio_id=payload.portfolio_id, org_id=org_id)
        if not p:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        # Aggregate lots into summary lines to reduce context bloat
        # Instead of sending all individual lots, we send:
        # - totalQuantity: sum of lot quantities
        # - avgCostBasis: weighted average purchase price
        # - lotCount: number of lots (for reference)
        holdings_data = p.get("holdings", [])
        if isinstance(holdings_data, str):
            try:
                import json
                holdings_data = json.loads(holdings_data)
            except Exception:
                holdings_data = []
        
        aggregated_holdings = None
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
        
        portfolio_context = {
            "name": p.get("name"),
            "tickers": p.get("tickers", []),
            "weights": p.get("weights", []),
            "is_default": p.get("is_default", False),
            "holdings": aggregated_holdings,
            "value": p.get("value"),
            "cash_balance": p.get("cash_balance"),
        }

    # Persist user message to Postgres with RLS context
    user_msg_id = uuid.uuid4().hex
    user_message_saved = False

    if config.enable_postgres:
        try:
            await pg.save_chat_message(
                user_id=clerk_user_id,
                session_id=session_id,
                role='user',
                content=payload.message,
                metadata={"portfolio_id": payload.portfolio_id} if payload.portfolio_id else None,
                org_id=org_id
            )
            user_message_saved = True
        except Exception as e:
            # Log error but continue with SQLite fallback
            logger.warning(f"Failed to save user message to Postgres: {e}")

    # Fallback to SQLite for development or Postgres failure
    if not user_message_saved or not config.enable_postgres:
        await insert_message(user_msg_id, session_id, 'user', payload.message, datetime.now().isoformat())

    # Build history from Postgres if available, otherwise SQLite
    if config.enable_postgres:
        # Load history from Postgres using RLS context
        async with pg.acquire_with_org_context(clerk_user_id, org_id) as conn:
            messages = await conn.fetch("""
                SELECT role, content, created_at
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT 50
            """, session_id)

            history = []
            for msg in messages:
                history.append({
                    "role": msg['role'],
                    "content": msg['content'],
                    "timestamp": msg['created_at'].isoformat() if msg['created_at'] else None
                })
    else:
        # Fallback to SQLite
        history = await load_recent_history(session_id)

    # Call orchestrator with optional portfolio context and agent mode
    result = await orchestrator.process_query(
        query=payload.message,
        session_id=session_id,
        history=history,
        portfolio_context=portfolio_context,
        agent_mode=payload.agent_mode,  # Pass agent mode to orchestrator
    )

    # Normalize result into ChatResponse fields
    if isinstance(result, str):
        response_text = result
        sources = None
        charts = None
        metrics = None
    elif isinstance(result, dict):
        response_text = result.get("content") or result.get("response") or str(result)
        sources = result.get("sources")
        charts = result.get("charts")
        metrics = result.get("metrics")
    else:
        response_text = str(result)
        sources = None
        charts = None
        metrics = None

    # Persist assistant message to Postgres with RLS context
    assistant_msg_id = uuid.uuid4().hex
    assistant_message_saved = False

    if config.enable_postgres:
        try:
            await pg.save_chat_message(
                user_id=clerk_user_id,
                session_id=session_id,
                role='assistant',
                content=response_text,
                metadata={"portfolio_id": payload.portfolio_id} if payload.portfolio_id else None,
                org_id=org_id  # ✅ FIXED: Now matches user message save pattern
            )
            assistant_message_saved = True
        except Exception as e:
            # Log error but continue with SQLite fallback
            logger.warning(f"Failed to save assistant message to Postgres: {e}")

    # Fallback to SQLite for development or Postgres failure
    if not assistant_message_saved or not config.enable_postgres:
        await insert_message(assistant_msg_id, session_id, 'assistant', response_text, datetime.now().isoformat())

    return ChatResponse(
        response=response_text,
        sources=sources,
        charts=charts,
        metrics=metrics,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        message_id=assistant_msg_id,
    )
