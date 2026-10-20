"""
Screener API Router
Standalone stock screening endpoints - NO LangGraph integration.
Following InsightGeneratorAgent pattern with direct Runner execution.
"""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import Dict, Any
from agents import Runner, SQLiteSession
import asyncio
import uuid
import logging

from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client
from core.ai.langgraph_utils import execute_with_retry

config = get_config()
router = APIRouter(prefix="/v6/screener", tags=["screener"])
logger = logging.getLogger(__name__)

# Mode-specific agents - each mode gets its own agent with only the relevant server
_screener_agents: dict = {}

def get_screener_agent(mode: str = "stocks"):
    """
    Get mode-specific screener agent. Forces routing by only including relevant server.
    
    Modes:
    - stocks: FMP run_stock_screener only
    - flow: UW uw_stock_screener only  
    - options: UW uw_hottest_contracts only
    - analysts: UW uw_analyst_ratings only
    """
    global _screener_agents
    
    if mode in _screener_agents:
        return _screener_agents[mode]
    
    import os
    from core.agents.ScreenerAgent import create_screener_agent
    
    agent = None
    
    if mode == "stocks":
        # FMP basic stock screener
        fmp_api_key = os.getenv("FMP_API_KEY")
        if fmp_api_key:
            from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
            market_server = FMPMarketDataServer(api_key=fmp_api_key)
            agent = create_screener_agent(market_server=market_server, mode=mode)
            logger.info(f"Screener agent [{mode}]: FMP server")
        else:
            from core.mcp_servers.YFinanceServer import YFinanceServer
            market_server = YFinanceServer()
            agent = create_screener_agent(market_server=market_server, mode=mode)
            logger.info(f"Screener agent [{mode}]: YFinance fallback")
    
    elif mode == "flow":
        # UW stock screener (options flow on stocks)
        uw_api_key = os.getenv("UW_API_KEY") or os.getenv("UNUSUAL_WHALES_API_KEY")
        if uw_api_key:
            from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
            uw_market_server = UWMarketServer(api_key=uw_api_key)
            agent = create_screener_agent(uw_market_server=uw_market_server, mode=mode)
            logger.info(f"Screener agent [{mode}]: UW Market server")
        else:
            raise ValueError("UW_API_KEY required for flow mode")
    
    elif mode == "options":
        # UW hottest contracts (option contracts)
        uw_api_key = os.getenv("UW_API_KEY") or os.getenv("UNUSUAL_WHALES_API_KEY")
        if uw_api_key:
            from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
            uw_options_server = UWOptionsServer(api_key=uw_api_key)
            agent = create_screener_agent(uw_options_server=uw_options_server, mode=mode)
            logger.info(f"Screener agent [{mode}]: UW Options server")
        else:
            raise ValueError("UW_API_KEY required for options mode")
    
    elif mode == "analysts":
        # UW analyst ratings
        uw_api_key = os.getenv("UW_API_KEY") or os.getenv("UNUSUAL_WHALES_API_KEY")
        if uw_api_key:
            from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
            uw_market_server = UWMarketServer(api_key=uw_api_key)
            agent = create_screener_agent(uw_market_server=uw_market_server, mode=mode)
            logger.info(f"Screener agent [{mode}]: UW Market server (analysts)")
        else:
            raise ValueError("UW_API_KEY required for analysts mode")
    
    else:
        raise ValueError(f"Unknown screener mode: {mode}")
    
    _screener_agents[mode] = agent
    return agent


