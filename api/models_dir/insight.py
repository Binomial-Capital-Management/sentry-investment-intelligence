from pydantic import BaseModel, Field, validator, model_validator
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class PageType(str, Enum):
    """Dashboard page types for insights"""
    MARKETS = "markets"
    CRYPTO = "crypto"
    MACRO = "macro"

class InsightContentBase(BaseModel):
    """Flexible content structure for insights"""
    text: Optional[str] = Field(None, description="Main insight text displayed to user")
    summary: Optional[str] = Field(None, description="Legacy summary field (maps to text)")
    data: Optional[Dict[str, Any]] = Field(None, description="Supporting data (metrics, changes, etc.)")
    source: Optional[str] = Field(None, description="Data source or attribution")

    @model_validator(mode='after')
    def validate_text_or_summary(self):
        """Ensure either text or summary exists, and map summary to text"""
        if self.text is None and self.summary:
            self.text = self.summary
        if self.text is None:
            # Gracefully handle malformed data with a default message
            self.text = "Content unavailable"
        return self

    class Config:
        from_attributes = True

class InsightBase(BaseModel):
    """Base model for user insights"""
    page_type: PageType = Field(..., description="Dashboard page: markets, crypto, or macro")
    region: Optional[str] = Field(None, description="Region for markets page: us, eu, china, korea, japan")
    title: str = Field(..., min_length=1, max_length=500, description="Insight title")
    content: InsightContentBase = Field(..., description="Insight content with text and optional data")
    priority: int = Field(5, ge=1, le=10, description="Priority 1-10 (higher = more important)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for future use")

    @validator('title')
    def validate_title(cls, v):
        """Ensure title is not just whitespace"""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty or whitespace")
        return v.strip()

    @validator('region')
    def validate_region(cls, v, values):
        """Validate region is only set for markets page and has valid value"""
        if v is not None:
            # Region can only be set for markets page
            if values.get('page_type') != PageType.MARKETS:
                raise ValueError("region can only be set for markets page_type")
            # Must be one of the valid market regions
            if v not in ['us', 'eu', 'china', 'korea', 'japan']:
                raise ValueError(f"Invalid region '{v}' for markets page. Must be: us, eu, china, korea, japan")
        return v

    class Config:
        from_attributes = True

class InsightCreate(InsightBase):
    """Model for creating a new insight"""
    user_id: str = Field(..., description="Clerk user ID")
    expires_at: Optional[datetime] = Field(None, description="When insight expires (default 24 hours)")

    class Config:
        from_attributes = True

class InsightUpdate(BaseModel):
    """Model for updating an insight"""
    is_read: Optional[bool] = Field(None, description="Mark insight as read/unread")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Update priority")

    class Config:
        from_attributes = True

class InsightResponse(InsightBase):
    """Model for insight API responses"""
    id: UUID = Field(..., description="Unique insight ID")
    user_id: str = Field(..., description="User ID (for admin purposes)")
    is_read: bool = Field(False, description="Whether user has read this insight")
    generated_at: datetime = Field(..., description="When insight was generated")
    expires_at: datetime = Field(..., description="When insight expires")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

class InsightListResponse(BaseModel):
    """Response model for list of insights"""
    insights: List[InsightResponse] = Field(..., description="List of insights")
    total: int = Field(..., description="Total count")
    page_type: Optional[PageType] = Field(None, description="Filtered page type")

    class Config:
        from_attributes = True

class InsightGenerateRequest(BaseModel):
    """Request model for generating insights"""
    page_type: Optional[PageType] = Field(None, description="Generate for specific page (or all if None)")
    region: Optional[str] = Field(None, description="Generate for specific region (markets page only)")
    force_regenerate: bool = Field(False, description="Force regeneration even if recent insights exist")

    @validator('region')
    def validate_region(cls, v, values):
        """Validate region is only set for markets page"""
        if v is not None:
            if values.get('page_type') != PageType.MARKETS:
                raise ValueError("region can only be specified when page_type is 'markets'")
            if v not in ['us', 'eu', 'china', 'korea', 'japan']:
                raise ValueError(f"Invalid region '{v}'. Must be: us, eu, china, korea, japan")
        return v

    class Config:
        from_attributes = True
