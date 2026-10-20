"""Custom Exception Classes for Canvas API.

Provides domain-specific exceptions that map to HTTP status codes.
These are caught by the global exception handler and converted to proper responses.

Usage:
    from core.exceptions import NotFoundError, UnauthorizedError
    
    # In a service:
    if not process:
        raise ProcessNotFoundError(process_id)
    
    # In a router (will be handled automatically):
    raise ToolNotFoundError(tool_id)
"""

from typing import Optional, Dict, Any


class CanvasBaseException(Exception):
    """Base exception for all Canvas-related errors."""
    
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.details = details or {}
        if error_code:
            self.error_code = error_code
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to JSON-serializable dict."""
        result = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


# =============================================================================
# AUTHENTICATION / AUTHORIZATION ERRORS (4xx)
# =============================================================================

class UnauthorizedError(CanvasBaseException):
    """User is not authenticated (401)."""
    status_code = 401
    error_code = "UNAUTHORIZED"
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message)


class ForbiddenError(CanvasBaseException):
    """User is authenticated but lacks permission (403)."""
    status_code = 403
    error_code = "FORBIDDEN"
    
    def __init__(self, message: str = "Permission denied", resource: Optional[str] = None):
        details = {"resource": resource} if resource else None
        super().__init__(message, details)


# =============================================================================
# NOT FOUND ERRORS (404)
# =============================================================================

class NotFoundError(CanvasBaseException):
    """Generic resource not found (404)."""
    status_code = 404
    error_code = "NOT_FOUND"
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} not found: {resource_id}",
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class ProcessNotFoundError(NotFoundError):
    """Canvas process not found."""
    error_code = "PROCESS_NOT_FOUND"
    
    def __init__(self, process_id: str):
        super().__init__("Process", process_id)


class ToolNotFoundError(NotFoundError):
    """Canvas tool not found in registry."""
    error_code = "TOOL_NOT_FOUND"
    
    def __init__(self, tool_id: str):
        super().__init__("Tool", tool_id)


class ThreadNotFoundError(NotFoundError):
    """Chat thread not found."""
    error_code = "THREAD_NOT_FOUND"
    
    def __init__(self, thread_id: str):
        super().__init__("Thread", thread_id)


# =============================================================================
# VALIDATION ERRORS (400/422)
# =============================================================================

class ValidationError(CanvasBaseException):
    """Request validation failed (400)."""
    status_code = 400
    error_code = "VALIDATION_ERROR"
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(message, error_details)


class InvalidParameterError(ValidationError):
    """A specific parameter is invalid."""
    error_code = "INVALID_PARAMETER"
    
    def __init__(self, param: str, message: str, value: Any = None):
        details = {"param": param}
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, field=param, details=details)


# =============================================================================
# SERVICE / EXECUTION ERRORS (500)
# =============================================================================

class ServiceError(CanvasBaseException):
    """Generic service layer error (500)."""
    status_code = 500
    error_code = "SERVICE_ERROR"
    
    def __init__(self, message: str, service: Optional[str] = None):
        details = {"service": service} if service else None
        super().__init__(message, details)


class ToolExecutionError(CanvasBaseException):
    """Tool execution failed (500)."""
    status_code = 500
    error_code = "TOOL_EXECUTION_ERROR"
    
    def __init__(self, tool_id: str, message: str, cause: Optional[str] = None):
        details = {"tool_id": tool_id}
        if cause:
            details["cause"] = cause
        super().__init__(message, details)


class DatabaseError(ServiceError):
    """Database operation failed."""
    error_code = "DATABASE_ERROR"
    
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, service="database")


class AgentError(ServiceError):
    """AI agent execution failed."""
    error_code = "AGENT_ERROR"
    
    def __init__(self, message: str, agent: Optional[str] = None):
        super().__init__(message, service=agent or "agent")


# =============================================================================
# TIMEOUT / RATE LIMIT ERRORS
# =============================================================================

class TimeoutError(CanvasBaseException):
    """Operation timed out (408)."""
    status_code = 408
    error_code = "TIMEOUT"
    
    def __init__(self, message: str = "Operation timed out", timeout_seconds: Optional[int] = None):
        details = {"timeout_seconds": timeout_seconds} if timeout_seconds else None
        super().__init__(message, details)


class RateLimitError(CanvasBaseException):
    """Rate limit exceeded (429)."""
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {"retry_after_seconds": retry_after} if retry_after else None
        super().__init__(message, details)


# =============================================================================
# STREAMING ERRORS
# =============================================================================

class StreamingError(CanvasBaseException):
    """Error during SSE streaming (sent as event, not HTTP status)."""
    status_code = 500  # Only used if error happens before streaming starts
    error_code = "STREAMING_ERROR"
    
    def __init__(self, message: str, fatal: bool = True):
        super().__init__(message, details={"fatal": fatal})
        self.fatal = fatal
