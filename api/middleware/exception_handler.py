"""Global Exception Handler for FastAPI.

Catches custom exceptions and converts them to proper HTTP responses.
Also handles unexpected exceptions with logging.

Usage in app_fastapi.py:
    from api.middleware.exception_handler import register_exception_handlers
    
    app = FastAPI()
    register_exception_handlers(app)
"""

import logging
from typing import Union

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.exceptions import (
    CanvasBaseException,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
    ServiceError,
    TimeoutError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


async def canvas_exception_handler(
    request: Request, 
    exc: CanvasBaseException
) -> JSONResponse:
    """
    Handle all Canvas custom exceptions.
    
    Logs the error and returns a structured JSON response.
    """
    # Log at appropriate level based on status code
    if exc.status_code >= 500:
        logger.error(
            f"[{exc.error_code}] {exc.message}",
            extra={
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
                "details": exc.details,
                "user_id": getattr(request.state, 'user_id', None),
            },
            exc_info=True
        )
    elif exc.status_code >= 400:
        logger.warning(
            f"[{exc.error_code}] {exc.message}",
            extra={
                "status_code": exc.status_code,
                "path": request.url.path,
                "details": exc.details,
            }
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def http_exception_handler(
    request: Request, 
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle standard HTTP exceptions (from FastAPI/Starlette).
    
    Converts them to consistent JSON format.
    """
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": str(exc.detail),
        },
    )


async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    
    Formats validation errors in a user-friendly way.
    """
    # Extract first error for message
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    
    # Build field path from location
    loc = first_error.get("loc", [])
    field = ".".join(str(l) for l in loc if l != "body")
    
    message = first_error.get("msg", "Validation error")
    if field:
        message = f"{field}: {message}"
    
    logger.warning(
        f"Validation error: {message}",
        extra={
            "path": request.url.path,
            "errors": errors,
        }
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": message,
            "details": {
                "errors": [
                    {
                        "field": ".".join(str(l) for l in e.get("loc", []) if l != "body"),
                        "message": e.get("msg"),
                        "type": e.get("type"),
                    }
                    for e in errors
                ]
            },
        },
    )


async def unhandled_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.
    
    Logs full traceback but returns generic error to client.
    """
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "user_id": getattr(request.state, 'user_id', None),
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI app.
    
    Call this in your app initialization:
        register_exception_handlers(app)
    """
    # Custom Canvas exceptions
    app.add_exception_handler(CanvasBaseException, canvas_exception_handler)
    
    # Standard HTTP exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # Pydantic validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Catch-all for unexpected errors
    app.add_exception_handler(Exception, unhandled_exception_handler)
    
    logger.info("Exception handlers registered")
