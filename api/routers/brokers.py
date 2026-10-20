"""
Broker connection API endpoints for IBKR integration.

Key features:
- IMMEDIATE first sync on connection (not waiting for scheduler)
- Returns positions directly in connection response
- Proper error handling with graceful degradation

Following CODING_RULES.md: KISS, DRY, YAGNI, no hardcoding.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

from api.models_dir.broker import (
    IBKRConnectionRequest,
    BrokerConnectionResponse,
    BrokerConnectionStatusResponse
)
from core.database.postgres_client import get_postgres_rls_client
from core.integrations.ibkr_service import get_ibkr_service
from core.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brokers", tags=["Broker Connections"])


def _derive_transaction_type(trade: Dict[str, Any]) -> str:
    """Infer BUY/SELL from IBKR trade payload."""
    buy_sell = str(trade.get('buySell') or trade.get('side') or "").upper()
    if 'BUY' in buy_sell:
        return 'BUY'
    if 'SELL' in buy_sell:
        return 'SELL'
    # Fallback to proceeds sign if available
    proceeds = trade.get('proceeds') or trade.get('tradeMoney')
    try:
        proceeds_val = float(proceeds) if proceeds is not None else 0.0
        return 'SELL' if proceeds_val > 0 else 'BUY'
    except (ValueError, TypeError):
        return 'BUY'


def _parse_trade_datetime(trade: Dict[str, Any]) -> str:
    """Combine tradeDate + time into ISO string."""
    date_str = str(trade.get('tradeDate') or trade.get('reportDate') or "").strip()
    time_str = str(trade.get('tradeTime') or "").strip()
    date_time_field = trade.get('dateTime')

    if date_time_field and isinstance(date_time_field, str) and ';' in date_time_field:
        # IBKR format "YYYYMMDD;HHMMSS"
        parts = date_time_field.split(';', 1)
        date_str = date_str or parts[0]
        time_str = time_str or parts[1]

    try:
        if date_str:
            # Normalize date
            if '-' in date_str:
                base_date = datetime.fromisoformat(date_str).date()
            else:
                base_date = datetime.strptime(date_str, "%Y%m%d").date()

            if time_str:
                time_str = time_str.replace(':', '')
                hh = time_str[0:2] if len(time_str) >= 2 else "00"
                mm = time_str[2:4] if len(time_str) >= 4 else "00"
                ss = time_str[4:6] if len(time_str) >= 6 else "00"
                parsed = datetime.strptime(f"{base_date} {hh}:{mm}:{ss}", "%Y-%m-%d %H:%M:%S")
                return parsed.isoformat()
            return datetime.combine(base_date, datetime.min.time()).isoformat()
    except Exception:
        pass

    return datetime.utcnow().isoformat()


def _build_trade_notes(trade: Dict[str, Any]) -> str:
    """Concise note string capturing broker fees/ids."""
    parts = []
    for key in ['ibCommission', 'otherCommission', 'brokerExecutionCommission', 'tradeFee', 'taxes']:
        val = trade.get(key)
        if val not in [None, '', 0, 0.0]:
            parts.append(f"{key}={val}")
    if trade.get('exchange'):
        parts.append(f"exchange={trade.get('exchange')}")
    if trade.get('transactionType'):
        parts.append(f"type={trade.get('transactionType')}")
    return "; ".join(parts) if parts else "IBKR trade import"


async def _ingest_ibkr_trades(
    pg,
    user_id: str,
    portfolio_id: str,
    trades: List[Dict[str, Any]],
    org_id: Optional[str] = None
) -> int:
    """Upsert IBKR trades into portfolio_transactions with deduping via external_id."""
    if not trades:
        return 0

    ingested = 0
    errors = 0
    
    for idx, trade in enumerate(trades):
        try:
            # Defensive: Skip if trade is None or not a dict
            if not trade or not isinstance(trade, dict):
                logger.warning(f"[IBKR Trades] Skipping invalid trade at index {idx}: not a dict")
                errors += 1
                continue
            
            transaction_type = _derive_transaction_type(trade)
            
            # Defensive numeric parsing with explicit None checks
            quantity_raw = trade.get('quantity') or trade.get('size') or trade.get('shares')
            try:
                quantity = abs(float(quantity_raw)) if quantity_raw is not None else 0.0
            except (ValueError, TypeError):
                logger.warning(f"[IBKR Trades] Invalid quantity '{quantity_raw}' for trade {idx}, defaulting to 0")
                quantity = 0.0
            
            price_raw = trade.get('tradePrice') or trade.get('price') or trade.get('closePrice')
            try:
                price = float(price_raw) if price_raw is not None else 0.0
            except (ValueError, TypeError):
                logger.warning(f"[IBKR Trades] Invalid price '{price_raw}' for trade {idx}, defaulting to 0")
                price = 0.0
            
            try:
                fx_rate = float(trade.get('fxRateToBase') or 1.0)
            except (ValueError, TypeError):
                fx_rate = 1.0
            
            currency = trade.get('currency') or trade.get('reportCurrency') or trade.get('listingCurrency')

            # Normalize monetary values to base currency (USD) using fxRateToBase
            proceeds_raw = trade.get('proceeds') or trade.get('tradeMoney') or trade.get('cost')
            try:
                if proceeds_raw is not None:
                    total_amount = abs(float(proceeds_raw)) * fx_rate
                else:
                    total_amount = abs(quantity * price) * fx_rate
            except (ValueError, TypeError):
                total_amount = abs(quantity * price) * fx_rate

            price_converted = price * fx_rate if price else 0.0
            
            try:
                transaction_date = _parse_trade_datetime(trade)
            except Exception:
                transaction_date = datetime.utcnow().isoformat()
            
            # Defensive: ensure ticker is a string
            ticker_raw = trade.get('symbol') or trade.get('ticker') or 'UNKNOWN'
            ticker = str(ticker_raw).upper() if ticker_raw else 'UNKNOWN'
            
            external_id = trade.get('_external_id') or trade.get('tradeID') or trade.get('orderID')
            
            try:
                notes = _build_trade_notes(trade)
            except Exception:
                notes = "IBKR trade import"

            # Extract realized P&L from IBKR (only for SELL trades)
            realized_pnl = None
            if transaction_type == 'SELL':
                # IBKR provides fifoPnlRealized or mtmPnl for closed positions
                pnl_raw = trade.get('fifoPnlRealized') or trade.get('mtmPnl')
                if pnl_raw is not None:
                    try:
                        # Convert to USD if needed using fxRateToBase
                        realized_pnl = float(pnl_raw) * fx_rate
                    except (ValueError, TypeError):
                        logger.warning(f"[IBKR Trades] Failed to parse realized P&L: {pnl_raw}")

            # Skip trades with no meaningful data
            if quantity == 0 and total_amount == 0:
                logger.debug(f"[IBKR Trades] Skipping trade {idx} with zero quantity and amount. Keys found: {list(trade.keys())}")
                continue

            result = await pg.record_transaction(
                user_id=user_id,
                portfolio_id=portfolio_id,
                transaction_type=transaction_type,
                ticker=ticker,
                quantity=quantity,
                price=price_converted,
                total_amount=total_amount,
                transaction_date=transaction_date,
                cost_basis=None,
                realized_gain_loss=realized_pnl,
                lots_affected=None,
                notes=notes,
                org_id=org_id,
                source="ibkr",
                external_id=str(external_id) if external_id else None
            )
            
            if result:
                ingested += 1
            else:
                errors += 1
                
        except Exception as exc:
            errors += 1
            logger.warning(f"[IBKR Trades] Skipping trade {idx} for portfolio {portfolio_id}: {exc}", exc_info=True)
            # Continue processing remaining trades - don't crash on single trade failure

    if errors > 0:
        logger.warning(f"[IBKR Trades] Completed with {errors} errors out of {len(trades)} trades")
    
    return ingested


@router.post("/ibkr/connect", response_model=BrokerConnectionResponse, status_code=status.HTTP_201_CREATED)
async def connect_ibkr(
    req: Request,
    request: IBKRConnectionRequest
):
    """
    Connect IBKR account with IMMEDIATE first sync.

    Flow:
    1. Store encrypted credentials in database
    2. Fetch positions immediately (validates credentials + retrieves data in single call)
    3. Return positions in response

    User sees portfolio in 3-5 seconds total (not hours!).
    """
    # Get user_id from request state (set by middleware)
    user_id = req.state.user_id
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    service = get_ibkr_service()

    if not service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IBKR integration not available - check server configuration"
        )

    # Step 1: VALIDATE TOKEN FIRST (before saving anything)
    logger.info(f"Validating IBKR token for user {user_id} before saving...")

    # Temporarily store credentials for validation
    temp_encrypted_token = service.encrypt_token(request.flex_token)

    # Try to fetch positions to validate token (DON'T save connection yet)
    try:
        # Create temporary connection dict for validation
        temp_connection = {
            'id': 'temp-validation',
            'flex_token_encrypted': temp_encrypted_token,
            'flex_query_id': request.flex_query_id,
            'token_expires_at': request.token_expires_at,
            'created_at': None
        }

        # Monkey-patch service to use temp connection for validation
        original_get_connection = service._get_connection
        async def temp_get_connection(user_id_param):
            return temp_connection
        service._get_connection = temp_get_connection

        # Validate token by attempting to fetch positions
        result = await service.get_user_positions(user_id, use_cache=False)

        # Restore original method
        service._get_connection = original_get_connection

        # Handle both dict (new format with cash) and list (old format) responses
        if isinstance(result, dict):
            positions = result.get('positions', [])
            cash_balance = result.get('cash_balance', 0.0)
            trades = result.get('trades', [])
        else:
            positions = result
            cash_balance = 0.0
            trades = []

        logger.info(
            f"Token validation successful for user {user_id}: "
            f"{len(positions)} positions, ${cash_balance:,.2f} cash"
        )

    except Exception as e:
        logger.error(f"Token validation failed for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid IBKR credentials: {str(e)}"
        )

    # Step 2: Token is valid - NOW save to database
    try:
        encrypted_token = temp_encrypted_token

        # Token expiration (IBKR Flex tokens generally don't expire unless manually revoked)
        token_expires_at = None
        if request.token_expires_at:
            token_expires_at = request.token_expires_at
        # Otherwise, leave as NULL (no expiration)

        pg = await get_postgres_rls_client()
        org_id = getattr(req.state, 'org_id', None) or ''

        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Check for existing connection with same name (multiple connections allowed)
            existing = await conn.fetchrow("""
                SELECT id, status
                FROM broker_connections
                WHERE user_id = $1 AND broker_type = 'ibkr' AND connection_name = $2 AND org_id = $3
            """, user_id, request.connection_name, org_id)

            # If exists with same name and is active, reject (prevent duplicates)
            if existing and existing['status'] == 'active':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"IBKR connection '{request.connection_name}' already exists. Use a different name or disconnect first."
                )

            # Insert or update connection (token already validated above)
            if existing:
                # Reactivate existing connection
                connection_id = await conn.fetchval("""
                    UPDATE broker_connections
                    SET
                        flex_token_encrypted = $1,
                        flex_query_id = $2,
                        token_expires_at = $3,
                        connection_name = $4,
                        status = 'active',
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = $5
                    RETURNING id
                """, encrypted_token, request.flex_query_id, token_expires_at, request.connection_name, existing['id'])
            else:
                # Create new connection with org_id
                connection_id = await conn.fetchval("""
                    INSERT INTO broker_connections (
                        user_id,
                        org_id,
                        broker_type,
                        flex_token_encrypted,
                        flex_query_id,
                        token_expires_at,
                        connection_name,
                        status
                    )
                    VALUES ($1, $2, 'ibkr', $3, $4, $5, $6, 'active')
                    RETURNING id
                """, user_id, org_id, encrypted_token, request.flex_query_id, token_expires_at, request.connection_name)

        logger.info(f"IBKR connection saved for user {user_id} (token already validated)")

        # Step 3: Auto-create portfolio from positions with holdings (using validated data)
        portfolio_id = None
        portfolio_name = f"IBKR - {request.connection_name}"

        if positions:
            # Build holdings data with TICKER-BASED LOT AGGREGATION
            # Multiple IBKR positions for same ticker → ONE holding with multiple lots

            import uuid
            import json
            from datetime import datetime
            from collections import defaultdict

            # Step 0: Use cash balance from IBKR service (from CashReport XML section)
            # Note: Old method tried to extract from positions with assetCategory='CASH',
            # but that requires specific Flex Query configuration
            cash_by_currency = {'USD': cash_balance} if cash_balance > 0 else {}
            total_cash_value = cash_balance

            logger.info(f"Cash balance from IBKR: USD ${cash_balance:,.2f}")

            # Step 1: Group positions by ticker
            ticker_positions = defaultdict(list)
            for pos in positions:
                ticker = pos.get('symbol', 'UNKNOWN')
                ticker = ticker.upper() if ticker else 'UNKNOWN'
                ticker_positions[ticker].append(pos)

            # Step 2: Create ONE holding per unique ticker with multiple lots
            holdings_data = []
            tickers = []
            weights = []
            total_portfolio_value = 0.0

            for ticker, ticker_pos_list in ticker_positions.items():
                # Aggregate metrics for this ticker across all its lots
                lots = []
                ticker_total_quantity = 0.0
                ticker_total_cost_basis = 0.0
                ticker_total_value = 0.0
                ticker_total_pnl = 0.0
                current_price = 0.0

                # Process each position as a lot
                for pos in ticker_pos_list:
                    quantity = pos.get('position', 0)
                    cost_basis_price = pos.get('costBasisPrice', 0)
                    mark_price = pos.get('markPrice', 0)
                    position_value = pos.get('positionValue', 0)
                    pnl = pos.get('fifoPnlUnrealized', 0)

                    # Get currency conversion rate (FX rate to base currency USD)
                    fx_rate = pos.get('fxRateToBase', 1.0)
                    currency = pos.get('currency', 'USD')

                    # Validate numeric fields
                    if not isinstance(quantity, (int, float)) or not isinstance(position_value, (int, float)):
                        logger.warning(f"Skipping lot for {ticker}: invalid numeric fields")
                        continue

                    # Convert all monetary values to USD using fxRateToBase
                    position_value_usd = float(position_value) * float(fx_rate)
                    cost_basis_usd = float(quantity * cost_basis_price) * float(fx_rate) if cost_basis_price and quantity else 0.0
                    pnl_usd = float(pnl) * float(fx_rate) if pnl else 0.0
                    purchase_price = float(cost_basis_price) if cost_basis_price else float(mark_price)

                    # Create lot object with USD-converted values
                    lot = {
                        "lotId": str(uuid.uuid4()),
                        "quantity": float(quantity),
                        "purchasePrice": purchase_price,
                        "purchaseDate": pos.get('reportDate') or pos.get('_fetched_at', datetime.utcnow().isoformat()),
                        "costBasis": cost_basis_usd,  # ✅ Converted to USD
                        "currentValue": position_value_usd,  # ✅ Converted to USD
                        "unrealizedPnL": pnl_usd,  # ✅ Converted to USD
                        "originalCurrency": currency,  # Store for transparency
                        "fxRate": float(fx_rate)  # Store conversion rate used
                    }
                    lots.append(lot)

                    # Aggregate ticker-level metrics (all in USD now)
                    ticker_total_quantity += float(quantity)
                    ticker_total_cost_basis += cost_basis_usd
                    ticker_total_value += position_value_usd
                    ticker_total_pnl += pnl_usd
                    current_price = float(mark_price) if mark_price else current_price

                # Skip if no valid lots
                if not lots:
                    logger.warning(f"No valid lots for {ticker}, skipping")
                    continue

                # Build IBKR metadata (use first position as representative)
                first_pos = ticker_pos_list[0]
                ibkr_metadata = {
                    'source': 'ibkr',
                    'accountId': first_pos.get('accountId'),
                    'currency': first_pos.get('currency'),
                    'assetCategory': first_pos.get('assetCategory'),
                    'subCategory': first_pos.get('subCategory'),
                    'description': first_pos.get('description'),
                    'conid': first_pos.get('conid'),
                    'fxRateToBase': first_pos.get('fxRateToBase'),
                    'multiplier': first_pos.get('multiplier'),
                    'openPrice': first_pos.get('openPrice'),
                    'percentOfNAV': first_pos.get('percentOfNAV'),
                    'side': first_pos.get('side'),
                    # Security identifiers
                    'isin': first_pos.get('isin'),
                    'cusip': first_pos.get('cusip'),
                    'figi': first_pos.get('figi'),
                    'securityID': first_pos.get('securityID'),
                    'securityIDType': first_pos.get('securityIDType'),
                    # Exchange and issuer info
                    'listingExchange': first_pos.get('listingExchange'),
                    'issuer': first_pos.get('issuer'),
                    'issuerCountryCode': first_pos.get('issuerCountryCode'),
                    'reportDate': first_pos.get('reportDate'),
                    # Options/derivatives fields
                    'strike': first_pos.get('strike'),
                    'expiry': first_pos.get('expiry'),
                    'putCall': first_pos.get('putCall'),
                    'underlyingSymbol': first_pos.get('underlyingSymbol'),
                    'underlyingConid': first_pos.get('underlyingConid'),
                    # Trade tracking
                    'levelOfDetail': first_pos.get('levelOfDetail'),
                    'code': first_pos.get('code'),
                }
                # Remove None and empty string values
                ibkr_metadata = {k: v for k, v in ibkr_metadata.items() if v is not None and v != ''}

                # Create aggregated holding with all lots
                holding = {
                    "ticker": ticker,
                    "lots": lots,
                    "currentPrice": current_price,
                    "priceUpdatedAt": first_pos.get('_fetched_at', datetime.utcnow().isoformat()),
                    "totalQuantity": ticker_total_quantity,
                    "totalCostBasis": ticker_total_cost_basis,
                    "totalValue": ticker_total_value,
                    "totalUnrealizedPnL": ticker_total_pnl,
                    "averageCostBasis": ticker_total_cost_basis / ticker_total_quantity if ticker_total_quantity != 0 else 0,
                    "metadata": ibkr_metadata
                }

                holdings_data.append(holding)
                tickers.append(ticker)
                total_portfolio_value += ticker_total_value

            # Step 3: Calculate weights (one per unique ticker)
            # Include cash in denominator so weights sum to < 1.0 when cash is present
            if total_portfolio_value > 0 and tickers:
                total_value_with_cash = total_portfolio_value + total_cash_value
                weights = [
                    holding["totalValue"] / total_value_with_cash if total_value_with_cash > 0 else 0
                    for holding in holdings_data
                ]

                # Create portfolio with holdings
                # Prepare portfolio metadata with cash breakdown
                portfolio_metadata = {'cash_by_currency': cash_by_currency} if cash_by_currency else {}

                async with pg.acquire_with_org_context(user_id, org_id) as conn:
                    portfolio_id = await conn.fetchval("""
                        INSERT INTO portfolios (
                            user_id,
                            name,
                            tickers,
                            weights,
                            value,
                            cash_balance,
                            holdings,
                            metadata,
                            source_type,
                            broker_connection_id,
                            synced_at,
                            is_default
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'broker', $9, NOW(), false)
                        RETURNING id
                    """, user_id, portfolio_name, tickers, weights,
                         total_portfolio_value + total_cash_value,  # Include cash in total value
                         total_cash_value,  # cash_balance
                         json.dumps(holdings_data),
                         json.dumps(portfolio_metadata),  # metadata with cash_by_currency
                         connection_id)

                logger.info(f"Auto-created portfolio {portfolio_id} with {len(holdings_data)} holdings from IBKR")

        # Upsert IBKR trades into transaction ledger (optional, best effort)
        if portfolio_id and trades:
            try:
                ingested = await _ingest_ibkr_trades(
                    pg=pg,
                    user_id=user_id,
                    portfolio_id=str(portfolio_id),
                    trades=trades,
                    org_id=org_id
                )
                logger.info(f"[IBKR Trades] Ingested {ingested} trade(s) for portfolio {portfolio_id}")
            except Exception as exc:
                logger.warning(f"[IBKR Trades] Failed to ingest trades for portfolio {portfolio_id}: {exc}", exc_info=True)

        # Return success with positions and portfolio info
        return BrokerConnectionResponse(
            status="connected",
            message=f"IBKR account connected successfully. {len(positions)} positions loaded.",
            positions=positions,
            positions_count=len(positions),
            connection_id=str(connection_id),
            portfolio_id=str(portfolio_id) if portfolio_id else None,
            portfolio_name=portfolio_name if portfolio_id else None
        )

    except ValueError as e:
        # Credential validation errors (invalid token/query ID)
        logger.error(f"Invalid IBKR credentials for user {user_id}: {e}")

        # Delete the connection since credentials are invalid
        async with pg.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    DELETE FROM broker_connections WHERE id = $1
                """, connection_id)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid IBKR credentials. Please check your Current Token and Query ID."
        )

    except Exception as e:
        error_str = str(e)
        logger.error(f"First sync failed for user {user_id}: {error_str}")

        # Check for rate limiting error
        if "Code=1018" in error_str or "Too many requests" in error_str:
            # Mark connection as error with specific rate limit message
            async with pg.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE broker_connections
                        SET status = 'error', error_message = $1
                        WHERE id = $2
                    """, "Rate limit exceeded. Please wait a moment and try refreshing.", connection_id)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="IBKR rate limit exceeded. Please wait a moment and try again."
            )

        # Generic error - mark connection as error but don't fail completely
        async with pg.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    UPDATE broker_connections
                    SET status = 'error', error_message = $1
                    WHERE id = $2
                """, error_str[:500], connection_id)

        # Return partial success (connection saved, sync failed)
        return BrokerConnectionResponse(
            status="connected_with_error",
            message="Connection saved, but initial sync failed. Will retry on next scheduled sync.",
            positions=None,
            positions_count=0,
            connection_id=str(connection_id)
        )


