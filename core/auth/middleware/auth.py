"""
Authentication middleware - ONLY extracts and verifies JWT tokens.
Single responsibility: Token extraction and verification.
"""

import logging
from typing import Optional, Set
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPAuthorizationCredentials

from core.auth import get_clerk_auth
from core.auth.dev import attempt_dev_auth, get_fallback_dev_user, is_dev_mode_available
from core.config import get_config

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS: Set[str] = {
    "/health",
    "/metrics", 
    "/docs",
    "/openapi.json",
    "/v6/health",
}

# Path prefixes that don't require authentication
PUBLIC_PATH_PREFIXES = (
    "/ws/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate requests.
    
    Responsibilities:
    - Extract JWT token from Authorization header
    - Verify token with Clerk
    - Set request.state.user with verified user info
    - Handle dev mode bypass
    
    Does NOT handle: RLS context, organization context
    """
    
    async def dispatch(self, request: Request, call_next):
        # Initialize user state
        request.state.user = None
        request.state.user_id = None
        request.state.clerk_user_id = None
        
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        config = get_config()
        
        try:
            # 1. Try dev mode auth first (if available)
            if is_dev_mode_available():
                dev_auth = attempt_dev_auth(request)
                if dev_auth:
                    request.state.user = dev_auth
                    request.state.user_id = dev_auth['user_id']
                    request.state.clerk_user_id = dev_auth['clerk_user_id']
                    request.state.auth_checked = True
                    return await call_next(request)
            
            # 2. Try Clerk auth if enabled
            if config.enable_auth:
                user = await self._verify_clerk_token(request, config)
                if user:
                    request.state.user = user
                    request.state.user_id = user['user_id']
                    request.state.clerk_user_id = user['user_id']
            
            # 3. Fallback dev user when auth is disabled
            if not request.state.user and not config.enable_auth:
                fallback = get_fallback_dev_user()
                if fallback:
                    request.state.user = fallback
                    request.state.user_id = fallback['user_id']
                    request.state.clerk_user_id = fallback['clerk_user_id']
            
            return await call_next(request)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in auth middleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        if path in PUBLIC_PATHS:
            return True
        
        for prefix in PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return True
        
        return False
    
    async def _verify_clerk_token(self, request: Request, config) -> Optional[dict]:
        """Verify JWT token using Clerk."""
        auth = get_clerk_auth()
        
        try:
            # For user endpoints, require auth
            if request.url.path.startswith("/api/v6/user/"):
                return await auth.required_auth(request)
            
            # For other endpoints, try optional auth
            current_user = await auth.optional_auth_from_request(request)
            
            if current_user:
                return {
                    'user_id': current_user.get('user_id'),
                    'email': current_user.get('email'),
                    'session_id': current_user.get('session_id'),
                }
            
            # Try SSE ticket for EventSource requests
            current_user = await self._try_sse_ticket(request)
            if current_user:
                return current_user
            
            # Try query param token (legacy, less secure)
            current_user = await self._try_query_token(request, auth)
            if current_user:
                return current_user
            
            return None
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
    
    async def _try_sse_ticket(self, request: Request) -> Optional[dict]:
        """Try SSE ticket authentication."""
        ticket = request.query_params.get('ticket')
        if not ticket:
            return None
        
        try:
            from api.routers.sse_tickets import validate_and_consume_ticket
            ticket_user = await validate_and_consume_ticket(ticket)
            if ticket_user:
                logger.debug(f"SSE ticket validated for user: {ticket_user.get('user_id')}")
                return ticket_user
        except Exception as e:
            logger.debug(f"SSE ticket validation failed: {e}")
        
        return None
    
    async def _try_query_token(self, request: Request, auth) -> Optional[dict]:
        """Try query param token authentication (legacy)."""
        token = request.query_params.get('token')
        if not token:
            return None
        
        try:
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            user = await auth.verify_token(credentials)
            if user:
                return {
                    'user_id': user.get('user_id'),
                    'email': user.get('email'),
                    'session_id': user.get('session_id'),
                }
        except Exception as e:
            logger.debug(f"Query token verification failed: {e}")
        
        return None
