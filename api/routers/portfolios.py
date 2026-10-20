from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
import logging
import json

from api.models_dir.portfolio import PortfolioCreate, PortfolioUpdate, PortfolioResponse, PurchaseLot
from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


class FetchPricesRequest(BaseModel):
    tickers: List[str]


class FetchPricesResponse(BaseModel):
    prices: Dict[str, float]
    timestamp: str


class BuySharesRequest(BaseModel):
    """Request to buy shares and add to portfolio"""
    ticker: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    price: float = Field(..., ge=0)
    purchase_date: Optional[str] = None


class SellSharesRequest(BaseModel):
    """Request to sell shares from portfolio"""
    ticker: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    price: float = Field(..., ge=0)
    lot_ids: Optional[List[str]] = Field(None, description="Specific lot IDs to sell (FIFO if None)")
    sell_date: Optional[str] = None


class UpdateCashRequest(BaseModel):
    """Request to update portfolio cash balance"""
    amount: float = Field(..., ge=0)
    operation: str = Field(..., description="'add' to add cash, 'set' to set absolute value")


class DeleteTransactionsRequest(BaseModel):
    """Request to delete multiple transactions"""
    transaction_ids: List[str] = Field(..., min_items=1, description="List of transaction IDs to delete")


class PortfolioImportRequest(BaseModel):
    """Request to import portfolio from CSV/Excel file"""
    name: str = Field(..., min_length=1, max_length=255, description="Portfolio name")
    file_data: List[List[Any]] = Field(..., description="Parsed CSV/Excel data as 2D array")
    ticker_column_index: int = Field(..., ge=0, description="Column index containing tickers")
    weight_column_index: Optional[int] = Field(None, ge=0, description="Column index containing weights (optional)")
    skip_header_rows: int = Field(default=1, ge=0, description="Number of header rows to skip")


class PortfolioImportResponse(BaseModel):
    """Response after importing portfolio"""
    portfolio_id: str
    name: str
    tickers_imported: int
    warnings: List[str] = []


# ========== Accounting Response Models ==========

class TransactionResponse(BaseModel):
    """Portfolio transaction record"""
    id: str
    portfolio_id: str
    transaction_type: str  # 'BUY' or 'SELL'
    source: Optional[str] = "manual"
    external_id: Optional[str] = None
    ticker: str
    quantity: float
    price: float
    total_amount: float
    transaction_date: str
    cost_basis: Optional[float] = None
    realized_gain_loss: Optional[float] = None
    lots_affected: Optional[List[Dict]] = None
    notes: Optional[str] = None
    created_at: str


class TransactionHistoryResponse(BaseModel):
    """Transaction history for a portfolio with pagination"""
    portfolio_id: str
    transactions: List[TransactionResponse]
    total: int  # Total number of transactions matching filters
    page: int  # Current page number
    per_page: int  # Items per page
    total_pages: int  # Total number of pages


class RealizedGainsResponse(BaseModel):
    """Realized gains/losses summary"""
    portfolio_id: str
    total_realized_gains: float
    total_cost_basis: float
    total_proceeds: float
    transactions_count: int
    by_ticker: Dict[str, Dict[str, float]]  # ticker -> {gains, cost_basis, proceeds}


class CostBasisResponse(BaseModel):
    """Cost basis report for current holdings"""
    portfolio_id: str
    positions: List[Dict[str, Any]]  # {ticker, quantity, avg_cost, total_cost_basis}
    total_cost_basis: float


class TaxLotsResponse(BaseModel):
    """Tax lots report (all purchase lots in portfolio)"""
    portfolio_id: str
    tax_lots: List[Dict[str, Any]]  # {ticker, lotId, quantity, purchasePrice, purchaseDate, holding_period_days}
    total_lots: int


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: PortfolioCreate,
    request: Request,
):
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    # In dev mode or when user not in DB, use clerk_user_id directly
    # This allows dev mode to work without database users
    internal_user_id = clerk_user_id

    # Save portfolio
    holdings_list = None
    if payload.holdings:
        holdings_list = [h.dict() for h in payload.holdings]

    new_portfolio = await pg.save_portfolio(
        user_id=internal_user_id,
        name=payload.name,
        tickers=payload.tickers,
        weights=payload.weights,
        is_default=payload.is_default,
        value=payload.value,
        cash_balance=payload.cash_balance,
        holdings=holdings_list,
        org_id=org_id
    )
    if not new_portfolio:
        raise HTTPException(status_code=500, detail="Failed to create portfolio")
    
    new_id = new_portfolio['id']

    # Return created portfolio with properly parsed types
    return PortfolioResponse(
        id=str(new_portfolio['id']),
        name=new_portfolio['name'],
        tickers=new_portfolio['tickers'],
        weights=new_portfolio['weights'],
        is_default=new_portfolio.get('is_default', False),
        value=new_portfolio.get('value'),
        cash_balance=new_portfolio.get('cash_balance'),
        holdings=new_portfolio.get('holdings'),  # Already parsed by postgres_client
        created_at=new_portfolio['created_at'].isoformat() if new_portfolio.get('created_at') else None
    )


