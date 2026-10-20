"""
SSE Ticket Exchange System

Provides short-lived, single-use tickets for SSE authentication.
This prevents JWT tokens from being exposed in URL query parameters,
which would be logged by proxies, CDNs, and appear in browser history.

Flow:
1. Frontend: POST /auth/sse-ticket with JWT in Authorization header
2. Backend: Validates JWT, generates random ticket, stores in Redis/cache with 30s TTL
3. Backend: Returns { ticket: "abc123" }
4. Frontend: Opens EventSource with ?ticket=abc123
5. Backend: Validates ticket ONCE, deletes from cache, proceeds with user context

Storage: Uses Redis when available (multi-instance safe), falls back to in-memory.

Following CODING_RULES.md: KISS, security-focused
"""

import secrets
import logging
import time
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse

from core.config import get_config
from core.auth import get_clerk_auth
from core.cache import cache

logger = logging.getLogger(__name__)
config = get_config()

router = APIRouter(prefix="/auth")

# In-memory fallback when Redis is unavailable
_ticket_store: Dict[str, Dict[str, Any]] = {}

# Ticket TTL in seconds
TICKET_TTL_SECONDS = 30

# Redis key prefix for SSE tickets
TICKET_KEY_PREFIX = "sse_ticket:"


def _use_redis() -> bool:
    """Check if Redis is available for ticket storage."""
    return cache.enabled and cache.redis is not None


def _cleanup_expired_tickets():
    """Remove expired tickets from in-memory store (only used as fallback)."""
    now = time.time()
    expired = [k for k, v in _ticket_store.items() if v.get('expires_at', 0) < now]
    for k in expired:
        del _ticket_store[k]


async def create_sse_ticket(user_id: str, org_id: Optional[str] = None) -> str:
    """
    Create a short-lived, single-use ticket for SSE authentication.
    
    Uses Redis when available for multi-instance deployments.
    Falls back to in-memory store for single-instance/dev.
    
    Args:
        user_id: Authenticated user ID
        org_id: Optional organization context
        
    Returns:
        Random ticket string (32 characters, URL-safe)
    """
    # Generate cryptographically secure random ticket
    ticket = secrets.token_urlsafe(24)  # 32 characters
    
    ticket_data = {
        'user_id': user_id,
        'org_id': org_id,
    }
    
    if _use_redis():
        # Store in Redis with TTL (auto-expires, no cleanup needed)
        key = f"{TICKET_KEY_PREFIX}{ticket}"
        try:
            cache.redis.setex(key, TICKET_TTL_SECONDS, json.dumps(ticket_data))
            logger.debug(f"Created SSE ticket in Redis for user {user_id}, TTL={TICKET_TTL_SECONDS}s")
        except Exception as e:
            logger.warning(f"Redis setex failed, falling back to memory: {e}")
            # Fallback to in-memory
            _ticket_store[ticket] = {
                **ticket_data,
                'expires_at': time.time() + TICKET_TTL_SECONDS,
            }
    else:
        # In-memory fallback
        _cleanup_expired_tickets()
        _ticket_store[ticket] = {
            **ticket_data,
            'expires_at': time.time() + TICKET_TTL_SECONDS,
        }
        logger.debug(f"Created SSE ticket in memory for user {user_id}, TTL={TICKET_TTL_SECONDS}s")
    
    return ticket


async def validate_and_consume_ticket(ticket: str) -> Optional[Dict[str, Any]]:
    """
    Validate a ticket and consume it (single-use).
    
    Uses Redis GETDEL for atomic get-and-delete when available.
    Falls back to in-memory store pop.
    
    Args:
        ticket: The ticket string to validate
        
    Returns:
        User context dict if valid, None if invalid/expired/already used
    """
    if not ticket:
        return None
    
    if _use_redis():
        key = f"{TICKET_KEY_PREFIX}{ticket}"
        try:
            # GETDEL: atomically get and delete (Redis 6.2+)
            # Falls back to GET + DEL for older Redis
            raw_data = None
            try:
                raw_data = cache.redis.getdel(key)
            except AttributeError:
                # Redis client doesn't support getdel, use get + delete
                raw_data = cache.redis.get(key)
                if raw_data:
                    cache.redis.delete(key)
            
            if not raw_data:
                logger.debug("SSE ticket not found in Redis or already used")
                return None
            
            ticket_data = json.loads(raw_data)
            logger.debug(f"Validated SSE ticket from Redis for user {ticket_data.get('user_id')}")
            return {
                'user_id': ticket_data['user_id'],
                'org_id': ticket_data.get('org_id'),
            }
        except Exception as e:
            logger.warning(f"Redis ticket validation failed: {e}")
            # Try in-memory fallback
            pass
    
    # In-memory fallback
    ticket_data = _ticket_store.pop(ticket, None)
    
    if not ticket_data:
        logger.debug("SSE ticket not found in memory or already used")
        return None
    
    # Check expiration (only needed for in-memory, Redis handles TTL)
    if ticket_data.get('expires_at', 0) < time.time():
        logger.debug("SSE ticket expired")
        return None
    
    logger.debug(f"Validated SSE ticket from memory for user {ticket_data.get('user_id')}")
    return {
        'user_id': ticket_data['user_id'],
        'org_id': ticket_data.get('org_id'),
    }


@router.post("/sse-ticket")
async def get_sse_ticket(request: Request):
    """
    Exchange a JWT for a short-lived SSE ticket.
    
    The ticket can be used once within 30 seconds to authenticate an SSE connection.
    This prevents JWT exposure in URL query parameters.
    
    Requires: Authorization header with valid JWT
    Returns: { ticket: "abc123", ttl: 30 }
    """
    if not config.enable_auth:
        # In dev mode without auth, return a dev ticket
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"ticket": "dev-ticket", "ttl": TICKET_TTL_SECONDS}
        )
    
    # Verify JWT from Authorization header
    auth = get_clerk_auth()
    
    try:
        user = await auth.required_auth(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSE ticket auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication"
        )
    
    user_id = user.get('user_id')
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    
    # Get org context if provided
    org_id = request.headers.get('X-Organization-ID')
    
    # Create ticket
    ticket = await create_sse_ticket(user_id, org_id)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "ticket": ticket,
            "ttl": TICKET_TTL_SECONDS,
            "storage": "redis" if _use_redis() else "memory"
        }
    )
