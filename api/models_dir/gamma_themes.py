"""
Gamma Theme Models

Pydantic schemas for Gamma visual theme management.
- 12 system-wide default themes (read-only)
- Up to 4 user custom themes (writable)

Database tables: gamma_themes, user_custom_themes
"""
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


class GammaTheme(BaseModel):
    """
    System-wide default Gamma theme (read-only).

    These are the 12 pre-configured visual themes available to all users.
    Users cannot create, modify, or delete system themes.
    """
    id: int = Field(..., description="System theme ID (auto-increment)")
    name: str = Field(..., description="Theme name (e.g., 'Galilee', 'Alpine')")
    gamma_theme_id: str = Field(..., description="Actual Gamma platform theme ID")
    color_description: str = Field(
        ...,
        description="Human-readable color palette (e.g., 'Olive, Sage, Ivory')"
    )
    created_at: datetime = Field(..., description="Theme creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Galilee",
                "gamma_theme_id": "actual_gamma_id_here",
                "color_description": "Olive, Sage, Ivory",
                "created_at": "2025-01-15T10:30:00Z"
            }
        }


class UserCustomTheme(BaseModel):
    """
    User-created custom Gamma theme.

    Users can create up to 4 custom themes by providing:
    - A unique name (within their account)
    - A Gamma platform theme ID

    Custom themes don't include color descriptions - user manages visual config on Gamma.
    """
    id: int = Field(..., description="Custom theme ID (auto-increment)")
    user_id: str = Field(..., description="Clerk user ID")
    name: str = Field(..., description="User-defined theme name")
    gamma_theme_id: str = Field(..., description="Actual Gamma platform theme ID")
    created_at: datetime = Field(..., description="Theme creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @validator('name')
    def validate_name(cls, v):
        """Validate theme name - must be non-empty after trimming."""
        v = v.strip()
        if not v:
            raise ValueError("Theme name cannot be empty")
        if len(v) > 50:
            raise ValueError("Theme name must be 50 characters or less")
        return v

    @validator('gamma_theme_id')
    def validate_gamma_theme_id(cls, v):
        """Validate Gamma theme ID - must be non-empty."""
        v = v.strip()
        if not v:
            raise ValueError("Gamma theme ID cannot be empty")
        if len(v) > 100:
            raise ValueError("Gamma theme ID must be 100 characters or less")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": "user_2abc123def",
                "name": "My Corporate Theme",
                "gamma_theme_id": "custom_gamma_id_xyz",
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:00Z"
            }
        }


# ===== Request Models =====

class UserCustomThemeCreateRequest(BaseModel):
    """Request model for POST /api/gamma-themes/custom"""
    name: str = Field(
        ...,
        description="User-defined theme name (unique per user)",
        min_length=1,
        max_length=50
    )
    gamma_theme_id: str = Field(
        ...,
        description="Gamma platform theme ID",
        min_length=1,
        max_length=100
    )

    @validator('name')
    def validate_name(cls, v):
        """Validate and normalize theme name."""
        v = v.strip()
        if not v:
            raise ValueError("Theme name cannot be empty")
        return v

    @validator('gamma_theme_id')
    def validate_gamma_theme_id(cls, v):
        """Validate and normalize Gamma theme ID."""
        v = v.strip()
        if not v:
            raise ValueError("Gamma theme ID cannot be empty")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Corporate Theme",
                "gamma_theme_id": "custom_gamma_id_xyz"
            }
        }


class UserCustomThemeUpdateRequest(BaseModel):
    """Request model for PUT /api/gamma-themes/custom/{theme_id}"""
    name: Optional[str] = Field(
        None,
        description="New theme name (if renaming)",
        min_length=1,
        max_length=50
    )
    gamma_theme_id: Optional[str] = Field(
        None,
        description="New Gamma platform theme ID (if changing)",
        min_length=1,
        max_length=100
    )

    @validator('name')
    def validate_name(cls, v):
        """Validate new theme name if provided."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Theme name cannot be empty")
        return v

    @validator('gamma_theme_id')
    def validate_gamma_theme_id(cls, v):
        """Validate new Gamma theme ID if provided."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Gamma theme ID cannot be empty")
        return v


# ===== Response Models =====

class GammaThemeListResponse(BaseModel):
    """Response model for GET /api/gamma-themes/default"""
    themes: List[GammaTheme] = Field(..., description="List of 12 default themes")
    count: int = Field(..., description="Total number of default themes (should be 12)")
    message: str = "Default Gamma themes retrieved successfully"


class UserCustomThemeListResponse(BaseModel):
    """Response model for GET /api/gamma-themes/custom"""
    themes: List[UserCustomTheme] = Field(..., description="User's custom themes (0-4)")
    count: int = Field(..., description="Number of custom themes (max 4)")
    remaining_slots: int = Field(
        ...,
        description="Number of remaining custom theme slots (4 - count)"
    )
    message: str = "Custom themes retrieved successfully"


class CombinedThemesResponse(BaseModel):
    """
    Response model for GET /api/gamma-themes/all

    Returns both default and custom themes in a single response.
    Useful for populating theme selection dropdowns.
    """
    default_themes: List[GammaTheme] = Field(..., description="12 system default themes")
    custom_themes: List[UserCustomTheme] = Field(..., description="User's custom themes (0-4)")
    total_count: int = Field(..., description="Total themes available (12-16)")
    can_add_custom: bool = Field(
        ...,
        description="Whether user can add more custom themes (count < 4)"
    )
    message: str = "All themes retrieved successfully"


class UserCustomThemeResponse(BaseModel):
    """Response model for single custom theme operations (POST, PUT, DELETE)"""
    theme: Optional[UserCustomTheme] = Field(
        None,
        description="The created/updated theme (null for DELETE)"
    )
    message: str = "Operation successful"
    remaining_slots: Optional[int] = Field(
        None,
        description="Remaining custom theme slots after operation"
    )


class ErrorResponse(BaseModel):
    """Standard error response for theme operations"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