@router.post("/import", response_model=PortfolioImportResponse, status_code=status.HTTP_201_CREATED)
async def import_portfolio(
    payload: PortfolioImportRequest,
    request: Request,
):
    """
    Import portfolio from parsed CSV/Excel data.

    Expects file data to be pre-parsed by frontend (using xlsx library).
    Validates tickers and creates portfolio with specified weights.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    try:
        # Skip header rows
        data_rows = payload.file_data[payload.skip_header_rows:]

        if not data_rows:
            raise HTTPException(
                status_code=400,
                detail="No data rows found after skipping headers"
            )

        # Extract tickers and weights
        tickers = []
        weights = []
        warnings = []

        for idx, row in enumerate(data_rows):
            row_num = idx + payload.skip_header_rows + 1

            # Check if row has enough columns
            if len(row) <= payload.ticker_column_index:
                warnings.append(f"Row {row_num}: Missing ticker column")
                continue

            # Extract ticker
            ticker_value = row[payload.ticker_column_index]
            if ticker_value is None or str(ticker_value).strip() == '':
                continue

            ticker = str(ticker_value).strip().upper()

            # Skip empty tickers or 'nan' values
            if not ticker or ticker == '' or ticker.lower() == 'nan':
                continue

            # Validate ticker format (1-5 uppercase letters)
            if not ticker.isalpha() or len(ticker) > 5:
                warnings.append(f"Row {row_num}: Invalid ticker '{ticker}' - must be 1-5 letters")
                continue

            tickers.append(ticker)

            # Extract weight if column specified
            if payload.weight_column_index is not None:
                if len(row) <= payload.weight_column_index:
                    warnings.append(f"Row {row_num}: Missing weight column")
                    weights.append(0.0)
                else:
                    try:
                        weight_value = row[payload.weight_column_index]
                        if weight_value is None or str(weight_value).strip() == '':
                            weight = 0.0
                        else:
                            weight = float(weight_value)
                            # Handle percentage format (e.g., 35 instead of 0.35)
                            if weight > 1:
                                weight = weight / 100.0

                            if weight < 0 or weight > 1:
                                warnings.append(f"Row {row_num}: Weight {weight} outside valid range [0,1]")
                                weight = max(0, min(1, weight))
                        weights.append(weight)
                    except (ValueError, TypeError) as e:
                        warnings.append(f"Row {row_num}: Invalid weight value '{weight_value}'")
                        weights.append(0.0)

        if not tickers:
            raise HTTPException(
                status_code=400,
                detail="No valid tickers found in file"
            )

        # Normalize weights
        if weights:
            total_weight = sum(weights)
            if total_weight == 0:
                # Equal weight if all zeros
                weights = [1.0 / len(tickers)] * len(tickers)
                warnings.append("All weights were zero - using equal weighting")
            elif abs(total_weight - 1.0) > 0.01:
                # Normalize to sum to 1.0
                weights = [w / total_weight for w in weights]
                warnings.append(f"Weights normalized from {total_weight:.4f} to 1.0")
        else:
            # Equal weight distribution if no weight column
            weights = [1.0 / len(tickers)] * len(tickers)

        # Check for duplicate portfolio name
        async with pg.acquire_with_org_context(internal_user_id, org_id) as conn:
            existing = await conn.fetchrow(
                """
                SELECT id FROM portfolios
                WHERE user_id = $1
                  AND LOWER(name) = LOWER($2)
                  AND (
                      (org_id IS NULL AND $3 IS NULL)
                      OR org_id = $3
                  )
                """,
                internal_user_id,
                payload.name,
                org_id
            )
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Portfolio '{payload.name}' already exists"
                )

        # Create portfolio using existing save_portfolio method
        new_portfolio = await pg.save_portfolio(
            user_id=internal_user_id,
            name=payload.name,
            tickers=tickers,
            weights=weights,
            is_default=False,
            value=None,
            cash_balance=0.0,
            holdings=None,
            org_id=org_id
        )

        if not new_portfolio:
            raise HTTPException(status_code=500, detail="Failed to create portfolio")

        portfolio_id = str(new_portfolio['id'])

        return PortfolioImportResponse(
            portfolio_id=portfolio_id,
            name=payload.name,
            tickers_imported=len(tickers),
            warnings=warnings
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portfolio import error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("", response_model=List[PortfolioResponse])
async def list_portfolios(
    request: Request,
):
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    # DEBUG: Log what org context we're using
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"🔍 PORTFOLIOS DEBUG - user_id: {clerk_user_id}, org_id: {org_id}, header: {request.headers.get('X-Organization-ID')}")

    # In dev mode or when user not in DB, use clerk_user_id directly
    # This allows dev mode to work without database users
    internal_user_id = clerk_user_id
    rows = await pg.get_user_portfolios(internal_user_id, org_id=org_id)
    logger.warning(f"🔍 PORTFOLIOS DEBUG - Found {len(rows)} portfolios")
    # Convert UUID and datetime to strings for Pydantic
    # Filter out MANUAL portfolios with empty tickers/weights (broken portfolios)
    # Keep broker portfolios even if empty (they may not have positions yet)
    return [
        PortfolioResponse(
            id=str(r['id']),
            name=r['name'],
            tickers=r['tickers'],
            weights=r['weights'],
            is_default=r.get('is_default', False),
            value=r.get('value'),
            cash_balance=r.get('cash_balance'),
            holdings=r.get('holdings'),  # Already parsed by postgres_client
            created_at=r['created_at'].isoformat() if r.get('created_at') else None,
            updated_at=r['updated_at'].isoformat() if r.get('updated_at') else None,
            broker_connection_id=str(r['broker_connection_id']) if r.get('broker_connection_id') else None,
            source_type=r.get('source_type'),
            synced_at=r['synced_at'].isoformat() if r.get('synced_at') else None
        )
        for r in rows
        if (
            # Keep broker portfolios regardless of tickers/weights (may be empty before first sync)
            r.get('source_type') == 'broker'
            or
            # Only keep manual portfolios if they have valid tickers/weights
            (r.get('tickers') and len(r['tickers']) > 0 and r.get('weights') and len(r['weights']) > 0)
        )
    ]

@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: str,
    request: Request,
):
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    # In dev mode or when user not in DB, use clerk_user_id directly
    # This allows dev mode to work without database users
    internal_user_id = clerk_user_id
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    # Convert UUID and datetime to strings for Pydantic
    return PortfolioResponse(
        id=str(p['id']),
        name=p['name'],
        tickers=p['tickers'],
        weights=p['weights'],
        is_default=p.get('is_default', False),
        value=p.get('value'),
        cash_balance=p.get('cash_balance'),
        holdings=p.get('holdings'),  # Already parsed by postgres_client
        created_at=p['created_at'].isoformat() if p.get('created_at') else None,
        updated_at=p['updated_at'].isoformat() if p.get('updated_at') else None,
        broker_connection_id=str(p['broker_connection_id']) if p.get('broker_connection_id') else None,
        source_type=p.get('source_type'),
        synced_at=p['synced_at'].isoformat() if p.get('synced_at') else None
    )

@router.put("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: str,
    payload: PortfolioUpdate,
    request: Request,
):
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    # In dev mode or when user not in DB, use clerk_user_id directly
    # This allows dev mode to work without database users
    internal_user_id = clerk_user_id

    holdings_list = None
    if hasattr(payload, 'holdings') and payload.holdings:
        holdings_list = [h.dict() for h in payload.holdings]

    ok = await pg.update_portfolio(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        name=payload.name,
        tickers=payload.tickers,
        weights=payload.weights,
        value=payload.value,
        cash_balance=payload.cash_balance,
        holdings=holdings_list,
        org_id=org_id
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update portfolio")
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    # Convert UUID and datetime to strings for Pydantic
    return PortfolioResponse(
        id=str(p['id']),
        name=p['name'],
        tickers=p['tickers'],
        weights=p['weights'],
        is_default=p.get('is_default', False),
        value=p.get('value'),
        cash_balance=p.get('cash_balance'),
        holdings=p.get('holdings'),  # Already parsed by postgres_client
        created_at=p['created_at'].isoformat() if p.get('created_at') else None,
        updated_at=p['updated_at'].isoformat() if p.get('updated_at') else None,
        broker_connection_id=str(p['broker_connection_id']) if p.get('broker_connection_id') else None,
        source_type=p.get('source_type'),
        synced_at=p['synced_at'].isoformat() if p.get('synced_at') else None
    )

@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: str,
    request: Request,
):
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    # In dev mode or when user not in DB, use clerk_user_id directly
    # This allows dev mode to work without database users
    internal_user_id = clerk_user_id
    ok = await pg.delete_portfolio(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Portfolio not found or not deleted")
    return None

@router.post("/{portfolio_id}/set-default", status_code=status.HTTP_204_NO_CONTENT)
async def set_default_portfolio(
    portfolio_id: str,
    request: Request,
):
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    # In dev mode or when user not in DB, use clerk_user_id directly
    # This allows dev mode to work without database users
    internal_user_id = clerk_user_id
    ok = await pg.set_default_portfolio(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to set default portfolio")
    return None


@router.post("/prices", response_model=FetchPricesResponse)
async def fetch_prices(
    payload: FetchPricesRequest,
    request: Request,
):
    """
    Fetch current prices for tickers using FMP /stable/quote endpoint.
    Fetches one ticker at a time since batch requests are not supported.
    """
    import aiohttp
    import os
    import asyncio

    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not payload.tickers:
        return FetchPricesResponse(prices={}, timestamp=datetime.utcnow().isoformat())

    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        raise HTTPException(status_code=500, detail="FMP API key not configured")

    async def fetch_single_price(session: aiohttp.ClientSession, ticker: str) -> tuple[str, float]:
        """Fetch price for a single ticker using FMP /stable/quote with symbol param"""
        url = f"https://financialmodelingprep.com/stable/quote?symbol={ticker}&apikey={fmp_api_key}"
        print(f"[PRICE DEBUG] Fetching price for {ticker} from: {url}")
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:  # 4x for FMP API
                print(f"[PRICE DEBUG] {ticker} - Response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"[PRICE DEBUG] {ticker} - Response data: {data}")
                    if isinstance(data, list) and len(data) > 0:
                        price = data[0].get('price')
                        if price is not None:
                            print(f"[PRICE DEBUG] {ticker} - Found price: {price}")
                            return (ticker, float(price))
                print(f"[PRICE DEBUG] {ticker} - No price found, returning 0.0")
                return (ticker, 0.0)
        except Exception as e:
            print(f"[PRICE DEBUG] Error fetching price for {ticker}: {e}")
            return (ticker, 0.0)

    try:
        prices = {}
        async with aiohttp.ClientSession() as session:
            # Fetch prices with concurrency limit to prevent API overwhelming
            semaphore = asyncio.Semaphore(50)

            async def fetch_with_limit(ticker):
                async with semaphore:
                    return await fetch_single_price(session, ticker)

            tasks = [fetch_with_limit(ticker) for ticker in payload.tickers]
            results = await asyncio.gather(*tasks)

            for ticker, price in results:
                prices[ticker] = price

        return FetchPricesResponse(
            prices=prices,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch prices: {str(e)}")


@router.post("/{portfolio_id}/buy", response_model=PortfolioResponse)
async def buy_shares(
    portfolio_id: str,
    payload: BuySharesRequest,
    request: Request,
):
    """
    Buy shares: deduct from cash, add lot to holdings.
    Cash must be sufficient for purchase.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Get portfolio
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Explicit validation with parseFloat
    try:
        quantity = float(payload.quantity)
        price = float(payload.price)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid quantity or price format")

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    if price <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than 0")

    # Parse holdings (already parsed by postgres_client)
    holdings_data = p.get('holdings') if p.get('holdings') else []
    cash_balance = float(p.get('cash_balance', 0) or 0)

    # Calculate purchase cost
    total_cost = quantity * price

    # Check sufficient cash
    if cash_balance < total_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient cash. Need ${total_cost:.2f}, have ${cash_balance:.2f}"
        )

    # Deduct from cash
    new_cash = cash_balance - total_cost

    # Create new lot
    import uuid
    purchase_date = payload.purchase_date or datetime.utcnow().isoformat()
    new_lot = {
        "quantity": quantity,
        "purchasePrice": price,
        "purchaseDate": purchase_date,
        "lotId": str(uuid.uuid4())
    }

    # Update holdings
    ticker_upper = payload.ticker.upper()
    ticker_found = False
    for holding in holdings_data:
        if holding.get('ticker', '').upper() == ticker_upper:
            # Add lot to existing ticker
            if 'lots' not in holding or holding['lots'] is None:
                holding['lots'] = []
            holding['lots'].append(new_lot)
            ticker_found = True
            break

    if not ticker_found:
        # Add new ticker
        holdings_data.append({
            "ticker": ticker_upper,
            "lots": [new_lot],
            "currentPrice": payload.price,
            "priceUpdatedAt": datetime.utcnow().isoformat()
        })

    # Recalculate weights based on market value
    # Calculate total portfolio value
    total_holdings_value = 0.0
    for holding in holdings_data:
        current_price = holding.get('currentPrice', 0) or 0
        lots = holding.get('lots', []) or []
        total_qty = sum(lot.get('quantity', 0) for lot in lots)
        total_holdings_value += total_qty * current_price

    total_portfolio_value = total_holdings_value + new_cash

    # Calculate weights
    tickers = []
    weights = []
    for holding in holdings_data:
        ticker = holding.get('ticker')
        current_price = holding.get('currentPrice', 0) or 0
        lots = holding.get('lots', []) or []
        total_qty = sum(lot.get('quantity', 0) for lot in lots)
        position_value = total_qty * current_price

        tickers.append(ticker)
        if total_portfolio_value > 0:
            weights.append(position_value / total_portfolio_value)
        else:
            weights.append(0.0)

    # Update portfolio
    ok = await pg.update_portfolio(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        name=None,
        tickers=tickers,
        weights=weights,
        value=total_portfolio_value,
        cash_balance=new_cash,
        holdings=holdings_data,
        org_id=org_id
    )

    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update portfolio")

    # Record transaction for accounting
    transaction_id = await pg.record_transaction(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        transaction_type='BUY',
        ticker=ticker_upper,
        quantity=quantity,
        price=price,
        total_amount=total_cost,
        transaction_date=purchase_date,
        lots_affected=[new_lot],  # Record the lot that was created
        org_id=org_id
    )

    if not transaction_id:
        logger.warning(f"Failed to record transaction for buy: {ticker_upper}")

    # Return updated portfolio
    updated_p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not updated_p:
        raise HTTPException(status_code=404, detail="Portfolio not found after update")

    return PortfolioResponse(
        id=str(updated_p['id']),
        name=updated_p['name'],
        tickers=updated_p['tickers'],
        weights=updated_p['weights'],
        is_default=updated_p.get('is_default', False),
        value=updated_p.get('value'),
        cash_balance=updated_p.get('cash_balance'),
        holdings=updated_p.get('holdings'),  # Already parsed by postgres_client
        created_at=updated_p['created_at'].isoformat() if updated_p.get('created_at') else None,
        updated_at=updated_p['updated_at'].isoformat() if updated_p.get('updated_at') else None
    )


