from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional, AsyncIterator, Any
from pydantic import BaseModel
import logging
import uuid
import asyncio
from datetime import datetime
import json

from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/postmortem", tags=["postmortem"])

# Track active postmortem analysis tasks for cancellation
_active_postmortem_tasks: dict[str, asyncio.Task] = {}
_postmortem_tasks_lock = asyncio.Lock()


class ImportFiltersRequest(BaseModel):
    portfolio_ids: List[str]
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    tickers: Optional[List[str]] = None
    source: Optional[str] = "all"  # 'all', 'manual', 'ibkr'
    min_value: Optional[float] = None


class PreviewMetrics(BaseModel):
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    biggest_win: float
    biggest_loss: float


class TransactionImportPreviewResponse(BaseModel):
    count: int
    metrics: PreviewMetrics


class Transaction(BaseModel):
    id: str
    portfolio_id: str
    portfolio_name: str
    ticker: str
    transaction_type: str
    quantity: float
    price: float
    transaction_date: str
    realized_gain_loss: Optional[float]
    total_amount: float


class TransactionsResponse(BaseModel):
    transactions: List[Transaction]
    total: int
    total_pages: int


class SavePostMortemRequest(BaseModel):
    transaction_ids: List[str]


class SavePostMortemResponse(BaseModel):
    success: bool
    postmortem_id: str
    transaction_count: int


class PostMortem(BaseModel):
    id: str
    title: Optional[str]
    transaction_count: int
    created_at: str
    updated_at: str


class PostMortemsListResponse(BaseModel):
    postmortems: List[PostMortem]
    total: int
    total_pages: int


class ChatThread(BaseModel):
    id: str
    postmortem_id: str
    title: Optional[str]
    created_at: str
    updated_at: str


class ChatThreadsResponse(BaseModel):
    threads: List[ChatThread]
    total: int


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


class CreateThreadResponse(BaseModel):
    thread_id: str
    title: Optional[str]


class UpdateThreadRequest(BaseModel):
    title: str


