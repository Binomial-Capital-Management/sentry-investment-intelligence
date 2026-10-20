"""
Ticker Search Models
"""
from typing import List
from pydantic import BaseModel


class TickerSearchResult(BaseModel):
    """Search result from FMP ticker search"""
    symbol: str
    name: str
    exchange: str


class TickerUniverseResponse(BaseModel):
    """Full ticker universe for client-side search"""
    tickers: List[TickerSearchResult]
    count: int