@router.post("/{portfolio_id}/sell", response_model=PortfolioResponse)
async def sell_shares(
    portfolio_id: str,
    payload: SellSharesRequest,
    request: Request,
):
    """
    Sell shares: remove lots from holdings (FIFO if no lot_ids), add to cash.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Get portfolio
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Explicit validation with parseFloat
    try:
        quantity = float(payload.quantity)
        price = float(payload.price)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid quantity or price format")

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    if price <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than 0")

    # Parse holdings (already parsed by postgres_client)
    holdings_data = p.get('holdings') if p.get('holdings') else []
    cash_balance = float(p.get('cash_balance', 0) or 0)

    # Find ticker
    ticker_upper = payload.ticker.upper()
    holding_index = None
    for i, holding in enumerate(holdings_data):
        if holding.get('ticker', '').upper() == ticker_upper:
            holding_index = i
            break

    if holding_index is None:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker_upper} not found in portfolio")

    holding = holdings_data[holding_index]
    lots = holding.get('lots', []) or []

    # Calculate total quantity available
    total_qty = sum(lot.get('quantity', 0) for lot in lots)
    if total_qty < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient shares. Need {quantity}, have {total_qty}"
        )

    # Sell shares (FIFO or specific lots) with accounting
    remaining_to_sell = quantity
    lots_sold = []  # Track sold lots for accounting
    cost_basis_total = 0.0  # Track total cost basis

    if payload.lot_ids:
        # Sell specific lots
        for lot in lots[:]:
            if lot.get('lotId') in payload.lot_ids and remaining_to_sell > 0:
                lot_qty = lot.get('quantity', 0)
                lot_purchase_price = lot.get('purchasePrice', 0)

                if lot_qty <= remaining_to_sell:
                    # Remove entire lot
                    qty_sold = lot_qty
                    lots.remove(lot)
                    remaining_to_sell -= lot_qty
                else:
                    # Partial lot sale
                    qty_sold = remaining_to_sell
                    lot['quantity'] -= remaining_to_sell
                    remaining_to_sell = 0

                # Record sold lot for accounting
                lots_sold.append({
                    'lotId': lot.get('lotId'),
                    'quantity': qty_sold,
                    'purchasePrice': lot_purchase_price,
                    'purchaseDate': lot.get('purchaseDate')
                })
                cost_basis_total += qty_sold * lot_purchase_price
    else:
        # FIFO: sell oldest lots first
        # Sort by purchase date
        def parse_date(lot):
            pd = lot.get('purchaseDate')
            if isinstance(pd, str):
                try:
                    return datetime.fromisoformat(pd.replace('Z', '+00:00'))
                except:
                    return datetime.min
            return datetime.min

        lots.sort(key=parse_date)

        for lot in lots[:]:
            if remaining_to_sell <= 0:
                break
            lot_qty = lot.get('quantity', 0)
            lot_purchase_price = lot.get('purchasePrice', 0)

            if lot_qty <= remaining_to_sell:
                # Remove entire lot
                qty_sold = lot_qty
                lots.remove(lot)
                remaining_to_sell -= lot_qty
            else:
                # Partial lot sale
                qty_sold = remaining_to_sell
                lot['quantity'] -= remaining_to_sell
                remaining_to_sell = 0

            # Record sold lot for accounting
            lots_sold.append({
                'lotId': lot.get('lotId'),
                'quantity': qty_sold,
                'purchasePrice': lot_purchase_price,
                'purchaseDate': lot.get('purchaseDate')
            })
            cost_basis_total += qty_sold * lot_purchase_price

    # Update holding lots
    holding['lots'] = lots

    # If no lots left, remove ticker from holdings
    if not lots:
        holdings_data.pop(holding_index)

    # Add sale proceeds to cash
    sale_proceeds = quantity * price
    new_cash = cash_balance + sale_proceeds

    # Recalculate weights based on market value
    total_holdings_value = 0.0
    for h in holdings_data:
        current_price = h.get('currentPrice', 0) or 0
        h_lots = h.get('lots', []) or []
        total_qty = sum(lot.get('quantity', 0) for lot in h_lots)
        total_holdings_value += total_qty * current_price

    total_portfolio_value = total_holdings_value + new_cash

    # Calculate weights
    tickers = []
    weights = []
    for h in holdings_data:
        ticker = h.get('ticker')
        current_price = h.get('currentPrice', 0) or 0
        h_lots = h.get('lots', []) or []
        total_qty = sum(lot.get('quantity', 0) for lot in h_lots)
        position_value = total_qty * current_price

        tickers.append(ticker)
        if total_portfolio_value > 0:
            weights.append(position_value / total_portfolio_value)
        else:
            weights.append(0.0)

    # Handle empty portfolio
    if not tickers:
        tickers = ["CASH"]
        weights = [0.0]

    # Update portfolio
    ok = await pg.update_portfolio(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        name=None,
        tickers=tickers,
        weights=weights,
        value=total_portfolio_value,
        cash_balance=new_cash,
        holdings=holdings_data if holdings_data else None,
        org_id=org_id
    )

    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update portfolio")

    # Calculate realized gain/loss for accounting
    sale_date = payload.sell_date or datetime.utcnow().isoformat()
    realized_gain_loss = sale_proceeds - cost_basis_total

    # Record transaction for accounting
    transaction_id = await pg.record_transaction(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        transaction_type='SELL',
        ticker=ticker_upper,
        quantity=quantity,
        price=price,
        total_amount=sale_proceeds,
        transaction_date=sale_date,
        cost_basis=cost_basis_total,
        realized_gain_loss=realized_gain_loss,
        lots_affected=lots_sold,  # Record which lots were sold
        org_id=org_id
    )

    if not transaction_id:
        logger.warning(f"Failed to record transaction for sell: {ticker_upper}")

    # Return updated portfolio
    updated_p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not updated_p:
        raise HTTPException(status_code=404, detail="Portfolio not found after update")

    return PortfolioResponse(
        id=str(updated_p['id']),
        name=updated_p['name'],
        tickers=updated_p['tickers'],
        weights=updated_p['weights'],
        is_default=updated_p.get('is_default', False),
        value=updated_p.get('value'),
        cash_balance=updated_p.get('cash_balance'),
        holdings=updated_p.get('holdings'),  # Already parsed by postgres_client
        created_at=updated_p['created_at'].isoformat() if updated_p.get('created_at') else None,
        updated_at=updated_p['updated_at'].isoformat() if updated_p.get('updated_at') else None
    )


@router.put("/{portfolio_id}/cash", response_model=PortfolioResponse)
async def update_cash_balance(
    portfolio_id: str,
    payload: UpdateCashRequest,
    request: Request,
):
    """
    Update portfolio cash balance directly.
    Operation: 'add' to add cash, 'set' to set absolute value.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Validate operation
    if payload.operation not in ['add', 'set']:
        raise HTTPException(status_code=400, detail="Operation must be 'add' or 'set'")

    # Get portfolio
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Parse holdings (already parsed by postgres_client)
    holdings_data = p.get('holdings') if p.get('holdings') else []
    cash_balance = float(p.get('cash_balance', 0) or 0)

    # Calculate new cash
    if payload.operation == 'add':
        new_cash = cash_balance + payload.amount
    else:  # 'set'
        new_cash = payload.amount

    if new_cash < 0:
        raise HTTPException(status_code=400, detail="Cash balance cannot be negative")

    # Recalculate weights based on market value
    total_holdings_value = 0.0
    for holding in holdings_data:
        current_price = holding.get('currentPrice', 0) or 0
        lots = holding.get('lots', []) or []
        total_qty = sum(lot.get('quantity', 0) for lot in lots)
        total_holdings_value += total_qty * current_price

    total_portfolio_value = float(total_holdings_value) + float(new_cash)

    # Calculate weights
    tickers = []
    weights = []
    for holding in holdings_data:
        ticker = holding.get('ticker')
        current_price = holding.get('currentPrice', 0) or 0
        lots = holding.get('lots', []) or []
        total_qty = sum(lot.get('quantity', 0) for lot in lots)
        position_value = total_qty * current_price

        tickers.append(ticker)
        if total_portfolio_value > 0:
            weights.append(position_value / total_portfolio_value)
        else:
            weights.append(0.0)

    # Handle empty portfolio
    if not tickers:
        tickers = p.get('tickers', ["CASH"])
        weights = p.get('weights', [0.0])

    # Update portfolio
    ok = await pg.update_portfolio(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        name=None,
        tickers=tickers,
        weights=weights,
        value=total_portfolio_value,
        cash_balance=new_cash,
        holdings=holdings_data if holdings_data else None,
        org_id=org_id
    )

    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update portfolio")

    # Return updated portfolio
    updated_p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not updated_p:
        raise HTTPException(status_code=404, detail="Portfolio not found after update")

    return PortfolioResponse(
        id=str(updated_p['id']),
        name=updated_p['name'],
        tickers=updated_p['tickers'],
        weights=updated_p['weights'],
        is_default=updated_p.get('is_default', False),
        value=updated_p.get('value'),
        cash_balance=updated_p.get('cash_balance'),
        holdings=updated_p.get('holdings'),  # Already parsed by postgres_client
        created_at=updated_p['created_at'].isoformat() if updated_p.get('created_at') else None,
        updated_at=updated_p['updated_at'].isoformat() if updated_p.get('updated_at') else None
    )