@router.get("/ibkr/positions", response_model=List[Dict[str, Any]])
async def get_positions(req: Request):
    """
    Get user's IBKR positions.

    Returns cached data if available (50ms response).
    Fetches from IBKR if cache expired (3-5s response).
    """
    user_id = req.state.user_id
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    service = get_ibkr_service()

    if not service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IBKR integration not available"
        )

    try:
        result = await service.get_user_positions(user_id)

        # Handle both dict (new format with cash) and list (old format) responses
        if isinstance(result, dict):
            positions = result.get('positions', [])
        else:
            positions = result

        return positions

    except ValueError as e:
        # No IBKR connection found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get positions for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch positions from IBKR. Please try again later."
        )


@router.post("/ibkr/sync/{portfolio_id}", status_code=status.HTTP_200_OK)
async def manual_sync_portfolio(
    portfolio_id: str,
    req: Request,
):
    """
    Manually sync IBKR positions for a specific portfolio.

    Flow:
    1. Verify portfolio belongs to user and is IBKR-linked
    2. Force fresh fetch from IBKR (bypass cache)
    3. Update portfolio with new positions
    4. Return sync result
    """
    user_id = req.state.user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    org_id = getattr(req.state, 'org_id', None) or ''

    service = get_ibkr_service()
    if not service.enabled:
        raise HTTPException(status_code=503, detail="IBKR integration unavailable")

    pg = await get_postgres_rls_client()

    # Verify portfolio is IBKR-linked with org_id check
    # Note: For personal workspace, org_id is NULL in DB but '' in request context
    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        if org_id:
            # Org workspace: exact match on org_id
            portfolio = await conn.fetchrow("""
                SELECT id, broker_connection_id, source_type, name
                FROM portfolios
                WHERE id = $1 AND org_id = $2
            """, portfolio_id, org_id)
        else:
            # Personal workspace: org_id is NULL, match by user_id
            portfolio = await conn.fetchrow("""
                SELECT id, broker_connection_id, source_type, name
                FROM portfolios
                WHERE id = $1 AND user_id = $2 AND org_id IS NULL
            """, portfolio_id, user_id)

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        if portfolio['source_type'] != 'broker' or not portfolio['broker_connection_id']:
            raise HTTPException(
                status_code=400,
                detail="Portfolio is not linked to IBKR"
            )

    try:
        # Force fresh fetch (bypass 6-hour cache)
        logger.info(f"[IBKR Sync] Fetching positions for user {user_id}, portfolio {portfolio_id}")
        result = await service.get_user_positions(user_id, use_cache=False)

        # Handle both dict (new format with cash) and list (old format) responses
        if isinstance(result, dict):
            positions = result.get('positions', [])
            cash_balance = result.get('cash_balance', 0.0)
            trades = result.get('trades', [])
            logger.info(f"[IBKR Sync] Retrieved {len(positions)} positions, ${cash_balance:,.2f} cash")
        else:
            positions = result
            cash_balance = 0.0
            trades = []
            logger.info(f"[IBKR Sync] Retrieved {len(positions)} positions (legacy format)")

        if not positions:
            logger.warning(f"[IBKR Sync] No positions found for user {user_id}")
            return {
                "status": "success",
                "message": "No positions found in IBKR account",
                "synced_at": datetime.utcnow().isoformat(),
                "position_count": 0
            }

        # Update portfolio with fresh positions - SAME LOGIC AS connect_ibkr
        # CRITICAL: IBKR returns 'symbol', not 'ticker'
        # Implement ticker-based lot aggregation for consistency

        import uuid
        from collections import defaultdict

        # Step 1: Group positions by ticker (symbol)
        ticker_positions = defaultdict(list)
        for pos in positions:
            ticker = pos.get('symbol', 'UNKNOWN')
            ticker = ticker.upper() if ticker else 'UNKNOWN'
            ticker_positions[ticker].append(pos)

        logger.info(f"[IBKR Sync] Grouped {len(positions)} positions into {len(ticker_positions)} unique tickers")

        # Step 2: Create ONE holding per unique ticker with multiple lots
        holdings_data = []
        tickers = []
        total_portfolio_value = 0.0

        for ticker, ticker_pos_list in ticker_positions.items():
            # Aggregate metrics for this ticker across all its lots
            lots = []
            ticker_total_quantity = 0.0
            ticker_total_cost_basis = 0.0
            ticker_total_value = 0.0
            ticker_total_pnl = 0.0
            current_price = 0.0

            # Process each position as a lot
            for pos in ticker_pos_list:
                quantity = pos.get('position', 0)
                cost_basis_price = pos.get('costBasisPrice', 0)
                mark_price = pos.get('markPrice', 0)
                position_value = pos.get('positionValue', 0)
                pnl = pos.get('fifoPnlUnrealized', 0)

                # Get currency conversion rate (FX rate to base currency USD)
                fx_rate = pos.get('fxRateToBase', 1.0)
                currency = pos.get('currency', 'USD')
                
                # Debug logging for FX conversion
                if currency != 'USD':
                    logger.info(f"[IBKR Sync] FX conversion for {ticker}: currency={currency}, fxRateToBase={fx_rate}, positionValue={position_value} -> USD={float(position_value) * float(fx_rate):.2f}")

                # Validate numeric fields
                if not isinstance(quantity, (int, float)) or not isinstance(position_value, (int, float)):
                    logger.warning(f"Skipping lot for {ticker}: invalid numeric fields")
                    continue

                # Convert all monetary values to USD using fxRateToBase
                position_value_usd = float(position_value) * float(fx_rate)
                cost_basis_usd = float(quantity * cost_basis_price) * float(fx_rate) if cost_basis_price and quantity else 0.0
                pnl_usd = float(pnl) * float(fx_rate) if pnl else 0.0
                purchase_price = float(cost_basis_price) if cost_basis_price else float(mark_price)

                # Create lot object with USD-converted values
                lot = {
                    "lotId": str(uuid.uuid4()),
                    "quantity": float(quantity),
                    "purchasePrice": purchase_price,
                    "purchaseDate": pos.get('reportDate') or pos.get('_fetched_at', datetime.utcnow().isoformat()),
                    "costBasis": cost_basis_usd,  # Converted to USD
                    "currentValue": position_value_usd,  # Converted to USD
                    "unrealizedPnL": pnl_usd,  # Converted to USD
                    "originalCurrency": currency,  # Store for transparency
                    "fxRate": float(fx_rate)  # Store conversion rate used
                }
                lots.append(lot)

                # Aggregate ticker-level metrics (all in USD now)
                ticker_total_quantity += float(quantity)
                ticker_total_cost_basis += cost_basis_usd
                ticker_total_value += position_value_usd
                ticker_total_pnl += pnl_usd
                current_price = float(mark_price) if mark_price else current_price

            # Skip if no valid lots
            if not lots:
                logger.warning(f"No valid lots for {ticker}, skipping")
                continue

            # Build IBKR metadata (use first position as representative)
            first_pos = ticker_pos_list[0]
            ibkr_metadata = {
                'source': 'ibkr',
                'accountId': first_pos.get('accountId'),
                'currency': first_pos.get('currency'),
                'assetCategory': first_pos.get('assetCategory'),
                'subCategory': first_pos.get('subCategory'),
                'description': first_pos.get('description'),
                'conid': first_pos.get('conid'),
                'fxRateToBase': first_pos.get('fxRateToBase'),
                'multiplier': first_pos.get('multiplier'),
                'openPrice': first_pos.get('openPrice'),
                'percentOfNAV': first_pos.get('percentOfNAV'),
                'side': first_pos.get('side'),
            }
            # Remove None and empty string values
            ibkr_metadata = {k: v for k, v in ibkr_metadata.items() if v is not None and v != ''}

            # Create aggregated holding with all lots
            holding = {
                "ticker": ticker,
                "lots": lots,
                "currentPrice": current_price,
                "priceUpdatedAt": first_pos.get('_fetched_at', datetime.utcnow().isoformat()),
                "totalQuantity": ticker_total_quantity,
                "totalCostBasis": ticker_total_cost_basis,
                "totalValue": ticker_total_value,
                "totalUnrealizedPnL": ticker_total_pnl,
                "averageCostBasis": ticker_total_cost_basis / ticker_total_quantity if ticker_total_quantity != 0 else 0,
                "metadata": ibkr_metadata
            }

            holdings_data.append(holding)
            tickers.append(ticker)
            total_portfolio_value += ticker_total_value
            
            # Debug: log the holding being saved
            if holding.get('metadata', {}).get('currency') and holding['metadata']['currency'] != 'USD':
                logger.info(f"[IBKR Sync] Saving {ticker}: totalValue={ticker_total_value:.2f} USD (currency={holding['metadata'].get('currency')})")

        logger.info(f"[IBKR Sync] Created {len(holdings_data)} holdings with {len(tickers)} tickers")
        logger.info(f"[IBKR Sync] Total portfolio value: ${total_portfolio_value:,.2f}")

        # Step 3: Calculate weights based on market values (not equal weights)
        if total_portfolio_value > 0 and tickers:
            weights = [
                holding["totalValue"] / total_portfolio_value if total_portfolio_value > 0 else 0
                for holding in holdings_data
            ]
        else:
            weights = []

        # Update portfolio (user_id MUST come first, then portfolio_id)
        # ATOMIC UPDATE: Write holdings AND cash in single transaction to avoid race condition
        await pg.update_portfolio(
            user_id=user_id,
            portfolio_id=portfolio_id,
            tickers=tickers,
            weights=weights,
            holdings=holdings_data,
            cash_balance=cash_balance  # Include cash to prevent race condition
        )
        logger.info(f"[IBKR Sync] Successfully updated portfolio {portfolio_id} with {len(tickers)} tickers, {len(holdings_data)} holdings, and ${cash_balance:,.2f} cash")

        # Update synced_at timestamp separately (metadata only)
        # Note: portfolios uses NULL for personal workspace, not empty string
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            if org_id:
                await conn.execute("""
                    UPDATE portfolios
                    SET synced_at = $1
                    WHERE id = $2 AND org_id = $3
                """, datetime.utcnow(), portfolio_id, org_id)
            else:
                await conn.execute("""
                    UPDATE portfolios
                    SET synced_at = $1
                    WHERE id = $2 AND user_id = $3 AND org_id IS NULL
                """, datetime.utcnow(), portfolio_id, user_id)

        logger.info(f"[IBKR Sync] Portfolio {portfolio_id} synced with {len(positions)} positions")

        # Ingest trades (best effort, deduped by external_id)
        if trades:
            try:
                ingested = await _ingest_ibkr_trades(
                    pg=pg,
                    user_id=user_id,
                    portfolio_id=portfolio_id,
                    trades=trades,
                    org_id=org_id
                )
                logger.info(f"[IBKR Trades] Ingested {ingested} trade(s) during manual sync for portfolio {portfolio_id}")
            except Exception as exc:
                logger.warning(f"[IBKR Trades] Failed to ingest trades for portfolio {portfolio_id}: {exc}", exc_info=True)

        return {
            "status": "success",
            "message": f"Synced {len(positions)} position(s) from IBKR",
            "synced_at": datetime.utcnow().isoformat(),
            "position_count": len(positions)
        }

    except ValueError as e:
        logger.error(f"[IBKR Sync] No connection found for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[IBKR Sync] Manual sync failed for portfolio {portfolio_id}: {e}", exc_info=True)
        import traceback
        logger.error(f"[IBKR Sync] Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=502, detail=f"Failed to sync from IBKR: {str(e)}")


@router.get("/ibkr/status", response_model=BrokerConnectionStatusResponse)
async def get_connection_status(req: Request):
    """Get current IBKR connection status."""
    user_id = req.state.user_id
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    org_id = getattr(req.state, 'org_id', None) or ''
    pg = await get_postgres_rls_client()

    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        connection = await conn.fetchrow("""
            SELECT
                status,
                last_sync_at,
                error_message,
                token_expires_at
            FROM broker_connections
            WHERE user_id = $1 AND broker_type = 'ibkr' AND org_id = $2
        """, user_id, org_id)

    if not connection:
        return BrokerConnectionStatusResponse(
            connected=False,
            broker_type="ibkr",
            status="not_connected",
            last_sync_at=None,
            error_message=None,
            token_expires_at=None
        )

    return BrokerConnectionStatusResponse(
        connected=connection['status'] == 'active',
        broker_type="ibkr",
        status=connection['status'],
        last_sync_at=connection['last_sync_at'].isoformat() if connection['last_sync_at'] else None,
        error_message=connection['error_message'],
        token_expires_at=connection['token_expires_at'].isoformat() if connection['token_expires_at'] else None
    )


@router.delete("/ibkr/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_ibkr(req: Request):
    """Disconnect IBKR account and clear cached data. Properly scoped to the current organization workspace."""
    user_id = req.state.user_id
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    org_id = getattr(req.state, 'org_id', None) or ''
    pg = await get_postgres_rls_client()

    async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
        result = await conn.execute("""
            UPDATE broker_connections
            SET status = 'inactive', updated_at = NOW()
            WHERE user_id = $1 AND broker_type = 'ibkr' AND status = 'active' AND org_id = $2
        """, user_id, org_id)

        # Check if any rows were updated
        if result == "UPDATE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active IBKR connection found"
            )

    # Clear cached positions
    try:
        cache_key = f"ibkr_positions:{user_id}"
        cache.redis.delete(cache_key) if cache.enabled else None
    except Exception as e:
        logger.warning(f"Failed to clear cache for {user_id}: {e}")

    logger.info(f"IBKR connection disconnected for user {user_id}")

    return None
