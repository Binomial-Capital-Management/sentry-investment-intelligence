"""
Memory Notebook Pydantic Models

Request/response models for the Memory Notebook feature.
See docs/memory-notebook-feature-spec.md for full specification.
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Literal, Optional, Any, Union
from datetime import datetime
from uuid import UUID


# =============================================================================
# Enums as Literals (for OpenAPI schema generation)
# =============================================================================

SectionType = Literal['entities', 'decisions', 'preferences', 'context', 'general']
ReferenceType = Literal['text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table', 'dataset', 'web', 'sec_filing', 'transcript']
SourceType = Literal['user', 'ai', 'tool']
PressureLevel = Literal['low', 'medium', 'high', 'critical']


# =============================================================================
# Memory Note Models
# =============================================================================

class MemoryNoteCreate(BaseModel):
    """Request model for creating a memory note."""
    
    content: str = Field(
        ..., 
        min_length=1, 
        max_length=50000,
        description="The note content to remember"
    )
    section: SectionType = Field(
        default='general',
        description="Category for organization"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Injection priority (1-10, higher = appears earlier in context)"
    )
    source: SourceType = Field(
        default='user',
        description="Who created this note"
    )
    source_message_id: Optional[str] = Field(
        None,
        description="UUID of the message that triggered this note"
    )
    reference_type: ReferenceType = Field(
        default='text',
        description="Type of content being referenced"
    )
    reference_id: Optional[str] = Field(
        None,
        description="UUID of the referenced object (file, portfolio, chart, etc.)"
    )
    reference_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context (offsets for excerpts, filenames, etc.)"
    )

    @validator('source_message_id', 'reference_id', pre=True)
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string if needed."""
        if isinstance(v, UUID):
            return str(v)
        return v


class MemoryNoteUpdate(BaseModel):
    """Request model for updating a memory note (partial update)."""
    
    content: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50000,
        description="Updated note content"
    )
    section: Optional[SectionType] = Field(
        None,
        description="Updated category"
    )
    priority: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Updated priority"
    )
    summary: Optional[str] = Field(
        None,
        max_length=500,
        description="AI-generated summary (optional)"
    )
    reference_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated reference metadata"
    )


class MemoryNoteResponse(BaseModel):
    """Response model for a single memory note."""
    
    id: str
    session_id: str
    section: str
    content: str
    summary: Optional[str] = None
    reference_type: str
    reference_id: Optional[str] = None
    reference_metadata: Optional[Dict[str, Any]] = None
    source: str
    source_message_id: Optional[str] = None
    priority: int
    is_chunked: bool = Field(
        default=False,
        description="True if this note has been indexed for semantic retrieval"
    )
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @validator('id', 'session_id', 'reference_id', 'source_message_id', pre=True)
    def convert_uuid(cls, v):
        """Convert UUID to string if needed."""
        if isinstance(v, UUID):
            return str(v)
        return v

    @validator('created_at', 'updated_at', pre=True)
    def convert_datetime(cls, v):
        """Convert datetime to ISO string if needed."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    class Config:
        from_attributes = True


class MemoryNotebookResponse(BaseModel):
    """Response model for all notes in a session."""
    
    session_id: str
    notes: List[MemoryNoteResponse]
    total_count: int
    sections: List[str] = Field(
        default_factory=list,
        description="List of sections that have notes"
    )
    
    @validator('session_id', pre=True)
    def convert_session_id(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


# =============================================================================
# Token Stats Models (Context Window Visibility)
# =============================================================================

class ContextTokenStats(BaseModel):
    """Token usage breakdown for context window visibility.
    
    Provides full transparency on how the context window is being used,
    built on existing utilities in core/ai/utils/context_manager.py.
    """
    
    # Provider info
    provider: str = Field(description="LLM provider (openai, anthropic, google, etc.)")
    model: str = Field(description="Model identifier")
    context_limit: int = Field(description="Provider's maximum context window in tokens")
    
    # Breakdown by layer
    memory_notebook_tokens: int = Field(
        description="Tokens used by pinned memory notes (never compacted)"
    )
    compaction_summary_tokens: int = Field(
        description="Tokens used by AI-generated summary of trimmed messages"
    )
    message_history_tokens: int = Field(
        description="Tokens used by recent message history"
    )
    system_prompt_tokens: int = Field(
        description="Tokens used by system instructions"
    )
    
    # Computed totals
    total_used: int = Field(description="Sum of all token usage")
    remaining: int = Field(description="Tokens available (context_limit - total_used)")
    usage_percent: float = Field(description="Percentage of context window used")
    
    # Pressure indicator
    pressure_level: PressureLevel = Field(
        description="Context pressure: low (<50%), medium (50-75%), high (75-90%), critical (>90%)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "openai",
                "model": "gpt-5",
                "context_limit": 300000,
                "memory_notebook_tokens": 2450,
                "compaction_summary_tokens": 1200,
                "message_history_tokens": 18350,
                "system_prompt_tokens": 3000,
                "total_used": 25000,
                "remaining": 275000,
                "usage_percent": 8.3,
                "pressure_level": "low"
            }
        }


# =============================================================================
# Bulk Operations Models
# =============================================================================

class BulkDeleteRequest(BaseModel):
    """Request model for bulk deletion of notes."""
    
    note_ids: List[str] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of note IDs to delete"
    )


class BulkDeleteResponse(BaseModel):
    """Response model for bulk deletion."""
    
    deleted_count: int
    failed_ids: List[str] = Field(default_factory=list)


# =============================================================================
# Message Excerpt Models (for highlight-and-pin feature)
# =============================================================================

class MessageExcerptCreate(BaseModel):
    """Request model for pinning a highlighted message excerpt."""
    
    message_id: str = Field(description="UUID of the source message")
    start_offset: int = Field(ge=0, description="Character offset where selection starts")
    end_offset: int = Field(ge=0, description="Character offset where selection ends")
    section: SectionType = Field(default='context')
    priority: int = Field(default=5, ge=1, le=10)
    
    @validator('end_offset')
    def validate_offsets(cls, v, values):
        """Ensure end_offset > start_offset."""
        if 'start_offset' in values and v <= values['start_offset']:
            raise ValueError('end_offset must be greater than start_offset')
        return v


# =============================================================================
# Reference Attachment Models
# =============================================================================

class FileReferenceCreate(BaseModel):
    """Request model for attaching a file reference to memory."""
    
    file_id: str = Field(description="UUID of the file")
    note: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="What to remember about this file"
    )
    section: SectionType = Field(default='context')
    priority: int = Field(default=5, ge=1, le=10)


class PortfolioReferenceCreate(BaseModel):
    """Request model for attaching a portfolio reference to memory."""
    
    portfolio_id: str = Field(description="UUID of the portfolio")
    note: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="What to remember about this portfolio"
    )
    section: SectionType = Field(default='entities')
    priority: int = Field(default=5, ge=1, le=10)


class ChartReferenceCreate(BaseModel):
    """Request model for attaching a chart reference to memory."""
    
    chart_config: Dict[str, Any] = Field(
        description="Chart configuration/spec that was generated"
    )
    note: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="What to remember about this chart"
    )
    data_summary: Optional[str] = Field(
        None,
        max_length=500,
        description="Brief summary of the data shown"
    )
    section: SectionType = Field(default='context')
    priority: int = Field(default=5, ge=1, le=10)

