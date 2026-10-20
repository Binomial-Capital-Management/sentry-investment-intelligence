"""
User Lists Models (Tracker Lists + Screeners)
Following CODING_RULES.md: KISS, minimal validation
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


class UserListCreate(BaseModel):
    """Create new tracker list or screener"""
    name: str = Field(..., min_length=1, max_length=255)
    type: Literal["tracker", "screener"]

    # For tracker lists: manual tickers
    tickers: Optional[List[str]] = None

    # For screeners: FMP filter parameters
    screener_filters: Optional[Dict[str, Any]] = None

    @validator('tickers')
    def validate_tracker_tickers(cls, v, values):
        """Trackers must have at least one ticker"""
        if values.get('type') == 'tracker':
            if not v or len(v) == 0:
                raise ValueError("Tracker lists must have at least one ticker")
        return v

    @validator('screener_filters')
    def validate_screener_filters(cls, v, values):
        """Screeners must have filters"""
        if values.get('type') == 'screener':
            if not v or len(v) == 0:
                raise ValueError("Screeners must have filter parameters")
        return v


class UserListUpdate(BaseModel):
    """Update existing list"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tickers: Optional[List[str]] = None
    screener_filters: Optional[Dict[str, Any]] = None


class UserListResponse(BaseModel):
    """Response model for user lists"""
    id: UUID
    user_id: str
    name: str
    type: Literal["tracker", "screener"]
    tickers: Optional[List[str]]
    screener_filters: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListsListResponse(BaseModel):
    """Response for listing multiple lists"""
    lists: List[UserListResponse]
    total: int
