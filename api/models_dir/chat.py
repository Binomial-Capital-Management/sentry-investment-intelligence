from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

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
    agent_mode: Optional[str] = None  # 'auto', 'risk', 'web', 'market', 'filings'
    file_ids: Optional[List[str]] = None
    drive_file_ids: Optional[List[str]] = None

class ChatMessageResponse(BaseModel):
    response: str
    message_id: Optional[str] = None
    session_id: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None
    charts: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
