"""
User Settings Router

Handles user export styles (presets) stored in PostgreSQL with RLS.
Each user can save up to 10 named export styles.
Logos stored in S3 via existing uploads infrastructure.

Following CODING_RULES.md:
- NO HARDCODING - All defaults from gamma_client.py
- KISS - Simple CRUD endpoints with PostgreSQL
- DRY - Reusable helper functions
"""
import logging
import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request, status
from urllib.parse import unquote

from core.auth.clerk_verify import get_clerk_auth
from core.database.postgres_client import get_postgres_rls_client
from core.services.artifact_storage import get_artifact_storage
from api.models_dir.export_settings import (
    ExportSettings,
    ExportStyle,
    ExportStyleCreateRequest,
    ExportStyleUpdateRequest,
    ExportStyleResponse,
    ExportStyleListResponse,
    SetDefaultStyleRequest,
    # Keep old models for backward compatibility (deprecated)
    ExportSettingsResponse,
    ExportSettingsUpdateRequest,
    ExportSettingsUpdateResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user-settings", tags=["user-settings"])


async def generate_logo_url_from_file_id(file_id: str, user_id: str) -> Optional[str]:
    """
    Generate S3 presigned URL from file_id.

    Args:
        file_id: File ID from uploads table
        user_id: Clerk user ID for RLS validation

    Returns:
        S3 presigned URL (1-year expiration) or None if file not found
    """
    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            file_record = await conn.fetchrow(
                "SELECT stored_key, original_name FROM files WHERE id = $1",
                file_id
            )

            if not file_record:
                logger.warning(f"File {file_id} not found for user {user_id[:8]}")
                return None

            # Generate presigned URL with 1-year expiration
            artifact_storage = get_artifact_storage()
            presigned_url = artifact_storage.generate_presigned_url(
                category="uploads",
                filename=file_record['stored_key'],
                expiration=31536000  # 1 year in seconds
            )

            return presigned_url

    except Exception as e:
        logger.error(f"Failed to generate logo URL: {e}")
        return None


# ===== Export Styles CRUD Endpoints =====

@router.get("/export-styles", response_model=ExportStyleListResponse)
async def list_export_styles(
    request: Request,
):
    """
    List all export styles for the current user.

    Returns all saved export styles with default style identified.
    Uses RLS for automatic user isolation.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            rows = await conn.fetch(
                """
                SELECT style_name, settings, is_default, created_at, updated_at
                FROM user_export_settings
                WHERE user_id = $1
                ORDER BY is_default DESC, created_at ASC
                """,
                clerk_user_id
            )

            styles = []
            default_style_name = None

            for row in rows:
                # Parse settings from JSONB (may be dict or string depending on asyncpg version)
                settings_dict = row['settings'] if isinstance(row['settings'], dict) else json.loads(row['settings'])

                style = ExportStyle(
                    style_name=row['style_name'],
                    settings=ExportSettings(**settings_dict),
                    is_default=row['is_default'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                styles.append(style)

                if row['is_default']:
                    default_style_name = row['style_name']

            return ExportStyleListResponse(
                styles=styles,
                count=len(styles),
                default_style=default_style_name
            )

    except Exception as e:
        logger.error(f"Failed to fetch export styles: {e}")
        # Graceful degradation - return empty list
        return ExportStyleListResponse(
            styles=[],
            count=0,
            default_style=None,
            message="Failed to fetch export styles"
        )


@router.post("/export-styles", response_model=ExportStyleResponse, status_code=status.HTTP_201_CREATED)
async def create_export_style(
    payload: ExportStyleCreateRequest,
    request: Request,
):
    """
    Create a new export style.

    Maximum 10 styles per user (enforced by database trigger).
    If is_default=true, automatically unsets previous default.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    settings = payload.settings

    try:
        # Generate logo URL if file_id provided
        if settings.logo_source == "custom" and settings.logo_file_id:
            logo_url = await generate_logo_url_from_file_id(settings.logo_file_id, clerk_user_id)
            if logo_url:
                settings.logo_url = logo_url
                logger.info(f"Generated logo URL for user {clerk_user_id[:8]}")
            # Note: Missing file warning already logged by generate_logo_url_from_file_id

        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            # Start transaction for atomic default switching
            async with conn.transaction():
                # If marking as default, unset previous default first
                if payload.is_default:
                    await conn.execute(
                        """
                        UPDATE user_export_settings
                        SET is_default = false
                        WHERE user_id = $1 AND is_default = true
                        """,
                        clerk_user_id
                    )

                # Insert new style
                row = await conn.fetchrow(
                    """
                    INSERT INTO user_export_settings (user_id, style_name, settings, is_default)
                    VALUES ($1, $2, $3::jsonb, $4)
                    RETURNING style_name, settings, is_default, created_at, updated_at
                    """,
                    clerk_user_id,
                    payload.style_name,
                    json.dumps(settings.dict(exclude_none=False)),
                    payload.is_default
                )

            logger.info(f"Export style '{payload.style_name}' created for user {clerk_user_id[:8]}")

            # Parse settings from JSONB (may be dict or string depending on asyncpg version)
            settings_dict = row['settings'] if isinstance(row['settings'], dict) else json.loads(row['settings'])

            created_style = ExportStyle(
                style_name=row['style_name'],
                settings=ExportSettings(**settings_dict),
                is_default=row['is_default'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

            return ExportStyleResponse(
                style=created_style,
                message=f"Export style '{payload.style_name}' created successfully"
            )

    except Exception as e:
        logger.error(f"Failed to create export style: {e}")
        if "duplicate key" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Export style '{payload.style_name}' already exists"
            )
        elif "maximum 10 export styles" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 export styles per user. Delete an existing style before creating a new one."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create export style"
        )


@router.get("/export-styles/{style_name}", response_model=ExportStyleResponse)
async def get_export_style(
    style_name: str,
    request: Request,
):
    """
    Get a specific export style by name.

    Uses RLS for automatic user isolation.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # URL decode style name (handles spaces and special characters)
    style_name = unquote(style_name)

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT style_name, settings, is_default, created_at, updated_at
                FROM user_export_settings
                WHERE user_id = $1 AND style_name = $2
                """,
                clerk_user_id,
                style_name
            )

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Export style '{style_name}' not found"
                )

            # Parse settings from JSONB (may be dict or string depending on asyncpg version)
            settings_dict = row['settings'] if isinstance(row['settings'], dict) else json.loads(row['settings'])

            style = ExportStyle(
                style_name=row['style_name'],
                settings=ExportSettings(**settings_dict),
                is_default=row['is_default'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

            return ExportStyleResponse(style=style)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch export style: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch export style"
        )


@router.put("/export-styles/{style_name}", response_model=ExportStyleResponse)
async def update_export_style(
    style_name: str,
    payload: ExportStyleUpdateRequest,
    request: Request,
):
    """
    Update an existing export style.

    Can update settings and optionally rename the style.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # URL decode style name
    style_name = unquote(style_name)
    settings = payload.settings

    try:
        # Generate logo URL if file_id provided
        if settings.logo_source == "custom" and settings.logo_file_id:
            logo_url = await generate_logo_url_from_file_id(settings.logo_file_id, clerk_user_id)
            if logo_url:
                settings.logo_url = logo_url
                logger.info(f"Generated logo URL for user {clerk_user_id[:8]}")

        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            # Check if style exists first
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM user_export_settings WHERE user_id = $1 AND style_name = $2)",
                clerk_user_id,
                style_name
            )

            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Export style '{style_name}' not found"
                )

            # If renaming, check for conflicts
            if payload.new_style_name and payload.new_style_name != style_name:
                conflict_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM user_export_settings WHERE user_id = $1 AND style_name = $2)",
                    clerk_user_id,
                    payload.new_style_name
                )

                if conflict_exists:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Export style '{payload.new_style_name}' already exists"
                    )

                # Rename + update settings
                row = await conn.fetchrow(
                    """
                    UPDATE user_export_settings
                    SET style_name = $3, settings = $4::jsonb, updated_at = NOW()
                    WHERE user_id = $1 AND style_name = $2
                    RETURNING style_name, settings, is_default, created_at, updated_at
                    """,
                    clerk_user_id,
                    style_name,
                    payload.new_style_name,
                    json.dumps(settings.dict(exclude_none=False))
                )

                logger.info(f"Export style renamed '{style_name}' → '{payload.new_style_name}' for user {clerk_user_id[:8]}")
            else:
                # Update settings only
                row = await conn.fetchrow(
                    """
                    UPDATE user_export_settings
                    SET settings = $3::jsonb, updated_at = NOW()
                    WHERE user_id = $1 AND style_name = $2
                    RETURNING style_name, settings, is_default, created_at, updated_at
                    """,
                    clerk_user_id,
                    style_name,
                    json.dumps(settings.dict(exclude_none=False))
                )

                logger.info(f"Export style '{style_name}' updated for user {clerk_user_id[:8]}")

            # Parse settings from JSONB (may be dict or string depending on asyncpg version)
            settings_dict = row['settings'] if isinstance(row['settings'], dict) else json.loads(row['settings'])

            updated_style = ExportStyle(
                style_name=row['style_name'],
                settings=ExportSettings(**settings_dict),
                is_default=row['is_default'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

            return ExportStyleResponse(
                style=updated_style,
                message=f"Export style '{row['style_name']}' updated successfully"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update export style: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update export style"
        )


@router.delete("/export-styles/{style_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export_style(
    style_name: str,
    request: Request,
):
    """
    Delete an export style.

    Cannot delete default style or the only remaining style.
    Protected by database triggers.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # URL decode style name
    style_name = unquote(style_name)

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            # Delete will fail via trigger if it's default or last style
            result = await conn.execute(
                "DELETE FROM user_export_settings WHERE user_id = $1 AND style_name = $2",
                clerk_user_id,
                style_name
            )

            if result == "DELETE 0":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Export style '{style_name}' not found"
                )

            logger.info(f"Export style '{style_name}' deleted for user {clerk_user_id[:8]}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete export style: {e}")
        if "cannot delete the default" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the default export style. Set another style as default first."
            )
        elif "cannot delete the only" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the only export style. Create another style first."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete export style"
        )


