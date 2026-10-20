"""
Workflow API Endpoints
Status: Production
Created: September 2025

PURPOSE: CRUD operations and validation for workflows.
Uses RLS for complete user isolation.
Engine execution controlled by feature flag.
"""

from fastapi import APIRouter, Request, HTTPException, Query, Depends, Response
from typing import List, Dict, Optional, Any
from uuid import UUID
import json
import logging
import time
from collections import defaultdict
from datetime import datetime

from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client
from core.workflows.types import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowListResponse,
    WorkflowValidationRequest, WorkflowValidationResponse,
    WorkflowRunCreate, WorkflowRunResponse,
    SimplifiedWorkflow, InputNode, AgentNode, OutputNode
)
from core.workflows.validation import WorkflowValidator
from core.workflows.engine import WorkflowEngine
from core.services.artifact_storage import get_artifact_storage

logger = logging.getLogger(__name__)
config = get_config()


def get_org_id(request: Request) -> str:
    """Extract org_id from request state, defaulting to empty string for personal workspace."""
    return getattr(request.state, 'org_id', None) or ''

# Simple in-memory rate limiter
class RateLimiter:
    def __init__(self, calls_per_minute: int = 10):
        self.calls_per_minute = calls_per_minute
        self.calls = defaultdict(list)

    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit"""
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        self.calls[user_id] = [t for t in self.calls[user_id] if t > minute_ago]

        # Check limit
        if len(self.calls[user_id]) >= self.calls_per_minute:
            return False

        # Record call
        self.calls[user_id].append(now)
        return True

rate_limiter = RateLimiter(calls_per_minute=config.workflows_rate_limit_per_minute if hasattr(config, 'workflows_rate_limit_per_minute') else 10)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ===== CRUD OPERATIONS =====

@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    request: Request,
    workflow: WorkflowCreate
) -> WorkflowResponse:
    """
    Create a new workflow after validation.
    Stores in PostgreSQL with RLS isolation.
    Supports both simplified and legacy formats.
    """
    user_id = request.state.user_id
    pg = await get_postgres_rls_client()

    # Validate the workflow
    validator = WorkflowValidator()
    if workflow.simplified_workflow:
        # Validate simplified format
        validation_result = validator.validate_simplified(workflow.simplified_workflow)
    else:
        # Legacy format - store as-is for now (will be migrated later)
        validation_result = validator.validate_legacy(workflow.nodes, workflow.edges)

    if not validation_result.is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Workflow validation failed",
                "errors": validation_result.errors,
                "warnings": validation_result.warnings
            }
        )

    # Store in database with org_id for workspace isolation
    org_id = get_org_id(request)
    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        # Convert simplified workflow to JSON for storage
        if workflow.simplified_workflow:
            workflow_json = json.dumps(workflow.simplified_workflow.dict())
            nodes_json = "[]"  # Empty for simplified format
            edges_json = "[]"

            # DEBUG: Log what we're saving
            logger.info(f"[SAVE WORKFLOW] Saving simplified workflow: {workflow_json[:500]}")
        else:
            workflow_json = "{}"
            nodes_json = json.dumps(workflow.nodes) if workflow.nodes else "[]"
            edges_json = json.dumps(workflow.edges) if workflow.edges else "[]"

        row = await conn.fetchrow(
            """
            INSERT INTO workflows (
                user_id, org_id, name, description, nodes, edges, configuration, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, version, created_at, updated_at
            """,
            user_id,
            org_id,
            workflow.name,
            workflow.description,
            nodes_json,
            edges_json,
            workflow_json if workflow.simplified_workflow else json.dumps(workflow.configuration or {}),
            workflow.status.value
        )

    return WorkflowResponse(
        id=row["id"],
        user_id=user_id,
        name=workflow.name,
        description=workflow.description,
        simplified_workflow=workflow.simplified_workflow,
        nodes=workflow.nodes,
        edges=workflow.edges,
        configuration=workflow.configuration,
        status=workflow.status,
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    minimal: bool = Query(False, description="Return minimal fields only (id, name, created_at)")
) -> WorkflowListResponse:
    """
    List user's workflows with pagination.
    Only returns workflows owned by the authenticated user (RLS).
    """
    user_id = request.state.user_id
    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()
    
    offset = (page - 1) * page_size
    
    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        # Select minimal or full fields based on parameter
        if minimal:
            select_fields = """
                w.id, w.name, w.created_at, w.status,
                (SELECT MAX(wr.created_at) FROM workflow_runs wr WHERE wr.workflow_id = w.id) as last_run_at
            """
        else:
            select_fields = """
                w.id, w.name, w.description, w.nodes, w.edges, w.configuration,
                w.status, w.version, w.created_at, w.updated_at,
                (SELECT MAX(wr.created_at) FROM workflow_runs wr WHERE wr.workflow_id = w.id) as last_run_at
            """

        if status:
            # Get workflows with status filter and org_id
            rows = await conn.fetch(
                f"""
                SELECT {select_fields}
                FROM workflows w
                WHERE w.deleted_at IS NULL AND w.status = $1 AND w.org_id = $2
                ORDER BY w.created_at DESC
                LIMIT $3 OFFSET $4
                """,
                status, org_id, page_size, offset
            )

            # Get total count with status filter and org_id
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM workflows WHERE deleted_at IS NULL AND status = $1 AND org_id = $2",
                status, org_id
            )
        else:
            # Get workflows without status filter but with org_id
            rows = await conn.fetch(
                f"""
                SELECT {select_fields}
                FROM workflows w
                WHERE w.deleted_at IS NULL AND w.org_id = $1
                ORDER BY w.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                org_id, page_size, offset
            )

            # Get total count with org_id filter
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM workflows WHERE deleted_at IS NULL AND org_id = $1",
                org_id
            )
    
    # Convert to response models
    workflows = []
    for row in rows:
        if minimal:
            workflows.append(WorkflowResponse(
                id=row["id"],
                user_id=user_id,
                name=row["name"],
                description="",
                simplified_workflow=None,
                nodes=None,
                edges=None,
                configuration=None,
                status=row["status"],
                version=1,
                created_at=row["created_at"],
                updated_at=row["created_at"],
                last_run_at=row.get("last_run_at")
            ))
        else:
            # Parse simplified workflow from configuration
            config_json = json.loads(row["configuration"])
            if "input_node" not in config_json:
                raise HTTPException(400, "Legacy workflow format not supported")

            simplified = SimplifiedWorkflow(
                input_node=InputNode(**config_json["input_node"]),
                agent_nodes=[AgentNode(**a) for a in config_json["agent_nodes"]],
                output_node=OutputNode(**config_json["output_node"])
            )
            workflows.append(WorkflowResponse(
                id=row["id"],
                user_id=user_id,
                name=row["name"],
                description=row["description"],
                simplified_workflow=simplified,
                nodes=None,
                edges=None,
                configuration=None,
                status=row["status"],
                version=row["version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_run_at=row.get("last_run_at")
            ))
    
    return WorkflowListResponse(
        workflows=workflows,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    request: Request,
    workflow_id: UUID
) -> WorkflowResponse:
    """
    Get a single workflow by ID.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()
    
    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, name, description, nodes, edges, configuration,
                   status, version, created_at, updated_at
            FROM workflows
            WHERE id = $1 AND deleted_at IS NULL AND org_id = $2
            """,
            workflow_id, org_id
        )
    
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Parse simplified workflow from configuration
    config_json = json.loads(row["configuration"])
    if "input_node" not in config_json:
        raise HTTPException(400, "Legacy workflow format not supported")

    simplified = SimplifiedWorkflow(
        input_node=InputNode(**config_json["input_node"]),
        agent_nodes=[AgentNode(**a) for a in config_json["agent_nodes"]],
        output_node=OutputNode(**config_json["output_node"])
    )

    return WorkflowResponse(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        description=row["description"],
        simplified_workflow=simplified,
        nodes=None,
        edges=None,
        configuration=None,
        status=row["status"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    request: Request,
    workflow_id: UUID,
    update: WorkflowUpdate
) -> WorkflowResponse:
    """
    Update an existing workflow.
    Validates changes and uses optimistic locking with version field.
    """
    user_id = request.state.user_id
    pg = await get_postgres_rls_client()

    # Validate simplified workflow if provided
    if update.simplified_workflow is not None:
        validator = WorkflowValidator()
        validation_result = validator.validate_simplified(update.simplified_workflow)

        if not validation_result.is_valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Workflow validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings
                }
            )
    
    # Build dynamic update query
    update_fields = []
    params = [workflow_id, user_id]
    param_idx = 3
    
    if update.name is not None:
        update_fields.append(f"name = ${param_idx}")
        params.append(update.name)
        param_idx += 1
    
    if update.description is not None:
        update_fields.append(f"description = ${param_idx}")
        params.append(update.description)
        param_idx += 1

    if update.simplified_workflow is not None:
        update_fields.append(f"configuration = ${param_idx}")
        params.append(json.dumps(update.simplified_workflow.dict()))
        param_idx += 1
    
    if update.status is not None:
        update_fields.append(f"status = ${param_idx}")
        params.append(update.status.value)
        param_idx += 1
    
    # Add version check for optimistic locking
    version_check = ""
    if update.version is not None:
        version_check = f" AND version = ${param_idx}"
        params.append(update.version)
    
    # Always update version and updated_at
    update_fields.append("version = version + 1")
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    org_id = get_org_id(request)
    params.append(org_id)
    org_id_param_idx = len(params)
    
    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE workflows
            SET {', '.join(update_fields)}
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL AND org_id = ${org_id_param_idx}{version_check}
            RETURNING id, user_id, name, description, nodes, edges, configuration,
                      status, version, created_at, updated_at
            """,
            *params
        )
    
    if not row:
        # Check if workflow exists
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM workflows WHERE id = $1 AND deleted_at IS NULL AND org_id = $2",
                workflow_id, org_id
            )
        
        if not exists:
            raise HTTPException(status_code=404, detail="Workflow not found")
        else:
            raise HTTPException(
                status_code=409,
                detail="Version conflict - workflow was modified by another process"
            )
    
    # Parse and return updated workflow
    config_json = json.loads(row["configuration"])
    if "input_node" not in config_json:
        raise HTTPException(400, "Legacy workflow format not supported")

    simplified = SimplifiedWorkflow(
        input_node=InputNode(**config_json["input_node"]),
        agent_nodes=[AgentNode(**a) for a in config_json["agent_nodes"]],
        output_node=OutputNode(**config_json["output_node"])
    )

    return WorkflowResponse(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        description=row["description"],
        simplified_workflow=simplified,
        nodes=None,
        edges=None,
        configuration=None,
        status=row["status"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.delete("/{workflow_id}")
async def delete_workflow(
    request: Request,
    workflow_id: UUID
) -> Dict[str, str]:
    """
    Soft delete a workflow (sets deleted_at timestamp).
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()
    
    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        result = await conn.execute(
            """
            UPDATE workflows
            SET deleted_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL AND org_id = $3
            """,
            workflow_id, user_id, org_id
        )
    
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return {"message": "Workflow deleted successfully"}


