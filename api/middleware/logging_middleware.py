"""Logging Context Middleware for FastAPI.

Propagates request context (request_id, user_id, org_id) to the logging system
so that all log messages within a request include these identifiers.

Usage in app_fastapi.py:
    from api.middleware.logging_middleware import LoggingContextMiddleware
    
    app.add_middleware(LoggingContextMiddleware)
"""

import uuid
import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import set_request_context, clear_request_context

logger = logging.getLogger(__name__)


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that sets up logging context for each request.
    
    - Generates unique request_id for tracing
    - Extracts user_id and org_id from request.state (set by auth middleware)
    - Propagates context to all loggers via contextvars
    - Clears context after request completes
    - Logs request start/end with timing
    """
    
    # Paths to skip logging (health checks, static files, etc.)
    SKIP_PATHS = {'/health', '/healthz', '/ready', '/readyz', '/favicon.ico'}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for health checks and static files
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]  # Short ID for readability
        
        # Store in request state for access in endpoints
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.perf_counter()
        
        # Set initial context (user_id/org_id will be set by auth middleware before this runs)
        # But we set request_id immediately
        set_request_context(request_id=request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # After auth middleware has run, update context with user info
            user_id = getattr(request.state, 'user_id', None)
            org_id = getattr(request.state, 'org_id', None)
            
            if user_id or org_id:
                set_request_context(user_id=user_id, org_id=org_id)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log request completion (skip for SSE streams - they're long-running)
            if not response.headers.get('content-type', '').startswith('text/event-stream'):
                log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
                logger.log(
                    log_level,
                    f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)",
                    extra={
                        'request_id': request_id,
                        'method': request.method,
                        'path': request.url.path,
                        'status_code': response.status_code,
                        'duration_ms': round(duration_ms, 2),
                        'user_id': user_id,
                        'org_id': org_id,
                    }
                )
            
            # Add request_id to response headers for client debugging
            response.headers['X-Request-ID'] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.error(
                f"{request.method} {request.url.path} -> ERROR ({duration_ms:.1f}ms): {type(e).__name__}",
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': round(duration_ms, 2),
                    'error_type': type(e).__name__,
                    'user_id': getattr(request.state, 'user_id', None),
                },
                exc_info=True
            )
            raise
            
        finally:
            # Always clear context to prevent leaking to other requests
            clear_request_context()


def get_request_id(request: Request) -> str:
    """Get request_id from request state, or generate one if not set."""
    return getattr(request.state, 'request_id', str(uuid.uuid4())[:8])