@router.put("/export-styles/{style_name}/set-default", response_model=ExportStyleResponse)
async def set_default_export_style(
    style_name: str,
    request: Request,
):
    """
    Mark an export style as the default.

    Automatically unsets previous default style.
    Default style is used when no style explicitly selected.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # URL decode style name
    style_name = unquote(style_name)

    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            async with conn.transaction():
                # Check if style exists
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM user_export_settings WHERE user_id = $1 AND style_name = $2)",
                    clerk_user_id,
                    style_name
                )

                if not exists:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Export style '{style_name}' not found"
                    )

                # Unset previous default
                await conn.execute(
                    "UPDATE user_export_settings SET is_default = false WHERE user_id = $1 AND is_default = true",
                    clerk_user_id
                )

                # Set new default
                row = await conn.fetchrow(
                    """
                    UPDATE user_export_settings
                    SET is_default = true, updated_at = NOW()
                    WHERE user_id = $1 AND style_name = $2
                    RETURNING style_name, settings, is_default, created_at, updated_at
                    """,
                    clerk_user_id,
                    style_name
                )

            logger.info(f"Export style '{style_name}' set as default for user {clerk_user_id[:8]}")

            # Parse settings from JSONB (may be dict or string depending on asyncpg version)
            settings_dict = row['settings'] if isinstance(row['settings'], dict) else json.loads(row['settings'])

            updated_style = ExportStyle(
                style_name=row['style_name'],
                settings=ExportSettings(**settings_dict),
                is_default=row['is_default'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

            return ExportStyleResponse(
                style=updated_style,
                message=f"Export style '{style_name}' set as default"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set default export style: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default export style"
        )


# ===== Helper Functions =====

async def fetch_user_export_style(clerk_user_id: str, style_name: Optional[str] = None) -> ExportSettings:
    """
    Helper function to fetch user's export style settings from PostgreSQL.

    Used by export endpoints (exports.py, executor.py) to get user preferences.
    Returns default ExportSettings if not configured or on error.

    Args:
        clerk_user_id: Clerk user ID
        style_name: Optional specific style name. If None, fetches default style.

    Returns:
        ExportSettings with user preferences or defaults
    """
    try:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(clerk_user_id) as conn:
            if style_name:
                # Fetch specific style
                row = await conn.fetchrow(
                    """
                    SELECT settings FROM user_export_settings
                    WHERE user_id = $1 AND style_name = $2
                    """,
                    clerk_user_id,
                    style_name
                )
            else:
                # Fetch default style
                row = await conn.fetchrow(
                    """
                    SELECT settings FROM user_export_settings
                    WHERE user_id = $1 AND is_default = true
                    """,
                    clerk_user_id
                )

            logger.info(f"DEBUG fetch_user_export_style: Query completed. row={row is not None}, style_name={style_name}")

            if row and row['settings']:
                raw_settings = row['settings']
                logger.info(f"DEBUG fetch_user_export_style: raw_settings type={type(raw_settings)}, raw_settings={raw_settings}")

                # Parse settings from JSONB (may be dict or string depending on asyncpg version)
                settings_dict = raw_settings if isinstance(raw_settings, dict) else json.loads(raw_settings)
                logger.info(f"DEBUG fetch_user_export_style: style_name={style_name}, settings_dict keys={list(settings_dict.keys())}")
                logger.info(f"DEBUG fetch_user_export_style: settings_dict.theme_id={settings_dict.get('theme_id')}, settings_dict.language={settings_dict.get('language')}, settings_dict.logo_size={settings_dict.get('logo_size')}")

                result = ExportSettings(**settings_dict)
                logger.info(f"DEBUG fetch_user_export_style: ExportSettings object theme_id={result.theme_id}, language={result.language}, logo_size={result.logo_size}")
                return result
            else:
                logger.info(f"DEBUG fetch_user_export_style: No row found or settings is None. row={row}, row['settings'] if row else None = {row['settings'] if row else 'N/A'}")
                logger.debug(f"No export style found for user {clerk_user_id[:8]}, using defaults")
                return ExportSettings()

    except Exception as e:
        logger.error(f"EXCEPTION in fetch_user_export_style for {clerk_user_id[:8]}, style_name={style_name}: {e}", exc_info=True)
        # Graceful degradation - return defaults
        return ExportSettings()


# Keep for backward compatibility (deprecated - will be removed in future version)
async def fetch_user_export_settings(clerk_user_id: str) -> ExportSettings:
    """
    DEPRECATED: Use fetch_user_export_style() instead.

    Fetches default export style for backward compatibility.
    """
    logger.warning("fetch_user_export_settings() is deprecated. Use fetch_user_export_style() instead.")
    return await fetch_user_export_style(clerk_user_id, style_name=None)
