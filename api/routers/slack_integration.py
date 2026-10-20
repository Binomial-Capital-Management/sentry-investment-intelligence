from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional

from core.services.slack_service import (
    get_slack_service,
    SlackServiceError,
)

router = APIRouter(prefix="/api/slack", tags=["integrations:slack"])


@router.get("/authorize")
async def slack_authorize(request: Request):
    """Return the Slack OAuth authorization URL for the current user."""
    user_id = request.state.user_id
    service = get_slack_service()
    try:
        url = service.build_authorize_url(user_id)
        return {"authorization_url": url}
    except SlackServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/oauth/callback")
async def slack_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Slack OAuth redirect target."""
    service = get_slack_service()

    if error:
        return HTMLResponse(
            content=f"<html><body>Slack authorization failed: {error}</body></html>",
            status_code=400,
        )

    if not code or not state:
        return HTMLResponse(
            content="<html><body>Missing Slack authorization parameters.</body></html>",
            status_code=400,
        )

    try:
        workspace = await service.exchange_code(code, state)
    except SlackServiceError as exc:
        return HTMLResponse(
            content=f"<html><body>Slack authorization failed: {exc}</body></html>",
            status_code=400,
        )

    return HTMLResponse(
        content=f"<html><body>Slack workspace '{workspace.team_name or workspace.team_id}' connected. You can close this window.</body></html>"
    )


@router.get("/workspaces")
async def list_workspaces(request: Request):
    """List Slack workspaces connected by the current user."""
    service = get_slack_service()
    try:
        workspaces = await service.list_workspaces(request.state.user_id)
        return {"workspaces": [workspace.__dict__ for workspace in workspaces]}
    except SlackServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/workspaces/{team_id}")
async def delete_workspace(request: Request, team_id: str):
    """Disconnect a Slack workspace."""
    service = get_slack_service()
    try:
        await service.delete_workspace(request.state.user_id, team_id)
        return {"status": "deleted"}
    except SlackServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/channels")
async def list_channels(
    request: Request,
    team_id: str = Query(..., description="Slack team ID to list channels for"),
):
    service = get_slack_service()
    try:
        channels = await service.list_channels(request.state.user_id, team_id)
        return {"channels": channels}
    except SlackServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