class ChatMessage(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    metadata: Optional[dict] = None
    created_at: str


class ChatMessagesResponse(BaseModel):
    messages: List[ChatMessage]
    total: int


@router.get("/list", response_model=PostMortemsListResponse)
async def list_postmortems(
    request: Request,
    page: int = 1,
    per_page: int = 20
):
    """
    List all saved post-mortems for the current user in the current workspace.
    Properly isolated by organization context.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Count total (RLS handles user isolation, we filter org_id explicitly)
            count_result = await conn.fetchrow("""
                SELECT COUNT(*) as total
                FROM portfolio_postmortems
                WHERE org_id = $1
            """, org_id)
            total = count_result['total']
            total_pages = (total + per_page - 1) // per_page

            # Fetch post-mortems with transaction count from junction table
            offset = (page - 1) * per_page
            rows = await conn.fetch("""
                SELECT
                    pm.id,
                    pm.title,
                    COUNT(pmt.transaction_id) as transaction_count,
                    pm.created_at,
                    pm.updated_at
                FROM portfolio_postmortems pm
                LEFT JOIN postmortem_transactions pmt ON pm.id = pmt.postmortem_id
                WHERE pm.org_id = $3
                GROUP BY pm.id, pm.title, pm.created_at, pm.updated_at
                ORDER BY pm.created_at DESC
                LIMIT $1 OFFSET $2
            """, per_page, offset, org_id)

            postmortems = [
                {
                    "id": str(row['id']),
                    "title": row['title'],
                    "transaction_count": int(row['transaction_count']),
                    "created_at": row['created_at'].isoformat(),
                    "updated_at": row['updated_at'].isoformat()
                }
                for row in rows
            ]

            return {
                "postmortems": postmortems,
                "total": total,
                "total_pages": total_pages
            }

    except Exception as e:
        logger.error(f"Failed to fetch post-mortems: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch post-mortems: {str(e)}")


@router.get("/transactions", response_model=TransactionsResponse)
async def get_all_transactions(
    request: Request,
    portfolio_id: Optional[str] = None,
    ticker: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
):
    """
    Fetch all transactions across user's portfolios with filters and pagination.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''
    logger.info(f"🔍 Fetching transactions for user_id: {user_id}, org_id: {org_id}")
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Verify RLS context is set
            rls_check = await conn.fetchval("SELECT current_setting('app.current_user_id', true)")
            logger.info(f"🔍 RLS context in transaction query: {rls_check}")
            # Build WHERE conditions
            conditions = []
            params = []
            param_idx = 1

            if portfolio_id:
                conditions.append(f"pt.portfolio_id = ${param_idx}")
                params.append(uuid.UUID(portfolio_id))
                param_idx += 1

            if ticker:
                conditions.append(f"pt.ticker = ${param_idx}")
                params.append(ticker)
                param_idx += 1

            if date_from:
                conditions.append(f"pt.transaction_date >= ${param_idx}")
                params.append(date_from)
                param_idx += 1

            if date_to:
                conditions.append(f"pt.transaction_date <= ${param_idx}")
                params.append(date_to)
                param_idx += 1

            # Filter to SELL transactions only (only these have realized P&L for post-mortems)
            conditions.append("pt.transaction_type = 'SELL'")

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            # Count total
            count_query = f"""
                SELECT COUNT(*) as total
                FROM portfolio_transactions pt
                INNER JOIN portfolios p ON pt.portfolio_id = p.id
                {where_clause}
            """
            logger.info(f"Count query: {count_query}, params: {params}")
            count_result = await conn.fetchrow(count_query, *params)
            total = count_result['total']
            total_pages = (total + per_page - 1) // per_page
            logger.info(f"Found {total} total SELL transactions")

            # Fetch transactions with their corresponding BUY transactions
            offset = (page - 1) * per_page
            query = f"""
                WITH sell_transactions AS (
                    SELECT
                        pt.id,
                        pt.portfolio_id,
                        p.name as portfolio_name,
                        pt.ticker,
                        pt.transaction_type,
                        pt.quantity,
                        pt.price,
                        pt.transaction_date,
                        pt.realized_gain_loss,
                        pt.total_amount
                    FROM portfolio_transactions pt
                    INNER JOIN portfolios p ON pt.portfolio_id = p.id
                    {where_clause}
                    ORDER BY pt.transaction_date DESC
                    LIMIT ${param_idx} OFFSET ${param_idx + 1}
                ),
                related_buys AS (
                    SELECT DISTINCT
                        pt.id,
                        pt.portfolio_id,
                        p.name as portfolio_name,
                        pt.ticker,
                        pt.transaction_type,
                        pt.quantity,
                        pt.price,
                        pt.transaction_date,
                        pt.realized_gain_loss,
                        pt.total_amount
                    FROM portfolio_transactions pt
                    INNER JOIN portfolios p ON pt.portfolio_id = p.id
                    INNER JOIN sell_transactions st ON
                        pt.ticker = st.ticker
                        AND pt.portfolio_id = st.portfolio_id
                        AND pt.transaction_type = 'BUY'
                        AND pt.transaction_date <= st.transaction_date
                )
                SELECT * FROM sell_transactions
                UNION ALL
                SELECT * FROM related_buys
                ORDER BY transaction_date ASC
            """
            params.extend([per_page, offset])
            logger.info(f"Fetching SELL transactions with related BUYs, query params: {params}")
            tx_rows = await conn.fetch(query, *params)
            logger.info(f"📊 CTE query returned {len(tx_rows)} rows")

            transactions = [
                {
                    "id": str(row['id']),
                    "portfolio_id": str(row['portfolio_id']),
                    "portfolio_name": row['portfolio_name'],
                    "ticker": row['ticker'],
                    "transaction_type": row['transaction_type'],
                    "quantity": float(row['quantity']),
                    "price": float(row['price']),
                    "transaction_date": row['transaction_date'].isoformat(),
                    "realized_gain_loss": float(row['realized_gain_loss']) if row['realized_gain_loss'] is not None else None,
                    "total_amount": float(row['total_amount'])
                }
                for row in tx_rows
            ]

            return {
                "transactions": transactions,
                "total": total,
                "total_pages": total_pages
            }

    except Exception as e:
        logger.error(f"Failed to fetch transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")


@router.post("/save", response_model=SavePostMortemResponse)
async def save_postmortem(
    request: Request,
    data: SavePostMortemRequest
):
    """
    Save selected transactions as a post-mortem for AI analysis.
    Creates a record that can be used for trade review and insights.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''

    if not data.transaction_ids:
        raise HTTPException(status_code=400, detail="No transactions selected")

    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Create post-mortem record with org_id
            postmortem_id = await conn.fetchval("""
                INSERT INTO portfolio_postmortems (user_id, org_id, created_at)
                VALUES ($1, $2, NOW())
                RETURNING id
            """, user_id, org_id)

            # Insert transaction associations into junction table with org_id
            for tx_id in data.transaction_ids:
                await conn.execute("""
                    INSERT INTO postmortem_transactions (postmortem_id, transaction_id, org_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                """, postmortem_id, uuid.UUID(tx_id), org_id)

            return {
                "success": True,
                "postmortem_id": str(postmortem_id),
                "transaction_count": len(data.transaction_ids)
            }

    except Exception as e:
        logger.error(f"Failed to save post-mortem: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save post-mortem: {str(e)}")


class DeletePostMortemRequest(BaseModel):
    postmortem_ids: List[str]


class DeletePostMortemResponse(BaseModel):
    success: bool
    deleted_count: int


class UpdatePostMortemRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None


class UpdatePostMortemResponse(BaseModel):
    success: bool
    postmortem_id: str


@router.delete("/delete", response_model=DeletePostMortemResponse)
async def delete_postmortems(
    request: Request,
    data: DeletePostMortemRequest
):
    """
    Delete one or more post-mortems.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''

    if not data.postmortem_ids:
        raise HTTPException(status_code=400, detail="No post-mortems selected")

    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Delete post-mortems with org_id check (RLS + explicit filter)
            result = await conn.execute("""
                DELETE FROM portfolio_postmortems
                WHERE id = ANY($1) AND org_id = $2
            """, [uuid.UUID(pid) for pid in data.postmortem_ids], org_id)

            # Extract count from result string like "DELETE 3"
            deleted_count = int(result.split()[-1]) if result else 0

            return {
                "success": True,
                "deleted_count": deleted_count
            }

    except Exception as e:
        logger.error(f"Failed to delete post-mortems: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete post-mortems: {str(e)}")


@router.get("/{postmortem_id}")
async def get_postmortem_details(
    request: Request,
    postmortem_id: str
):
    """
    Get detailed post-mortem with all associated transactions.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Fetch post-mortem with org_id check
            pm_row = await conn.fetchrow("""
                SELECT
                    id,
                    title,
                    notes,
                    created_at,
                    updated_at
                FROM portfolio_postmortems
                WHERE id = $1 AND org_id = $2
            """, uuid.UUID(postmortem_id), org_id)

            if not pm_row:
                raise HTTPException(status_code=404, detail="Post-mortem not found")

            # Fetch transactions via junction table
            tx_rows = await conn.fetch("""
                SELECT
                    pt.id,
                    pt.portfolio_id,
                    p.name as portfolio_name,
                    pt.ticker,
                    pt.transaction_type,
                    pt.quantity,
                    pt.price,
                    pt.transaction_date,
                    pt.realized_gain_loss,
                    pt.total_amount
                FROM postmortem_transactions pmt
                INNER JOIN portfolio_transactions pt ON pmt.transaction_id = pt.id
                INNER JOIN portfolios p ON pt.portfolio_id = p.id
                WHERE pmt.postmortem_id = $1
                ORDER BY pt.transaction_date ASC
            """, uuid.UUID(postmortem_id))

            transactions = [
                {
                    "id": str(row['id']),
                    "portfolio_id": str(row['portfolio_id']),
                    "portfolio_name": row['portfolio_name'],
                    "ticker": row['ticker'],
                    "transaction_type": row['transaction_type'],
                    "quantity": float(row['quantity']),
                    "price": float(row['price']),
                    "transaction_date": row['transaction_date'].isoformat(),
                    "realized_gain_loss": float(row['realized_gain_loss']) if row['realized_gain_loss'] is not None else None,
                    "total_amount": float(row['total_amount'])
                }
                for row in tx_rows
            ]

            return {
                "id": str(pm_row['id']),
                "title": pm_row['title'],
                "notes": pm_row['notes'],
                "transaction_count": len(transactions),
                "created_at": pm_row['created_at'].isoformat(),
                "updated_at": pm_row['updated_at'].isoformat(),
                "transactions": transactions
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch post-mortem details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch post-mortem details: {str(e)}")


@router.patch("/{postmortem_id}", response_model=UpdatePostMortemResponse)
async def update_postmortem(
    request: Request,
    postmortem_id: str,
    data: UpdatePostMortemRequest
):
    """
    Update post-mortem title or notes.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Build update fields
            updates = []
            params = []
            param_idx = 1

            if data.title is not None:
                updates.append(f"title = ${param_idx}")
                params.append(data.title)
                param_idx += 1

            if data.notes is not None:
                updates.append(f"notes = ${param_idx}")
                params.append(data.notes)
                param_idx += 1

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            updates.append(f"updated_at = NOW()")
            params.append(uuid.UUID(postmortem_id))
            params.append(org_id)

            query = f"""
                UPDATE portfolio_postmortems
                SET {', '.join(updates)}
                WHERE id = ${param_idx} AND org_id = ${param_idx + 1}
                RETURNING id
            """

            result = await conn.fetchval(query, *params)

            if not result:
                raise HTTPException(status_code=404, detail="Post-mortem not found")

            return {
                "success": True,
                "postmortem_id": str(result)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update post-mortem: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update post-mortem: {str(e)}")


class UpdateTransactionsRequest(BaseModel):
    transaction_ids: List[str]


@router.put("/{postmortem_id}/transactions")
async def update_postmortem_transactions(
    request: Request,
    postmortem_id: str,
    data: UpdateTransactionsRequest
):
    """
    Update the transactions associated with a post-mortem.
    Replaces all existing transactions with the new list.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Verify post-mortem exists and user has access with org_id check
            pm_check = await conn.fetchval(
                "SELECT id FROM portfolio_postmortems WHERE id = $1 AND org_id = $2",
                uuid.UUID(postmortem_id), org_id
            )

            if not pm_check:
                raise HTTPException(status_code=404, detail="Post-mortem not found")

            # Delete existing transaction associations
            await conn.execute(
                "DELETE FROM postmortem_transactions WHERE postmortem_id = $1",
                uuid.UUID(postmortem_id)
            )

            # Insert new transaction associations with org_id
            if data.transaction_ids:
                for tx_id in data.transaction_ids:
                    await conn.execute(
                        """
                        INSERT INTO postmortem_transactions (postmortem_id, transaction_id, org_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT DO NOTHING
                        """,
                        uuid.UUID(postmortem_id),
                        uuid.UUID(tx_id),
                        org_id
                    )

            # Update the updated_at timestamp
            await conn.execute(
                "UPDATE portfolio_postmortems SET updated_at = NOW() WHERE id = $1 AND org_id = $2",
                uuid.UUID(postmortem_id), org_id
            )

            return {
                "success": True,
                "postmortem_id": postmortem_id,
                "transaction_count": len(data.transaction_ids)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update post-mortem transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update transactions: {str(e)}")


@router.post("/preview", response_model=TransactionImportPreviewResponse)
async def preview_transactions_for_import(
    request: Request,
    filters: ImportFiltersRequest
):
    """
    Preview transactions that match import filters.
    Returns count and metrics without fetching all transaction details.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''

    if not filters.portfolio_ids:
        raise HTTPException(status_code=400, detail="At least one portfolio must be selected")

    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Build query with filters
            query = """
                SELECT
                    COUNT(*) as count,
                    COALESCE(SUM(realized_gain_loss) FILTER (WHERE realized_gain_loss IS NOT NULL), 0) as total_pnl,
                    COUNT(*) FILTER (WHERE realized_gain_loss > 0) as wins,
                    COUNT(*) FILTER (WHERE realized_gain_loss < 0) as losses,
                    COALESCE(AVG(realized_gain_loss) FILTER (WHERE realized_gain_loss > 0), 0) as avg_win,
                    COALESCE(AVG(realized_gain_loss) FILTER (WHERE realized_gain_loss < 0), 0) as avg_loss,
                    COALESCE(MAX(realized_gain_loss), 0) as biggest_win,
                    COALESCE(MIN(realized_gain_loss), 0) as biggest_loss
                FROM portfolio_transactions
                WHERE portfolio_id = ANY($1)
            """

            params = [filters.portfolio_ids]
            param_idx = 2

            # Date filters
            if filters.date_from:
                query += f" AND transaction_date >= ${param_idx}"
                params.append(filters.date_from)
                param_idx += 1

            if filters.date_to:
                query += f" AND transaction_date <= ${param_idx}"
                params.append(filters.date_to)
                param_idx += 1

            # Ticker filter
            if filters.tickers:
                query += f" AND ticker = ANY(${param_idx})"
                params.append(filters.tickers)
                param_idx += 1

            # Source filter
            if filters.source and filters.source != "all":
                query += f" AND source = ${param_idx}"
                params.append(filters.source)
                param_idx += 1

            # Min value filter
            if filters.min_value:
                query += f" AND ABS(total_amount) >= ${param_idx}"
                params.append(filters.min_value)
                param_idx += 1

            # Execute aggregation query
            result = await conn.fetchrow(query, *params)

            # Calculate metrics
            count = result['count'] or 0
            total_pnl = float(result['total_pnl'] or 0)
            wins = result['wins'] or 0
            losses = result['losses'] or 0
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            avg_win = float(result['avg_win'] or 0)
            avg_loss = float(result['avg_loss'] or 0)
            payoff_ratio = (avg_win / abs(avg_loss)) if avg_loss < 0 else 0

            return {
                "count": count,
                "metrics": {
                    "total_pnl": total_pnl,
                    "win_rate": round(win_rate, 1),
                    "avg_win": avg_win,
                    "avg_loss": avg_loss,
                    "payoff_ratio": round(payoff_ratio, 2),
                    "biggest_win": float(result['biggest_win'] or 0),
                    "biggest_loss": float(result['biggest_loss'] or 0)
                }
            }

    except Exception as e:
        logger.error(f"Failed to preview transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to preview transactions: {str(e)}")


class AnalyzePostMortemRequest(BaseModel):
    message: str
    model: Optional[str] = "gpt-5.1"
    selected_transaction_ids: List[str] = []
    web_search: bool = False
    file_ids: Optional[List[str]] = []


class AnalyzePostMortemResponse(BaseModel):
    response: str
    session_id: str
    message_id: str
    timestamp: str


@router.post("/{postmortem_id}/analyze", response_model=AnalyzePostMortemResponse)
async def analyze_postmortem(
    request: Request,
    postmortem_id: str,
    data: AnalyzePostMortemRequest
):
    """
    Analyze post-mortem trades using AI with transaction context.
    Properly scoped to the current organization workspace.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', None) or ''
    pg = await get_postgres_rls_client()

    try:
        # Get orchestrator
        from api.orchestrator import get_v6_orchestrator
        orchestrator = get_v6_orchestrator()

        # Fetch post-mortem and its transactions with org_id check
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Get post-mortem with org_id filter
            pm_row = await conn.fetchrow("""
                SELECT id, title, notes
                FROM portfolio_postmortems
                WHERE id = $1 AND org_id = $2
            """, uuid.UUID(postmortem_id), org_id)

            if not pm_row:
                raise HTTPException(status_code=404, detail="Post-mortem not found")

            # Get all transactions via junction table
            tx_rows = await conn.fetch("""
                SELECT
                    pt.id,
                    pt.portfolio_id,
                    p.name as portfolio_name,
                    pt.ticker,
                    pt.transaction_type,
                    pt.quantity,
                    pt.price,
                    pt.transaction_date,
                    pt.realized_gain_loss,
                    pt.total_amount
                FROM postmortem_transactions pmt
                JOIN portfolio_transactions pt ON pmt.transaction_id = pt.id
                JOIN portfolios p ON pt.portfolio_id = p.id
                WHERE pmt.postmortem_id = $1
                ORDER BY pt.transaction_date
            """, uuid.UUID(postmortem_id))

        # Build transaction context for analysis
        transactions = []
        for row in tx_rows:
            tx = {
                "id": str(row['id']),
                "ticker": row['ticker'],
                "type": row['transaction_type'],
                "quantity": float(row['quantity']),
                "price": float(row['price']),
                "date": row['transaction_date'].isoformat(),
                "realized_pnl": float(row['realized_gain_loss']) if row['realized_gain_loss'] is not None else None,
                "total_amount": float(row['total_amount']),
                "portfolio": row['portfolio_name']
            }
            transactions.append(tx)

        # Filter to selected transactions if specified
        if data.selected_transaction_ids:
            selected_set = set(data.selected_transaction_ids)
            transactions = [tx for tx in transactions if tx['id'] in selected_set]

        # Build enriched context for the AI
        transaction_summary = f"\n\nAnalyzing {len(transactions)} trade(s) from post-mortem '{pm_row['title'] or 'Untitled'}':\n"
        for tx in transactions:
            pnl_str = f"P&L: ${tx['realized_pnl']:,.2f}" if tx['realized_pnl'] is not None else "P&L: N/A"
            transaction_summary += f"- {tx['type']} {tx['quantity']} {tx['ticker']} @ ${tx['price']:.2f} on {tx['date'][:10]} ({pnl_str})\n"

        # Combine user query with transaction context
        enriched_message = data.message + transaction_summary

        # Generate unique session for this analysis
        import uuid as uuid_module
        session_id = uuid_module.uuid4().hex
        message_id = uuid_module.uuid4().hex

        # Create chat session first
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            await conn.execute(
                """
                INSERT INTO chat_sessions (id, user_id, org_id, title, created_at, updated_at)
                VALUES ($1::uuid, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                uuid.UUID(session_id),
                user_id,
                org_id,
                f"Post-Mortem: {pm_row['title'] or 'Untitled'}",
                datetime.now(),
                datetime.now()
            )

        # Process through orchestrator with web search and file attachments
        workflow_context = {}
        attachments = []

        if data.web_search:
            workflow_context["web_search_enabled"] = True

        # Handle file attachments
        if data.file_ids and user_id:
            try:
                async with pg.acquire_with_org_context(user_id, org_id) as conn:
                    validated_file_ids: list[str] = []
                    for file_id in data.file_ids[:10]:  # Limit to 10 files
                        try:
                            file_record = await conn.fetchrow(
                                "SELECT id, original_name, content_type, size_bytes FROM files WHERE id = $1",
                                uuid.UUID(file_id)
                            )
                            if file_record:
                                record = {
                                    "id": str(file_record['id']),
                                    "name": file_record['original_name'],
                                    "type": file_record['content_type'],
                                    "size": file_record['size_bytes'],
                                    "source": "upload",
                                }
                                attachments.append(record)
                                validated_file_ids.append(str(file_record['id']))
                                logger.info(f"Validated file {file_id}: {file_record['original_name']}")
                        except Exception as e:
                            logger.warning(f"Invalid file_id {file_id}: {e}")

                    if validated_file_ids:
                        workflow_context["file_ids"] = validated_file_ids
            except Exception as e:
                logger.warning(f"Failed to load file contexts: {e}")

        if attachments:
            workflow_context["attachments"] = attachments

        # Use dedicated post-mortem agent (following screener pattern)
        from core.agents.PostMortemAgent import create_postmortem_agent
        from agents import SQLiteSession
        from core.ai.langgraph_utils import execute_with_retry
        from core.config import get_config
        import asyncio

        config = get_config()

        # Get servers from orchestrator
        market_server = getattr(orchestrator, 'fmp_market_server', None) or getattr(orchestrator, 'yfinance_server', None)
        alternatives_server = getattr(orchestrator, 'fmp_alternatives_server', None)
        polygon_options_server = getattr(orchestrator, 'polygon_options_server', None)
        tradeflow_server = getattr(orchestrator, 'fmp_tradeflow_server', None)

        # Create post-mortem agent with all available servers
        postmortem_agent = create_postmortem_agent(
            market_server=market_server,
            alternatives_server=alternatives_server,
            polygon_options_server=polygon_options_server,
            tradeflow_server=tradeflow_server,
            model=data.model
        )

        # Create SQLite session for agent persistence
        sqlite_session = SQLiteSession(session_id, config.openai_sessions_db_path)

        # Execute agent with retry + timeout (following screener pattern)
        logger.info(f"Executing post-mortem agent for user {user_id}, session {session_id}")
        agent_timeout = getattr(config, "agent_node_timeout_seconds", 1200)

        try:
            result = await asyncio.wait_for(
                execute_with_retry(
                    postmortem_agent,
                    enriched_message,
                    sqlite_session,
                    max_turns=15,
                    agent_name="postmortem",
                    selected_model=data.model,
                ),
                timeout=agent_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(f"Post-mortem agent timed out after {agent_timeout}s for session {session_id}")
            raise HTTPException(
                status_code=504,
                detail={
                    "message": "Analysis timed out. Please try again with fewer transactions.",
                    "error_type": "timeout",
                    "timeout_seconds": agent_timeout,
                    "session_id": session_id,
                },
            )

        # Extract response from result
        assistant_response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Save analysis to PostgreSQL
        if pg and user_id:
            try:
                async with pg.acquire_with_org_context(user_id, org_id) as conn:
                    # Save user message
                    await conn.execute(
                        """
                        INSERT INTO chat_messages (id, session_id, user_id, org_id, role, content, created_at)
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
                        """,
                        uuid.UUID(message_id), uuid.UUID(session_id), user_id, org_id, 'user', enriched_message, datetime.now()
                    )
                    # Save assistant response
                    assistant_msg_id = uuid.uuid4().hex
                    await conn.execute(
                        """
                        INSERT INTO chat_messages (id, session_id, user_id, org_id, role, content, created_at)
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
                        """,
                        uuid.UUID(assistant_msg_id), uuid.UUID(session_id), user_id, org_id, 'assistant', assistant_response, datetime.now()
                    )
            except Exception as e:
                logger.warning(f"Failed to save analysis messages to PostgreSQL: {e}")

        return {
            "response": assistant_response,
            "session_id": session_id,
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze post-mortem: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze post-mortem: {str(e)}")


@router.get("/{postmortem_id}/analyze/stream")
async def analyze_postmortem_stream(
    postmortem_id: str,
    request: Request,
    thread_id: Optional[str] = None,
    selected_model: Optional[str] = Query(None, alias="model"),
):
    """
    Stream post-mortem analysis with SSE events (like main chat).
    If thread_id is provided, saves messages to that thread.
    If thread_id is not provided, creates a new thread automatically.
    """
    from api.orchestrator import get_v6_orchestrator

    orchestrator = get_v6_orchestrator()
    user_id = getattr(request.state, 'user_id', None)
    org_id = getattr(request.state, 'org_id', None) or ''

    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    async def event_generator() -> AsyncIterator[str]:
        seq = 0
        content_chunks = []
        active_thread_id = thread_id
        user_message_id = None
        assistant_message_id = None
        queue: asyncio.Queue[str] = asyncio.Queue()
        
        # Overall timeout for the entire streaming operation (10 minutes)
        STREAM_TIMEOUT_SECONDS = 600
        stream_start_time = datetime.now()

        def send_error(error_msg: str, fatal: bool = True) -> str:
            """Helper to format error SSE events. Fatal=True by default to prevent loops."""
            nonlocal seq
            seq += 1
            error_payload = {
                "type": "error", 
                "error": error_msg,
                "fatal": fatal,  # If true, frontend should NOT attempt to reconnect
            }
            logger.error(f"Postmortem stream error (fatal={fatal}): {error_msg}")
            return f"id: {seq}\ndata: {json.dumps(error_payload)}\n\n"

        def check_timeout() -> bool:
            """Check if we've exceeded the stream timeout."""
            elapsed = (datetime.now() - stream_start_time).total_seconds()
            return elapsed > STREAM_TIMEOUT_SECONDS

        def to_uuid(value) -> uuid.UUID:
            """Safely convert value to UUID, handling asyncpg UUID objects."""
            if value is None:
                raise ValueError("UUID value cannot be None")
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(str(value))

        try:
            pg = await get_postgres_rls_client()

            # Fetch post-mortem details
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                pm_row = await conn.fetchrow(
                    """
                    SELECT id, user_id, title
                    FROM portfolio_postmortems
                    WHERE id = $1 AND user_id = $2
                    """,
                    uuid.UUID(postmortem_id), user_id
                )

                if not pm_row:
                    yield send_error("Post-mortem not found", fatal=True)
                    return

                # Get transaction IDs from query parameter or use all from junction table
                selected_tx_ids_param = request.query_params.get('selected_transaction_ids', '').strip()
                if selected_tx_ids_param:
                    # User selected specific transactions
                    transaction_ids_str = [tx_id.strip() for tx_id in selected_tx_ids_param.split(',') if tx_id.strip()]
                    transaction_ids = [uuid.UUID(tx_id) for tx_id in transaction_ids_str]
                    logger.info(f"Using {len(transaction_ids)} selected transaction IDs from query parameter")

                    # Fetch selected transactions
                    transactions = await conn.fetch("""
                        SELECT
                            pt.id, pt.portfolio_id, p.name as portfolio_name,
                            pt.ticker, pt.transaction_type, pt.quantity, pt.price,
                            pt.transaction_date, pt.realized_gain_loss, pt.total_amount
                        FROM portfolio_transactions pt
                        JOIN portfolios p ON pt.portfolio_id = p.id
                        WHERE pt.id = ANY($1::uuid[])
                        ORDER BY pt.transaction_date ASC
                    """, transaction_ids)
                else:
                    # Use all transactions from junction table
                    transactions = await conn.fetch("""
                        SELECT
                            pt.id, pt.portfolio_id, p.name as portfolio_name,
                            pt.ticker, pt.transaction_type, pt.quantity, pt.price,
                            pt.transaction_date, pt.realized_gain_loss, pt.total_amount
                        FROM postmortem_transactions pmt
                        JOIN portfolio_transactions pt ON pmt.transaction_id = pt.id
                        JOIN portfolios p ON pt.portfolio_id = p.id
                        WHERE pmt.postmortem_id = $1
                        ORDER BY pt.transaction_date ASC
                    """, uuid.UUID(postmortem_id))
                    logger.info(f"Using all {len(transactions)} transactions from junction table")

                if not transactions:
                    yield send_error("No transactions found in this post-mortem", fatal=True)
                    return

                # Create thread if not provided
                if not active_thread_id:
                    active_thread_id = await conn.fetchval("""
                        INSERT INTO postmortem_chat_threads (postmortem_id, user_id, org_id, title)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                    """, uuid.UUID(postmortem_id), user_id, org_id, f"Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                    logger.info(f"Created new thread {active_thread_id} for post-mortem {postmortem_id}")
                else:
                    # Verify thread exists and belongs to user, otherwise create a fresh one
                    # active_thread_id may already be a UUID object from asyncpg
                    thread_id_param = to_uuid(active_thread_id)
                    thread_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM postmortem_chat_threads WHERE id = $1 AND user_id = $2)",
                        thread_id_param, user_id
                    )
                    if not thread_exists:
                        logger.warning(f"Thread {active_thread_id} not found for user {user_id}; creating new thread")
                        active_thread_id = await conn.fetchval("""
                            INSERT INTO postmortem_chat_threads (postmortem_id, user_id, org_id, title)
                            VALUES ($1, $2, $3, $4)
                            RETURNING id
                        """, uuid.UUID(postmortem_id), user_id, org_id, f"Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                        logger.info(f"Created new thread {active_thread_id} for post-mortem {postmortem_id} after missing thread")

            if not transactions:
                yield send_error("No transactions found in this post-mortem", fatal=True)
                return

            # Send start event with thread_id
            seq += 1
            start_payload = {"type": "start", "thread_id": str(active_thread_id)}
            yield f"id: {seq}\ndata: {json.dumps(start_payload)}\n\n"

            # Build enriched message with transaction data + optional user prompt
            user_prompt = (request.query_params.get("message") or "").strip()
            transaction_summary = []
            for tx in transactions:
                transaction_summary.append({
                    "date": tx['transaction_date'].isoformat() if hasattr(tx['transaction_date'], 'isoformat') else str(tx['transaction_date']),
                    "ticker": tx['ticker'],
                    "type": tx['transaction_type'],
                    "quantity": float(tx['quantity']),
                    "price": float(tx['price']),
                    "realized_pnl": float(tx['realized_gain_loss']) if tx['realized_gain_loss'] is not None else None
                })

            # Build enriched message for AI (trade context as reference, not command)
            trade_context = f"[Trade context: {len(transactions)} trade(s) attached]\n{json.dumps(transaction_summary, indent=2)}"

            if user_prompt:
                # User typed something - put their message first, context as reference
                enriched_message = f"{user_prompt}\n\n{trade_context}"
            else:
                # No prompt - default to analysis request
                enriched_message = f"Please analyze these {len(transactions)} trade(s).\n\n{trade_context}"

            # Build clean user message for display (no JSON data)
            display_message = user_prompt if user_prompt else f"Analyze {len(transactions)} trades from \"{pm_row['title'] or 'Untitled'}\""

            # Save clean user message with transaction metadata
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                user_message_id = await conn.fetchval("""
                    INSERT INTO postmortem_chat_messages (thread_id, user_id, org_id, role, content, metadata)
                    VALUES ($1, $2, $3, 'user', $4, $5)
                    RETURNING id
                """, to_uuid(active_thread_id), user_id, org_id or '', display_message,
                json.dumps({"transactions": transaction_summary}))

            # Use PostMortemAgent directly with execute_with_stream
            from core.agents.PostMortemAgent import create_postmortem_agent
            from agents import SQLiteSession
            from core.ai.langgraph_utils import execute_with_stream, execute_with_retry
            from core.config import get_config
            from core.ai.utils.message_compactor import get_provider_from_model

            config = get_config()
            # Accept both ?model and ?selected_model query params (UI currently sends selected_model)
            raw_model_param = (
                selected_model
                or request.query_params.get("selected_model")
                or request.query_params.get("model")
            )
            model_choice = raw_model_param or config.agent_model

            provider = get_provider_from_model(model_choice) if model_choice else "openai"
            # Only OpenAI truly supports streaming with OpenAI Agents SDK
            # Other providers (anthropic, gemini, bedrock, xai) cause __fake_id__ errors with streaming
            # Use simulated stream (non-streaming with heartbeats) for non-OpenAI providers - matches v6.py behavior
            streaming_providers = {"openai"}
            can_stream = provider in streaming_providers
            if not can_stream:
                logger.info(
                    "[postmortem_stream] Provider %s not streaming-capable for model=%s; falling back to non-stream execution",
                    provider,
                    model_choice,
                )
            # Get servers from orchestrator
            market_server = getattr(orchestrator, 'fmp_market_server', None) or getattr(orchestrator, 'yfinance_server', None)
            alternatives_server = getattr(orchestrator, 'fmp_alternatives_server', None)
            polygon_options_server = getattr(orchestrator, 'polygon_options_server', None)
            tradeflow_server = getattr(orchestrator, 'fmp_tradeflow_server', None)

            postmortem_agent = create_postmortem_agent(
                market_server=market_server,
                alternatives_server=alternatives_server,
                polygon_options_server=polygon_options_server,
                tradeflow_server=tradeflow_server,
                model=model_choice
            )

            sqlite_session = SQLiteSession(str(active_thread_id), config.openai_sessions_db_path)

            logger.info(f"Streaming post-mortem agent for user {user_id}, post-mortem {postmortem_id}, thread {active_thread_id}")

            async def enqueue(payload: dict, event_name: Optional[str] = None):
                nonlocal seq
                seq += 1
                lines = [f"id: {seq}"]
                if event_name:
                    lines.append(f"event: {event_name}")
                lines.append(f"data: {json.dumps(payload)}")
                await queue.put("\n".join(lines) + "\n\n")

            # Stream callback for content tokens
            async def on_token(content: str):
                """Callback for streaming tokens"""
                if not content:
                    return
                content_chunks.append(content)
                await enqueue({"type": "content", "content": content})

            # Stream callback for tool events (code interpreter, web search, etc.)
            async def on_event(event: dict):
                """Callback for tool events - maps to frontend ToolEvent format"""
                event_type = event.get("type")

                # Map internal event types to frontend-compatible format
                # Frontend expects: tool_call_started, tool_call_output, reasoning_delta, reasoning_summary_done, etc.
                # Handle both prefixed (response.output_text.delta) and non-prefixed (output_text.delta) versions

                # SKIP ALL content-related events - these are handled by on_token callback
                # on_token already sends {"type": "content", "content": delta}
                # This prevents duplicate content from being sent to the frontend
                content_event_types = {
                    "output_text.delta", "response.output_text.delta",
                    "output_text.done", "response.output_text.done",
                    "content_part.delta", "response.content_part.delta",
                    "content_part.done", "response.content_part.done",
                }
                if event_type in content_event_types:
                    return

                # Also skip if this event has a 'delta' key and is output-text related
                # (handles cases where type might not match exactly due to normalization)
                if event.get("delta") is not None and "output_text" in str(event_type or ""):
                    return

                # Function call argument deltas (tool arguments being built)
                if event_type in ("function_call_arguments.delta", "response.function_call_arguments.delta"):
                    # Skip these - they're intermediate tool call details
                    # We only care about tool_call.started and tool_call.output
                    return

                if event_type in ("tool_call.started", "response.tool_call.started"):
                    payload = {
                        "type": "tool_call_started",
                        "event": {
                            "item_id": event.get("item_id"),
                            "tool_name": event.get("tool_name"),
                            "name": event.get("tool_name"),
                        }
                    }
                elif event_type in ("tool_call.output", "response.tool_call.output"):
                    payload = {
                        "type": "tool_call_output",
                        "event": {
                            "item_id": event.get("item_id"),
                            "output": event.get("output"),
                        }
                    }
                elif event_type == "reasoning.summary_done":
                    payload = {
                        "type": "reasoning_summary_done",
                        "event": {
                            "text": event.get("text", ""),
                        }
                    }
                elif event_type in ("reasoning_delta", "response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
                    payload = {
                        "type": "reasoning_delta",
                        "event": {
                            "delta": event.get("delta", "") or event.get("text", ""),
                        }
                    }
                elif event_type in ("reasoning_done", "response.reasoning_summary_text.done", "response.reasoning_text.done"):
                    payload = {
                        "type": "reasoning_summary_done",
                        "event": {
                            "text": event.get("text", ""),
                        }
                    }
                elif event_type in ("reasoning.summary_part", "response.reasoning_summary_part.added"):
                    payload = {
                        "type": "reasoning_delta",
                        "event": {
                            "delta": event.get("text", "") or event.get("delta", ""),
                        }
                    }
                elif event_type == "agent.updated":
                    payload = {
                        "type": "agent_updated",
                        "event": {
                            "agent_name": event.get("agent_name"),
                        }
                    }
                # Code Interpreter events
                elif event_type == "code_interpreter.in_progress":
                    payload = {
                        "type": "tool_call_started",
                        "event": {
                            "item_id": event.get("item_id"),
                            "tool_name": "code_interpreter",
                            "name": "code_interpreter",
                        }
                    }
                elif event_type == "code_interpreter.completed":
                    payload = {
                        "type": "tool_call_output",
                        "event": {
                            "item_id": event.get("item_id"),
                            "output": event.get("output", ""),
                        }
                    }
                elif event_type == "code_interpreter.code_delta":
                    payload = {
                        "type": "code_interpreter_code_delta",
                        "event": {
                            "item_id": event.get("item_id"),
                            "code": event.get("code", ""),
                        }
                    }
                # Web Search events
                elif event_type == "web_search.in_progress":
                    payload = {
                        "type": "tool_call_started",
                        "event": {
                            "item_id": event.get("item_id"),
                            "tool_name": "web_search",
                            "name": "web_search",
                        }
                    }
                elif event_type == "web_search.completed":
                    payload = {
                        "type": "tool_call_output",
                        "event": {
                            "item_id": event.get("item_id"),
                            "output": event.get("output", ""),
                        }
                    }
                # File Search events
                elif event_type == "file_search.in_progress":
                    payload = {
                        "type": "tool_call_started",
                        "event": {
                            "item_id": event.get("item_id"),
                            "tool_name": "file_search",
                            "name": "file_search",
                        }
                    }
                elif event_type == "file_search.completed":
                    payload = {
                        "type": "tool_call_output",
                        "event": {
                            "item_id": event.get("item_id"),
                            "output": event.get("output", ""),
                        }
                    }
                # MCP events
                elif event_type == "mcp_call.in_progress":
                    payload = {
                        "type": "tool_call_started",
                        "event": {
                            "item_id": event.get("item_id"),
                            "tool_name": event.get("tool_name", "mcp_call"),
                            "name": event.get("tool_name", "mcp_call"),
                        }
                    }
                elif event_type == "mcp_call.completed":
                    payload = {
                        "type": "tool_call_output",
                        "event": {
                            "item_id": event.get("item_id"),
                            "output": event.get("output", ""),
                        }
                    }
                elif event_type == "mcp_call.failed":
                    payload = {
                        "type": "tool_call_output",
                        "event": {
                            "item_id": event.get("item_id"),
                            "output": f"Failed: {event.get('error', 'Unknown error')}",
                            "error": event.get("error"),
                        }
                    }
                # OpenAI SDK response lifecycle events
                elif event_type in ("response.created", "response.started"):
                    payload = {
                        "type": "start",
                        "event": event
                    }
                elif event_type in ("response.completed", "response.done"):
                    payload = {
                        "type": "response_completed",
                        "event": event
                    }
                else:
                    payload = {
                        "type": event_type,
                        "event": event
                    }

                await enqueue(payload)

            if can_stream:
                # Execute with streaming
                stream_task = asyncio.create_task(
                    execute_with_stream(
                        agent=postmortem_agent,
                        query=enriched_message,
                        session=sqlite_session,
                        on_token=on_token,
                        on_event=on_event,
                        max_turns=15,
                        agent_name="postmortem",
                        selected_model=model_choice
                    )
                )

                # Register task for cancellation
                async with _postmortem_tasks_lock:
                    _active_postmortem_tasks[str(active_thread_id)] = stream_task

                try:
                    # Drain queue while streaming is in progress
                    while True:
                        # Check timeout
                        if check_timeout():
                            logger.warning(f"PostMortem stream timeout after {STREAM_TIMEOUT_SECONDS}s for thread {active_thread_id}")
                            stream_task.cancel()
                            yield send_error(f"Analysis timed out after {STREAM_TIMEOUT_SECONDS // 60} minutes", fatal=True)
                            return
                        
                        if stream_task.done() and queue.empty():
                            break
                        try:
                            payload = await asyncio.wait_for(queue.get(), timeout=0.25)
                            yield payload
                        except asyncio.TimeoutError:
                            continue

                    # Check for stream errors
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        logger.info(f"PostMortem analysis cancelled for thread {active_thread_id}")
                        await enqueue({"type": "cancelled"})
                        while not queue.empty():
                            yield await queue.get()
                        return
                    except Exception as stream_error:
                        logger.error(f"PostMortem agent streaming failed: {stream_error}", exc_info=True)
                        # Mark as fatal to prevent reconnection loops
                        await enqueue({"type": "error", "error": str(stream_error), "fatal": True})
                        while not queue.empty():
                            yield await queue.get()
                        return
                finally:
                    # Clean up task registry
                    async with _postmortem_tasks_lock:
                        _active_postmortem_tasks.pop(str(active_thread_id), None)
            else:
                # Non-OpenAI: Use execute_with_retry with session=None
                # This avoids __fake_id__ corruption from SQLiteSession
                # Conversation memory is maintained via PostgreSQL + enriched_message
                import re as _re
                heartbeat_interval = 5

                task = asyncio.create_task(
                    execute_with_retry(
                        postmortem_agent,
                        enriched_message,
                        session=None,  # No SQLiteSession for non-OpenAI
                        max_turns=15,
                        agent_name="postmortem",
                        selected_model=model_choice,
                    )
                )

                # Register task for cancellation
                async with _postmortem_tasks_lock:
                    _active_postmortem_tasks[str(active_thread_id)] = task

                try:
                    # Send heartbeats while waiting with timeout check
                    while True:
                        # Check timeout
                        if check_timeout():
                            logger.warning(f"PostMortem non-stream timeout after {STREAM_TIMEOUT_SECONDS}s for thread {active_thread_id}")
                            task.cancel()
                            yield send_error(f"Analysis timed out after {STREAM_TIMEOUT_SECONDS // 60} minutes", fatal=True)
                            return
                        
                        done, _ = await asyncio.wait({task}, return_when=asyncio.FIRST_COMPLETED, timeout=heartbeat_interval)
                        if task in done:
                            break
                        await enqueue({"type": "status", "message": "working..."})

                    # Get result
                    try:
                        result = await task
                    except asyncio.CancelledError:
                        logger.info(f"PostMortem analysis cancelled for thread {active_thread_id}")
                        await enqueue({"type": "cancelled"})
                        while not queue.empty():
                            yield await queue.get()
                        return

                    final_text = getattr(result, "final_output", None) or str(result)

                    # Tokenize and stream response
                    tokens = _re.findall(r'\S+|\n', final_text)
                    for idx, tok in enumerate(tokens):
                        if tok == '\n':
                            chunk = tok
                        else:
                            chunk = tok + " " if idx < len(tokens) - 1 and tokens[idx + 1] != '\n' else tok
                        content_chunks.append(chunk)
                        await enqueue({"type": "content", "content": chunk})

                except Exception as non_stream_err:
                    logger.error(f"PostMortem agent simulated stream failed: {non_stream_err}", exc_info=True)
                    # Mark as fatal to prevent reconnection loops
                    await enqueue({"type": "error", "error": str(non_stream_err), "fatal": True})
                    while not queue.empty():
                        yield await queue.get()
                    return
                finally:
                    # Clean up task registry
                    async with _postmortem_tasks_lock:
                        _active_postmortem_tasks.pop(str(active_thread_id), None)

            # Save assistant response to thread
            full_content = ''.join(content_chunks)
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                assistant_message_id = await conn.fetchval("""
                    INSERT INTO postmortem_chat_messages (thread_id, user_id, org_id, role, content)
                    VALUES ($1, $2, $3, 'assistant', $4)
                    RETURNING id
                """, to_uuid(active_thread_id), user_id, org_id or '', full_content)

                # Update thread timestamp
                await conn.execute("""
                    UPDATE postmortem_chat_threads
                    SET updated_at = NOW()
                    WHERE id = $1
                """, to_uuid(active_thread_id))

            logger.info(f"Post-mortem analysis complete: {len(full_content)} chars generated, saved to thread {active_thread_id}")

            # Send done event with SSE event name so EventSource recognizes it
            await enqueue({"type": "done", "thread_id": str(active_thread_id)}, event_name="done")
            while not queue.empty():
                yield await queue.get()

        except Exception as e:
            logger.error(f"Streaming post-mortem analysis failed: {e}", exc_info=True)
            # ALWAYS mark as fatal to prevent infinite retry loops
            yield send_error(f"Analysis failed: {str(e)}", fatal=True)
            return  # Explicitly exit the generator

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.post("/{postmortem_id}/analyze/cancel")
async def cancel_postmortem_analysis(
    postmortem_id: str,
    request: Request,
    thread_id: Optional[str] = Query(None)
):
    """
    Cancel an active streaming post-mortem analysis session.
    """
    user_id = getattr(request.state, 'user_id', None)

    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    logger.info(f"[cancel] Cancelling post-mortem analysis: postmortem_id={postmortem_id}, thread_id={thread_id}, user={user_id}")

    if not thread_id:
        logger.warning(f"[cancel] No thread_id provided for cancellation")
        return {
            "success": False,
            "message": "No thread_id provided",
            "postmortem_id": postmortem_id,
        }

    # Look up and cancel the task from our registry
    async with _postmortem_tasks_lock:
        task = _active_postmortem_tasks.get(thread_id)

    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info(f"[cancel] Successfully cancelled post-mortem analysis for thread {thread_id}")
        return {"success": True, "message": "Analysis cancelled", "thread_id": thread_id}

    logger.warning(f"[cancel] No active analysis found for thread {thread_id}")
    return {
        "success": False,
        "message": "No active analysis found",
        "postmortem_id": postmortem_id,
        "thread_id": thread_id,
    }


# ============================================
# POST-MORTEM CHAT THREAD ENDPOINTS
# ============================================

@router.get("/{postmortem_id}/threads", response_model=ChatThreadsResponse)
async def list_threads(
    postmortem_id: str,
    request: Request
):
    """
    List all chat threads for a specific post-mortem.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', '')
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # Verify post-mortem exists and belongs to user
            pm_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM portfolio_postmortems WHERE id = $1 AND user_id = $2)",
                uuid.UUID(postmortem_id), user_id
            )

            if not pm_exists:
                raise HTTPException(status_code=404, detail="Post-mortem not found")

            # Fetch threads
            rows = await conn.fetch("""
                SELECT id, postmortem_id, title, created_at, updated_at
                FROM postmortem_chat_threads
                WHERE postmortem_id = $1 AND user_id = $2
                ORDER BY updated_at DESC
            """, uuid.UUID(postmortem_id), user_id)

            threads = [
                ChatThread(
                    id=str(row['id']),
                    postmortem_id=str(row['postmortem_id']),
                    title=row['title'],
                    created_at=row['created_at'].isoformat(),
                    updated_at=row['updated_at'].isoformat()
                )
                for row in rows
            ]

            return ChatThreadsResponse(threads=threads, total=len(threads))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list threads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _parse_metadata(raw: Any) -> Optional[dict]:
    """
    Normalize metadata field from DB into a dictionary.

    Handles cases where metadata is stored as JSON text.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            # Best-effort: wrap as string payload
            return {"raw": raw}
    return None


@router.post("/{postmortem_id}/threads", response_model=CreateThreadResponse)
async def create_thread(
    postmortem_id: str,
    request: Request,
    body: CreateThreadRequest
):
    """
    Create a new chat thread for a post-mortem.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', '')
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # Verify post-mortem exists and belongs to user
            pm_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM portfolio_postmortems WHERE id = $1 AND user_id = $2)",
                uuid.UUID(postmortem_id), user_id
            )

            if not pm_exists:
                raise HTTPException(status_code=404, detail="Post-mortem not found")

            # Create thread (org_id defaults to '' in database)
            thread_id = await conn.fetchval("""
                INSERT INTO postmortem_chat_threads (postmortem_id, user_id, title)
                VALUES ($1, $2, $3)
                RETURNING id
            """, uuid.UUID(postmortem_id), user_id, body.title)

            return CreateThreadResponse(
                thread_id=str(thread_id),
                title=body.title
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}/messages", response_model=ChatMessagesResponse)
async def get_thread_messages(
    thread_id: str,
    request: Request
):
    """
    Get all messages for a specific thread.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', '')
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # Verify thread exists and belongs to user
            thread_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM postmortem_chat_threads WHERE id = $1 AND user_id = $2)",
                uuid.UUID(thread_id), user_id
            )

            if not thread_exists:
                raise HTTPException(status_code=404, detail="Thread not found")

            # Fetch messages
            rows = await conn.fetch("""
                SELECT id, thread_id, role, content, metadata, created_at
                FROM postmortem_chat_messages
                WHERE thread_id = $1 AND user_id = $2
                ORDER BY created_at ASC
            """, uuid.UUID(thread_id), user_id)

            messages = [
                ChatMessage(
                    id=str(row['id']),
                    thread_id=str(row['thread_id']),
                    role=row['role'],
                    content=row['content'],
                    metadata=_parse_metadata(row['metadata']),
                    created_at=row['created_at'].isoformat()
                )
                for row in rows
            ]

            return ChatMessagesResponse(messages=messages, total=len(messages))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thread messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/threads/{thread_id}", response_model=dict)
async def update_thread(
    thread_id: str,
    request: Request,
    body: UpdateThreadRequest
):
    """
    Update thread title.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', '')
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # Update thread
            result = await conn.execute("""
                UPDATE postmortem_chat_threads
                SET title = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3
            """, body.title, uuid.UUID(thread_id), user_id)

            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Thread not found")

            return {"success": True, "title": body.title}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/threads/{thread_id}", response_model=dict)
async def delete_thread(
    thread_id: str,
    request: Request
):
    """
    Delete a thread and all its messages.
    """
    user_id = request.state.user_id
    org_id = getattr(request.state, 'org_id', '')
    pg = await get_postgres_rls_client()

    try:
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # Delete thread (messages cascade automatically)
            result = await conn.execute("""
                DELETE FROM postmortem_chat_threads
                WHERE id = $1 AND user_id = $2
            """, uuid.UUID(thread_id), user_id)

            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Thread not found")

            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
