"""
Context Variable Management Utilities
Provides safe context variable handling with proper token management and cleanup.
Following CODING_RULES.md: Guard against context leakage with proper cleanup.
"""

import contextvars
from typing import Optional, Any, Dict, Callable
from contextlib import contextmanager, asynccontextmanager
import logging

logger = logging.getLogger(__name__)

# Global context variables with defaults
user_context = contextvars.ContextVar('user_id', default=None)
session_context = contextvars.ContextVar('session_id', default=None)
request_context = contextvars.ContextVar('request_id', default=None)
model_context = contextvars.ContextVar('selected_model', default=None)
token_sink_context = contextvars.ContextVar('stream_token_sink', default=None)
drive_context = contextvars.ContextVar('drive_context', default=None)
cancel_event_context = contextvars.ContextVar('cancel_event', default=None)  # ✅ ADDED: For cancellation
event_emitter_context = contextvars.ContextVar('event_emitter', default=None)  # ✅ ADDED: For agentic action events


class ContextManager:
    """Manages context variables with proper token handling to prevent leakage."""
    
    @staticmethod
    @contextmanager
    def set_context(**kwargs):
        """
        Set context variables with automatic cleanup.

        Usage:
            with ContextManager.set_context(user_id="123", session_id="456"):
                # Context variables are set here
                do_work()
            # Context variables are automatically reset here
        """
        tokens = {}

        try:
            # Set new values and store tokens for cleanup
            if 'user_id' in kwargs:
                tokens['user_id'] = user_context.set(kwargs['user_id'])
            if 'session_id' in kwargs:
                tokens['session_id'] = session_context.set(kwargs['session_id'])
            if 'request_id' in kwargs:
                tokens['request_id'] = request_context.set(kwargs['request_id'])
            if 'selected_model' in kwargs:
                tokens['selected_model'] = model_context.set(kwargs['selected_model'])
            if 'token_sink' in kwargs:
                tokens['token_sink'] = token_sink_context.set(kwargs['token_sink'])
            if 'drive_context' in kwargs:
                tokens['drive_context'] = drive_context.set(kwargs['drive_context'])

            yield
            
        finally:
            # Always reset context variables to prevent leakage
            for var_name, token in tokens.items():
                try:
                    if var_name == 'user_id':
                        user_context.reset(token)
                    elif var_name == 'session_id':
                        session_context.reset(token)
                    elif var_name == 'request_id':
                        request_context.reset(token)
                    elif var_name == 'selected_model':
                        model_context.reset(token)
                    elif var_name == 'token_sink':
                        token_sink_context.reset(token)
                    elif var_name == 'drive_context':
                        drive_context.reset(token)
                except Exception as e:
                    logger.warning(f"Failed to reset context {var_name}: {e}")
    
    @staticmethod
    @asynccontextmanager
    async def async_set_context(**kwargs):
        """
        Async version of set_context for use in async code.

        Usage:
            async with ContextManager.async_set_context(user_id="123"):
                await async_work()
        """
        tokens = {}

        try:
            # Set new values and store tokens for cleanup
            if 'user_id' in kwargs:
                tokens['user_id'] = user_context.set(kwargs['user_id'])
            if 'session_id' in kwargs:
                tokens['session_id'] = session_context.set(kwargs['session_id'])
            if 'request_id' in kwargs:
                tokens['request_id'] = request_context.set(kwargs['request_id'])
            if 'selected_model' in kwargs:
                tokens['selected_model'] = model_context.set(kwargs['selected_model'])
            if 'token_sink' in kwargs:
                tokens['token_sink'] = token_sink_context.set(kwargs['token_sink'])
            if 'drive_context' in kwargs:
                tokens['drive_context'] = drive_context.set(kwargs['drive_context'])

            yield
            
        finally:
            # Always reset context variables to prevent leakage
            for var_name, token in tokens.items():
                try:
                    if var_name == 'user_id':
                        user_context.reset(token)
                    elif var_name == 'session_id':
                        session_context.reset(token)
                    elif var_name == 'request_id':
                        request_context.reset(token)
                    elif var_name == 'selected_model':
                        model_context.reset(token)
                    elif var_name == 'token_sink':
                        token_sink_context.reset(token)
                    elif var_name == 'drive_context':
                        drive_context.reset(token)
                except Exception as e:
                    logger.warning(f"Failed to reset context {var_name}: {e}")
    
    @staticmethod
    def get_context() -> Dict[str, Optional[Any]]:
        """
        Get all current context values.

        Returns:
            Dictionary with current context values
        """
        return {
            'user_id': user_context.get(),
            'session_id': session_context.get(),
            'request_id': request_context.get(),
            'selected_model': model_context.get(),
            'token_sink': token_sink_context.get(),
            'drive_context': drive_context.get(),
        }
    
    @staticmethod
    def clear_all_context():
        """
        Clear all context variables. Use with caution!
        This should only be used in cleanup scenarios.
        """
        try:
            # Set all to None (can't fully clear without tokens)
            user_context.set(None)
            session_context.set(None)
            request_context.set(None)
            drive_context.set(None)
        except Exception as e:
            logger.warning(f"Failed to clear context: {e}")


def with_context(**context_kwargs):
    """
    Decorator to set context variables for a function call.
    
    Usage:
        @with_context(user_id="123")
        def my_function():
            # user_id context is available here
            pass
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                async with ContextManager.async_set_context(**context_kwargs):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with ContextManager.set_context(**context_kwargs):
                    return func(*args, **kwargs)
            return sync_wrapper
    return decorator


# Export convenient access functions
def get_user_id() -> Optional[str]:
    """Get current user ID from context."""
    return user_context.get()


def get_session_id() -> Optional[str]:
    """Get current session ID from context."""
    return session_context.get()


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_context.get()


def get_token_sink() -> Optional[Any]:
    """Get current streaming token sink (asyncio.Queue-like) from context."""
    return token_sink_context.get()


def set_token_sink(sink: Any):
    """Set streaming token sink for current context. Returns context token for reset."""
    return token_sink_context.set(sink)


def reset_token_sink(token: Any):
    """Reset the streaming token sink context using the provided token."""
    if token is None:
        return
    try:
        token_sink_context.reset(token)
    except Exception:
        pass


def get_drive_context() -> Optional[Any]:
    """Get current Google Drive integration context for the active request."""
    return drive_context.get()


def set_drive_context(ctx: Any):
    """Set Google Drive context for the active request."""
    return drive_context.set(ctx)


def reset_drive_context(token: Any):
    """Reset Google Drive context using provided token."""
    if token is None:
        return
    try:
        drive_context.reset(token)
    except Exception:
        pass


def get_cancel_event() -> Optional[Any]:
    """Get current cancellation event for the active request."""
    return cancel_event_context.get()


def set_cancel_event(event: Any):
    """Set cancellation event for the active request. Returns context token for reset."""
    return cancel_event_context.set(event)


def reset_cancel_event(token: Any):
    """Reset cancellation event context using provided token."""
    if token is None:
        return
    try:
        cancel_event_context.reset(token)
    except Exception:
        pass


def get_event_emitter() -> Optional[Callable]:
    """Get current event emitter callback for agentic actions."""
    return event_emitter_context.get()


def set_event_emitter(emitter: Callable):
    """Set event emitter callback for agentic actions. Returns context token for reset."""
    return event_emitter_context.set(emitter)


def reset_event_emitter(token: Any):
    """Reset event emitter context using provided token."""
    if token is None:
        return
    try:
        event_emitter_context.reset(token)
    except Exception:
        pass


# Check for asyncio
try:
    import asyncio
except ImportError:
    asyncio = None
