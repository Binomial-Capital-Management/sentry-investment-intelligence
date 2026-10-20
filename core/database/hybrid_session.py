"""
Hybrid session management for Binomial Risk Analyst V6.
Bridges PostgreSQL (users) with SQLite (LangGraph state).

Following CODING_RULES.md: KISS, MVP first, no over-engineering.
Phase 1: Write-through to PostgreSQL, read from SQLite.
Phase 2: Full PostgreSQL migration (future).
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import secrets

from core.config import get_config
from core.database import get_postgres_client

logger = logging.getLogger(__name__)

class HybridSessionManager:
    """
    Manages sessions across PostgreSQL and SQLite.
    MVP approach - minimal complexity, maximum compatibility.
    """
    
    def __init__(self):
        self.config = get_config()
        self.postgres_enabled = self.config.enable_postgres
        self.migration_phase = self.config.postgres_migration_phase
        
    async def track_user_activity(
        self,
        clerk_user_id: Optional[str],
        analysis_type: str,
        tickers: list
    ):
        """
        Track user activity in PostgreSQL if enabled.
        This is write-only for now (audit trail).
        """
        if not self.postgres_enabled or not clerk_user_id:
            # PostgreSQL not enabled or anonymous user
            return
            
        try:
            pg_client = await get_postgres_client()
            await pg_client.track_analysis(
                clerk_user_id=clerk_user_id,
                analysis_type=analysis_type,
                tickers=tickers
            )
            logger.debug(f"Tracked analysis for user {clerk_user_id}")
        except Exception as e:
            # Don't fail the request if tracking fails
            logger.warning(f"Failed to track user activity: {e}")
    
    async def get_user_credits(self, clerk_user_id: str) -> Optional[int]:
        """
        Get user's remaining credits from PostgreSQL.
        Returns None if PostgreSQL not enabled.
        """
        if not self.postgres_enabled:
            return None
            
        try:
            pg_client = await get_postgres_client()
            user = await pg_client.get_user(clerk_user_id)
            return user.get('usage_credits') if user else None
        except Exception as e:
            logger.error(f"Failed to get user credits: {e}")
            return None
    
    def should_use_postgres_sessions(self) -> bool:
        """
        Determine if we should use PostgreSQL for sessions.
        Phase 1: False (use SQLite)
        Phase 2: True (use PostgreSQL)
        """
        return self.postgres_enabled and self.migration_phase >= 2
    
    async def create_session(
        self,
        user_id: Optional[str] = None,
        session_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new session in PostgreSQL with RLS.
        Falls back to SQLite if PostgreSQL not enabled.
        """
        if not self.should_use_postgres_sessions():
            # Still using SQLite for sessions
            return None
            
        try:
            pg_client = await get_postgres_client()
            
            # Generate session token if not provided
            if not session_token:
                session_token = secrets.token_urlsafe(32)
            
            session = await pg_client.create_chat_session(
                user_id=user_id,
                session_token=session_token
            )
            
            if session:
                logger.debug(f"Created PostgreSQL session for user {user_id}")
            
            return session
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL session: {e}")
            return None
    
    async def get_session(
        self,
        user_id: Optional[str],
        session_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get session from PostgreSQL with RLS.
        """
        if not self.should_use_postgres_sessions():
            return None
            
        try:
            pg_client = await get_postgres_client()
            return await pg_client.get_chat_session(
                user_id=user_id,
                session_token=session_token
            )
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    async def save_message(
        self,
        user_id: Optional[str],
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Save message to PostgreSQL with RLS.
        """
        if not self.should_use_postgres_sessions():
            return None
            
        try:
            pg_client = await get_postgres_client()
            return await pg_client.save_chat_message(
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return None
    
    async def get_chat_history(
        self,
        user_id: Optional[str],
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get chat history from PostgreSQL with RLS.
        """
        if not self.should_use_postgres_sessions():
            return []
            
        try:
            pg_client = await get_postgres_client()
            return await pg_client.get_chat_history(
                user_id=user_id,
                session_id=session_id,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []


# Global instance
_hybrid_manager = None

def get_hybrid_session_manager() -> HybridSessionManager:
    """Get or create the global hybrid session manager."""
    global _hybrid_manager
    if _hybrid_manager is None:
        _hybrid_manager = HybridSessionManager()
    return _hybrid_manager