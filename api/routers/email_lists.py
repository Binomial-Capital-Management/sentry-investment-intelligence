"""
API endpoints for email lists (reusable recipient groups).
"""

from fastapi import APIRouter, HTTPException, Request, status
from typing import List
from uuid import UUID
import json

from core.tasks.types import EmailList, EmailListCreate, EmailListUpdate
from core.database.postgres_client import get_postgres_rls_client

router = APIRouter(prefix="/api/email-lists", tags=["email-lists"])


@router.get("", response_model=List[EmailList])
async def list_email_lists(request: Request):
    """List all email lists for the authenticated user."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_user_context(user_id) as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, name, description, recipients, created_at, updated_at
            FROM email_lists
            ORDER BY name ASC
            """
        )

    return [
        EmailList(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            description=row["description"],
            recipients=json.loads(row["recipients"]) if isinstance(row["recipients"], str) else row["recipients"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.post("", response_model=EmailList, status_code=status.HTTP_201_CREATED)
async def create_email_list(request: Request, payload: EmailListCreate):
    """Create a new email list."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_user_context(user_id) as conn:
        # Check for duplicate name
        existing = await conn.fetchrow(
            "SELECT id FROM email_lists WHERE user_id = $1 AND name = $2",
            user_id, payload.name
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Email list with name '{payload.name}' already exists"
            )

        # Insert new list
        row = await conn.fetchrow(
            """
            INSERT INTO email_lists (user_id, name, description, recipients)
            VALUES ($1, $2, $3, $4)
            RETURNING id, user_id, name, description, recipients, created_at, updated_at
            """,
            user_id,
            payload.name,
            payload.description,
            json.dumps(payload.recipients)
        )

    return EmailList(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        description=row["description"],
        recipients=json.loads(row["recipients"]) if isinstance(row["recipients"], str) else row["recipients"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/{list_id}", response_model=EmailList)
async def get_email_list(request: Request, list_id: UUID):
    """Get a specific email list by ID."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_user_context(user_id) as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, name, description, recipients, created_at, updated_at
            FROM email_lists
            WHERE id = $1
            """,
            list_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Email list not found")

    return EmailList(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        description=row["description"],
        recipients=json.loads(row["recipients"]) if isinstance(row["recipients"], str) else row["recipients"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.put("/{list_id}", response_model=EmailList)
async def update_email_list(request: Request, list_id: UUID, payload: EmailListUpdate):
    """Update an existing email list."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_user_context(user_id) as conn:
        # Check if list exists
        existing = await conn.fetchrow(
            "SELECT id, name FROM email_lists WHERE id = $1",
            list_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Email list not found")

        # Check for name conflict if name is being changed
        if payload.name and payload.name != existing["name"]:
            name_conflict = await conn.fetchrow(
                "SELECT id FROM email_lists WHERE user_id = $1 AND name = $2 AND id != $3",
                user_id, payload.name, list_id
            )
            if name_conflict:
                raise HTTPException(
                    status_code=400,
                    detail=f"Email list with name '{payload.name}' already exists"
                )

        # Build update query dynamically
        updates = []
        params = []
        param_count = 1

        if payload.name is not None:
            updates.append(f"name = ${param_count}")
            params.append(payload.name)
            param_count += 1

        if payload.description is not None:
            updates.append(f"description = ${param_count}")
            params.append(payload.description)
            param_count += 1

        if payload.recipients is not None:
            updates.append(f"recipients = ${param_count}")
            params.append(json.dumps(payload.recipients))
            param_count += 1

        if not updates:
            # No fields to update, just return existing
            return await get_email_list(request, list_id)

        # Add list_id as final parameter
        params.append(list_id)

        query = f"""
            UPDATE email_lists
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, user_id, name, description, recipients, created_at, updated_at
        """

        row = await conn.fetchrow(query, *params)

    return EmailList(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        description=row["description"],
        recipients=json.loads(row["recipients"]) if isinstance(row["recipients"], str) else row["recipients"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_list(request: Request, list_id: UUID):
    """Delete an email list."""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_user_context(user_id) as conn:
        result = await conn.execute(
            "DELETE FROM email_lists WHERE id = $1",
            list_id
        )

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Email list not found")

    return None