@router.post("/chat")
async def screener_chat(request: Request, body: dict):
    """
    Execute screener query using direct Runner execution (NO LangGraph).
    Follows InsightGeneratorAgent pattern - standalone agent.

    Modes:
    - stocks: FMP basic stock screener (fundamentals)
    - flow: UW stock screener (options flow on stocks)
    - options: UW hottest contracts (option contracts)
    - analysts: UW analyst ratings

    Returns AI response with markdown table of screener results.
    """
    user_id = request.state.user_id
    query = body.get("message")
    session_id = body.get("session_id")
    mode = body.get("mode", "stocks")  # Default to FMP stocks

    if not query:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Validate mode
    valid_modes = {"stocks", "flow", "options", "analysts"}
    if mode not in valid_modes:
        mode = "stocks"

    try:
        pg = await get_postgres_rls_client()
    except Exception as e:
        logger.error("Failed to acquire Postgres client for screener", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Database unavailable", "error_type": "db_unavailable"}
        ) from e

    # Always create session with provided ID or generate new one
    # This ensures the session exists before we try to save messages
    if not session_id:
        session_id = str(uuid.uuid4())

    logger.info(f"Creating/verifying screener session {session_id} for user {user_id}")
    session = await pg.create_screener_session(
        user_id=user_id,
        session_id=session_id,
        title=query[:100]
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to create session",
                "error_type": "db_write_failed",
                "session_id": session_id
            }
        )

    logger.info(f"Session confirmed: {session['id']}")

    try:
        # Get mode-specific screener agent (forces routing to correct tool)
        try:
            screener_agent = get_screener_agent(mode)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Create SQLite session for agent persistence
        sqlite_session = SQLiteSession(session_id, config.openai_sessions_db_path)

        # Execute agent with retry + timeout (NO LangGraph)
        logger.info(f"Executing screener agent for user {user_id}, session {session_id}, mode {mode}")
        agent_timeout = getattr(config, "agent_node_timeout_seconds", 1200)
        try:
            result = await asyncio.wait_for(
                execute_with_retry(
                    screener_agent,
                    query,  # Original query - routing is forced by agent's available tools
                    sqlite_session,
                    max_turns=15,
                    agent_name=f"screener_{mode}",
                    selected_model=config.agent_model,
                ),
                timeout=agent_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(f"Screener agent timed out after {agent_timeout}s for session {session_id}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "message": "Screener request timed out. Please try again with a narrower filter.",
                    "error_type": "timeout",
                    "timeout_seconds": agent_timeout,
                    "session_id": session_id,
                },
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Save messages to PostgreSQL using helper methods (ensures RLS consistency)
        logger.info(f"Saving user message to session {session_id}")
        try:
            user_msg_id = await pg.save_screener_message(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=query
            )
        except Exception as e:
            logger.error("Failed to persist user screener message", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Database unavailable while saving user message",
                    "error_type": "db_unavailable",
                    "session_id": session_id
                }
            ) from e

        if not user_msg_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "Failed to save user message",
                    "error_type": "db_write_failed",
                    "session_id": session_id
                }
            )

        logger.info(f"User message saved: {user_msg_id}")

        logger.info(f"Saving assistant message to session {session_id}")
        try:
            assistant_msg_id = await pg.save_screener_message(
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content=response
            )
        except Exception as e:
            logger.error("Failed to persist assistant screener message", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Database unavailable while saving assistant message",
                    "error_type": "db_unavailable",
                    "session_id": session_id
                }
            ) from e

        if not assistant_msg_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "Failed to save assistant message",
                    "error_type": "db_write_failed",
                    "session_id": session_id
                }
            )

        logger.info(f"Assistant message saved: {assistant_msg_id}")

        return JSONResponse({
            "response": response,
            "session_id": session_id,
            "status": "completed"  # Indicate synchronous completion
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Screener chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Screener agent execution failed",
                "error": str(e),
                "error_type": "agent_error",
                "session_id": session_id
            }
        )


@router.post("/sessions")
async def create_screener_session(request: Request):
    """Create a new screener session"""
    user_id = request.state.user_id

    pg = await get_postgres_rls_client()
    session = await pg.create_screener_session(
        user_id=user_id,
        title="New Screening Session"
    )

    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return JSONResponse({
        "session_id": str(session['id']),
        "status": "created"
    })


@router.get("/sessions")
async def list_screener_sessions(request: Request):
    """List user's screener sessions"""
    user_id = request.state.user_id

    pg = await get_postgres_rls_client()
    sessions_data = await pg.get_screener_sessions(user_id=user_id, limit=50)

    sessions = [
        {
            "id": str(s["id"]),
            "title": s["title"],
            "created_at": s["created_at"].isoformat(),
            "updated_at": s["updated_at"].isoformat()
        }
        for s in sessions_data
    ]

    return JSONResponse({"sessions": sessions})


@router.get("/sessions/{session_id}/messages")
async def get_screener_messages(request: Request, session_id: str):
    """Get messages for a screener session"""
    user_id = request.state.user_id

    pg = await get_postgres_rls_client()
    messages_data = await pg.get_screener_messages(
        user_id=user_id,
        session_id=session_id
    )

    messages = [
        {
            "id": str(msg["id"]),
            "role": msg["role"],
            "content": msg["content"],
            "metadata": msg["metadata"],
            "created_at": msg["created_at"].isoformat()
        }
        for msg in messages_data
    ]

    return JSONResponse({"messages": messages})


@router.get("/session/{session_id}")
async def get_screener_session_status(request: Request, session_id: str):
    """
    Poll endpoint to check screener session status and get results.
    Used by frontend to restore state after page refresh.

    Returns:
    - status: 'completed' if assistant message exists, 'in_progress' otherwise
    - response: The assistant's response (markdown table) if completed
    - session_id: The session ID
    """
    user_id = request.state.user_id

    pg = await get_postgres_rls_client()

    # Verify session exists and belongs to user
    async with pg.acquire_with_user_context(user_id) as conn:
        session_row = await conn.fetchrow(
            "SELECT id, title, created_at FROM screener_sessions WHERE id = $1",
            uuid.UUID(session_id)
        )

        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if there's an assistant message (indicates completion)
        messages = await conn.fetch(
            """
            SELECT id, role, content, created_at
            FROM screener_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            uuid.UUID(session_id)
        )

        # Find assistant message
        assistant_msg = next((m for m in messages if m["role"] == "assistant"), None)

        if assistant_msg:
            # Session completed - return the response
            return JSONResponse({
                "session_id": session_id,
                "status": "completed",
                "response": assistant_msg["content"],
                "created_at": assistant_msg["created_at"].isoformat()
            })
        else:
            # Session in progress or just created
            return JSONResponse({
                "session_id": session_id,
                "status": "in_progress",
                "response": None
            })
