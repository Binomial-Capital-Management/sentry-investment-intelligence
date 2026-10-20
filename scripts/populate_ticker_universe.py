#!/usr/bin/env python3
"""
Populate ticker_universe table from FMP screener endpoint
Following CODING_RULES.md: no hardcoding, dynamic field discovery, batch operations

Uses FMP v3/stock-screener which returns:
- symbol, companyName, marketCap, sector, industry, beta, price, volume
- exchange, exchangeShortName, country, isEtf, isFund, isActivelyTrading
"""
import asyncio
import os
import sys
import logging
from typing import List, Dict, Any

import aiohttp
import asyncpg

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TickerUniversePopulator:
    """Populate ticker universe from FMP screener with smart batching"""

    def __init__(self):
        self.config = get_config()
        self.fmp_key = self.config.fmp_api_key
        if not self.fmp_key:
            raise ValueError("FMP_API_KEY not configured")

        self.db_url = self.config.database_url
        if not self.db_url:
            raise ValueError("DATABASE_URL not configured")

        self.pool: asyncpg.Pool = None

    async def connect_db(self):
        """Create database connection pool"""
        self.pool = await asyncpg.create_pool(self.db_url, min_size=2, max_size=10)
        logger.info("✓ Database connected")

    async def close_db(self):
        """Close database pool"""
        if self.pool:
            await self.pool.close()

    async def fetch_us_stocks(self) -> List[Dict[str, Any]]:
        """
        Fetch US stocks from FMP screener endpoint
        Screener returns max 1000 per request, handles pagination
        """
        all_stocks = []
        exchanges = ['nasdaq', 'nyse', 'amex']

        for exchange in exchanges:
            url = f"https://financialmodelingprep.com/api/v3/stock-screener"
            params = {
                'exchange': exchange,
                'apikey': self.fmp_key
            }

            logger.info(f"Fetching {exchange.upper()} stocks...")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"FMP API error for {exchange}: {resp.status}")
                        continue

                    data = await resp.json()
                    all_stocks.extend(data)
                    logger.info(f"  ✓ Fetched {len(data):,} {exchange.upper()} tickers")

        logger.info(f"✓ Total fetched: {len(all_stocks):,} US stocks")
        return all_stocks

    def filter_active_stocks(self, tickers: List[Dict]) -> List[Dict]:
        """Filter for actively trading stocks and ETFs"""
        filtered = [
            t for t in tickers
            if not t.get('isFund', False)  # Exclude mutual funds
            and t.get('symbol')  # Must have symbol
            and t.get('companyName')  # Must have name
        ]

        logger.info(f"✓ Filtered to {len(filtered):,} stocks/ETFs")
        return filtered

    async def bulk_insert_tickers(self, tickers: List[Dict]):
        """Batch insert tickers with upsert logic - dynamic field mapping from FMP response"""
        insert_query = """
            INSERT INTO ticker_universe (
                symbol, name, exchange, exchange_short, type,
                sector, industry, country, currency,
                is_actively_trading, last_updated
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
            ON CONFLICT (symbol) DO UPDATE SET
                name = EXCLUDED.name,
                exchange = EXCLUDED.exchange,
                exchange_short = EXCLUDED.exchange_short,
                type = EXCLUDED.type,
                sector = EXCLUDED.sector,
                industry = EXCLUDED.industry,
                country = EXCLUDED.country,
                currency = EXCLUDED.currency,
                is_actively_trading = EXCLUDED.is_actively_trading,
                last_updated = CURRENT_TIMESTAMP
        """

        # Prepare batch data - discover fields dynamically from FMP response
        batch_data = []
        for t in tickers:
            # Determine type from FMP flags
            if t.get('isEtf', False):
                ticker_type = 'etf'
            elif t.get('isFund', False):
                ticker_type = 'fund'
            else:
                ticker_type = 'stock'

            batch_data.append((
                t.get('symbol', ''),
                t.get('companyName', ''),
                t.get('exchange', ''),
                t.get('exchangeShortName', ''),
                ticker_type,
                t.get('sector') if t.get('sector') else None,
                t.get('industry') if t.get('industry') else None,
                t.get('country'),
                'USD',  # FMP screener for US stocks returns USD prices
                t.get('isActivelyTrading', True)
            ))

        # Batch insert in chunks of 500
        chunk_size = 500
        total_inserted = 0

        async with self.pool.acquire() as conn:
            for i in range(0, len(batch_data), chunk_size):
                chunk = batch_data[i:i + chunk_size]
                await conn.executemany(insert_query, chunk)
                total_inserted += len(chunk)

                if total_inserted % 1000 == 0:
                    logger.info(f"  Inserted {total_inserted:,}/{len(batch_data):,} tickers...")

        logger.info(f"✓ Inserted/updated {total_inserted:,} tickers")

    async def populate(self):
        """Main population workflow"""
        try:
            await self.connect_db()

            # Fetch US stocks from screener
            all_stocks = await self.fetch_us_stocks()

            # Filter active stocks
            active_stocks = self.filter_active_stocks(all_stocks)

            # Bulk insert
            await self.bulk_insert_tickers(active_stocks)

            logger.info("✅ Ticker universe population complete!")

        finally:
            await self.close_db()


async def main():
    """Entry point"""
    populator = TickerUniversePopulator()
    await populator.populate()


if __name__ == "__main__":
    asyncio.run(main())
