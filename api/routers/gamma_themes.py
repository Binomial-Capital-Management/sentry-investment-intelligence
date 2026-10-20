"""
Gamma Themes Router

Handles Gamma visual theme management with PostgreSQL + RLS.
- 12 system-wide default themes (read-only)
- Up to 4 user custom themes (writable per user)

Following CODING_RULES.md:
- NO HARDCODING - Theme IDs stored in database
- KISS - Simple CRUD endpoints with PostgreSQL
- DRY - Reusable patterns from user_settings.py
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, status

from core.auth.clerk_verify import get_clerk_auth
from core.database.postgres_client import get_postgres_rls_client
from api.models_dir.gamma_themes import (
    GammaTheme,
    UserCustomTheme,
    GammaThemeListResponse,
    UserCustomThemeListResponse,
    CombinedThemesResponse,
    UserCustomThemeCreateRequest,
    UserCustomThemeUpdateRequest,
    UserCustomThemeResponse,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gamma-themes", tags=["gamma-themes"])


# ===== Default System Themes (Read-Only) =====

@router.get("/default", response_model=GammaThemeListResponse)
async def list_default_themes(
    request: Request,
    user = Depends(get_clerk_auth().get_current_user)
):
    """
    List all 12 system-wide default Gamma themes.

    These themes are read-only and available to all users.
    Returns: Galilee, Alpine, Carmel, Sedona, Sequoia, Summit,
             Riviera, Highlands, Appalachia, Manhattan, Valais, Yangtze
    """
    try:
        pg = await get_postgres_rls_client()
        # No RLS context needed - system themes are global
        async with pg.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, gamma_theme_id, color_description, created_at
                FROM gamma_themes
                ORDER BY name ASC
                """
            )

            themes = [
                GammaTheme(
                    id=row['id'],
                    name=row['name'],
                    gamma_theme_id=row['gamma_theme_id'],
                    color_description=row['color_description'],
                    created_at=row['created_at']
                )
                for row in rows
            ]

            return GammaThemeListResponse(
                themes=themes,
                count=len(themes)
            )

    except Exception as e:
        logger.error(f"Failed to fetch default themes: {e}")
        # Graceful degradation - return empty list
        return GammaThemeListResponse(
            themes=[],
            count=0,
            message="Failed to fetch default themes"
        )


# ===== User Custom Themes (CRUD) =====

