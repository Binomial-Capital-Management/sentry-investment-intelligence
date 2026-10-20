"""
Ticker Search API - Fuzzy search using local ticker_universe database
Following CODING_RULES.md: no hardcoding, use pg_trgm for fuzzy matching
"""
import logging
from fastapi import APIRouter, Query, HTTPException
from typing import List

from api.models_dir.ticker_search import TickerSearchResult, TickerUniverseResponse
from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ticker-search", tags=["ticker-search"])


@router.get("", response_model=List[TickerSearchResult])
async def search_tickers(
    q: str = Query(..., min_length=1, max_length=50, description="Search query")
):
    """
    Fuzzy search for stock tickers using local database with pg_trgm.

    Searches both symbol and company name fields.
    Returns top 15 matches ranked by similarity score and market cap.

    Args:
        q: Search query (ticker symbol or company name fragment)

    Returns:
        List of matching tickers with symbol, name, and exchange
    """
    try:
        pg = await get_postgres_rls_client()

        # Fuzzy search query using pg_trgm similarity + ILIKE for exact prefix matches
        # Prioritize: exact symbol match > symbol prefix > name similarity
        query = """
            SELECT
                symbol,
                name,
                exchange_short as exchange,
                CASE
                    WHEN UPPER(symbol) = UPPER($1) THEN 1000
                    WHEN UPPER(symbol) LIKE UPPER($1) || '%' THEN 500
                    ELSE (similarity(name, $1) + similarity(symbol, $1)) * 100
                END as score
            FROM ticker_universe
            WHERE
                is_actively_trading = true
                AND (
                    symbol ILIKE $2
                    OR name ILIKE $2
                    OR similarity(name, $1) > 0.1
                    OR similarity(symbol, $1) > 0.1
                )
            ORDER BY score DESC
            LIMIT 15
        """

        search_pattern = f"%{q}%"

        async with pg.pool.acquire() as conn:
            rows = await conn.fetch(query, q, search_pattern)

        return [
            TickerSearchResult(
                symbol=r['symbol'],
                name=r['name'],
                exchange=r['exchange'] or ''
            )
            for r in rows
        ]

    except Exception as e:
        logger.error(f"Error searching tickers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search tickers")


@router.get("/universe", response_model=TickerUniverseResponse)
async def get_ticker_universe():
    """Return all actively-trading tickers for client-side search."""
    try:
        pg = await get_postgres_rls_client()

        query = """
            SELECT symbol, name, exchange_short as exchange
            FROM ticker_universe
            WHERE is_actively_trading = true
            ORDER BY symbol
        """

        async with pg.pool.acquire() as conn:
            rows = await conn.fetch(query)

        tickers = [
            TickerSearchResult(
                symbol=r['symbol'],
                name=r['name'],
                exchange=r['exchange'] or ''
            )
            for r in rows
        ]

        return TickerUniverseResponse(tickers=tickers, count=len(tickers))

    except Exception as e:
        logger.error(f"Error fetching ticker universe: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch ticker universe")


@router.get("/details")
async def get_ticker_details(
    symbols: str = Query(..., description="Comma-separated list of ticker symbols")
):
    """
    Get detailed information for multiple ticker symbols.

    Args:
        symbols: Comma-separated ticker symbols (e.g., "AAPL,MSFT,GOOGL")

    Returns:
        Dictionary mapping symbols to their details (name, sector, industry, description)
    """
    try:
        pg = await get_postgres_rls_client()

        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]

        if not symbol_list:
            return {}

        query = """
            SELECT
                symbol,
                name,
                sector,
                industry,
                description,
                exchange_short as exchange
            FROM ticker_universe
            WHERE symbol = ANY($1)
        """

        async with pg.pool.acquire() as conn:
            rows = await conn.fetch(query, symbol_list)

        return {
            r['symbol']: {
                'name': r['name'],
                'sector': r['sector'],
                'industry': r['industry'],
                'description': r['description'],
                'exchange': r['exchange']
            }
            for r in rows
        }

    except Exception as e:
        logger.error(f"Error fetching ticker details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch ticker details")
