"""
Pydantic models for the FinFeed Prediction Markets MCP server.

All datetime fields are optional so upstream parsing failures can be handled
gracefully without interrupting execution.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OutcomeInfo(BaseModel):
    """Single outcome within a prediction market."""

    outcome_id: str
    outcome_name: str
    probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    price: Optional[float] = Field(None, ge=0.0)
    volume_24h: Optional[float] = Field(None, ge=0.0)
    additional_properties: Dict[str, Any] = Field(default_factory=dict)


class MarketCatalogEntry(BaseModel):
    """Catalog representation of a market in the FinFeed API."""

    market_id: str
    exchange_id: str
    api_market_id: str
    title: str
    platform: str
    category: Optional[str] = None
    status: str
    close_date: Optional[datetime] = None
    outcome_type: str
    outcomes: List[OutcomeInfo] = Field(default_factory=list)
    liquidity: Optional[float] = Field(None, ge=0.0)
    volume_24h: Optional[float] = Field(None, ge=0.0)
    last_updated: Optional[datetime] = None
    additional_properties: Dict[str, Any] = Field(default_factory=dict)
    quality_score: Optional[float] = Field(None, ge=0.0, le=100.0)


class MarketResolved(BaseModel):
    """Response returned to agents after resolving a market query."""

    market_id: str
    exchange_id: str
    title: str
    platform: str
    outcome_type: str
    outcomes: List[OutcomeInfo] = Field(default_factory=list)
    status: str
    close_date: Optional[datetime] = None
    score: float
    required_params: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    needs_disambiguation: bool = False
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    quality_score: Optional[float] = Field(None, ge=0.0, le=100.0)


class MarketPrices(BaseModel):
    """Snapshot of current prices/probabilities for a market."""

    market_id: str
    outcomes: List[OutcomeInfo] = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    notes: List[str] = Field(default_factory=list)
    quality_score: Optional[float] = Field(None, ge=0.0, le=100.0)


class OHLCVRecord(BaseModel):
    """Single OHLCV record for a market outcome."""

    timestamp: Optional[datetime] = None
    outcome_id: str
    open: Optional[float] = Field(None, ge=0.0)
    high: Optional[float] = Field(None, ge=0.0)
    low: Optional[float] = Field(None, ge=0.0)
    close: Optional[float] = Field(None, ge=0.0)
    volume: Optional[float] = Field(None, ge=0.0)
    additional_properties: Dict[str, Any] = Field(default_factory=dict)


class MarketHistory(BaseModel):
    """Collection of OHLCV records for a market."""

    market_id: str
    period_id: str
    data: List[OHLCVRecord] = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    notes: List[str] = Field(default_factory=list)


class ConsensusProbability(BaseModel):
    """Aggregated probability view across multiple platforms."""

    consensus_probability: float = Field(..., ge=0.0, le=1.0)
    platforms: List[Dict[str, Any]] = Field(default_factory=list)
    disagreement_score: float = Field(..., ge=0.0)
    notes: List[str] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    """Structured error response for tool failures."""

    code: str
    message: str
    retriable: bool
    status: Optional[int] = None
    source: str


class ToolMetadata(BaseModel):
    """Metadata about a single tool exposed by the MCP server."""

    name: str
    description: str
    required_params: List[str] = Field(default_factory=list)
    optional_params: List[str] = Field(default_factory=list)
    notes: str = ""
    examples: List[str] = Field(default_factory=list)


class ToolCatalog(BaseModel):
    """Collection of tool metadata returned by discover_prediction_fields."""

    server: str
    version: str
    tools: List[ToolMetadata] = Field(default_factory=list)


class Period(BaseModel):
    """Supported OHLCV period definition."""

    period_id: Optional[str] = None
    length_seconds: Optional[int] = Field(None, ge=0)
    length_months: Optional[int] = Field(None, ge=0)
    unit_count: Optional[int] = Field(None, ge=0)
    unit_name: Optional[str] = None
    display_name: Optional[str] = None


class Exchange(BaseModel):
    """Metadata describing an exchange/platform."""

    exchange_id: Optional[str] = None
    market_name_institution_description: Optional[str] = None
    website: Optional[str] = None
    additional_properties: Dict[str, Any] = Field(default_factory=dict)


class Orderbook(BaseModel):
    """Current order book snapshot for a market outcome."""

    exchange_id: Optional[str] = None
    market_id: Optional[str] = None
    time_exchange: Optional[datetime] = None
    time_coinapi: Optional[datetime] = None
    asks: Optional[List[Dict[str, Any]]] = None
    bids: Optional[List[Dict[str, Any]]] = None


class Trade(BaseModel):
    """Individual trade record."""

    id: Optional[str] = None
    market_id: Optional[str] = None
    price: Optional[float] = Field(None, ge=0.0)
    quantity: Optional[float] = Field(None, ge=0.0)
    timestamp: Optional[datetime] = None
    outcome: Optional[str] = None
    side: Optional[str] = None


class Quote(BaseModel):
    """Bid/ask quote record."""

    entry_time: Optional[datetime] = None
    recv_time: Optional[datetime] = None
    ask: Optional[float] = Field(None, ge=0.0)
    bid: Optional[float] = Field(None, ge=0.0)
    ask_volume: Optional[float] = Field(None, ge=0.0)
    bid_volume: Optional[float] = Field(None, ge=0.0)


class TradeQuoteLatest(BaseModel):
    """Latest trade and quote pair."""

    trade: Optional[Trade] = None
    quote: Optional[Quote] = None


class TradesAndQuotes(BaseModel):
    """Collection of recent trades and quotes."""

    trades: Optional[List[Trade]] = None
    quotes: Optional[List[Quote]] = None


__all__ = [
    "ConsensusProbability",
    "ErrorEnvelope",
    "Exchange",
    "MarketCatalogEntry",
    "MarketHistory",
    "MarketPrices",
    "MarketResolved",
    "Orderbook",
    "OHLCVRecord",
    "OutcomeInfo",
    "Period",
    "Quote",
    "ToolCatalog",
    "ToolMetadata",
    "Trade",
    "TradeQuoteLatest",
    "TradesAndQuotes",
]
