"""
Portfolio Value History API
Endpoints for retrieving historical portfolio values and triggering manual snapshots.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import json

from api.models_dir.portfolio import PortfolioValueHistoryResponse
from core.database.postgres_client import get_postgres_rls_client

router = APIRouter(prefix="/portfolio-history", tags=["Portfolio History"])
logger = logging.getLogger(__name__)


def _parse_json_field(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


@router.get("/{portfolio_id}/history", response_model=List[PortfolioValueHistoryResponse])
async def get_portfolio_value_history(
    portfolio_id: str,
    request: Request,
    days: Optional[int] = Query(30, ge=1, le=365, description="Number of days of history to retrieve"),
):
    """
    Get historical portfolio values for charting.
    Returns daily snapshots for the specified number of days.
    """
    try:
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        org_id = getattr(request.state, 'org_id', None)
        pg = await get_postgres_rls_client()

        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # First verify user owns this portfolio
            portfolio = await conn.fetchrow(
                "SELECT id FROM portfolios WHERE id = $1",
                portfolio_id
            )

            if not portfolio:
                logger.error(f"Portfolio {portfolio_id} not found for user {user_id}")
                raise HTTPException(status_code=404, detail="Portfolio not found")

            logger.info(f"Fetching history for portfolio {portfolio_id}, user {user_id}")

            # Get value history
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            rows = await conn.fetch("""
                SELECT
                    id,
                    portfolio_id,
                    snapshot_date,
                    total_value,
                    holdings_snapshot,
                    prices_snapshot,
                    created_at
                FROM portfolio_value_history
                WHERE portfolio_id = $1
                  AND snapshot_date >= $2
                ORDER BY snapshot_date DESC
            """, portfolio_id, cutoff_date)

            # If no historical data, return current portfolio value as single data point
            if not rows:
                logger.info(f"No historical data found, fetching current value for portfolio {portfolio_id}")
                current_portfolio = await conn.fetchrow("""
                    SELECT id, value, updated_at
                    FROM portfolios
                    WHERE id = $1
                """, portfolio_id)

                if current_portfolio and current_portfolio['value']:
                    logger.info(f"Returning current value: ${current_portfolio['value']:,.2f}")
                    return [
                        PortfolioValueHistoryResponse(
                            id=str(current_portfolio['id']),
                            portfolio_id=portfolio_id,
                            snapshot_date=current_portfolio['updated_at'].isoformat(),
                            total_value=float(current_portfolio['value']),
                            created_at=current_portfolio['updated_at'].isoformat(),
                            holdings_snapshot=None,
                            prices_snapshot=None,
                        )
                    ]
                logger.warning(f"Portfolio {portfolio_id} has no value set")
                return []

            return [
                PortfolioValueHistoryResponse(
                    id=str(r['id']),
                    portfolio_id=str(r['portfolio_id']),
                    snapshot_date=r['snapshot_date'].isoformat(),
                    total_value=float(r['total_value']),
                    created_at=r['created_at'].isoformat(),
                    holdings_snapshot=_parse_json_field(r['holdings_snapshot']) if r['holdings_snapshot'] else None,
                    prices_snapshot=_parse_json_field(r['prices_snapshot']) if r['prices_snapshot'] else None,
                )
                for r in rows
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching portfolio history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio history: {str(e)}")


@router.post("/{portfolio_id}/snapshot")
async def create_portfolio_snapshot(
    portfolio_id: str,
    request: Request,
):
    """
    Manually create a portfolio value snapshot.
    Fetches current prices and saves a snapshot to history.
    """
    try:
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        org_id = getattr(request.state, 'org_id', None)
        from core.services.portfolio_scheduler import portfolio_scheduler

        pg = await get_postgres_rls_client()

        # Verify user owns this portfolio
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            portfolio = await conn.fetchrow("""
                SELECT id, user_id, name, tickers, holdings
                FROM portfolios
                WHERE id = $1
            """, portfolio_id)

            if not portfolio:
                raise HTTPException(status_code=404, detail="Portfolio not found")

        # Trigger refresh for this specific portfolio
        # (We'll create a helper method in the scheduler for this)
        await _refresh_single_portfolio(portfolio, org_id)

        return {
            "success": True,
            "message": f"Snapshot created for portfolio {portfolio['name']}",
            "portfolio_id": portfolio_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portfolio snapshot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {str(e)}")


@router.post("/refresh-all")
async def trigger_manual_refresh_all(
    request: Request,
):
    """
    Manually trigger price refresh for all portfolios (admin/testing).
    This bypasses the schedule and runs immediately.
    """
    try:
        from core.services.portfolio_scheduler import portfolio_scheduler

        # Trigger manual refresh
        await portfolio_scheduler.run_manual_refresh()

        return {
            "success": True,
            "message": "Manual refresh triggered for all portfolios"
        }

    except Exception as e:
        logger.error(f"Error triggering manual refresh: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger refresh: {str(e)}")


async def _refresh_single_portfolio(portfolio: dict, org_id: Optional[str] = None):
    """Helper to refresh a single portfolio with current prices."""
    from core.database.postgres_client import get_postgres_rls_client
    import pytz
    import aiohttp
    import asyncio
    import os

    pg = await get_postgres_rls_client()
    portfolio_id = portfolio['id']
    user_id = portfolio['user_id']
    holdings = portfolio['holdings']
    if isinstance(holdings, (str, bytes)):
        holdings = json.loads(holdings if isinstance(holdings, str) else holdings.decode("utf-8"))

    if not holdings:
        return

    # Fetch current prices using FMP API
    tickers = [h['ticker'] for h in holdings]
    fmp_api_key = os.getenv('FMP_API_KEY')

    async def fetch_single_price(session: aiohttp.ClientSession, ticker: str) -> tuple[str, float]:
        """Fetch price for a single ticker using FMP /stable/quote"""
        url = f"https://financialmodelingprep.com/stable/quote?symbol={ticker}&apikey={fmp_api_key}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:  # 4x for FMP API
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        price = data[0].get('price', 0.0)
                        return (ticker, float(price) if price else 0.0)
                return (ticker, 0.0)
        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return (ticker, 0.0)

    prices = {}
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_single_price(session, ticker) for ticker in tickers]
        results = await asyncio.gather(*tasks)
        for ticker, price in results:
            prices[ticker] = price
    current_timestamp = datetime.now(pytz.UTC)
    current_timestamp_str = current_timestamp.isoformat()

    # Update holdings with current prices
    updated_holdings = []
    for holding in holdings:
        ticker = holding['ticker']
        current_price = prices.get(ticker)

        updated_holding = {**holding}
        if current_price:
            updated_holding['currentPrice'] = current_price
            updated_holding['priceUpdatedAt'] = current_timestamp_str

        updated_holdings.append(updated_holding)

    # Calculate total value (handle both old and new formats)
    total_value = 0
    def _quantity_from_holding(position: dict) -> float:
        lots = position.get('lots')
        if isinstance(lots, list) and lots:
            return sum(float(lot.get('quantity', 0) or 0) for lot in lots)
        return float(position.get('quantity', 0) or 0)

    for holding in updated_holdings:
        current_price = float(holding.get('currentPrice') or 0.0)
        total_quantity = _quantity_from_holding(holding)
        total_value += total_quantity * current_price

    # Calculate weights (handle both old and new formats)
    weights = []
    for holding in updated_holdings:
        current_price = float(holding.get('currentPrice') or 0.0)
        total_quantity = _quantity_from_holding(holding)
        value = total_quantity * current_price
        weight = value / total_value if total_value > 0 else 0
        weights.append(weight)

    # Update portfolio and create snapshot
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        await conn.execute("""
            UPDATE portfolios
            SET
                holdings = $1::jsonb,
                value = $2,
                weights = $3,
                updated_at = NOW()
            WHERE id = $4
        """, json.dumps(updated_holdings), total_value, weights, portfolio_id)

        # Create value history snapshot
        # Allow multiple snapshots per day for testing and intraday tracking
        await conn.execute("""
            INSERT INTO portfolio_value_history (
                portfolio_id,
                user_id,
                snapshot_date,
                total_value,
                holdings_snapshot,
                prices_snapshot
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
            ON CONFLICT (portfolio_id, snapshot_date) DO NOTHING
        """, portfolio_id, user_id, current_timestamp, total_value,
            json.dumps(updated_holdings), json.dumps(prices))

    logger.info(f"Refreshed portfolio {portfolio_id}: ${total_value:,.2f}")