# ===== VALIDATION ENDPOINTS =====

@router.post("/validate", response_model=WorkflowValidationResponse)
async def validate_workflow(
    validation_request: WorkflowValidationRequest
) -> WorkflowValidationResponse:
    """
    Validate a workflow without saving it.
    Only supports simplified workflow format.
    """
    if not validation_request.simplified_workflow:
        raise HTTPException(400, "Must provide simplified_workflow")

    validator = WorkflowValidator()
    return validator.validate_simplified(validation_request.simplified_workflow)


@router.post("/{workflow_id}/validate", response_model=WorkflowValidationResponse)
async def validate_existing_workflow(
    request: Request,
    workflow_id: UUID
) -> WorkflowValidationResponse:
    """
    Validate an existing workflow by ID.
    Fetches the workflow and validates its current configuration.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        row = await conn.fetchrow(
            """
            SELECT configuration
            FROM workflows
            WHERE id = $1 AND deleted_at IS NULL AND org_id = $2
            """,
            workflow_id, org_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Parse and validate simplified workflow
    config_json = json.loads(row["configuration"])
    if "input_node" not in config_json:
        raise HTTPException(400, "Legacy workflow format not supported")

    simplified = SimplifiedWorkflow(
        input_node=InputNode(**config_json["input_node"]),
        agent_nodes=[AgentNode(**a) for a in config_json["agent_nodes"]],
        output_node=OutputNode(**config_json["output_node"])
    )

    validator = WorkflowValidator()
    return validator.validate_simplified(simplified)


# ===== WORKFLOW RUNS =====

@router.get("/{workflow_id}/runs", response_model=List[WorkflowRunResponse])
async def list_workflow_runs(
    request: Request,
    workflow_id: UUID,
    limit: int = Query(20, ge=1, le=100)
) -> List[WorkflowRunResponse]:
    """
    List runs for a specific workflow.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()
    
    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        rows = await conn.fetch(
            """
            SELECT id, workflow_id, user_id, status, summary as result,
                   configuration, error, started_at, completed_at, created_at
            FROM workflow_runs
            WHERE workflow_id = $1 AND user_id = $2 AND org_id = $3
            ORDER BY created_at DESC
            LIMIT $4
            """,
            workflow_id, user_id, org_id, limit
        )
    
    return [
        WorkflowRunResponse(
            id=row["id"],
            workflow_id=row["workflow_id"],
            user_id=row["user_id"],
            status=row["status"],
            input_data={},  # Default empty dict
            output_data=json.loads(row["result"]) if row["result"] else None,
            configuration=json.loads(row["configuration"]),
            error=row["error"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"]
        )
        for row in rows
    ]


@router.post("/{workflow_id}/run")
async def run_workflow(
    request: Request,
    workflow_id: UUID,
    run_request: Optional[WorkflowRunCreate] = None
) -> Dict[str, str]:
    """
    Execute a workflow using the workflow engine.
    Returns run_id for polling status.

    Supports idempotency via Idempotency-Key header - if the same key is sent,
    returns the existing run_id instead of creating a new run.
    """
    if not config.workflows_engine_enabled:
        raise HTTPException(
            status_code=501,
            detail="Workflow execution engine is currently disabled. Set WORKFLOWS_ENGINE_ENABLED=true to enable."
        )

    user_id = request.state.user_id

    # Check rate limit
    if not rate_limiter.check_rate_limit(user_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before making another request."
        )

    engine = WorkflowEngine()

    try:
        # Use async execution to return immediately
        run_id = await engine.run_workflow_async(str(workflow_id), user_id)
        return {"run_id": run_id}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        raise HTTPException(500, detail="Workflow execution failed")


@router.get("/workflow-runs/{run_id}")
async def get_workflow_run(
    request: Request,
    run_id: UUID
):
    """
    Get workflow run status for polling.
    Returns run details, steps, and summary.
    Supports ETag/Last-Modified for efficient polling.
    """
    import hashlib
    from fastapi.responses import JSONResponse, Response
    
    user_id = request.state.user_id
    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    logger.info(f"[GET RUN] Querying run_id={run_id}, user_id={user_id}, org_id={org_id}")

    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        # Get run with org_id filter
        logger.info(f"[GET RUN] Executing SELECT with RLS context for user_id={user_id}, org_id={org_id}")

        run = await conn.fetchrow("""
            SELECT id, workflow_id, status, summary, error,
                   started_at, completed_at, created_at, updated_at
            FROM workflow_runs
            WHERE id = $1 AND org_id = $2
        """, run_id, org_id)

        logger.info(f"[GET RUN] Query result: {'Found' if run else 'Not found'}")

        if not run:
            # Additional diagnostic query
            count_any = await conn.fetchval("SELECT COUNT(*) FROM workflow_runs WHERE id = $1", run_id)
            logger.warning(f"[GET RUN] Row with id={run_id} exists without user filter: {count_any > 0}")
            raise HTTPException(404, "Workflow run not found")
            
        # Get steps (RLS via run_id foreign key) 
        steps = await conn.fetch("""
            SELECT node_id, node_type, node_label, status, 
                   started_at, completed_at, execution_order
            FROM workflow_run_steps 
            WHERE run_id = $1
            ORDER BY execution_order
        """, run_id)
    
    # ETag / Last-Modified headers for efficient polling
    etag_src = f"{run['status']}|{run['updated_at']}"
    etag = hashlib.sha256(etag_src.encode()).hexdigest()
    last_modified = run["updated_at"].strftime("%a, %d %b %Y %H:%M:%S GMT") if run["updated_at"] else None
    
    # Check If-None-Match and If-Modified-Since
    inm = request.headers.get("If-None-Match")
    ims = request.headers.get("If-Modified-Since")
    if inm == etag or (ims and last_modified and ims == last_modified):
        return Response(status_code=304)
    
    # Handle JSONB summary which may be already decoded by asyncpg
    summary = run["summary"]
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except Exception:
            summary = None
    
    # Determine poll_hint based on status
    poll_hint = 2000 if run["status"] in ["queued", "running"] else None
    
    payload = {
        "id": str(run["id"]),
        "workflow_id": str(run["workflow_id"]),
        "status": run["status"],
        "started_at": run["started_at"].isoformat() if run["started_at"] else None,
        "completed_at": run["completed_at"].isoformat() if run["completed_at"] else None,
        "updated_at": run["updated_at"].isoformat() if run["updated_at"] else None,
        "summary": summary,
        "error": run["error"],
        "poll_hint": poll_hint,
        "steps": [
            {
                "node_id": s["node_id"],
                "node_type": s["node_type"],
                "node_label": s["node_label"],
                "status": s["status"],
                "started_at": s["started_at"].isoformat() if s["started_at"] else None,
                "completed_at": s["completed_at"].isoformat() if s["completed_at"] else None,
                "order": s["execution_order"]
            }
            for s in steps
        ]
    }
    
    resp = JSONResponse(payload)
    resp.headers["ETag"] = etag
    if last_modified:
        resp.headers["Last-Modified"] = last_modified
    return resp


@router.delete("/workflow-runs/{run_id}")
async def delete_workflow_run(
    request: Request,
    run_id: UUID
) -> Dict[str, str]:
    """
    Delete a workflow run.
    Only the user who owns the run can delete it.
    Properly scoped to the current organization workspace.
    Cascades to workflow_run_steps via foreign key.
    """
    user_id = request.state.user_id
    org_id = get_org_id(request)
    pg = await get_postgres_rls_client()

    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        # Delete will cascade to workflow_run_steps due to foreign key
        result = await conn.execute(
            "DELETE FROM workflow_runs WHERE id = $1 AND org_id = $2",
            run_id, org_id
        )

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Workflow run not found")

    return {"message": "Workflow run deleted successfully"}


@router.get("/download/{filename}")
async def download_workflow_file(
    request: Request,
    filename: str
) -> Response:
    """
    Download a generated workflow file (PDF or PPT).
    Files are stored in /tmp/workflows/ and must be owned by the requesting user.
    """
    from fastapi.responses import FileResponse

    user_id = request.state.user_id

    # Security: Validate filename to prevent directory traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    artifact_storage = get_artifact_storage()
    file_path = await artifact_storage.ensure_local_file("workflows", filename)
    if not file_path:
        raise HTTPException(404, "File not found")

    # Extract run_id from filename (format: workflow_{run_id}_{timestamp}.{ext})
    try:
        parts = filename.split("_")
        if len(parts) < 3 or parts[0] != "workflow":
            raise HTTPException(400, "Invalid filename format")

        run_id = parts[1]

        # Verify user owns this run with org_id check
        org_id = get_org_id(request)
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM workflow_runs WHERE id = $1 AND org_id = $2",
                run_id, org_id
            )

        if not exists:
            raise HTTPException(403, "Access denied to this file")

    except (IndexError, ValueError):
        raise HTTPException(400, "Invalid filename format")

    # Determine media type
    if filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename
    )
