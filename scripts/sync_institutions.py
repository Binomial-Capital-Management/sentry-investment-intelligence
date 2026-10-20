#!/usr/bin/env python3
"""
Sync Institution Universe from FMP API

Fetches all 13F filers from FMP's institutional-ownership/list endpoint
and populates the institution_universe table.

Usage:
    python scripts/sync_institutions.py

Environment:
    FMP_API_KEY: Your FMP API key
    DATABASE_URL: PostgreSQL connection string
"""
import asyncio
import logging
import os
import sys
from typing import List, Dict

import aiohttp

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database.postgres_client import get_postgres_rls_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_BASE_URL = "https://financialmodelingprep.com"


async def fetch_institutions() -> List[Dict]:
    """Fetch all institutions from FMP API."""
    if not FMP_API_KEY:
        raise ValueError("FMP_API_KEY environment variable not set")
    
    url = f"{FMP_BASE_URL}/api/v4/institutional-ownership/list"
    params = {"apikey": FMP_API_KEY}
    
    logger.info("Fetching institutions from FMP...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=60) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"FMP API error: {response.status} - {error_text}")
            
            data = await response.json()
            logger.info(f"Fetched {len(data)} institutions from FMP")
            return data


async def upsert_institutions(institutions: List[Dict]) -> int:
    """
    Upsert institutions into database.
    
    Returns number of rows affected.
    """
    if not institutions:
        return 0
    
    pg = await get_postgres_rls_client()
    
    # Prepare batch insert/update
    query = """
        INSERT INTO institution_universe (cik, name)
        VALUES ($1, $2)
        ON CONFLICT (cik) DO UPDATE SET
            name = EXCLUDED.name,
            last_updated = CURRENT_TIMESTAMP
    """
    
    async with pg.pool.acquire() as conn:
        # Use executemany for batch insert
        count = 0
        batch_size = 500
        
        for i in range(0, len(institutions), batch_size):
            batch = institutions[i:i + batch_size]
            
            async with conn.transaction():
                for inst in batch:
                    cik = inst.get("cik", "").strip()
                    name = inst.get("name", "").strip()
                    
                    if cik and name:
                        await conn.execute(query, cik, name)
                        count += 1
            
            logger.info(f"Processed {min(i + batch_size, len(institutions))}/{len(institutions)} institutions")
    
    return count


async def main():
    """Main sync function."""
    logger.info("=" * 60)
    logger.info("Starting Institution Universe Sync")
    logger.info("=" * 60)
    
    try:
        # Fetch from FMP
        institutions = await fetch_institutions()
        
        if not institutions:
            logger.warning("No institutions returned from FMP")
            return
        
        # Upsert into database
        count = await upsert_institutions(institutions)
        
        logger.info("=" * 60)
        logger.info(f"Sync complete! Upserted {count} institutions")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
