from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from typing import Optional

from core.services.teams_service import (
    get_teams_service,
    TeamsServiceError,
)

router = APIRouter(prefix="/api/teams", tags=["integrations:teams"])


@router.get("/authorize")
async def teams_authorize(request: Request):
    service = get_teams_service()
    try:
        url = service.build_authorize_url(request.state.user_id)
        return {"authorization_url": url}
    except TeamsServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/oauth/callback")
async def teams_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    service = get_teams_service()
    if error:
        return HTMLResponse(
            content=f"<html><body>Teams authorization failed: {error}</body></html>",
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse(
            content="<html><body>Missing Teams authorization parameters.</body></html>",
            status_code=400,
        )
    try:
        workspace = await service.exchange_code(code, state)
    except TeamsServiceError as exc:
        return HTMLResponse(
            content=f"<html><body>Teams authorization failed: {exc}</body></html>",
            status_code=400,
        )
    return HTMLResponse(
        content=f"<html><body>Teams tenant '{workspace.tenant_name or workspace.tenant_id}' connected. You can close this window.</body></html>"
    )


@router.get("/workspaces")
async def list_workspaces(request: Request):
    service = get_teams_service()
    try:
        workspaces = await service.list_workspaces(request.state.user_id)
        return {"workspaces": [workspace.__dict__ for workspace in workspaces]}
    except TeamsServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/workspaces/{tenant_id}")
async def delete_workspace(request: Request, tenant_id: str):
    service = get_teams_service()
    try:
        await service.delete_workspace(request.state.user_id, tenant_id)
        return {"status": "deleted"}
    except TeamsServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/teams")
async def list_teams(
    request: Request,
    tenant_id: str = Query(..., description="Azure AD tenant ID"),
):
    service = get_teams_service()
    try:
        teams = await service.list_teams(request.state.user_id, tenant_id)
        return {"teams": [team.__dict__ for team in teams]}
    except TeamsServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/channels")
async def list_channels(
    request: Request,
    tenant_id: str = Query(..., description="Azure AD tenant ID"),
    team_id: str = Query(..., description="Teams team ID"),
):
    service = get_teams_service()
    try:
        channels = await service.list_channels(request.state.user_id, tenant_id, team_id)
        return {"channels": [channel.__dict__ for channel in channels]}
    except TeamsServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

