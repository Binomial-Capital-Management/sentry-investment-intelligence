"""
RLS (Row-Level Security) middleware - ONLY sets PostgreSQL user context.
Single responsibility: Set RLS context for database operations.
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_config

logger = logging.getLogger(__name__)


class RLSMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set PostgreSQL RLS context.
    
    Responsibilities:
    - Set request.state.rls_user_id for database operations
    - Ensure RLS context is available for downstream services
    
    Does NOT handle: Token verification, organization context
    
    Requires: AuthMiddleware to run first (sets request.state.user)
    """
    
    async def dispatch(self, request: Request, call_next):
        # Initialize RLS state
        request.state.rls_user_id = None
        
        config = get_config()
        
        # Get user from auth middleware
        user = getattr(request.state, 'user', None)
        user_id = getattr(request.state, 'user_id', None)
        
        # Set RLS context if we have a user and Postgres is enabled
        if user_id and config.enable_postgres:
            request.state.rls_user_id = user_id
            logger.debug(f"Set RLS context for user: {user_id}")
        
        return await call_next(request)
