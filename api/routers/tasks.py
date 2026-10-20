"""
Tasks API endpoints.
Provides CRUD, toggle, trigger, and history routes for the Tasks feature.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
import pytz

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from apscheduler.triggers.cron import CronTrigger

from core.tasks.db import TasksRepository
from core.tasks.parser import parse_task_definition, TaskParserError
from core.tasks.types import (
    TaskDefinition,
    TaskDeliveryConfig,
    TaskDeliveryPreference,
    TaskFrequency,
    TaskRunHistoryItem,
    TaskRunListResponse,
    TaskRunRecord,
    TaskRunStatus,
    TaskScheduleConfig,
    TaskStatus,
    TaskTriggerType,
    TaskRecord,
)
from core.tasks.types import EmailDeliveryConfig
from core.tasks.service import TasksService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
tasks_repo = TasksRepository()
logger = logging.getLogger(__name__)


def calculate_next_run(
    frequency: TaskFrequency,
    time_str: Optional[str],
    days_of_week: Optional[List[int]],
    day_of_month: Optional[int],
    start_date: Optional[datetime],
    timezone_str: str = "America/New_York",
    cron_expression: Optional[str] = None,
) -> Optional[datetime]:
    """
    Calculate the next run time for a task based on its schedule.
    Returns datetime in UTC.
    """
    try:
        tz = pytz.timezone(timezone_str)
    except Exception:
        tz = pytz.UTC

    now = datetime.now(tz)

    # Parse time from string (e.g., "02:30 PM" or "14:30")
    if time_str:
        try:
            # Try 12-hour format first
            if "AM" in time_str.upper() or "PM" in time_str.upper():
                time_obj = datetime.strptime(time_str, "%I:%M %p").time()
            else:
                # 24-hour format
                time_obj = datetime.strptime(time_str, "%H:%M").time()
        except Exception:
            # Default to midnight if parsing fails
            time_obj = datetime.strptime("00:00", "%H:%M").time()
    else:
        time_obj = datetime.strptime("00:00", "%H:%M").time()

    if frequency == TaskFrequency.DAILY:
        # Daily: Run at specified time every day
        next_run = tz.normalize(tz.localize(datetime.combine(now.date(), time_obj)))
        if next_run <= now:
            next_run += timedelta(days=1)
            next_run = tz.normalize(next_run)

    elif frequency == TaskFrequency.WEEKDAYS:
        # Weekdays: Next Mon-Fri at the specified time
        next_run = None
        for _ in range(8):
            candidate = now + timedelta(days=_)
            if candidate.weekday() < 5:  # Mon-Fri
                candidate_time = tz.normalize(tz.localize(datetime.combine(candidate.date(), time_obj)))
                if candidate_time > now:
                    next_run = candidate_time
                    break
        if not next_run:
            next_run = tz.normalize(tz.localize(datetime.combine(now.date(), time_obj)) + timedelta(days=1))

    elif frequency == TaskFrequency.WEEKLY:
        # Weekly: Run on specified days of week
        if not days_of_week:
            days_of_week = [now.weekday()]  # Default to current day

        # Find next occurrence of any selected day
        next_run = None
        for _ in range(8):  # Check next 7 days
            candidate = now + timedelta(days=_)
            if candidate.weekday() in days_of_week:
                candidate_time = tz.normalize(tz.localize(datetime.combine(candidate.date(), time_obj)))
                if candidate_time > now:
                    next_run = candidate_time
                    break

        if not next_run:
            # Fallback: next week same day
            next_run = tz.normalize(tz.localize(datetime.combine(now.date(), time_obj)) + timedelta(days=7))

    elif frequency == TaskFrequency.BIWEEKLY:
        # Current implementation matches scheduler fallback: treat as weekly
        if not days_of_week:
            days_of_week = [now.weekday()]

        next_run = None
        for _ in range(15):  # two-week window
            candidate = now + timedelta(days=_)
            if candidate.weekday() in days_of_week:
                candidate_time = tz.normalize(tz.localize(datetime.combine(candidate.date(), time_obj)))
                if candidate_time > now:
                    next_run = candidate_time
                    break

        if not next_run:
            next_run = tz.normalize(tz.localize(datetime.combine(now.date(), time_obj)) + timedelta(days=14))

    elif frequency == TaskFrequency.MONTHLY:
        # Monthly: Run on specified day of month
        if not day_of_month:
            day_of_month = now.day

        # Try current month first
        try:
            next_run = tz.normalize(tz.localize(datetime.combine(now.date().replace(day=day_of_month), time_obj)))
            if next_run <= now:
                # Move to next month
                if now.month == 12:
                    next_run = tz.normalize(tz.localize(datetime.combine(datetime(now.year + 1, 1, day_of_month).date(), time_obj)))
                else:
                    next_run = tz.normalize(tz.localize(datetime.combine(datetime(now.year, now.month + 1, day_of_month).date(), time_obj)))
        except ValueError:
            # Day doesn't exist in month, use last day
            next_run = tz.normalize(tz.localize(datetime.combine(now.date().replace(day=28), time_obj)) + timedelta(days=30))

    elif frequency == TaskFrequency.CUSTOM and cron_expression:
        try:
            trigger = CronTrigger.from_crontab(cron_expression, timezone=tz)
            next_fire = trigger.get_next_fire_time(None, now)
            if next_fire:
                return next_fire.astimezone(pytz.UTC)
        except Exception as exc:
            logger.warning("Failed to compute next run from cron expression '%s': %s", cron_expression, exc)
        return None

    else:
        # Custom/Once fallback: Combine start_date (for date) with time_str (for time)
        if start_date:
            # Extract date from start_date, combine with time from time_str
            target_date = start_date.date() if hasattr(start_date, 'date') else start_date
            next_run = tz.normalize(tz.localize(datetime.combine(target_date, time_obj)))
        else:
            next_run = tz.localize(datetime.combine(now.date(), time_obj)) + timedelta(days=1)

    # Convert to UTC for storage
    return next_run.astimezone(pytz.UTC) if next_run else None
tasks_service = TasksService(tasks_repo)


class TaskCreatePayload(BaseModel):
    name: str
    description: Optional[str] = None
    frequency: TaskFrequency
    timezone: Optional[str] = "UTC"
    time: Optional[str] = None
    cron_expression: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    day_of_month: Optional[int] = None
    start_date: Optional[str] = None
    email: Optional[str] = None
    delivery_preference: Optional[TaskDeliveryPreference] = None
    canvas_data: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.DRAFT


class TaskResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    frequency: str
    timezone: Optional[str]
    time: Optional[str]
    cron_expression: Optional[str]
    days_of_week: Optional[List[int]]
    day_of_month: Optional[int]
    start_date: Optional[str]
    delivery_preference: Optional[TaskDeliveryPreference]
    email: Optional[str]
    status: TaskStatus
    canvas_data: Dict[str, Any]
    agent_config: Dict[str, Any]
    metadata: Dict[str, Any]
    next_run_at: Optional[str]
    last_run_at: Optional[str]
    created_at: str
    updated_at: str


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse] = Field(default_factory=list)


class TaskRunResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    status: TaskRunStatus
    trigger_type: TaskTriggerType
    input_snapshot: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    delivery_results: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_time_ms: Optional[int]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    updated_at: str


def _require_user_id(request: Request) -> str:
    user_id: Optional[str] = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


def _build_schedule_config(payload: TaskCreatePayload) -> TaskScheduleConfig:
    return TaskScheduleConfig(
        frequency=payload.frequency,
        time=payload.time,
        timezone=payload.timezone or "UTC",
        start_date=payload.start_date,
        day_of_month=payload.day_of_month,
        days_of_week=payload.days_of_week,
        cron_expression=payload.cron_expression,
        metadata={},
    )


def _validate_schedule_payload(payload: TaskCreatePayload) -> None:
    """
    Validate schedule semantics against what the frontend sends.
    - ONCE requires start_date
    - CUSTOM requires cron_expression
    """
    if payload.frequency == TaskFrequency.ONCE and not payload.start_date:
        raise HTTPException(
            status_code=400,
            detail="Tasks with 'once' frequency require a start_date"
        )
    if payload.frequency == TaskFrequency.CUSTOM and not payload.cron_expression:
        raise HTTPException(
            status_code=400,
            detail="Tasks with 'custom' frequency require a cron_expression"
        )


def _build_delivery_config(payload: TaskCreatePayload) -> TaskDeliveryConfig:
    config = TaskDeliveryConfig(primary_channel=payload.delivery_preference)
    if payload.email:
        config.email = EmailDeliveryConfig(recipients=[payload.email])
    return config


def _serialize_task(record: TaskRecord) -> TaskResponse:
    schedule = record.schedule_config
    delivery = record.delivery_config
    email = None
    if delivery.email and delivery.email.recipients:
        email = delivery.email.recipients[0]
    return TaskResponse(
        id=record.id,
        name=record.name,
        description=record.description,
        frequency=record.schedule_frequency.value,
        timezone=schedule.timezone,
        time=schedule.time,
        cron_expression=schedule.cron_expression,
        days_of_week=schedule.days_of_week,
        day_of_month=schedule.day_of_month,
        start_date=schedule.start_date,
        delivery_preference=delivery.primary_channel,
        email=email,
        status=record.status,
        canvas_data=record.canvas_data.model_dump(),
        agent_config=record.agent_config.model_dump(),
        metadata=record.metadata,
        next_run_at=record.next_run_at.isoformat() if record.next_run_at else None,
        last_run_at=record.last_run_at.isoformat() if record.last_run_at else None,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


def _serialize_run(run: TaskRunRecord) -> TaskRunResponse:
    return TaskRunResponse(
        id=run.id,
        task_id=run.task_id,
        user_id=run.user_id,
        status=run.status,
        trigger_type=run.trigger_type,
        input_snapshot=run.input_snapshot,
        result=run.result,
        delivery_results=run.delivery_results,
        error_message=run.error_message,
        execution_time_ms=run.execution_time_ms,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


def _parse_definition(canvas_data: Dict[str, Any]) -> TaskDefinition:
    return parse_task_definition(canvas_data)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0)
) -> TaskListResponse:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)
    records = await tasks_repo.list_tasks(user_id, limit=limit, offset=offset, org_id=org_id)
    return TaskListResponse(tasks=[_serialize_task(rec) for rec in records])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(request: Request, payload: TaskCreatePayload) -> TaskResponse:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)

    _validate_schedule_payload(payload)

    try:
        definition = _parse_definition(payload.canvas_data)
    except TaskParserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Create task in database
    schedule_config = _build_schedule_config(payload)

    # Calculate next run time if task is active
    next_run_at = None
    if payload.status == TaskStatus.ACTIVE:
        # Parse start_date string to datetime if provided
        start_date_dt = None
        if payload.start_date:
            try:
                start_date_dt = datetime.fromisoformat(payload.start_date.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Failed to parse start_date '{payload.start_date}': {e}")

        next_run_at = calculate_next_run(
            frequency=payload.frequency,
            time_str=payload.time,
            days_of_week=payload.days_of_week,
            day_of_month=payload.day_of_month,
            start_date=start_date_dt,
            timezone_str=payload.timezone or "America/New_York",
            cron_expression=payload.cron_expression,
        )

    record = await tasks_repo.create_task(
        user_id,
        {
            "name": payload.name,
            "description": payload.description,
            "status": payload.status.value,
            "schedule_config": schedule_config.model_dump(),
            "delivery_config": _build_delivery_config(payload).model_dump(),
            "metadata": payload.metadata,
            "canvas_data": payload.canvas_data,
            "agent_config": definition.model_dump(),
            "next_run_at": next_run_at,
            "last_run_at": None,
        },
        org_id=org_id
    )

    # Register with scheduler if active
    if payload.status == TaskStatus.ACTIVE:
        from api.orchestrator import get_task_scheduler
        get_task_scheduler()._register_task_job(record)

    return _serialize_task(record)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(request: Request, task_id: UUID) -> TaskResponse:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)
    try:
        record = await tasks_repo.get_task(user_id, str(task_id), org_id=org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_task(record)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(request: Request, task_id: UUID, payload: TaskCreatePayload) -> TaskResponse:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)

    _validate_schedule_payload(payload)

    try:
        definition = _parse_definition(payload.canvas_data)
    except TaskParserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Build update data
    schedule_config = _build_schedule_config(payload)

    # Calculate next run time if task is active
    next_run_at = None
    if payload.status == TaskStatus.ACTIVE:
        # Parse start_date string to datetime if provided
        start_date_dt = None
        if payload.start_date:
            try:
                start_date_dt = datetime.fromisoformat(payload.start_date.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Failed to parse start_date '{payload.start_date}': {e}")

        next_run_at = calculate_next_run(
            frequency=payload.frequency,
            time_str=payload.time,
            days_of_week=payload.days_of_week,
            day_of_month=payload.day_of_month,
            start_date=start_date_dt,
            timezone_str=payload.timezone or "America/New_York",
            cron_expression=payload.cron_expression,
        )

    update_data = {
        "name": payload.name,
        "description": payload.description,
        "status": payload.status.value,
        "schedule_config": schedule_config.model_dump(),
        "delivery_config": _build_delivery_config(payload).model_dump(),
        "metadata": payload.metadata,
        "canvas_data": payload.canvas_data,
        "agent_config": definition.model_dump(),
        "next_run_at": next_run_at,
    }

    try:
        record = await tasks_repo.update_task(
            user_id,
            str(task_id),
            update_data,
            org_id=org_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Update scheduler registration
    from api.orchestrator import get_task_scheduler
    scheduler = get_task_scheduler()
    scheduler.unregister_task_job(str(task_id))  # Remove old job
    if payload.status == TaskStatus.ACTIVE:
        scheduler._register_task_job(record)  # Register new job if active

    return _serialize_task(record)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(request: Request, task_id: UUID):
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)

    # CRITICAL: Unregister scheduler job BEFORE deletion
    from api.orchestrator import get_task_scheduler
    scheduler = get_task_scheduler()
    scheduler.unregister_task_job(str(task_id))

    try:
        await tasks_repo.delete_task(user_id, str(task_id), org_id=org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/toggle", response_model=TaskResponse)
async def toggle_task(request: Request, task_id: UUID) -> TaskResponse:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)

    # Get current task to determine new status
    try:
        task = await tasks_repo.get_task(user_id, str(task_id), org_id=org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Validate task can be toggled (only active/paused tasks)
    if task.status not in {TaskStatus.ACTIVE, TaskStatus.PAUSED}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot toggle task with status '{task.status.value}'. Only active/paused tasks can be toggled."
        )

    # Determine new status
    new_status = TaskStatus.ACTIVE if task.status == TaskStatus.PAUSED else TaskStatus.PAUSED

    # Calculate next run time if activating
    next_run_at = None
    if new_status == TaskStatus.ACTIVE:
        schedule_config = task.schedule_config

        # Parse start_date string to datetime if provided
        start_date_dt = None
        if schedule_config.start_date:
            try:
                start_date_dt = datetime.fromisoformat(schedule_config.start_date.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Failed to parse start_date '{schedule_config.start_date}': {e}")

        next_run_at = calculate_next_run(
            frequency=schedule_config.frequency,
            time_str=schedule_config.time,
            days_of_week=schedule_config.days_of_week,
            day_of_month=schedule_config.day_of_month,
            start_date=start_date_dt,
            timezone_str=schedule_config.timezone or "America/New_York",
            cron_expression=schedule_config.cron_expression,
        )

    # Update task status in database
    update_data = {
        "status": new_status.value,
        "next_run_at": next_run_at,
    }

    # Update task
    try:
        record = await tasks_repo.update_task(user_id, str(task_id), update_data, org_id=org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Update scheduler registration
    from api.orchestrator import get_task_scheduler
    scheduler = get_task_scheduler()
    if new_status == TaskStatus.ACTIVE:
        scheduler._register_task_job(record)  # Register job when activating
    else:
        scheduler.unregister_task_job(str(task_id))  # Remove job when pausing

    return _serialize_task(record)


@router.post("/{task_id}/trigger", response_model=TaskRunResponse)
async def trigger_task(request: Request, task_id: UUID, background_tasks: BackgroundTasks) -> TaskRunResponse:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)
    # Ensure task exists and belongs to user
    try:
        task = await tasks_repo.get_task(user_id, str(task_id), org_id=org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    run = await tasks_repo.create_run(str(task_id), user_id, TaskTriggerType.MANUAL, org_id=org_id)
    await tasks_service.trigger_run(task, run, background_tasks)
    return _serialize_run(run)


@router.get("/{task_id}/runs", response_model=TaskRunListResponse)
async def list_task_runs(
    request: Request,
    task_id: UUID,
    limit: int = Query(50, ge=1, le=100),
) -> TaskRunListResponse:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)
    runs = await tasks_repo.list_run_history(user_id, str(task_id), limit, org_id=org_id)
    return TaskRunListResponse(runs=runs)


@router.get("/runs/{run_id}", response_model=TaskRunHistoryItem)
async def get_task_run(
    request: Request,
    run_id: UUID,
) -> TaskRunHistoryItem:
    user_id = _require_user_id(request)
    org_id = getattr(request.state, 'org_id', None)
    try:
        return await tasks_repo.get_run_history_entry(user_id, str(run_id), org_id=org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/artifacts/{category}/{filename}/download")
async def download_artifact(
    request: Request,
    category: str,
    filename: str,
):
    """
    Generate presigned URL for artifact download from S3.
    Redirects to presigned URL or returns 404 if S3 not configured.
    """
    from fastapi.responses import RedirectResponse
    from core.services.artifact_storage import get_artifact_storage

    user_id = _require_user_id(request)
    org_id = getattr(request.state, "org_id", None)

    # Only task artifacts are supported via this route
    if category != "tasks":
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Validate artifact ownership before issuing presigned URL
    owns_artifact = await tasks_repo.find_artifact_by_filename(user_id, filename, org_id=org_id)
    if not owns_artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Get artifact storage instance
    storage = get_artifact_storage()

    # Generate presigned URL (expires in 1 hour)
    presigned_url = storage.generate_presigned_url(
        category=category,
        filename=filename,
        expiration=3600
    )

    if not presigned_url:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found or S3 not configured"
        )

    # Redirect to presigned URL for download
    return RedirectResponse(url=presigned_url)


class ValidateCanvasPayload(BaseModel):
    canvas_data: Dict[str, Any]


class ValidationResult(BaseModel):
    valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    info: List[Dict[str, Any]]
    summary: Dict[str, Any]


@router.post("/validate", response_model=ValidationResult)
async def validate_canvas(
    request: Request,
    payload: ValidateCanvasPayload
) -> ValidationResult:
    """
    Validate task canvas structure and configuration.
    Checks workflow structure, node configs, connections, and flow logic.
    Returns structured validation results with errors, warnings, and suggestions.
    """
    _require_user_id(request)  # Ensure authenticated
    
    from core.tasks.validator import validate_canvas as run_validation
    
    try:
        result = run_validation(payload.canvas_data)
        return ValidationResult(**result)
    except Exception as e:
        logger.exception("Canvas validation failed")
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        ) from e
