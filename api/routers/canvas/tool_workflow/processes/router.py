"""Canvas Process Persistence Router.

Endpoints for saving, loading, and managing Canvas processes.
Uses FastAPI dependency injection for auth and database access.
"""

from fastapi import APIRouter
from typing import Optional
import logging

from core.exceptions import ProcessNotFoundError, DatabaseError
from ...types import (
    SaveProcessRequest,
    UpdateProcessRequest,
    FullUpdateProcessRequest,
    ApplyUpdateRequest,
)
from ...shared.dependencies import DB, CurrentUser, OrgId

logger = logging.getLogger(__name__)

router = APIRouter(tags=["canvas-processes"])


@router.post("/processes")
async def save_process(body: SaveProcessRequest, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Save a canvas process to the database."""
    # Store metric_cards inside metrics to avoid schema changes
    metrics_with_cards = {**body.metrics, "_metric_cards": body.metric_cards}

    process_id = await db.save_canvas_process(
        user_id=user_id,
        org_id=org_id,
        tool_id=body.tool_id,
        tickers=body.tickers,
        weights=body.weights,
        metrics=metrics_with_cards,
        stats_table=body.stats_table,
        charts=body.charts,
        name=body.name,
        object_type=body.object_type,
        hmm_enabled=body.hmm_enabled,
        current_regime=body.current_regime,
        regime_params=body.regime_params,
        graph_steps=body.graph_steps,
        graph_edges=body.graph_edges,
        params=body.params,
        process_type=body.process_type,
        config=body.config,
    )

    if not process_id:
        raise DatabaseError("Failed to save process")

    logger.info(f"Canvas process saved: {process_id} for user {user_id}")
    return {"status": "success", "id": process_id}


@router.get("/processes")
async def list_processes(
    user_id: CurrentUser,
    org_id: OrgId,
    db: DB,
    tool_id: Optional[str] = None, 
    process_type: Optional[str] = None,
    limit: int = 50
):
    """List saved canvas processes for the user."""
    logger.debug(f"list_processes: user_id={user_id}, org_id={org_id}, process_type={process_type}")

    processes = await db.get_canvas_processes(
        user_id=user_id,
        org_id=org_id,
        tool_id=tool_id,
        process_type=process_type,
        limit=limit,
    )

    logger.debug(f"Found {len(processes)} processes for process_type={process_type}")
    return {"processes": processes}


@router.get("/processes/{process_id}")
async def get_process(process_id: str, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Get a single canvas process by ID."""
    process = await db.get_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )

    if not process:
        raise ProcessNotFoundError(process_id)

    return process


@router.patch("/processes/{process_id}")
async def update_process(process_id: str, body: UpdateProcessRequest, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Update a canvas process (e.g., rename)."""
    success = await db.update_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
        name=body.name,
    )

    if not success:
        raise ProcessNotFoundError(process_id)

    logger.info(f"Canvas process updated: {process_id} for user {user_id}")
    return {"status": "success"}


@router.put("/processes/{process_id}")
async def full_update_process(process_id: str, body: FullUpdateProcessRequest, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Full update of a canvas process (name, tickers, params, config)."""
    # Verify process exists and belongs to user
    existing = await db.get_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )
    if not existing:
        raise ProcessNotFoundError(process_id)

    success = await db.full_update_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
        name=body.name,
        tickers=body.tickers,
        params=body.params,
        config=body.config,
    )

    if not success:
        raise DatabaseError("Failed to update process")

    logger.info(f"Canvas process fully updated: {process_id} for user {user_id}")
    return {"status": "success", "id": process_id}


@router.delete("/processes/{process_id}")
async def delete_process(process_id: str, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Delete a canvas process."""
    success = await db.delete_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )

    if not success:
        raise ProcessNotFoundError(process_id)

    logger.info(f"Canvas process deleted: {process_id} for user {user_id}")
    return {"status": "success"}


@router.post("/processes/{process_id}/apply-update")
async def apply_tool_update(process_id: str, body: ApplyUpdateRequest, user_id: CurrentUser, org_id: OrgId, db: DB):
    """Apply a pending tool re-run result to update the process."""
    # Verify process exists and belongs to user
    existing = await db.get_canvas_process(
        user_id=user_id,
        process_id=process_id,
        org_id=org_id,
    )
    if not existing:
        raise ProcessNotFoundError(process_id)

    # Build the updated process data
    result = body.full_result
    metrics = result.get("metrics", {})
    if result.get("metric_cards"):
        metrics["_metric_cards"] = result["metric_cards"]

    # Prefer new HMM values from result, fall back to existing
    hmm_enabled = result.get("hmm_enabled", existing.get("hmm_enabled", False))
    current_regime = result.get("current_regime") or existing.get("current_regime")
    regime_params = result.get("regime_params") or existing.get("regime_params")

    # Update the process using the full update method
    success = await db.update_canvas_process_full(
        user_id=user_id,
        process_id=process_id,
        tool_id=body.tool_id,
        tickers=body.tickers,
        weights=body.weights,
        metrics=metrics,
        stats_table=result.get("stats_table", []),
        charts=result.get("charts", {}),
        org_id=org_id,
        params=body.params,
        name=existing.get("name"),
        hmm_enabled=hmm_enabled,
        current_regime=current_regime,
        regime_params=regime_params,
    )

    if not success:
        raise DatabaseError("Failed to update process")

    logger.info(f"Applied tool update to process {process_id} for user {user_id}")
    return {"status": "success", "process_id": process_id}
