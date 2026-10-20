"""
Export Settings Models

Pydantic schemas for Gamma API export customization settings.
Settings are stored in PostgreSQL with RLS (user_export_settings table).
Supports multiple named export styles (presets) per user.
"""
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


class ExportSettings(BaseModel):
    """
    User's export customization settings for Gamma API.

    All fields are optional - defaults from gamma_client.py will be used when not set.
    """

    # Custom prompt override
    custom_prompt: Optional[str] = Field(
        None,
        description="Custom prompt to override default institutional prompt",
        max_length=5000
    )

    # Theme configuration
    theme_id: Optional[str] = Field(
        None,
        description="Gamma theme ID (e.g., 'r1dl0op2da2dczn')",
        max_length=100
    )

    # Logo configuration
    logo_source: Literal["themeLogo", "custom", "none"] = Field(
        "themeLogo",
        description="Logo source: themeLogo (from theme), custom (URL), or none (disabled)"
    )
    logo_file_id: Optional[str] = Field(
        None,
        description="File ID from uploads table (when logo_source='custom')"
    )
    logo_url: Optional[str] = Field(
        None,
        description="S3 presigned URL for logo (generated from logo_file_id)"
    )
    logo_position: str = Field(
        "topRight",
        description="Logo position: topLeft, topRight, topCenter, bottomLeft, bottomRight, bottomCenter"
    )
    logo_size: str = Field(
        "md",
        description="Logo size: sm, md, lg, xl"
    )

    # Text options
    language: str = Field(
        "en",
        description="Output language code (e.g., 'en', 'es', 'fr')"
    )
    verbosity: Literal["brief", "low", "mid", "high"] = Field(
        "mid",
        description="Content verbosity level"
    )
    tone: str = Field(
        "professional",
        description="Writing tone (e.g., 'professional', 'casual', 'technical')"
    )
    audience: str = Field(
        "expert",
        description="Target audience level (e.g., 'expert', 'general', 'beginner')"
    )

    @validator('logo_position')
    def validate_logo_position(cls, v):
        """Validate logo position against allowed values."""
        allowed = ["topLeft", "topRight", "topCenter", "bottomLeft", "bottomRight", "bottomCenter"]
        if v not in allowed:
            raise ValueError(f"logo_position must be one of: {allowed}")
        return v

    @validator('logo_size')
    def validate_logo_size(cls, v):
        """Validate logo size against allowed values."""
        allowed = ["sm", "md", "lg", "xl"]
        if v not in allowed:
            raise ValueError(f"logo_size must be one of: {allowed}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "custom_prompt": "Create a detailed investment analysis report...",
                "theme_id": "r1dl0op2da2dczn",
                "logo_source": "custom",
                "logo_file_id": "uuid-here",
                "logo_url": "https://s3.amazonaws.com/...",
                "logo_position": "topRight",
                "logo_size": "md",
                "language": "en",
                "verbosity": "mid",
                "tone": "professional",
                "audience": "expert"
            }
        }


class ExportSettingsResponse(BaseModel):
    """Response model for GET /api/user-settings/export"""
    settings: ExportSettings
    message: str = "Export settings retrieved successfully"


class ExportSettingsUpdateRequest(BaseModel):
    """Request model for PUT /api/user-settings/export"""
    settings: ExportSettings


class ExportSettingsUpdateResponse(BaseModel):
    """Response model for PUT /api/user-settings/export"""
    settings: ExportSettings
    message: str = "Export settings updated successfully"


# ===== Export Styles Models (Multi-Style System) =====

class ExportStyle(BaseModel):
    """
    Named export style (preset) with associated settings.
    Users can save multiple styles and switch between them.
    """
    style_name: str = Field(
        ...,
        description="User-defined name for this export style",
        min_length=1,
        max_length=50
    )
    settings: ExportSettings = Field(
        default_factory=ExportSettings,
        description="Export customization settings for this style"
    )
    is_default: bool = Field(
        False,
        description="Whether this is the default style (used when no style selected)"
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Timestamp when style was created"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Timestamp when style was last updated"
    )

    @validator('style_name')
    def validate_style_name(cls, v):
        """Validate style name - alphanumeric, spaces, hyphens, underscores only."""
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError("Style name can only contain letters, numbers, spaces, hyphens, and underscores")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "style_name": "Executive Summary",
                "settings": {
                    "custom_prompt": "Create a 2-page executive summary...",
                    "theme_id": "r1dl0op2da2dczn",
                    "language": "en",
                    "verbosity": "brief",
                    "tone": "executive"
                },
                "is_default": False
            }
        }


class ExportStyleCreateRequest(BaseModel):
    """Request model for POST /api/user-settings/export-styles"""
    style_name: str = Field(
        ...,
        description="Name for the new export style",
        min_length=1,
        max_length=50
    )
    settings: ExportSettings = Field(
        default_factory=ExportSettings,
        description="Export settings for this style"
    )
    is_default: bool = Field(
        False,
        description="Whether to mark this as the default style"
    )

    @validator('style_name')
    def validate_style_name(cls, v):
        """Validate style name."""
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError("Style name can only contain letters, numbers, spaces, hyphens, and underscores")
        return v.strip()


class ExportStyleUpdateRequest(BaseModel):
    """Request model for PUT /api/user-settings/export-styles/{style_name}"""
    settings: ExportSettings = Field(
        ...,
        description="Updated export settings for this style"
    )
    new_style_name: Optional[str] = Field(
        None,
        description="New name for the style (if renaming)",
        min_length=1,
        max_length=50
    )

    @validator('new_style_name')
    def validate_new_style_name(cls, v):
        """Validate new style name if provided."""
        if v is None:
            return v
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError("Style name can only contain letters, numbers, spaces, hyphens, and underscores")
        return v.strip()


class ExportStyleResponse(BaseModel):
    """Response model for single export style operations"""
    style: ExportStyle
    message: str = "Export style operation successful"


class ExportStyleListResponse(BaseModel):
    """Response model for GET /api/user-settings/export-styles"""
    styles: List[ExportStyle]
    count: int
    default_style: Optional[str] = Field(
        None,
        description="Name of the default style (if any)"
    )
    message: str = "Export styles retrieved successfully"


class SetDefaultStyleRequest(BaseModel):
    """Request model for PUT /api/user-settings/export-styles/{style_name}/set-default"""
    # No fields needed - style_name comes from URL path
    pass
