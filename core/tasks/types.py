"""
Typed models for the Tasks backend feature.
Encodes schedule, delivery, node, and persistence contracts used by parser and API layers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


# ===== Core Enums =====


class TaskStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TaskRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskTriggerType(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class TaskFrequency(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class TaskDeliveryPreference(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    SAVE_TO_SENTRY = "saveToSentry"


class TaskNodeType(str, Enum):
    START = "start"
    END = "end"
    AGENT = "agent"
    MERGE = "merge"
    DISTRIBUTE = "distribute"
    PORTFOLIO = "portfolio"
    FILE_UPLOAD = "fileUpload"
    ONEDRIVE = "oneDrive"
    GOOGLE_DRIVE = "googleDrive"
    GRAPH = "graph"
    PDF_REPORT = "pdfReport"
    PPT_PRESENTATION = "pptPresentation"
    WORKBOOK = "workbook"
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    SAVE_TO_SENTRY = "saveToSentry"


class TaskAgentMode(str, Enum):
    AUTO = "auto"
    GENERALIST = "generalist"
    RISK = "risk"
    FILINGS = "filings"
    MULTIPLES = "multiples"
    CHARTS = "charts"
    QUANT = "quant"
    DCF = "dcf"
    ALTERNATIVES = "alternatives"
    INSTITUTIONAL = "institutional"
    PREDICTION_MARKETS = "prediction_markets"
    FUNDS_PRODUCTS = "funds_products"


class TaskOutputType(str, Enum):
    TEXT = "text"
    PDF = "pdf"
    PRESENTATION = "presentation"
    WORKBOOK = "workbook"


class TaskDeliveryChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    SAVE_TO_SENTRY = "saveToSentry"


# ===== Canvas Payload =====


class CanvasPosition(BaseModel):
    x: float
    y: float


class CanvasNode(BaseModel):
    id: str
    type: str
    position: CanvasPosition
    data: Dict[str, Any] = Field(default_factory=dict)


class CanvasEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class CanvasData(BaseModel):
    nodes: List[CanvasNode] = Field(default_factory=list)
    edges: List[CanvasEdge] = Field(default_factory=list)


# ===== Schedule & Delivery =====


class TaskScheduleConfig(BaseModel):
    frequency: TaskFrequency = TaskFrequency.DAILY
    time: Optional[str] = None
    timezone: str = "UTC"
    start_date: Optional[str] = None  # ISO8601 date string
    day_of_month: Optional[int] = None
    days_of_week: Optional[List[int]] = None  # 0 = Sunday
    cron_expression: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("days_of_week", always=True)
    def validate_days(cls, value: Optional[List[int]], values: Dict[str, Any]) -> Optional[List[int]]:
        frequency = values.get("frequency")
        if frequency in {TaskFrequency.WEEKLY, TaskFrequency.BIWEEKLY}:
            if not value:
                raise ValueError("days_of_week required for weekly or biweekly frequency")
        if value:
            invalid = [day for day in value if day < 0 or day > 6]
            if invalid:
                raise ValueError("days_of_week must contain integers between 0 and 6")
        return value

    @validator("day_of_month")
    def validate_day_of_month(cls, value: Optional[int], values: Dict[str, Any]) -> Optional[int]:
        frequency = values.get("frequency")
        if frequency == TaskFrequency.MONTHLY:
            if value is None:
                raise ValueError("day_of_month required for monthly frequency")
        if value is not None and not (1 <= value <= 31):
            raise ValueError("day_of_month must be between 1 and 31")
        return value

    @validator("cron_expression")
    def validate_cron(cls, value: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        frequency = values.get("frequency")
        if frequency == TaskFrequency.CUSTOM and not value:
            raise ValueError("cron_expression required for custom frequency")
        if frequency in {
            TaskFrequency.ONCE,
            TaskFrequency.DAILY,
            TaskFrequency.WEEKDAYS,
            TaskFrequency.WEEKLY,
            TaskFrequency.BIWEEKLY,
            TaskFrequency.MONTHLY,
        } and value:
            # For non-custom frequencies we expect simple time values like "14:30".
            # Store it in the dedicated time field instead of cron_expression.
            raise ValueError("cron_expression is only valid when frequency is custom")
        return value


# ===== Email Lists =====


class EmailList(BaseModel):
    """Reusable email recipient list."""
    id: UUID
    user_id: str
    name: str
    description: Optional[str] = None
    recipients: List[EmailStr]
    created_at: datetime
    updated_at: datetime


class EmailListCreate(BaseModel):
    """Create a new email list."""
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    recipients: List[EmailStr] = Field(min_items=1, max_items=100)


class EmailListUpdate(BaseModel):
    """Update an existing email list."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    recipients: Optional[List[EmailStr]] = Field(None, min_items=1, max_items=100)


# ===== Delivery Configuration =====


