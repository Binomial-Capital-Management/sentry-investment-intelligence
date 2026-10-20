"""
User Lists API - CRUD for tracker lists and screeners
Following CODING_RULES.md: KISS, minimal, reuse existing patterns

IMPORTANT: All endpoints use org_id for proper workspace isolation.
"""
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Optional
from uuid import UUID

from api.models_dir.user_lists import (
    UserListCreate,
    UserListUpdate,
    UserListResponse,
    UserListsListResponse
)
from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user-lists", tags=["user-lists"])


def get_org_id(request: Request) -> str:
    """Extract org_id from request state, defaulting to empty string for personal workspace."""
    return getattr(request.state, 'org_id', None) or ''


@router.post("", response_model=UserListResponse, status_code=status.HTTP_201_CREATED)
async def create_user_list(
    payload: UserListCreate,
    request: Request,
):
    """
    Create new tracker list or screener.
    Properly scoped to the current organization workspace.

    Tracker example: {"name": "Tech Stocks", "type": "tracker", "tickers": ["AAPL", "MSFT"]}
    Screener example: {"name": "Large Cap", "type": "screener", "screener_filters": {...}}
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Insert new list with org_id
            row = await conn.fetchrow(
                """
                INSERT INTO user_lists (user_id, org_id, name, type, tickers, screener_filters)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, user_id, name, type, tickers, screener_filters, created_at, updated_at
                """,
                user_id,
                org_id,
                payload.name,
                payload.type,
                payload.tickers,
                json.dumps(payload.screener_filters) if payload.screener_filters else None
            )

            if not row:
                raise HTTPException(status_code=500, detail="Failed to create list")

            # Convert to response model
            return UserListResponse(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                type=row['type'],
                tickers=row['tickers'],
                screener_filters=json.loads(row['screener_filters']) if row['screener_filters'] else None,
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

    except Exception as e:
        logger.error(f"Error creating user list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=UserListsListResponse)
async def list_user_lists(
    request: Request,
    type: Optional[str] = None
):
    """
    Get all user's lists, optionally filtered by type.
    Properly scoped to the current organization workspace.

    Query params:
    - type: 'tracker' or 'screener' to filter
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Build query with optional type filter and org_id
            if type:
                query = """
                    SELECT id, user_id, name, type, tickers, screener_filters, created_at, updated_at
                    FROM user_lists
                    WHERE type = $1 AND org_id = $2
                    ORDER BY updated_at DESC
                """
                rows = await conn.fetch(query, type, org_id)
            else:
                query = """
                    SELECT id, user_id, name, type, tickers, screener_filters, created_at, updated_at
                    FROM user_lists
                    WHERE org_id = $1
                    ORDER BY updated_at DESC
                """
                rows = await conn.fetch(query, org_id)

            lists = [
                UserListResponse(
                    id=row['id'],
                    user_id=row['user_id'],
                    name=row['name'],
                    type=row['type'],
                    tickers=row['tickers'],
                    screener_filters=json.loads(row['screener_filters']) if row['screener_filters'] else None,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in rows
            ]

            return UserListsListResponse(lists=lists, total=len(lists))

    except Exception as e:
        logger.error(f"Error listing user lists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{list_id}", response_model=UserListResponse)
async def get_user_list(
    list_id: UUID,
    request: Request
):
    """Get single list by ID. Properly scoped to the current organization workspace."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, name, type, tickers, screener_filters, created_at, updated_at
                FROM user_lists
                WHERE id = $1 AND org_id = $2
                """,
                str(list_id), org_id
            )

            if not row:
                raise HTTPException(status_code=404, detail="List not found")

            return UserListResponse(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                type=row['type'],
                tickers=row['tickers'],
                screener_filters=json.loads(row['screener_filters']) if row['screener_filters'] else None,
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{list_id}", response_model=UserListResponse)
async def update_user_list(
    list_id: UUID,
    payload: UserListUpdate,
    request: Request
):
    """
    Update list name, tickers (tracker), or filters (screener).
    Properly scoped to the current organization workspace.

    Only provided fields will be updated.
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Build dynamic update query
            update_fields = []
            params = [str(list_id), org_id]
            param_num = 3

            if payload.name is not None:
                update_fields.append(f"name = ${param_num}")
                params.append(payload.name)
                param_num += 1

            if payload.tickers is not None:
                update_fields.append(f"tickers = ${param_num}")
                params.append(payload.tickers)
                param_num += 1

            if payload.screener_filters is not None:
                update_fields.append(f"screener_filters = ${param_num}")
                params.append(json.dumps(payload.screener_filters))
                param_num += 1

            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")

            query = f"""
                UPDATE user_lists
                SET {', '.join(update_fields)}
                WHERE id = $1 AND org_id = $2
                RETURNING id, user_id, name, type, tickers, screener_filters, created_at, updated_at
            """

            row = await conn.fetchrow(query, *params)

            if not row:
                raise HTTPException(status_code=404, detail="List not found")

            return UserListResponse(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                type=row['type'],
                tickers=row['tickers'],
                screener_filters=json.loads(row['screener_filters']) if row['screener_filters'] else None,
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_list(
    list_id: UUID,
    request: Request
):
    """Delete a list. Properly scoped to the current organization workspace."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            result = await conn.execute(
                "DELETE FROM user_lists WHERE id = $1 AND org_id = $2",
                str(list_id), org_id
            )

            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="List not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{list_id}/tickers/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def add_ticker_to_list(
    list_id: UUID,
    ticker: str,
    request: Request
):
    """Add ticker to tracker list (only works for type='tracker'). Properly scoped to the current organization workspace."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Check if it's a tracker
            list_type = await conn.fetchval(
                "SELECT type FROM user_lists WHERE id = $1 AND org_id = $2",
                str(list_id), org_id
            )

            if not list_type:
                raise HTTPException(status_code=404, detail="List not found")

            if list_type != 'tracker':
                raise HTTPException(status_code=400, detail="Can only add tickers to tracker lists")

            # Add ticker (array_append handles duplicates)
            await conn.execute(
                """
                UPDATE user_lists
                SET tickers = array_append(tickers, $1)
                WHERE id = $2 AND org_id = $3 AND NOT ($1 = ANY(tickers))
                """,
                ticker.upper(),
                str(list_id),
                org_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding ticker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{list_id}/tickers/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_ticker_from_list(
    list_id: UUID,
    ticker: str,
    request: Request
):
    """Remove ticker from tracker list. Properly scoped to the current organization workspace."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            await conn.execute(
                """
                UPDATE user_lists
                SET tickers = array_remove(tickers, $1)
                WHERE id = $2 AND org_id = $3
                """,
                ticker.upper(),
                str(list_id),
                org_id
            )

    except Exception as e:
        logger.error(f"Error removing ticker: {e}")
        raise HTTPException(status_code=500, detail=str(e))
