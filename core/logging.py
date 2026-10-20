"""Structured Logging Configuration.

Provides centralized logging configuration with:
- Structured JSON output for production
- Human-readable console output for development
- Request context injection (user_id, request_id, org_id)
- Integration with FastAPI middleware

Usage:
    # In app_fastapi.py (at startup):
    from core.logging import setup_logging, get_logger
    setup_logging()
    
    # In any module:
    from core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Processing request", user_id=user_id, tool_id=tool_id)
"""

import logging
import sys
import os
import json
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional
from functools import lru_cache

# Context variables for request-scoped data
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
org_id_var: ContextVar[Optional[str]] = ContextVar('org_id', default=None)


# =============================================================================
# LOG LEVEL CONFIGURATION
# =============================================================================

def get_log_level() -> int:
    """Get log level from environment."""
    level_name = os.getenv('LOG_LEVEL', 'INFO').upper()
    return getattr(logging, level_name, logging.INFO)


def is_production() -> bool:
    """Check if running in production."""
    env = os.getenv('ENV', os.getenv('ENVIRONMENT', 'development'))
    return env.lower() == 'production'


# =============================================================================
# CONTEXT MANAGEMENT
# =============================================================================

def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> None:
    """Set request context for logging."""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if org_id:
        org_id_var.set(org_id)


def clear_request_context() -> None:
    """Clear request context after request completes."""
    request_id_var.set(None)
    user_id_var.set(None)
    org_id_var.set(None)


def get_request_context() -> Dict[str, Optional[str]]:
    """Get current request context."""
    return {
        'request_id': request_id_var.get(),
        'user_id': user_id_var.get(),
        'org_id': org_id_var.get(),
    }


# =============================================================================
# CUSTOM FORMATTER
# =============================================================================

class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs structured JSON logs for production
    and human-readable logs for development.
    """
    
    def __init__(self, json_output: bool = False):
        super().__init__()
        self.json_output = json_output
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log data
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add request context
        context = get_request_context()
        for key, value in context.items():
            if value:
                log_data[key] = value
        
        # Add extra fields from record
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_data['location'] = f"{record.pathname}:{record.lineno}"
        
        if self.json_output:
            return json.dumps(log_data, default=str)
        else:
            # Human-readable format
            parts = [
                f"{log_data['timestamp']}",
                f"[{log_data['level']:8}]",
                f"{log_data['logger']}:",
                log_data['message'],
            ]
            
            # Add context info
            context_parts = []
            if context.get('user_id'):
                context_parts.append(f"user={context['user_id']}")
            if context.get('request_id'):
                context_parts.append(f"req={context['request_id'][:8]}")
            if context.get('org_id'):
                context_parts.append(f"org={context['org_id'][:8]}")
            
            if context_parts:
                parts.append(f"({', '.join(context_parts)})")
            
            # Add extra fields
            extras = {k: v for k, v in log_data.items() 
                     if k not in ('timestamp', 'level', 'logger', 'message', 
                                  'request_id', 'user_id', 'org_id', 'exception', 'location')}
            if extras:
                parts.append(f"| {extras}")
            
            result = " ".join(parts)
            
            if 'exception' in log_data:
                result += f"\n{log_data['exception']}"
            
            return result


# =============================================================================
# LOGGER WITH CONTEXT
# =============================================================================

class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes request context
    and supports keyword arguments for structured logging.
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        # Get extra dict or create one
        extra = kwargs.get('extra', {})
        if isinstance(extra, dict) and 'extra' in extra:
            extra = extra['extra']
        
        kwargs['extra'] = {'extra': extra}
        return msg, kwargs
    
    def _log_with_extra(self, log_level: int, msg: str, *args, **kwargs):
        """Helper to handle extra kwargs properly."""
        # Extract extra fields from kwargs
        extra_fields = {}
        standard_keys = {'exc_info', 'stack_info', 'stacklevel', 'extra', 'level'}
        
        for key in list(kwargs.keys()):
            if key not in standard_keys:
                extra_fields[key] = kwargs.pop(key)
        
        # Remove 'level' if accidentally passed
        kwargs.pop('level', None)
        
        # Merge with any existing extra
        existing_extra = kwargs.get('extra', {})
        if isinstance(existing_extra, dict):
            extra_fields.update(existing_extra)
        
        kwargs['extra'] = {'extra': extra_fields}
        
        if self.isEnabledFor(log_level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(log_level, msg, args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        self._log_with_extra(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self._log_with_extra(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self._log_with_extra(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self._log_with_extra(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        self._log_with_extra(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg, *args, exc_info=True, **kwargs):
        kwargs['exc_info'] = exc_info
        self._log_with_extra(logging.ERROR, msg, *args, **kwargs)


@lru_cache(maxsize=128)
def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger for the given name.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing tool", tool_id="monte_carlo", user_id=user_id)
    """
    base_logger = logging.getLogger(name)
    return ContextLogger(base_logger, {})


# =============================================================================
# SETUP FUNCTIONS
# =============================================================================

_logging_configured = False

def setup_logging(
    level: Optional[int] = None,
    json_output: Optional[bool] = None,
) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (default: from LOG_LEVEL env var)
        json_output: Whether to output JSON (default: True in production)
    """
    global _logging_configured
    if _logging_configured:
        return
    
    if level is None:
        level = get_log_level()
    
    if json_output is None:
        json_output = is_production()
    
    # Create formatter
    formatter = StructuredFormatter(json_output=json_output)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    _logging_configured = True
    
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        level=logging.getLevelName(level),
        json_output=json_output,
        environment='production' if is_production() else 'development',
    )


# =============================================================================
# FASTAPI MIDDLEWARE
# =============================================================================

class LoggingMiddleware:
    """
    FastAPI middleware for request logging and context injection.
    
    Usage in app_fastapi.py:
        from core.logging import LoggingMiddleware
        app.add_middleware(LoggingMiddleware)
    """
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger("api.request")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        from datetime import datetime
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Extract user context from scope (set by auth middleware)
        state = scope.get("state", {})
        user_id = getattr(state, 'user_id', None) if hasattr(state, 'user_id') else None
        org_id = getattr(state, 'org_id', None) if hasattr(state, 'org_id') else None
        
        # Set context for this request
        set_request_context(
            request_id=request_id,
            user_id=user_id,
            org_id=org_id,
        )
        
        # Track response status
        status_code = 500
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Calculate duration
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Get path and method
            path = scope.get("path", "unknown")
            method = scope.get("method", "unknown")
            
            # Log request completion
            log_method = self.logger.warning if status_code >= 400 else self.logger.info
            
            # Skip health checks and metrics
            if path not in ('/health', '/metrics', '/v6/health'):
                log_method(
                    f"{method} {path}",
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    request_id=request_id,
                )
            
            # Clear context
            clear_request_context()


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

# For backwards compatibility with existing code
def getLogger(name: str) -> ContextLogger:
    """Alias for get_logger for compatibility with logging.getLogger."""
    return get_logger(name)
