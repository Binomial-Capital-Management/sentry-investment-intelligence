"""
Market data endpoints for Binomial Risk Analyst.
Handles public market data like Fear & Greed Index.

Following CODING_RULES.md: KISS, MVP first, no hardcoding.
"""

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, date
from collections import defaultdict
import pytz

from core.database import get_postgres_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v6/market")


def get_market_status() -> Dict[str, Any]:
    """
    Determine current US market status based on Eastern Time.

    Returns:
        Dict with isOpen (bool) and statusText (str)
    """
    et_tz = pytz.timezone('America/New_York')
    now_et = datetime.now(et_tz)

    # Check if weekend
    weekday = now_et.weekday()  # 0=Monday, 6=Sunday
    if weekday >= 5:  # Saturday or Sunday
        return {"isOpen": False, "statusText": "Market Closed"}

    # Market hours: 9:30 AM - 4:00 PM ET
    market_open_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    if market_open_time <= now_et < market_close_time:
        return {"isOpen": True, "statusText": "Market Open"}
    else:
        return {"isOpen": False, "statusText": "Market Closed"}


@router.post("/fear-greed-index/refresh")
async def refresh_fear_greed_index() -> Dict[str, Any]:
    """
    Trigger manual refresh of Fear & Greed Index data.
    Note: In production, this invokes the Lambda function.
    For development, implements a direct fetch from RapidAPI.

    Returns:
        Dict with refresh status and metrics

    Raises:
        HTTPException: If refresh fails
    """
    try:
        import boto3
        import os

        # Check if we're in development mode (skip Lambda, use direct fetch)
        is_dev = os.getenv("DEV_SECRET") is not None or os.getenv("ENVIRONMENT", "").lower() in ("dev", "development", "local")
        
        # Try Lambda first if AWS_REGION is set AND we're not in dev mode
        aws_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))

        if aws_region and not is_dev:
            try:
                # Production: Try to invoke Lambda
                lambda_client = boto3.client('lambda', region_name=aws_region)

                response = lambda_client.invoke(
                    FunctionName='fear-greed-index',
                    InvocationType='RequestResponse',  # Synchronous
                    Payload=b'{}'
                )

                import json
                result = json.loads(response['Payload'].read())

                return {
                    "status": "success",
                    "message": "Fear & Greed Index refreshed via Lambda",
                    "lambda_response": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as lambda_error:
                # Lambda not found or error - fallback to direct fetch
                logger.warning(f"Lambda invocation failed, using direct fetch: {lambda_error}")

        # Development or Lambda fallback: Direct fetch from RapidAPI
        logger.info("Running direct RapidAPI FGI fetch")

        import httpx

        rapidapi_key = os.getenv('RAPIDAPI_FGI_KEY')
        if not rapidapi_key:
            raise HTTPException(status_code=500, detail="RAPIDAPI_FGI_KEY not configured")

        # Fetch from RapidAPI
        url = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi"
        headers = {
            "x-rapidapi-host": "fear-and-greed-index.p.rapidapi.com",
            "x-rapidapi-key": rapidapi_key
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            fgi_data = response.json()

        # Store in database
        pg = await get_postgres_client()

        async with pg.pool.acquire() as conn:
            # Extract data
            fgi_now = fgi_data["fgi"]["now"]
            fgi_prev = fgi_data["fgi"].get("previousClose")
            last_updated = datetime.fromisoformat(
                fgi_data["lastUpdated"]["humanDate"].replace("Z", "+00:00")
            )

            # Convert to naive datetime for PostgreSQL TIMESTAMP
            last_updated_naive = last_updated.replace(tzinfo=None)

            # Insert new record
            await conn.execute(
                """
                INSERT INTO fear_greed_index (
                    value,
                    value_text,
                    previous_close_value,
                    previous_close_text,
                    last_updated,
                    fetched_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                fgi_now["value"],
                fgi_now["valueText"],
                fgi_prev["value"] if fgi_prev else None,
                fgi_prev["valueText"] if fgi_prev else None,
                last_updated_naive
            )

        logger.info(f"Direct fetch complete: FGI value={fgi_now['value']}, sentiment={fgi_now['valueText']}")

        return {
            "status": "success",
            "message": "Fear & Greed Index refreshed (direct fetch)",
            "fgi_value": fgi_now["value"],
            "fgi_sentiment": fgi_now["valueText"],
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh Fear & Greed Index: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh Fear & Greed Index: {str(e)}"
        )


@router.get("/fear-greed-index")
async def get_fear_greed_index() -> Dict[str, Any]:
    """
    Get the latest Fear & Greed Index data from database.

    Returns:
        Dict containing FGI value, text, and timestamp

    Raises:
        HTTPException: If no data found or database error
    """
    try:
        pg = await get_postgres_client()

        async with pg.pool.acquire() as conn:
            # Get the most recent FGI data
            row = await conn.fetchrow("""
                SELECT
                    value,
                    value_text,
                    previous_close_value,
                    previous_close_text,
                    last_updated,
                    fetched_at
                FROM fear_greed_index
                ORDER BY fetched_at DESC
                LIMIT 1
            """)

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No Fear & Greed Index data available. Scheduler may not have run yet."
                )

            # Get current market status and date in ET
            market_status = get_market_status()
            et_tz = pytz.timezone('America/New_York')
            now_et = datetime.now(et_tz)

            return {
                "fgi": {
                    "now": {
                        "value": row["value"],
                        "valueText": row["value_text"]
                    },
                    "previousClose": {
                        "value": row["previous_close_value"],
                        "valueText": row["previous_close_text"]
                    } if row["previous_close_value"] is not None else None
                },
                "lastUpdated": {
                    "humanDate": row["last_updated"].isoformat() if row["last_updated"] else None,
                    "fetchedAt": row["fetched_at"].isoformat() if row["fetched_at"] else None
                },
                "marketStatus": {
                    "isOpen": market_status["isOpen"],
                    "statusText": market_status["statusText"],
                    "currentDate": now_et.strftime("%b %d, %Y"),
                    "currentTime": now_et.strftime("%I:%M %p ET"),
                    "timezone": "America/New_York"
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Fear & Greed Index: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Fear & Greed Index: {str(e)}"
        )


@router.get("/earnings-calendar")
async def get_earnings_calendar(
    symbol: Optional[str] = Query(None, description="Filter by stock symbol (e.g., AAPL)")
) -> Dict[str, Any]:
    """
    Get upcoming earnings calendar data, grouped by date.

    Args:
        symbol: Optional stock symbol to filter results

    Returns:
        Dict with calendar grouped by date and summary stats

    Raises:
        HTTPException: If database error occurs
    """
    try:
        pg = await get_postgres_client()

        async with pg.pool.acquire() as conn:
            # Get today's date for filtering (only show current/future earnings)
            today = datetime.now().date()
            
            # Build query based on symbol filter
            if symbol:
                query = """
                    SELECT
                        symbol,
                        date,
                        eps_actual,
                        eps_estimated,
                        revenue_actual,
                        revenue_estimated,
                        last_updated
                    FROM earnings_calendar
                    WHERE symbol = $1 AND date >= $2
                    ORDER BY date ASC, symbol ASC
                """
                rows = await conn.fetch(query, symbol.upper(), today)
            else:
                query = """
                    SELECT
                        symbol,
                        date,
                        eps_actual,
                        eps_estimated,
                        revenue_actual,
                        revenue_estimated,
                        last_updated
                    FROM earnings_calendar
                    WHERE date >= $1
                    ORDER BY date ASC, symbol ASC
                """
                rows = await conn.fetch(query, today)

            if not rows:
                return {
                    "calendar": {},
                    "summary": {
                        "totalEvents": 0,
                        "dateRange": None,
                        "lastFetched": None
                    }
                }

            # Group earnings by date
            calendar = defaultdict(lambda: {"date": None, "count": 0, "earnings": []})

            for row in rows:
                date_str = row["date"].isoformat()

                if calendar[date_str]["date"] is None:
                    calendar[date_str]["date"] = date_str

                calendar[date_str]["count"] += 1
                calendar[date_str]["earnings"].append({
                    "symbol": row["symbol"],
                    "date": date_str,
                    "epsActual": float(row["eps_actual"]) if row["eps_actual"] is not None else None,
                    "epsEstimated": float(row["eps_estimated"]) if row["eps_estimated"] is not None else None,
                    "revenueActual": int(row["revenue_actual"]) if row["revenue_actual"] is not None else None,
                    "revenueEstimated": int(row["revenue_estimated"]) if row["revenue_estimated"] is not None else None,
                    "lastUpdated": row["last_updated"].isoformat() if row["last_updated"] else None
                })

            # Convert defaultdict to regular dict
            calendar_dict = dict(calendar)

            # Get date range
            first_date = rows[0]["date"].isoformat()
            last_date = rows[-1]["date"].isoformat()

            # Get most recent fetch timestamp
            last_fetched = max(row["last_updated"] for row in rows if row["last_updated"])

            return {
                "calendar": calendar_dict,
                "summary": {
                    "totalEvents": len(rows),
                    "dateRange": {
                        "from": first_date,
                        "to": last_date
                    },
                    "lastFetched": last_fetched.isoformat() if last_fetched else None,
                    "filterApplied": {"symbol": symbol} if symbol else None
                }
            }

    except Exception as e:
        logger.error(f"Error fetching earnings calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch earnings calendar: {str(e)}"
        )


@router.post("/earnings-calendar/refresh")
async def refresh_earnings_calendar() -> Dict[str, Any]:
    """
    Trigger manual refresh of earnings calendar data.
    Note: In production, this invokes the Lambda function.
    For development, you can implement a local fetch.

    Returns:
        Dict with refresh status and metrics

    Raises:
        HTTPException: If refresh fails
    """
    try:
        import boto3
        import os

        # Try Lambda first if AWS_REGION is set
        aws_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))

        if aws_region:
            try:
                # Production: Try to invoke Lambda
                lambda_client = boto3.client('lambda', region_name=aws_region)

                response = lambda_client.invoke(
                    FunctionName='earnings-calendar-updater',
                    InvocationType='RequestResponse',  # Synchronous
                    Payload=b'{}'
                )

                import json
                result = json.loads(response['Payload'].read())

                return {
                    "status": "success",
                    "message": "Earnings calendar refreshed via Lambda",
                    "lambda_response": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as lambda_error:
                # Lambda not found or error - fallback to direct fetch
                logger.warning(f"Lambda invocation failed, using direct fetch: {lambda_error}")

        # Development or Lambda fallback: Direct fetch from FMP API
        logger.info("Running direct FMP fetch")

        import httpx
        from datetime import timedelta

        fmp_api_key = os.getenv('FMP_API_KEY')
        if not fmp_api_key:
            raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")

        # Calculate date range (today to +60 days)
        # FMP has a 4000 item limit - when exceeded, it drops early dates
        # So we make 4 requests of 15 days each to avoid hitting the limit
        today = datetime.now().date()
        from_date = today
        to_date = today + timedelta(days=60)

        url = "https://financialmodelingprep.com/stable/earnings-calendar"
        
        # Split into 4 chunks of ~15 days
        chunk_size = 15
        date_ranges = []
        current = from_date
        while current < to_date:
            chunk_end = min(current + timedelta(days=chunk_size), to_date)
            date_ranges.append((current, chunk_end))
            current = chunk_end
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            all_data = []
            for chunk_start, chunk_end in date_ranges:
                params = {
                    'from': chunk_start.strftime('%Y-%m-%d'),
                    'to': chunk_end.strftime('%Y-%m-%d'),
                    'apikey': fmp_api_key
                }
                response = await client.get(url, params=params)
                response.raise_for_status()
                all_data.extend(response.json())
            
            # Dedupe by symbol+date
            seen = set()
            earnings_data = []
            for e in all_data:
                key = (e.get('symbol'), e.get('date'))
                if key not in seen:
                    seen.add(key)
                    earnings_data.append(e)

        # Filter to only US-listed stocks (clean symbols)
        def is_us_listed(symbol: str) -> bool:
            """Filter to only US-listed stocks - removes foreign exchanges, OTC, ADRs, and preferred stocks"""
            if not symbol:
                return False
            # Remove foreign exchanges (symbols with dots: .TA, .V, .T, .HK, etc.)
            if '.' in symbol:
                return False
            # Remove OTC/Pink Sheets (ending in F)
            if symbol.endswith('F'):
                return False
            # Remove ADRs (ending in Y)
            if symbol.endswith('Y'):
                return False
            # Remove preferred stocks (contain hyphen like BAC-PB, WFC-PL, JPM-PC, etc.)
            if '-' in symbol:
                return False
            return True

        original_count = len(earnings_data)
        earnings_data = [e for e in earnings_data if is_us_listed(e.get('symbol', ''))]

        # Note: Removed estimate filter - many near-term earnings don't have estimates yet
        # and we still want to show them on the calendar

        # Filter to date range (today to +60 days) - client-side since FMP ignores date params
        def is_in_date_range(date_str: str) -> bool:
            """Filter to earnings within our target date range"""
            try:
                if isinstance(date_str, str):
                    dt = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    dt = date_str
                return from_date <= dt <= to_date
            except:
                return False

        earnings_data = [e for e in earnings_data if is_in_date_range(e.get('date', ''))]

        # Filter to only weekdays (Monday-Friday)
        def is_weekday(date_str: str) -> bool:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                return dt.weekday() < 5  # 0-4 = Mon-Fri, 5-6 = Sat-Sun
            except:
                return False

        earnings_data = [e for e in earnings_data if is_weekday(e.get('date', ''))]

        logger.info(f"Filtered earnings: {original_count} total → {len(earnings_data)} US-listed in date range {from_date} to {to_date} (weekdays only)")

        # Get database connection
        from core.database.postgres_client import get_postgres_client
        pg = await get_postgres_client()

        async with pg.pool.acquire() as conn:
            # Delete old data
            await conn.execute("DELETE FROM earnings_calendar")

            # Insert new data
            insert_query = """
            INSERT INTO earnings_calendar
            (symbol, date, eps_actual, eps_estimated, revenue_actual, revenue_estimated, last_updated)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (symbol, date) DO UPDATE
            SET eps_actual = EXCLUDED.eps_actual,
                eps_estimated = EXCLUDED.eps_estimated,
                revenue_actual = EXCLUDED.revenue_actual,
                revenue_estimated = EXCLUDED.revenue_estimated,
                last_updated = NOW()
            """

            inserted = 0
            for event in earnings_data:
                try:
                    # Parse date string to date object
                    date_str = event.get('date')
                    if date_str:
                        if isinstance(date_str, str):
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                        else:
                            date_obj = date_str
                    else:
                        continue  # Skip if no date

                    await conn.execute(
                        insert_query,
                        event.get('symbol'),
                        date_obj,
                        event.get('epsActual'),
                        event.get('epsEstimated'),
                        event.get('revenueActual'),
                        event.get('revenueEstimated')
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(f"Failed to insert {event.get('symbol')}: {e}")

        logger.info(f"Direct fetch complete: {inserted} events inserted")

        return {
            "status": "success",
            "message": f"Earnings calendar refreshed (direct fetch)",
            "events_inserted": inserted,
            "date_range": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh earnings calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh earnings calendar: {str(e)}"
        )


@router.get("/ipo-calendar")
async def get_ipo_calendar(
    exchange: Optional[str] = Query(None, description="Filter by exchange (e.g., NYSE, NASDAQ)")
) -> Dict[str, Any]:
    """
    Get IPO calendar data, grouped by date.

    Args:
        exchange: Optional exchange to filter results

    Returns:
        Dict with calendar grouped by date and summary stats

    Raises:
        HTTPException: If database error occurs
    """
    try:
        pg = await get_postgres_client()

        async with pg.pool.acquire() as conn:
            # Build query based on exchange filter
            if exchange:
                query = """
                    SELECT
                        symbol,
                        date,
                        company,
                        exchange,
                        actions,
                        shares,
                        price_range,
                        market_cap,
                        last_updated
                    FROM ipo_calendar
                    WHERE exchange = $1
                    ORDER BY date DESC, symbol ASC
                """
                rows = await conn.fetch(query, exchange.upper())
            else:
                query = """
                    SELECT
                        symbol,
                        date,
                        company,
                        exchange,
                        actions,
                        shares,
                        price_range,
                        market_cap,
                        last_updated
                    FROM ipo_calendar
                    ORDER BY date DESC, symbol ASC
                """
                rows = await conn.fetch(query)

            if not rows:
                return {
                    "calendar": {},
                    "summary": {
                        "totalEvents": 0,
                        "dateRange": None,
                        "lastFetched": None
                    }
                }

            # Group IPOs by date
            calendar = defaultdict(lambda: {"date": None, "count": 0, "ipos": []})

            for row in rows:
                date_str = row["date"].isoformat()

                if calendar[date_str]["date"] is None:
                    calendar[date_str]["date"] = date_str

                calendar[date_str]["count"] += 1
                calendar[date_str]["ipos"].append({
                    "symbol": row["symbol"],
                    "date": date_str,
                    "company": row["company"],
                    "exchange": row["exchange"],
                    "actions": row["actions"],
                    "shares": int(row["shares"]) if row["shares"] is not None else None,
                    "priceRange": row["price_range"],
                    "marketCap": int(row["market_cap"]) if row["market_cap"] is not None else None,
                    "lastUpdated": row["last_updated"].isoformat() if row["last_updated"] else None
                })

            # Convert defaultdict to regular dict
            calendar_dict = dict(calendar)

            # Get date range
            first_date = rows[0]["date"].isoformat()
            last_date = rows[-1]["date"].isoformat()

            # Get most recent fetch timestamp
            last_fetched = max(row["last_updated"] for row in rows if row["last_updated"])

            return {
                "calendar": calendar_dict,
                "summary": {
                    "totalEvents": len(rows),
                    "dateRange": {
                        "from": last_date,  # Most recent first
                        "to": first_date
                    },
                    "lastFetched": last_fetched.isoformat() if last_fetched else None,
                    "filterApplied": {"exchange": exchange} if exchange else None
                }
            }

    except Exception as e:
        logger.error(f"Error fetching IPO calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch IPO calendar: {str(e)}"
        )


@router.post("/ipo-calendar/refresh")
async def refresh_ipo_calendar() -> Dict[str, Any]:
    """
    Trigger manual refresh of IPO calendar data.
    Development mode: Direct fetch from FMP API

    Returns:
        Dict with refresh status and metrics

    Raises:
        HTTPException: If refresh fails
    """
    try:
        import httpx
        import os

        logger.info("Running direct FMP IPO fetch")

        fmp_api_key = os.getenv('FMP_API_KEY')
        if not fmp_api_key:
            raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")

        # Fetch from FMP
        url = "https://financialmodelingprep.com/stable/ipos-calendar"
        params = {'apikey': fmp_api_key}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            ipo_data = response.json()

        # Filter to only US exchanges
        def is_us_listed(symbol: str, exchange: str) -> bool:
            """Filter to only US exchanges"""
            if not symbol or not exchange:
                return False
            # Keep only US exchanges
            us_exchanges = ['NYSE', 'NASDAQ', 'NYSEAMERICAN', 'BATS']
            if exchange not in us_exchanges:
                return False
            # Remove symbols with dots (foreign exchanges)
            if '.' in symbol:
                return False
            return True

        original_count = len(ipo_data)
        ipo_data = [e for e in ipo_data if is_us_listed(e.get('symbol', ''), e.get('exchange', ''))]

        # Filter to only show last 3 months
        from datetime import timedelta
        today = datetime.utcnow().date()
        three_months_ago = today - timedelta(days=90)

        def is_in_date_range(date_str: str) -> bool:
            """Filter to recent IPOs within last 3 months"""
            try:
                if isinstance(date_str, str):
                    dt = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    dt = date_str
                return three_months_ago <= dt <= today
            except:
                return False

        after_us_filter = len(ipo_data)
        ipo_data = [e for e in ipo_data if is_in_date_range(e.get('date', ''))]

        logger.info(f"Filtered IPOs: {original_count} total → {after_us_filter} US-listed → {len(ipo_data)} recent (last 3mo)")

        # Get database connection
        from core.database.postgres_client import get_postgres_client
        pg = await get_postgres_client()

        async with pg.pool.acquire() as conn:
            # Delete old data
            await conn.execute("DELETE FROM ipo_calendar")

            # Insert new data
            insert_query = """
            INSERT INTO ipo_calendar
            (symbol, date, company, exchange, actions, shares, price_range, market_cap, last_updated)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """

            inserted = 0
            for event in ipo_data:
                try:
                    # Parse date string to date object
                    date_str = event.get('date')
                    if date_str:
                        if isinstance(date_str, str):
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                        else:
                            date_obj = date_str
                    else:
                        continue  # Skip if no date

                    await conn.execute(
                        insert_query,
                        event.get('symbol'),
                        date_obj,
                        event.get('company'),
                        event.get('exchange'),
                        event.get('actions'),
                        event.get('shares'),
                        event.get('priceRange'),
                        event.get('marketCap')
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(f"Failed to insert {event.get('symbol')}: {e}")

        logger.info(f"Direct fetch complete: {inserted} IPO events inserted")

        return {
            "status": "success",
            "message": f"IPO calendar refreshed (direct fetch)",
            "events_inserted": inserted,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh IPO calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh IPO calendar: {str(e)}"
        )