# ========== Accounting Endpoints ==========

@router.get("/{portfolio_id}/transactions", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    portfolio_id: str,
    request: Request,
    page: int = 1,
    per_page: int = 20,
    ticker: Optional[str] = None,
    transaction_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """
    Get paginated transaction history for a portfolio.
    Optionally filter by ticker, transaction type (BUY/SELL), and date range.
    date_from/date_to should be ISO date strings (YYYY-MM-DD).
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    if per_page > 100:
        per_page = 100

    # Verify portfolio exists and belongs to user
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Calculate offset for pagination
    offset = (page - 1) * per_page

    # Get total count for pagination metadata
    # Use same filters to get accurate count
    all_transactions = await pg.get_portfolio_transactions(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        ticker=ticker,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        limit=100000,  # Large number to get all matching transactions for count
        org_id=org_id
    )
    total_count = len(all_transactions)

    # Get paginated transactions
    paginated_transactions = all_transactions[offset:offset + per_page]

    # Convert to response format
    transaction_responses = []
    for t in paginated_transactions:
        transaction_responses.append(TransactionResponse(
            id=str(t['id']),
            portfolio_id=str(t['portfolio_id']),
            transaction_type=t['transaction_type'],
            source=t.get('source'),
            external_id=t.get('external_id'),
            ticker=t['ticker'],
            quantity=float(t['quantity']),
            price=float(t['price']),
            total_amount=float(t['total_amount']),
            transaction_date=t['transaction_date'].isoformat() if isinstance(t['transaction_date'], datetime) else t['transaction_date'],
            cost_basis=float(t['cost_basis']) if t.get('cost_basis') is not None else None,
            realized_gain_loss=float(t['realized_gain_loss']) if t.get('realized_gain_loss') is not None else None,
            lots_affected=json.loads(t['lots_affected']) if t.get('lots_affected') else None,
            notes=t.get('notes'),
            created_at=t['created_at'].isoformat() if isinstance(t['created_at'], datetime) else t['created_at']
        ))

    # Calculate total pages
    import math
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    return TransactionHistoryResponse(
        portfolio_id=portfolio_id,
        transactions=transaction_responses,
        total=total_count,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{portfolio_id}/realized-gains", response_model=RealizedGainsResponse)
async def get_realized_gains(
    portfolio_id: str,
    request: Request
):
    """
    Get realized gains/losses summary for a portfolio.
    Aggregates all SELL transactions.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Verify portfolio exists
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Get all SELL transactions
    sells = await pg.get_portfolio_transactions(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        transaction_type='SELL',
        limit=10000,  # Get all sells
        org_id=org_id
    )

    # Calculate aggregates
    total_realized_gains = 0.0
    total_cost_basis = 0.0
    total_proceeds = 0.0
    by_ticker = {}

    for sell in sells:
        ticker = sell['ticker']
        gain = float(sell.get('realized_gain_loss', 0) or 0)
        cost = float(sell.get('cost_basis', 0) or 0)
        proceeds = float(sell.get('total_amount', 0))

        total_realized_gains += gain
        total_cost_basis += cost
        total_proceeds += proceeds

        if ticker not in by_ticker:
            by_ticker[ticker] = {'gains': 0.0, 'cost_basis': 0.0, 'proceeds': 0.0}

        by_ticker[ticker]['gains'] += gain
        by_ticker[ticker]['cost_basis'] += cost
        by_ticker[ticker]['proceeds'] += proceeds

    return RealizedGainsResponse(
        portfolio_id=portfolio_id,
        total_realized_gains=total_realized_gains,
        total_cost_basis=total_cost_basis,
        total_proceeds=total_proceeds,
        transactions_count=len(sells),
        by_ticker=by_ticker
    )


@router.get("/{portfolio_id}/cost-basis", response_model=CostBasisResponse)
async def get_cost_basis(
    portfolio_id: str,
    request: Request
):
    """
    Get cost basis report for current holdings.
    Calculates average cost and total cost basis per position.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Get portfolio with holdings
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings_data = p.get('holdings') if p.get('holdings') else []  # Already parsed by postgres_client

    # Calculate cost basis for each position
    positions = []
    total_cost_basis = 0.0

    for holding in holdings_data:
        ticker = holding.get('ticker')
        lots = holding.get('lots', []) or []

        if not lots:
            continue

        # Calculate totals
        total_quantity = sum(lot.get('quantity', 0) for lot in lots)
        total_cost = sum(lot.get('quantity', 0) * lot.get('purchasePrice', 0) for lot in lots)
        avg_cost = total_cost / total_quantity if total_quantity > 0 else 0.0

        positions.append({
            'ticker': ticker,
            'quantity': total_quantity,
            'avg_cost': avg_cost,
            'total_cost_basis': total_cost
        })

        total_cost_basis += total_cost

    return CostBasisResponse(
        portfolio_id=portfolio_id,
        positions=positions,
        total_cost_basis=total_cost_basis
    )


@router.get("/{portfolio_id}/tax-lots", response_model=TaxLotsResponse)
async def get_tax_lots(
    portfolio_id: str,
    request: Request
):
    """
    Get tax lots report (all purchase lots with holding periods).
    Useful for tax planning and lot-level analysis.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Get portfolio with holdings
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings_data = p.get('holdings') if p.get('holdings') else []  # Already parsed by postgres_client

    # Collect all lots with holding periods
    tax_lots = []
    now = datetime.utcnow()

    for holding in holdings_data:
        ticker = holding.get('ticker')
        lots = holding.get('lots', []) or []

        for lot in lots:
            purchase_date_str = lot.get('purchaseDate')
            try:
                if isinstance(purchase_date_str, str):
                    purchase_date = datetime.fromisoformat(purchase_date_str.replace('Z', '+00:00'))
                else:
                    purchase_date = now

                holding_period_days = (now - purchase_date).days
            except:
                holding_period_days = 0

            tax_lots.append({
                'ticker': ticker,
                'lotId': lot.get('lotId'),
                'quantity': lot.get('quantity'),
                'purchasePrice': lot.get('purchasePrice'),
                'purchaseDate': purchase_date_str,
                'holding_period_days': holding_period_days,
                'is_long_term': holding_period_days > 365  # Long-term capital gains threshold
            })

    return TaxLotsResponse(
        portfolio_id=portfolio_id,
        tax_lots=tax_lots,
        total_lots=len(tax_lots)
    )


@router.delete("/{portfolio_id}/transactions")
async def delete_transactions(
    portfolio_id: str,
    request: Request,
    payload: DeleteTransactionsRequest
):
    """
    Delete multiple transactions.
    RLS ensures users can only delete their own transactions.
    """
    pg = await get_postgres_rls_client()
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Extract org_id from request state (set by RLS middleware)
    org_id = getattr(request.state, 'org_id', None)

    internal_user_id = clerk_user_id

    # Verify portfolio exists and belongs to user
    p = await pg.get_portfolio_by_id(user_id=internal_user_id, portfolio_id=portfolio_id, org_id=org_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if not payload.transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")

    # Delete transactions (RLS automatically filters to user's transactions)
    deleted_count = await pg.delete_transactions(
        user_id=internal_user_id,
        portfolio_id=portfolio_id,
        transaction_ids=payload.transaction_ids,
        org_id=org_id
    )

    return {"deleted": deleted_count, "message": f"Deleted {deleted_count} transaction(s)"}
