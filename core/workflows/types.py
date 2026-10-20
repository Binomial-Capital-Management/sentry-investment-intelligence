"""
Workflow Type Definitions - Simplified
Status: Production
Created: September 2025
Updated: October 2025 - Simplified to 3 node types

PURPOSE: Pydantic models for simplified workflow structure.
Sequential agent chaining: Input → Agent(s) → Output
NO HARDCODING - all enums and types are extensible.
"""

from typing import Dict, List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from uuid import UUID
from enum import Enum


# ===== ENUMS =====

class InputNodeType(str, Enum):
    """Types of input nodes that start a workflow"""
    PORTFOLIO = "portfolio"
    UPLOADED_FILE = "uploaded_file"
    EXTERNAL_DATA = "external_data"
    PROMPT = "prompt"


class AgentNodeType(str, Enum):
    """Available AI agents for processing"""
    GENERALIST = "generalist"
    RISK_SPECIALIST = "risk_specialist"
    DOCUMENT_ANALYST = "document_analyst"
    COMPARABLE_COMPANIES = "comparable_companies"
    CHART_ANALYST = "chart_analyst"
    QUANT_CODING = "quant_coding"
    ALTERNATIVES_CODING = "alternatives_coding"
    INSTITUTIONAL_ACTIVITY = "institutional_activity"
    DCF_AGENT = "dcf_agent"
    OPTIONS_CODING = "options_coding"
    FUNDS_PRODUCTS_ANALYST = "funds_products_analyst"
    PREDICTION_MARKETS_ANALYST = "prediction_markets_analyst"


class OutputNodeType(str, Enum):
    """Types of output formatting"""
    TEXT = "text"
    PDF = "pdf"
    PRESENTATION = "presentation"


class WorkflowStatus(str, Enum):
    """Workflow lifecycle states"""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    """Workflow run execution states"""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    # Keep old values for compatibility
    PENDING = "pending"  # Maps to QUEUED


class StepStatus(str, Enum):
    """Individual step execution states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ===== SIMPLIFIED NODE MODELS =====

class InputNode(BaseModel):
    """Input node - starts the workflow with data"""
    id: str
    type: InputNodeType

    # Type-specific fields (only one should be set)
    portfolio_id: Optional[str] = None
    file_id: Optional[str] = None
    prompt_text: Optional[str] = None
    external_source: Optional[str] = None  # 'google_drive' or 'onedrive' for external_data type

    # Removed validators - configuration is validated at execution time in WorkflowEngine
    # Validators here prevent loading workflows that haven't been configured yet


class AgentNode(BaseModel):
    """Agent node - processes data sequentially"""
    id: str
    agent_type: AgentNodeType
    custom_prompt: str  # Can use {input}, {previous_output} template variables

    @validator('custom_prompt')
    def validate_prompt(cls, v):
        if not v or not v.strip():
            raise ValueError("custom_prompt cannot be empty")
        return v.strip()


class OutputNode(BaseModel):
    """Output node - formats final result"""
    id: str
    type: OutputNodeType
    title: Optional[str] = None
    include_charts: bool = True


class SimplifiedWorkflow(BaseModel):
    """Complete workflow: 1 input → N agents → 1 output"""
    input_node: InputNode
    agent_nodes: List[AgentNode]
    output_node: OutputNode

    @validator('agent_nodes')
    def validate_agents(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Must have at least 1 agent node")
        return v


# ===== API REQUEST/RESPONSE MODELS =====

class WorkflowCreate(BaseModel):
    """Request model for creating a workflow - supports both formats"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    # Simplified format (preferred)
    simplified_workflow: Optional[SimplifiedWorkflow] = None

    # Legacy format (for backward compatibility - will be removed)
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    configuration: Optional[Dict[str, Any]] = None

    status: WorkflowStatus = WorkflowStatus.DRAFT

    @validator('name')
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Workflow name cannot be empty')
        return v.strip()

    @validator('simplified_workflow')
    def validate_workflow_format(cls, v, values):
        # Must provide either simplified_workflow OR (nodes + edges)
        if not v and not values.get('nodes'):
            raise ValueError('Must provide either simplified_workflow or nodes/edges')
        return v


class WorkflowUpdate(BaseModel):
    """Request model for updating a workflow"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    # Simplified format (preferred)
    simplified_workflow: Optional[SimplifiedWorkflow] = None

    # Legacy format (for backward compatibility)
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    configuration: Optional[Dict[str, Any]] = None

    status: Optional[WorkflowStatus] = None
    version: Optional[int] = None  # For optimistic locking


class WorkflowResponse(BaseModel):
    """Response model for workflow data - supports both formats"""
    id: UUID
    user_id: str
    name: str
    description: Optional[str]

    # Simplified format (if workflow uses new structure)
    simplified_workflow: Optional[SimplifiedWorkflow] = None

    # Legacy format (for backward compatibility)
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    configuration: Optional[Dict[str, Any]] = None

    status: WorkflowStatus
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None  # Last execution time

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    """Response for listing workflows"""
    workflows: List[WorkflowResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ===== WORKFLOW RUN MODELS =====

class WorkflowRunCreate(BaseModel):
    """Request to start a workflow run"""
    workflow_id: UUID
    input_data: Dict[str, Any] = Field(default_factory=dict)  # Optional override for input node
    configuration: Dict[str, Any] = Field(default_factory=dict)  # Runtime config overrides


class WorkflowRunResponse(BaseModel):
    """Response for workflow run data"""
    id: UUID
    workflow_id: UUID
    user_id: str
    status: RunStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    configuration: Dict[str, Any]
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class WorkflowRunStepResponse(BaseModel):
    """Response for individual step execution"""
    id: UUID
    run_id: UUID
    node_id: str
    node_type: str  # Agent type name
    node_label: Optional[str]  # Agent display name
    status: StepStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_order: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ===== VALIDATION MODELS =====

class WorkflowValidationRequest(BaseModel):
    """Request to validate a workflow without saving"""
    # Simplified format (preferred)
    simplified_workflow: Optional[SimplifiedWorkflow] = None

    # Legacy format (for backward compatibility)
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    configuration: Optional[Dict[str, Any]] = None

    @validator('simplified_workflow')
    def validate_format(cls, v, values):
        if not v and not values.get('nodes'):
            raise ValueError('Must provide either simplified_workflow or nodes/edges')
        return v


class WorkflowValidationResponse(BaseModel):
    """Response from workflow validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Simplified validation results
    agent_count: int = 0
    unknown_agents: List[str] = Field(default_factory=list)
