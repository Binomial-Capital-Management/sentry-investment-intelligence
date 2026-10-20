"""
Canvas API Dependencies - FastAPI Dependency Injection

Provides reusable dependencies for Canvas endpoints:
- Database client injection
- User authentication extraction
- Organization context extraction

Usage:
    from .dependencies import DB, CurrentUser, OrgId

    @router.get("/threads")
    async def get_threads(user_id: CurrentUser, org_id: OrgId, db: DB):
        return await db.get_canvas_chat_threads(user_id=user_id, org_id=org_id)
"""

from fastapi import Depends, Request, HTTPException
from typing import Annotated

from core.database.postgres_client import PostgresClient, get_postgres_client


async def get_db() -> PostgresClient:
    """
    Database client dependency.
    
    Returns the singleton PostgresClient instance.
    """
    return await get_postgres_client()


async def get_current_user(request: Request) -> str:
    """
    Extract and validate user_id from request state.
    
    The user_id is set by authentication middleware (Clerk in production,
    DEV_SECRET in development).
    
    Raises:
        HTTPException(401): If user_id is not present in request state
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


async def get_org_id(request: Request) -> str:
    """
    Extract org_id from request state.
    
    Returns empty string if org_id is not set (single-tenant mode).
    """
    return getattr(request.state, 'org_id', None) or ''


# Type aliases for cleaner endpoint signatures
DB = Annotated[PostgresClient, Depends(get_db)]
CurrentUser = Annotated[str, Depends(get_current_user)]
OrgId = Annotated[str, Depends(get_org_id)]
