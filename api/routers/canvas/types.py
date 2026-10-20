"""
Canvas API Pydantic Schemas

Request and response models for Canvas endpoints.
"""

from pydantic import BaseModel
from typing import Dict, Any, List, Optional


# =============================================================================
# PROCESS SCHEMAS
# =============================================================================

class SaveProcessRequest(BaseModel):
    """Request to save a new Canvas process."""
    tool_id: str
    tickers: List[str] = []
    weights: List[float] = []
    metrics: Dict[str, Any] = {}
    metric_cards: List[Dict[str, Any]] = []  # Generic displayable metrics
    stats_table: List[Dict[str, Any]] = []
    charts: Dict[str, Any] = {}
    name: Optional[str] = None
    object_type: Optional[str] = None  # Object type from registry (equity, portfolio, crypto, etc.)
    hmm_enabled: bool = False
    current_regime: Optional[str] = None
    regime_params: Optional[Dict[str, Any]] = None
    graph_steps: Optional[List[Dict[str, Any]]] = None
    graph_edges: Optional[List[Dict[str, Any]]] = None
    params: Dict[str, Any] = {}  # Original run parameters for re-run
    process_type: str = "tool"  # 'tool' or 'data_workspace'
    config: Optional[Dict[str, Any]] = None  # Config for data_workspace


class UpdateProcessRequest(BaseModel):
    """Request to update process metadata (name only)."""
    name: Optional[str] = None


class FullUpdateProcessRequest(BaseModel):
    """Full update for data workspace - same fields as SaveProcessRequest."""
    name: str
    tickers: List[str] = []
    params: Dict[str, Any] = {}
    config: Optional[Dict[str, Any]] = None


class ApplyUpdateRequest(BaseModel):
    """Request to apply a pending tool re-run to a process."""
    process_id: str
    tool_id: str
    tickers: List[str]
    weights: Optional[List[float]] = None
    params: Optional[Dict[str, Any]] = None
    full_result: Dict[str, Any]


# =============================================================================
# CHAT SCHEMAS
# =============================================================================

class CreateThreadRequest(BaseModel):
    """Request to create a new chat thread."""
    title: Optional[str] = None


class UpdateThreadRequest(BaseModel):
    """Request to update a chat thread (rename or pin/unpin)."""
    title: Optional[str] = None
    pinned: Optional[bool] = None


class ActionResultRequest(BaseModel):
    """Request to report an agent action execution result.
    
    Used by frontend to report success/failure of AI-initiated actions
    back to the backend for the AI feedback loop.
    """
    thread_id: str
    action_id: str
    action_type: str
    symbol: Optional[str] = None
    success: bool
    error: Optional[str] = None
    cancelled: Optional[bool] = False
    data: Optional[Dict[str, Any]] = None


class WorkspaceSnapshotRequest(BaseModel):
    """Request to save a workspace snapshot for chat-workspace binding.
    
    Stores tab configurations (not data) that can be restored when loading
    a chat from history.
    """
    captured_at: str  # ISO timestamp
    tabs: List[Dict[str, Any]]  # WorkspaceTab[] configs
    activeTabId: str


# =============================================================================
# TOOL SCHEMAS
# =============================================================================

class RunToolRequest(BaseModel):
    """Request to run a Canvas tool."""
    tickers: List[str] = []
    weights: Optional[List[float]] = None
    params: Dict[str, Any] = {}
    portfolio_id: Optional[str] = None


class ToolInfo(BaseModel):
    """Tool information for registry."""
    id: str
    name: str
    description: str
    category: str
    params_schema: Dict[str, Any]
    
    class Config:
        extra = "allow"  # Allow additional fields like executor