class EmailDeliveryConfig(BaseModel):
    recipients: List[EmailStr] = Field(default_factory=list)
    email_list_ids: List[UUID] = Field(default_factory=list)  # Saved email lists
    custom_message: Optional[str] = None
    ai_generated_message: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SlackDeliveryConfig(BaseModel):
    channel: Optional[str] = None
    webhook_url: Optional[str] = None
    connected: bool = False
    custom_message: Optional[str] = None
    ai_generated_message: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeamsDeliveryConfig(BaseModel):
    channel: Optional[str] = None
    webhook_url: Optional[str] = None
    connected: bool = False
    custom_message: Optional[str] = None
    ai_generated_message: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebhookDeliveryConfig(BaseModel):
    url: str
    headers: Dict[str, Any] = Field(default_factory=dict)
    secret: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SaveToSentryConfig(BaseModel):
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskDeliveryConfig(BaseModel):
    primary_channel: Optional[TaskDeliveryPreference] = None
    email: Optional[EmailDeliveryConfig] = None
    slack: Optional[SlackDeliveryConfig] = None
    teams: Optional[TeamsDeliveryConfig] = None
    webhook: Optional[WebhookDeliveryConfig] = None
    save_to_sentry: Optional[SaveToSentryConfig] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ===== Normalised Task Definition =====


class TaskMetadata(BaseModel):
    tags: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    extras: Dict[str, Any] = Field(default_factory=dict)


class TaskInputSpec(BaseModel):
    node_id: str
    type: TaskNodeType
    name: Optional[str] = None
    description: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class TaskAgentSettings(BaseModel):
    reasoning: Optional[str] = None
    response_length: Optional[str] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class TaskAgentStep(BaseModel):
    node_id: str
    mode: TaskAgentMode
    model: str
    tools: List[str] = Field(default_factory=list)
    mcp_servers: List[str] = Field(default_factory=list)
    instructions: Optional[str] = None
    settings: TaskAgentSettings = Field(default_factory=TaskAgentSettings)


class TaskOutputSpec(BaseModel):
    node_id: str
    type: TaskOutputType
    name: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class TaskDeliveryStep(BaseModel):
    node_id: str
    channel: TaskDeliveryChannel
    params: Dict[str, Any] = Field(default_factory=dict)


class TaskAssets(BaseModel):
    files: List[TaskInputSpec] = Field(default_factory=list)
    portfolios: List[TaskInputSpec] = Field(default_factory=list)
    drives: List[TaskInputSpec] = Field(default_factory=list)


class TaskDefinition(BaseModel):
    inputs: List[TaskInputSpec] = Field(default_factory=list)
    agents: List[TaskAgentStep] = Field(default_factory=list)
    outputs: List[TaskOutputSpec] = Field(default_factory=list)
    deliveries: List[TaskDeliveryStep] = Field(default_factory=list)
    assets: TaskAssets = Field(default_factory=TaskAssets)
    metadata: TaskMetadata = Field(default_factory=TaskMetadata)


# ===== Persistence DTOs =====


class TaskRecord(BaseModel):
    id: str
    user_id: str
    org_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    status: TaskStatus
    schedule_config: TaskScheduleConfig
    delivery_config: TaskDeliveryConfig
    metadata: Dict[str, Any] = Field(default_factory=dict)
    canvas_data: CanvasData
    agent_config: TaskDefinition
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @property
    def delivery_preference(self) -> Optional[TaskDeliveryPreference]:
        return self.delivery_config.primary_channel

    @property
    def schedule_frequency(self) -> TaskFrequency:
        return self.schedule_config.frequency


class TaskRunRecord(BaseModel):
    id: str
    task_id: str
    user_id: str
    org_id: Optional[str] = None
    status: TaskRunStatus
    trigger_type: TaskTriggerType
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    delivery_results: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TaskSavedOutputRecord(BaseModel):
    id: str
    task_run_id: str
    task_id: str
    user_id: str
    output: Optional[Any] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    delivery_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TaskRunHistoryItem(BaseModel):
    run: TaskRunRecord
    saved_output: Optional[TaskSavedOutputRecord] = None


class TaskRunListResponse(BaseModel):
    runs: List[TaskRunHistoryItem] = Field(default_factory=list)


class TaskListItem(BaseModel):
    id: str
    name: str
    status: TaskStatus
    frequency: TaskFrequency
    delivery_preference: Optional[TaskDeliveryPreference] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime


class TaskListResponse(BaseModel):
    tasks: List[TaskListItem] = Field(default_factory=list)


__all__ = [
    "CanvasData",
    "CanvasEdge",
    "CanvasNode",
    "CanvasPosition",
    "EmailDeliveryConfig",
    "SaveToSentryConfig",
    "SlackDeliveryConfig",
    "TaskAgentMode",
    "TaskAgentSettings",
    "TaskAgentStep",
    "TaskAssets",
    "TaskDefinition",
    "TaskDeliveryChannel",
    "TaskDeliveryConfig",
    "TaskDeliveryPreference",
    "TaskDeliveryStep",
    "TaskFrequency",
    "TaskInputSpec",
    "TaskListItem",
    "TaskListResponse",
    "TaskMetadata",
    "TaskNodeType",
    "TaskOutputSpec",
    "TaskOutputType",
    "TaskRecord",
    "TaskRunRecord",
    "TaskRunStatus",
    "TaskRunHistoryItem",
    "TaskRunListResponse",
    "TaskScheduleConfig",
    "TaskSavedOutputRecord",
    "TaskStatus",
    "TaskTriggerType",
    "TeamsDeliveryConfig",
    "WebhookDeliveryConfig",
]
