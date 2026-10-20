"""
Pydantic models for broker integration API.

NOTE: Response models are FLEXIBLE to support dynamic field discovery.
IBKR Flex Query allows any fields to be included/omitted, so we don't
hardcode specific fields - we accept whatever comes back.

Following CODING_RULES.md: NO HARDCODING, clean minimal schemas.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class IBKRConnectionRequest(BaseModel):
    """Request to connect IBKR account."""

    flex_token: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="24-digit IBKR Flex Token"
    )
    flex_query_id: str = Field(
        ...,
        min_length=6,
        max_length=10,
        description="IBKR Flex Query ID (6-10 digits)"
    )
    connection_name: str = Field(
        default="My IBKR Account",
        max_length=100,
        description="User-friendly name for this broker connection"
    )
    token_expires_at: Optional[str] = Field(
        None,
        description="Token expiration datetime (ISO format, optional)"
    )

    @validator('flex_token')
    def validate_token_format(cls, v):
        """Ensure Flex Token is 24 digits."""
        if not v.isdigit():
            raise ValueError("Flex Token must be 24 digits")
        return v

    @validator('flex_query_id')
    def validate_query_id_format(cls, v):
        """Ensure Flex Query ID is numeric."""
        if not v.isdigit():
            raise ValueError("Flex Query ID must be numeric")
        return v


class BrokerConnectionResponse(BaseModel):
    """Response after connecting broker account."""

    status: str = Field(..., description="Connection status")
    message: str = Field(..., description="User-friendly message")
    positions: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Positions fetched on connection (if successful)"
    )
    positions_count: Optional[int] = Field(
        None,
        description="Number of positions fetched"
    )
    connection_id: Optional[str] = Field(
        None,
        description="Database connection ID"
    )
    portfolio_id: Optional[str] = Field(
        None,
        description="Auto-created portfolio ID (if applicable)"
    )
    portfolio_name: Optional[str] = Field(
        None,
        description="Name of auto-created portfolio"
    )


class BrokerConnectionStatusResponse(BaseModel):
    """Current status of broker connection."""

    connected: bool = Field(..., description="Whether broker is connected")
    broker_type: str = Field(..., description="Type of broker (e.g., 'ibkr')")
    status: str = Field(..., description="Connection status")
    last_sync_at: Optional[str] = Field(None, description="Last sync timestamp")
    error_message: Optional[str] = Field(None, description="Last error (if any)")
    token_expires_at: Optional[str] = Field(None, description="Token expiration")
