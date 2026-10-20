"""
Earnings & IPO Calendar Lambda Function
Fetches 60 days of earnings calendar and IPO calendar from FMP API and stores in RDS PostgreSQL.
Triggered weekly by EventBridge on Sunday at 11 PM ET.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncpg
import httpx


def lambda_handler(event, context):
    """
    AWS Lambda handler function.

    Args:
        event: EventBridge scheduled event
        context: Lambda context object

    Returns:
        dict: Response with status and metrics
    """
    # Run async function
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(fetch_and_store_all())

    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }


async def fetch_and_store_all() -> Dict[str, Any]:
    """
    Main async function to fetch both earnings and IPOs.

    Returns:
        dict: Combined summary of both operations
    """
    start_time = datetime.utcnow()
    print(f"Starting earnings & IPO calendar fetch at {start_time.isoformat()}")

    try:
        # Fetch both calendars in parallel
        earnings_result, ipo_result = await asyncio.gather(
            fetch_and_store_earnings(),
            fetch_and_store_ipos(),
            return_exceptions=True
        )

        # Check for errors
        errors = []
        if isinstance(earnings_result, Exception):
            errors.append(f"Earnings fetch failed: {str(earnings_result)}")
            earnings_result = {"status": "error", "events_fetched": 0}
        if isinstance(ipo_result, Exception):
            errors.append(f"IPO fetch failed: {str(ipo_result)}")
            ipo_result = {"status": "error", "events_fetched": 0}

        duration = (datetime.utcnow() - start_time).total_seconds()

        combined_result = {
            "status": "success" if not errors else "partial_success",
            "earnings": earnings_result,
            "ipos": ipo_result,
            "errors": errors if errors else None,
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat()
        }

        print(json.dumps(combined_result, indent=2))
        return combined_result

    except Exception as e:
        error_result = {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }
        print(f"ERROR: {json.dumps(error_result, indent=2)}")
        raise


async def fetch_and_store_earnings() -> Dict[str, Any]:
    """
    Main async function to fetch earnings from FMP and store in RDS.

    Returns:
        dict: Summary of operation with metrics
    """
    start_time = datetime.utcnow()
    print(f"Starting earnings calendar fetch at {start_time.isoformat()}")

    # Get environment variables
    database_url = os.environ['DATABASE_URL']
    fmp_api_key = os.environ['FMP_API_KEY']

    try:
        # Calculate date range: next business day to +60 days
        today = datetime.now().date()

        # Start from next business day if today is weekend
        from_date = today
        while from_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            from_date = from_date + timedelta(days=1)

        end_date = from_date + timedelta(days=60)

        # Fetch earnings data from FMP
        earnings_data = await fetch_from_fmp(fmp_api_key, from_date, end_date)

        if not earnings_data:
            return {
                "status": "warning",
                "message": "No earnings data returned from FMP API",
                "events_fetched": 0
            }

        # Connect to RDS and refresh data
        deleted_count, inserted_count = await refresh_database(database_url, earnings_data)

        duration = (datetime.utcnow() - start_time).total_seconds()

        result = {
            "status": "success",
            "message": f"Fetched and stored earnings calendar",
            "events_fetched": len(earnings_data),
            "events_deleted": deleted_count,
            "events_inserted": inserted_count,
            "date_range": {
                "from": from_date.isoformat(),
                "to": end_date.isoformat()
            },
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat()
        }

        print(json.dumps(result, indent=2))
        return result

    except Exception as e:
        error_result = {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }
        print(f"ERROR: {json.dumps(error_result, indent=2)}")
        raise


async def fetch_from_fmp(
    api_key: str,
    from_date: datetime.date,
    to_date: datetime.date
) -> List[Dict[str, Any]]:
    """
    Fetch earnings calendar data from FMP API.

    Args:
        api_key: FMP API key
        from_date: Start date for earnings data
        to_date: End date for earnings data

    Returns:
        List of earnings events or empty list if fetch fails
    """
    try:
        url = "https://financialmodelingprep.com/stable/earnings-calendar"
        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "apikey": api_key
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

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

            original_count = len(data)
            data = [e for e in data if is_us_listed(e.get('symbol', ''))]

            # Filter to only events with at least one estimate
            data = [e for e in data if e.get('epsEstimated') or e.get('revenueEstimated')]

            # Filter to only weekdays (Monday-Friday)
            def is_weekday(date_str: str) -> bool:
                try:
                    dt = datetime.fromisoformat(date_str)
                    return dt.weekday() < 5  # 0-4 = Mon-Fri, 5-6 = Sat-Sun
                except:
                    return False

            data = [e for e in data if is_weekday(e.get('date', ''))]

            print(f"Filtered earnings: {original_count} total → {len(data)} US-listed with estimates (weekdays only)")

            return data

    except httpx.HTTPError as e:
        print(f"HTTP error fetching earnings data: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error fetching earnings data: {e}")
        raise


async def refresh_database(
    database_url: str,
    earnings_data: List[Dict[str, Any]]
) -> tuple[int, int]:
    """
    Delete old earnings data and insert fresh data.

    Args:
        database_url: PostgreSQL connection string
        earnings_data: List of earnings events from FMP API

    Returns:
        Tuple of (deleted_count, inserted_count)
    """
    # Parse DATABASE_URL
    conn = await asyncpg.connect(database_url)

    try:
        async with conn.transaction():
            # Create table if it doesn't exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS earnings_calendar (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    date DATE NOT NULL,
                    eps_actual DECIMAL(10, 4),
                    eps_estimated DECIMAL(10, 4),
                    revenue_actual BIGINT,
                    revenue_estimated BIGINT,
                    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(symbol, date)
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_earnings_calendar_date ON earnings_calendar(date)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_earnings_calendar_symbol ON earnings_calendar(symbol)")

            # Delete all existing data
            delete_result = await conn.execute("DELETE FROM earnings_calendar")
            # Extract count from result (format: "DELETE 123")
            deleted_count = int(delete_result.split()[-1]) if delete_result.startswith("DELETE") else 0
            print(f"Deleted {deleted_count} old earnings records")

            # Batch insert new data
            if earnings_data:
                insert_query = """
                    INSERT INTO earnings_calendar (
                        symbol,
                        date,
                        eps_actual,
                        eps_estimated,
                        revenue_actual,
                        revenue_estimated,
                        last_updated
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """

                # Prepare batch insert data
                values = []
                for event in earnings_data:
                    # Parse date string to date object
                    event_date = datetime.fromisoformat(event["date"]).date()

                    # Parse lastUpdated to datetime
                    last_updated = datetime.fromisoformat(
                        event["lastUpdated"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)

                    values.append((
                        event["symbol"],
                        event_date,
                        event.get("epsActual"),
                        event.get("epsEstimated"),
                        event.get("revenueActual"),
                        event.get("revenueEstimated"),
                        last_updated
                    ))

                # Execute batch insert
                await conn.executemany(insert_query, values)
                inserted_count = len(values)
                print(f"Inserted {inserted_count} earnings events")

                return deleted_count, inserted_count
            else:
                return deleted_count, 0

    finally:
        await conn.close()


async def fetch_and_store_ipos() -> Dict[str, Any]:
    """
    Fetch IPO calendar from FMP and store in RDS.

    Returns:
        dict: Summary of operation with metrics
    """
    start_time = datetime.utcnow()
    print(f"Starting IPO calendar fetch at {start_time.isoformat()}")

    # Get environment variables
    database_url = os.environ['DATABASE_URL']
    fmp_api_key = os.environ['FMP_API_KEY']

    try:
        # Fetch IPO data from FMP
        ipo_data = await fetch_ipos_from_fmp(fmp_api_key)

        if not ipo_data:
            return {
                "status": "warning",
                "message": "No IPO data returned from FMP API",
                "events_fetched": 0,
                "events_deleted": 0,
                "events_inserted": 0
            }

        # Connect to RDS and refresh data
        deleted_count, inserted_count = await refresh_ipo_database(database_url, ipo_data)

        duration = (datetime.utcnow() - start_time).total_seconds()

        result = {
            "status": "success",
            "message": f"Fetched and stored IPO calendar",
            "events_fetched": len(ipo_data),
            "events_deleted": deleted_count,
            "events_inserted": inserted_count,
            "duration_seconds": round(duration, 2)
        }

        print(json.dumps(result, indent=2))
        return result

    except Exception as e:
        error_result = {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
        }
        print(f"IPO ERROR: {json.dumps(error_result, indent=2)}")
        raise


async def fetch_ipos_from_fmp(api_key: str) -> List[Dict[str, Any]]:
    """
    Fetch IPO calendar data from FMP API.

    Args:
        api_key: FMP API key

    Returns:
        List of IPO events or empty list if fetch fails
    """
    try:
        url = "https://financialmodelingprep.com/stable/ipos-calendar"
        params = {"apikey": api_key}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Filter to only US-listed stocks (clean symbols)
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

            original_count = len(data)
            data = [e for e in data if is_us_listed(e.get('symbol', ''), e.get('exchange', ''))]

            # Filter to only show last 3 months
            today = datetime.utcnow().date()
            three_months_ago = today - timedelta(days=90)

            def is_in_date_range(date_str: str) -> bool:
                """Filter to recent IPOs within last 3 months"""
                try:
                    if isinstance(date_str, str):
                        dt = datetime.fromisoformat(date_str).date()
                    else:
                        dt = date_str
                    return three_months_ago <= dt <= today
                except:
                    return False

            after_us_filter = len(data)
            data = [e for e in data if is_in_date_range(e.get('date', ''))]

            print(f"Filtered IPOs: {original_count} total → {after_us_filter} US-listed → {len(data)} recent (last 3mo)")

            return data

    except httpx.HTTPError as e:
        print(f"HTTP error fetching IPO data: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error fetching IPO data: {e}")
        raise


async def refresh_ipo_database(
    database_url: str,
    ipo_data: List[Dict[str, Any]]
) -> tuple[int, int]:
    """
    Delete old IPO data and insert fresh data.

    Args:
        database_url: PostgreSQL connection string
        ipo_data: List of IPO events from FMP API

    Returns:
        Tuple of (deleted_count, inserted_count)
    """
    conn = await asyncpg.connect(database_url)

    try:
        async with conn.transaction():
            # Delete all existing data
            delete_result = await conn.execute("DELETE FROM ipo_calendar")
            deleted_count = int(delete_result.split()[-1]) if delete_result.startswith("DELETE") else 0
            print(f"Deleted {deleted_count} old IPO records")

            # Batch insert new data
            if ipo_data:
                insert_query = """
                    INSERT INTO ipo_calendar (
                        symbol,
                        date,
                        company,
                        exchange,
                        actions,
                        shares,
                        price_range,
                        market_cap,
                        last_updated
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """

                # Prepare batch insert data
                values = []
                for event in ipo_data:
                    # Parse date string to date object
                    event_date = datetime.fromisoformat(event["date"]).date()

                    values.append((
                        event.get("symbol"),
                        event_date,
                        event.get("company"),
                        event.get("exchange"),
                        event.get("actions"),
                        event.get("shares"),
                        event.get("priceRange"),
                        event.get("marketCap"),
                        datetime.utcnow()
                    ))

                # Execute batch insert
                await conn.executemany(insert_query, values)
                inserted_count = len(values)
                print(f"Inserted {inserted_count} IPO events")

                return deleted_count, inserted_count
            else:
                return deleted_count, 0

    finally:
        await conn.close()
