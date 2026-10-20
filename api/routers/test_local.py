"""
Local testing endpoints that bypass authentication.
ONLY enabled when ENABLE_AUTH=false for local development.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any
from datetime import datetime
import uuid
import logging

from api.models import ChatRequest, ChatResponse
from api.orchestrator import get_v6_orchestrator
from api.db import load_recent_history, insert_message
from api.utils import resolve_session_id
from core.config import get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/test", tags=["testing"])

# Only enable these endpoints in local dev mode
config = get_config()
if not config.enable_auth:
    
    @router.get("/portfolios")
    async def test_list_portfolios():
        """Return mock portfolios for testing."""
        return [
            {
                "id": "test-portfolio-1",
                "name": "Test Tech Portfolio",
                "tickers": ["AAPL", "MSFT", "GOOGL"],
                "weights": [0.4, 0.3, 0.3],
                "is_default": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            },
            {
                "id": "test-portfolio-2",
                "name": "Test Balanced Portfolio",
                "tickers": ["SPY", "BND", "GLD"],
                "weights": [0.5, 0.3, 0.2],
                "is_default": False,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        ]
    
    @router.get("/chats")
    async def test_list_chats():
        """Return mock chat sessions for testing."""
        return [
            {
                "id": "test-session-1",
                "title": "Test Risk Analysis Session",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        ]
    
    @router.post("/chat", response_model=ChatResponse)
    async def test_chat(request: ChatRequest, raw_request: Request):
        """
        Simple chat endpoint for local testing.
        Directly calls the orchestrator without authentication.
        """
        orchestrator = get_v6_orchestrator()
        
        # Generate or use session ID
        session_id = resolve_session_id(request.session_id, dict(raw_request.headers))
        
        # Save user message
        user_msg_id = uuid.uuid4().hex
        await insert_message(
            user_msg_id, 
            session_id, 
            'user', 
            request.message, 
            datetime.now().isoformat()
        )
        
        # Load history
        history = await load_recent_history(session_id, limit=20)
        
        # Mock portfolio context if requested
        portfolio_context = None
        if request.portfolio_id == "test-portfolio-1":
            portfolio_context = {
                "tickers": ["AAPL", "MSFT", "GOOGL"],
                "weights": [0.4, 0.3, 0.3],
                "value": 1000000
            }
        elif request.portfolio_id == "test-portfolio-2":
            portfolio_context = {
                "tickers": ["SPY", "BND", "GLD"],
                "weights": [0.5, 0.3, 0.2],
                "value": 1000000
            }
        
        # Process through orchestrator
        try:
            result = await orchestrator.process_query(
                query=request.message,
                session_id=session_id,
                history=history,
                portfolio_context=portfolio_context,
                agent_mode=request.agent_mode
            )
            
            # Format response
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
            
            # Save assistant message
            assistant_msg_id = uuid.uuid4().hex
            await insert_message(
                assistant_msg_id, 
                session_id, 
                'assistant', 
                response_text, 
                datetime.now().isoformat()
            )
            
            return ChatResponse(
                response=response_text,
                sources=sources,
                charts=charts,
                metrics=metrics,
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
                message_id=assistant_msg_id
            )
            
        except Exception as e:
            logger.error(f"Test chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/health")
    async def test_health():
        """Test endpoint health check."""
        return {
            "status": "healthy",
            "mode": "local_testing",
            "auth_enabled": False,
            "timestamp": datetime.now().isoformat()
        }