@router.get("/custom", response_model=UserCustomThemeListResponse)
async def list_custom_themes(
    request: Request,
    user = Depends(get_clerk_auth().get_current_user)
):
    """
    List all custom themes for the current user.

    Maximum 4 custom themes per user.
    Uses RLS for automatic user isolation.
    """
    clerk_user_id = user.get("user_id")

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, name, gamma_theme_id, created_at, updated_at
                FROM user_custom_themes
                WHERE user_id = $1
                ORDER BY created_at ASC
                """,
                clerk_user_id
            )

            themes = [
                UserCustomTheme(
                    id=row['id'],
                    user_id=row['user_id'],
                    name=row['name'],
                    gamma_theme_id=row['gamma_theme_id'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in rows
            ]

            count = len(themes)
            remaining_slots = max(0, 4 - count)

            return UserCustomThemeListResponse(
                themes=themes,
                count=count,
                remaining_slots=remaining_slots
            )

    except Exception as e:
        logger.error(f"Failed to fetch custom themes: {e}")
        # Graceful degradation - return empty list
        return UserCustomThemeListResponse(
            themes=[],
            count=0,
            remaining_slots=4,
            message="Failed to fetch custom themes"
        )


@router.post("/custom", response_model=UserCustomThemeResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_theme(
    payload: UserCustomThemeCreateRequest,
    request: Request,
    user = Depends(get_clerk_auth().get_current_user)
):
    """
    Create a new custom theme.

    Maximum 4 custom themes per user (enforced by application logic).
    Theme name must be unique per user.
    """
    clerk_user_id = user.get("user_id")

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            # Check current count - enforce 4 theme limit
            current_count = await conn.fetchval(
                "SELECT COUNT(*) FROM user_custom_themes WHERE user_id = $1",
                clerk_user_id
            )

            if current_count >= 4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum 4 custom themes per user. Delete an existing theme before creating a new one."
                )

            # Insert new custom theme
            row = await conn.fetchrow(
                """
                INSERT INTO user_custom_themes (user_id, name, gamma_theme_id)
                VALUES ($1, $2, $3)
                RETURNING id, user_id, name, gamma_theme_id, created_at, updated_at
                """,
                clerk_user_id,
                payload.name,
                payload.gamma_theme_id
            )

            logger.info(f"Custom theme '{payload.name}' created for user {clerk_user_id[:8]}")

            created_theme = UserCustomTheme(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                gamma_theme_id=row['gamma_theme_id'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

            # Calculate remaining slots
            remaining_slots = max(0, 4 - (current_count + 1))

            return UserCustomThemeResponse(
                theme=created_theme,
                message=f"Custom theme '{payload.name}' created successfully",
                remaining_slots=remaining_slots
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create custom theme: {e}")
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Custom theme '{payload.name}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create custom theme"
        )


@router.put("/custom/{theme_id}", response_model=UserCustomThemeResponse)
async def update_custom_theme(
    theme_id: int,
    payload: UserCustomThemeUpdateRequest,
    request: Request,
    user = Depends(get_clerk_auth().get_current_user)
):
    """
    Update an existing custom theme.

    Can update theme name and/or Gamma theme ID.
    Uses RLS for automatic user isolation.
    """
    clerk_user_id = user.get("user_id")

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            # Check if theme exists and belongs to user (RLS will enforce this)
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM user_custom_themes WHERE id = $1 AND user_id = $2)",
                theme_id,
                clerk_user_id
            )

            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Custom theme with ID {theme_id} not found"
                )

            # Build update query dynamically based on provided fields
            update_parts = []
            params = [theme_id, clerk_user_id]
            param_idx = 3

            if payload.name is not None:
                update_parts.append(f"name = ${param_idx}")
                params.append(payload.name)
                param_idx += 1

            if payload.gamma_theme_id is not None:
                update_parts.append(f"gamma_theme_id = ${param_idx}")
                params.append(payload.gamma_theme_id)
                param_idx += 1

            if not update_parts:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update. Provide name and/or gamma_theme_id."
                )

            # Always update updated_at
            update_parts.append("updated_at = NOW()")

            update_query = f"""
                UPDATE user_custom_themes
                SET {', '.join(update_parts)}
                WHERE id = $1 AND user_id = $2
                RETURNING id, user_id, name, gamma_theme_id, created_at, updated_at
            """

            row = await conn.fetchrow(update_query, *params)

            logger.info(f"Custom theme ID {theme_id} updated for user {clerk_user_id[:8]}")

            updated_theme = UserCustomTheme(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                gamma_theme_id=row['gamma_theme_id'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

            return UserCustomThemeResponse(
                theme=updated_theme,
                message=f"Custom theme '{row['name']}' updated successfully"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update custom theme: {e}")
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A theme with name '{payload.name}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update custom theme"
        )


@router.delete("/custom/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_theme(
    theme_id: int,
    request: Request,
    user = Depends(get_clerk_auth().get_current_user)
):
    """
    Delete a custom theme.

    Uses RLS for automatic user isolation (can only delete own themes).
    """
    clerk_user_id = user.get("user_id")

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            result = await conn.execute(
                "DELETE FROM user_custom_themes WHERE id = $1 AND user_id = $2",
                theme_id,
                clerk_user_id
            )

            if result == "DELETE 0":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Custom theme with ID {theme_id} not found"
                )

            logger.info(f"Custom theme ID {theme_id} deleted for user {clerk_user_id[:8]}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete custom theme: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete custom theme"
        )


# ===== Combined Endpoint (Default + Custom) =====

@router.get("/all", response_model=CombinedThemesResponse)
async def list_all_themes(
    request: Request,
    user = Depends(get_clerk_auth().get_current_user)
):
    """
    List all available themes for the current user.

    Returns both:
    - 12 system default themes (read-only)
    - User's custom themes (0-4)

    Useful for populating theme selection dropdowns in the frontend.
    """
    clerk_user_id = user.get("user_id")

    try:
        pg = await get_postgres_rls_client()

        # Fetch default themes (no RLS needed)
        async with pg.pool.acquire() as conn:
            default_rows = await conn.fetch(
                """
                SELECT id, name, gamma_theme_id, color_description, created_at
                FROM gamma_themes
                ORDER BY name ASC
                """
            )

            default_themes = [
                GammaTheme(
                    id=row['id'],
                    name=row['name'],
                    gamma_theme_id=row['gamma_theme_id'],
                    color_description=row['color_description'],
                    created_at=row['created_at']
                )
                for row in default_rows
            ]

        # Fetch custom themes (with RLS)
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            custom_rows = await conn.fetch(
                """
                SELECT id, user_id, name, gamma_theme_id, created_at, updated_at
                FROM user_custom_themes
                WHERE user_id = $1
                ORDER BY created_at ASC
                """,
                clerk_user_id
            )

            custom_themes = [
                UserCustomTheme(
                    id=row['id'],
                    user_id=row['user_id'],
                    name=row['name'],
                    gamma_theme_id=row['gamma_theme_id'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in custom_rows
            ]

        total_count = len(default_themes) + len(custom_themes)
        can_add_custom = len(custom_themes) < 4

        return CombinedThemesResponse(
            default_themes=default_themes,
            custom_themes=custom_themes,
            total_count=total_count,
            can_add_custom=can_add_custom
        )

    except Exception as e:
        logger.error(f"Failed to fetch combined themes: {e}")
        # Graceful degradation - return empty lists
        return CombinedThemesResponse(
            default_themes=[],
            custom_themes=[],
            total_count=0,
            can_add_custom=True,
            message="Failed to fetch themes"
        )
