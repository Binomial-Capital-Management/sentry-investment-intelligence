"""
Fear & Greed Index Lambda Function
Fetches market sentiment data from RapidAPI and stores in RDS PostgreSQL.
Triggered twice daily by EventBridge at 8 AM and 2 PM ET on weekdays.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
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
    result = loop.run_until_complete(fetch_and_store_fgi())

    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }


async def fetch_and_store_fgi() -> Dict[str, Any]:
    """
    Main async function to fetch Fear & Greed Index and store in RDS.

    Returns:
        dict: Summary of operation with metrics
    """
    start_time = datetime.utcnow()
    print(f"Starting Fear & Greed Index fetch at {start_time.isoformat()}")

    # Get environment variables
    database_url = os.environ['DATABASE_URL']
    rapidapi_key = os.environ['RAPIDAPI_FGI_KEY']

    try:
        # Fetch data from RapidAPI
        fgi_data = await fetch_from_rapidapi(rapidapi_key)

        if not fgi_data:
            return {
                "status": "error",
                "message": "No data returned from RapidAPI",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Store in RDS PostgreSQL
        await store_in_database(database_url, fgi_data)

        duration = (datetime.utcnow() - start_time).total_seconds()

        result = {
            "status": "success",
            "message": "Fear & Greed Index refreshed successfully",
            "fgi_value": fgi_data["fgi"]["now"]["value"],
            "fgi_sentiment": fgi_data["fgi"]["now"]["valueText"],
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


async def fetch_from_rapidapi(api_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch Fear & Greed Index data from RapidAPI.

    Args:
        api_key: RapidAPI key for Fear & Greed Index

    Returns:
        Dict with FGI data or None if fetch fails
    """
    try:
        url = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi"
        headers = {
            "x-rapidapi-host": "fear-and-greed-index.p.rapidapi.com",
            "x-rapidapi-key": api_key
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            print(f"Successfully fetched FGI data from RapidAPI")
            return data

    except httpx.HTTPError as e:
        print(f"HTTP error fetching FGI data: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error fetching FGI data: {e}")
        raise


async def store_in_database(database_url: str, data: Dict[str, Any]):
    """
    Store Fear & Greed Index data in PostgreSQL.

    Args:
        database_url: PostgreSQL connection string
        data: FGI data from RapidAPI
    """
    conn = await asyncpg.connect(database_url)

    try:
        async with conn.transaction():
            # Create table if it doesn't exist (safety check)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS fear_greed_index (
                    id SERIAL PRIMARY KEY,
                    value INT NOT NULL CHECK (value >= 0 AND value <= 100),
                    value_text VARCHAR(50) NOT NULL,
                    previous_close_value INT CHECK (previous_close_value >= 0 AND previous_close_value <= 100),
                    previous_close_text VARCHAR(50),
                    last_updated TIMESTAMP NOT NULL,
                    fetched_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fgi_fetched_at ON fear_greed_index(fetched_at DESC)"
            )

            # Extract data
            fgi_now = data["fgi"]["now"]
            fgi_prev = data["fgi"].get("previousClose")
            last_updated = datetime.fromisoformat(
                data["lastUpdated"]["humanDate"].replace("Z", "+00:00")
            )

            # Convert to naive datetime for PostgreSQL TIMESTAMP (without timezone)
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

            print(f"Stored FGI data in database: value={fgi_now['value']}, sentiment={fgi_now['valueText']}")

    finally:
        await conn.close()
