from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List

class ChatRequest(BaseModel):
    message: str
    portfolio: Optional[Dict[str, Any]] = None
    portfolio_id: Optional[str] = None  # ID of saved portfolio to use
    session_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None
    agent_mode: Optional[str] = None  # 'auto', 'risk', 'web', 'market', 'filings', 'multiples', 'charts'
    file_ids: Optional[List[str]] = None  # Attached file IDs (uploads)
    drive_file_ids: Optional[List[str]] = None  # Google Drive file IDs
    selected_model: Optional[str] = None  # Model override, e.g. 'gpt-5.1', 'litellm/anthropic/claude-sonnet-4-20250514', 'litellm/gemini/gemini-2.5-pro'
    prioritized_tools: Optional[List[str]] = None  # Tools to prioritize/force usage of

class ChatResponse(BaseModel):
    response: str
    version: str = "v6"
    status: str = "success"
    timestamp: str
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None
    charts: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
    extras: Optional[Dict[str, Any]] = None  # For code blocks, generated files, etc.

class TransformRequest(BaseModel):
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    operation: str = "to_table"
    options: Optional[Dict[str, Any]] = None

class ClassifyRequest(BaseModel):
    message: str


class ExportPdfRequest(BaseModel):
    session_id: Optional[str] = None
    message_id: Optional[str] = None  # if provided, export that assistant message
    mode: str = "analysis"  # "analysis" | "chat"
    content: Optional[str] = None  # Direct content for export (frontend can provide this)
    metadata: Optional[Dict[str, Any]] = None  # Charts, sources, etc from frontend
    analysis_data: Optional[Dict[str, Any]] = None  # when mode==analysis; optional override
    logo_path: Optional[str] = None

# Portfolio schemas moved to api/models/portfolio.py to avoid duplication

# --- Chat threading schemas (for /api/chats) ---

class ChatSessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)

class ChatSessionSummary(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ChatMessageCreate(BaseModel):
    message: str
    portfolio_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    agent_mode: Optional[str] = None  # 'auto', 'risk', 'web', 'market', 'filings', 'multiples', 'charts'
    file_ids: Optional[List[str]] = None  # Attached file IDs
    drive_file_ids: Optional[List[str]] = None  # Google Drive file IDs

class ChatMessageResponse(BaseModel):
    response: str
    message_id: Optional[str] = None
    session_id: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None
    charts: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None


# --- Excel Agent schemas (for /v1/excel/*) ---

class ExcelIndexRequest(BaseModel):
    """Full workbook data from Office.js for initial indexing."""
    workbook_data: Dict[str, Any]  # {sheets: {name: {values, formulas}}}
    workbook_hash: str
    workbook_name: str

class ExcelIndexResponse(BaseModel):
    status: str
    workbook_id: Optional[str] = None
    chunk_count: Optional[int] = None
    content_hash: Optional[str] = None
    message: Optional[str] = None

class ExcelDiffRequest(BaseModel):
    workbook_id: str
    current_hash: str

class ExcelDiffResponse(BaseModel):
    stale: bool
    stored_hash: Optional[str] = None
    reason: Optional[str] = None

class ExcelReindexSheetRequest(BaseModel):
    workbook_id: str
    sheet_name: str
    sheet_data: Dict[str, Any]  # {values: [][], formulas: [][]}

class ExcelSearchRequest(BaseModel):
    workbook_id: str
    query: str
    top_k: Optional[int] = None

class ExcelSearchResponse(BaseModel):
    chunks: List[Dict[str, Any]]

class ExcelPlanRequest(BaseModel):
    message: str
    workbook_id: str
    thread_id: Optional[str] = None  # For Postgres chat persistence
    session_id: Optional[str] = None  # Stable key for SQLiteSession (SDK-level memory)
    blueprint: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    portfolio: Optional[Dict[str, Any]] = None
    portfolio_id: Optional[str] = None
    file_ids: Optional[List[str]] = None
    bloomberg: bool = False  # Enable Bloomberg formula tools
    skip_context: bool = False  # Tool-first mode: skip RAG search, agent reads on-demand
    selection: Optional[Dict[str, Any]] = None  # {range, sheet, values, rowCount, colCount}
    edit_approval_mode: str = "accept"  # "ask" = pause for user approval on writes, "accept" = auto-approve

class ExcelValidateRequest(BaseModel):
    step: Dict[str, Any]
    actual: Dict[str, Any]
    workbook_id: str
    attempt: int = 0


# =============================================================================
# Excel Workbook Chat Models
# =============================================================================

class ExcelChatThreadCreate(BaseModel):
    workbook_id: str
    title: Optional[str] = None
    model: Optional[str] = None

class ExcelChatThreadSummary(BaseModel):
    id: str
    workbook_id: str
    title: Optional[str] = None
    model: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: Optional[int] = 0

class ExcelChatMessageCreate(BaseModel):
    role: str  # user | assistant | system | plan
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ExcelChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

class ExcelChatBulkSave(BaseModel):
    """Save an entire chat history at once (for the add-in)."""
    workbook_id: str
    title: Optional[str] = None
    model: Optional[str] = None
    messages: List[ExcelChatMessageCreate]

class ExcelChatBulkDeleteRequest(BaseModel):
    thread_ids: List[str]


class ExcelPlanSupplementRequest(BaseModel):
    """Request to supplement an in-progress plan with additional data."""
    workbook_id: str
    message: str
    data: Dict[str, Any]  # Supplemental data from surgical reads


class ExcelReadResponseBody(BaseModel):
    """Response from frontend after reading a range requested by excel_read_range."""
    read_id: str
    success: bool
    data: Optional[Dict[str, Any]] = None  # {values: [[]], formulas: [[]]}
    error: Optional[str] = None

class ExcelApprovalResponseBody(BaseModel):
    """Response from frontend after user approves/denies a write operation."""
    approval_id: str
    approved: bool
