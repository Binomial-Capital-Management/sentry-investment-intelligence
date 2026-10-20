"""
Insights API Router
Endpoints for managing AI-generated Quick Insights.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Request, HTTPException, Query, status

from api.models_dir.insight import (
    InsightResponse,
    InsightListResponse,
    InsightUpdate,
    InsightGenerateRequest,
    PageType
)
from core.database.postgres_client import get_postgres_client
from core.services.insight_scheduler import get_insight_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/", response_model=InsightListResponse)
async def get_user_insights(
    request: Request,
    page_type: Optional[PageType] = Query(None, description="Filter by page type"),
    region: Optional[str] = Query(None, description="Filter by region (markets page only)"),
    unread_only: bool = Query(False, description="Show only unread insights"),
    limit: int = Query(6, ge=1, le=50, description="Max results per page")
):
    """
    Get user's insights with optional filtering.

    Returns most recent insights sorted by priority (highest first),
    then by generation date (newest first).
    """
    try:
        user_id = request.state.user_id
        pg = await get_postgres_client()

        # Fetch insights from database with RLS
        insights_data = await pg.get_insights(
            user_id=user_id,
            page_type=page_type.value if page_type else None,
            region=region,
            limit=limit,
            unread_only=unread_only
        )

        # Convert to response models
        insights = [InsightResponse(**insight) for insight in insights_data]

        return InsightListResponse(
            insights=insights,
            total=len(insights),
            page_type=page_type
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch insights for user {request.state.user_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to fetch insights",
                "error": str(e),
                "error_type": "fetch_failed"
            }
        )


@router.post("/generate", response_model=dict)
async def generate_insights(
    request: Request,
    generate_request: InsightGenerateRequest
):
    """
    Trigger on-demand insight generation for current user.

    Useful for:
    - Testing insight generation
    - Manual refresh when user wants latest insights
    - Force regeneration after portfolio changes
    """
    try:
        user_id = request.state.user_id
        scheduler = await get_insight_scheduler()

        logger.info(
            "Manual insight generation triggered for user %s, page_type=%s, region=%s",
            user_id,
            generate_request.page_type,
            generate_request.region
        )

        # Generate insights for this user
        result = await scheduler.generate_insights_now(
            user_id=user_id,
            page_type=generate_request.page_type.value if generate_request.page_type else None,
            region=generate_request.region
        )

        return {
            "status": "success",
            "user_id": user_id,
            "insights_created": result.get("insights_created", 0),
            "generated_at": result.get("generated_at"),
            "errors": result.get("errors", [])
        }

    except RuntimeError as e:
        logger.error(f"Insight scheduler unavailable: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Insight scheduler unavailable",
                "error": str(e),
                "error_type": "scheduler_unavailable"
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to generate insights for user {request.state.user_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to generate insights",
                "error": str(e),
                "error_type": "generation_failed"
            }
        )


@router.patch("/{insight_id}", response_model=InsightResponse)
async def update_insight(
    request: Request,
    insight_id: UUID,
    update_data: InsightUpdate
):
    """
    Update an insight (typically to mark as read).

    RLS ensures users can only update their own insights.
    """
    try:
        user_id = request.state.user_id
        pg = await get_postgres_client()

        # Update insight with RLS
        updated_insight = await pg.update_insight(
            user_id=user_id,
            insight_id=insight_id,
            is_read=update_data.is_read,
            priority=update_data.priority
        )

        if not updated_insight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insight not found or access denied"
            )

        return InsightResponse(**updated_insight)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update insight {insight_id} for user {request.state.user_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to update insight",
                "error": str(e),
                "error_type": "update_failed"
            }
        )


@router.delete("/{insight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_insight(
    request: Request,
    insight_id: UUID
):
    """
    Delete a specific insight.

    RLS ensures users can only delete their own insights.
    """
    try:
        user_id = request.state.user_id
        pg = await get_postgres_client()

        # Delete insight with RLS
        deleted = await pg.delete_insight(user_id=user_id, insight_id=insight_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insight not found or access denied"
            )

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete insight {insight_id} for user {request.state.user_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to delete insight",
                "error": str(e),
                "error_type": "delete_failed"
            }
        )


@router.post("/admin/generate-all", response_model=dict)
async def admin_generate_all_insights(request: Request):
    """
    Admin endpoint: Trigger insight generation for ALL users.
    
    This mimics what the 6 AM scheduler does.
    Only works in dev mode with dev credentials.
    """
    import os
    
    # Only allow in dev mode
    is_production = os.getenv('ENV') == 'production' or os.getenv('ENVIRONMENT') == 'production'
    if is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin endpoints disabled in production"
        )
    
    try:
        scheduler = await get_insight_scheduler()
        
        logger.info("Admin: Triggering insight generation for ALL users")
        
        # This runs the same code as the daily scheduler
        await scheduler.generate_daily_insights()
        
        return {
            "status": "success",
            "message": "Daily insight generation completed for all users. Check logs for details."
        }
        
    except Exception as e:
        logger.error(f"Admin insight generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to generate insights for all users",
                "error": str(e)
            }
        )


@router.delete("/cleanup/expired", response_model=dict)
async def cleanup_expired_insights(request: Request):
    """
    Manually trigger cleanup of expired insights (older than 24 hours).

    Note: Scheduler automatically cleans up during daily generation,
    but this endpoint allows manual cleanup if needed.
    """
    try:
        user_id = request.state.user_id
        pg = await get_postgres_client()

        # Delete expired insights for this user
        deleted_count = await pg.delete_old_insights(user_id=user_id, older_than_hours=24)

        logger.info(f"Cleaned up {deleted_count} expired insights for user {user_id}")

        return {
            "status": "success",
            "deleted_count": deleted_count
        }

    except Exception as e:
        logger.error(
            f"Failed to cleanup insights for user {request.state.user_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to cleanup insights",
                "error": str(e),
                "error_type": "cleanup_failed"
            }
        )
