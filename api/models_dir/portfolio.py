from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Union
from datetime import datetime, date
from uuid import UUID

class PurchaseLot(BaseModel):
    """Individual purchase lot (one buy transaction or short position)"""
    quantity: float = Field(..., description="Number of shares in this lot (negative for short positions)")
    purchasePrice: float = Field(..., ge=0, description="Purchase price per share for this lot")
    purchaseDate: Union[str, date] = Field(..., description="Purchase date for this lot")
    lotId: Optional[str] = Field(None, description="Unique identifier for this lot")

    class Config:
        from_attributes = True

class HoldingItem(BaseModel):
    """Aggregated position for a ticker with all purchase lots"""
    ticker: str = Field(..., min_length=1, description="Stock ticker symbol")
    lots: Optional[List[PurchaseLot]] = Field(None, description="All purchase lots for this ticker (new format)")
    currentPrice: Optional[float] = Field(None, ge=0, description="Most recent fetched price")
    priceUpdatedAt: Optional[Union[str, datetime]] = Field(None, description="When price was last updated")

    # IBKR and broker-specific metadata
    metadata: Optional[Dict] = Field(None, description="Broker-specific fields (IBKR: conid, assetCategory, percentOfNAV, etc.)")

    # Legacy fields for backward compatibility
    quantity: Optional[float] = Field(None, description="Legacy: total quantity (old format)")
    purchasePrice: Optional[float] = Field(None, description="Legacy: average purchase price (old format)")
    purchaseDate: Optional[Union[str, date]] = Field(None, description="Legacy: purchase date (old format)")

    @validator('ticker')
    def normalize_ticker(cls, v):
        """Normalize ticker to uppercase"""
        return v.strip().upper()

    class Config:
        from_attributes = True

class PortfolioBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    tickers: List[str] = Field(default_factory=list, description="List of ticker symbols")
    cash_balance: Optional[float] = Field(None, ge=0, description="Cash balance in USD available for trading")
    weights: List[float] = Field(default_factory=list, description="Portfolio weights (must sum to 1.0 for manual portfolios)")
    value: Optional[float] = Field(None, gt=0, description="Portfolio value in USD")
    holdings: Optional[List[HoldingItem]] = Field(None, description="Detailed holdings with purchase history")

    @validator('tickers')
    def normalize_tickers(cls, v):
        """Normalize tickers to uppercase and remove empty strings"""
        # Allow empty arrays for broker portfolios (before first sync)
        if not v:
            return []

        cleaned = [t.strip().upper() for t in v if t and t.strip()]
        return cleaned

    @validator('weights')
    def validate_weights(cls, v, values):
        """Comprehensive weight validation - supports cash allocation and short positions"""
        # Allow empty arrays for broker portfolios (before first sync)
        if not v:
            return []

        # Check array length matches tickers
        if 'tickers' in values:
            if len(v) != len(values['tickers']):
                raise ValueError(
                    f'Number of weights ({len(v)}) must match '
                    f'number of tickers ({len(values["tickers"])})'
                )

        # Allow negative weights for short positions
        # Just validate that weights sum correctly based on cash balance
        weight_sum = sum(v)
        cash_balance = values.get('cash_balance')

        # If cash is present and positive, allow weights < 1.0
        # Use tolerance to handle floating-point precision errors
        if cash_balance is not None and cash_balance > 0:
            if weight_sum > 1.0 + 1e-2:  # Allow 1% tolerance for floating-point errors
                raise ValueError(
                    f'Weights cannot exceed 1.0 when cash is present, but got {weight_sum:.6f}'
                )
        else:
            # No cash: weights must sum to exactly 1.0 (can include negative for shorts)
            if abs(weight_sum - 1.0) > 1e-6:
                raise ValueError(
                    f'Weights must sum to 1.0 when no cash, but got {weight_sum:.6f}'
                )

        return v

class PortfolioCreate(PortfolioBase):
    is_default: bool = False

class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    tickers: Optional[List[str]] = None
    weights: Optional[List[float]] = None
    value: Optional[float] = None
    cash_balance: Optional[float] = None
    holdings: Optional[List[HoldingItem]] = None

class PortfolioResponse(PortfolioBase):
    id: Union[str, UUID]
    is_default: bool = False
    created_at: Optional[Union[str, datetime]] = None
    updated_at: Optional[Union[str, datetime]] = None
    value: Optional[float] = None
    broker_connection_id: Optional[Union[str, UUID]] = None
    source_type: Optional[str] = None
    synced_at: Optional[Union[str, datetime]] = None

    @validator('id', 'broker_connection_id', pre=True)
    def convert_id(cls, v):
        """Convert UUID to string if needed"""
        if isinstance(v, UUID):
            return str(v)
        return v

    @validator('created_at', 'updated_at', 'synced_at', pre=True)
    def convert_datetime(cls, v):
        """Convert datetime to ISO string if needed"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    class Config:
        from_attributes = True


class PortfolioValueHistoryResponse(BaseModel):
    """Response model for portfolio value history snapshots"""
    id: str
    portfolio_id: str
    snapshot_date: str
    total_value: float
    created_at: str
    holdings_snapshot: Optional[List[HoldingItem]] = None
    prices_snapshot: Optional[Dict[str, float]] = None

    class Config:
        from_attributes = True
