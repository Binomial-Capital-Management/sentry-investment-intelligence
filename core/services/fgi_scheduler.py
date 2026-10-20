"""
Fear & Greed Index Scheduler Service
Fetches market sentiment data from RapidAPI twice daily at 8 AM and 2 PM ET on weekdays.

DEPRECATED: This scheduler has been fully migrated to AWS Lambda (fear-greed-index).
- Production: Lambda with EventBridge scheduling (8 AM and 2 PM ET weekdays)
- Manual refresh: Direct RapidAPI fetch in api/routers/market_data.py
- Lambda function: lambdas/fear_greed_index/handler.py
- EventBridge rules: fear-greed-index-8am-et, fear-greed-index-2pm-et

This file is kept for reference only and is NOT loaded in production.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.database.postgres_client import get_postgres_client
from core.config import get_config

logger = logging.getLogger(__name__)


class FGIScheduler:
    """Manages scheduled Fear & Greed Index data fetching."""

    def __init__(self):
        """Initialize the FGI scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.pg_client = None
        self.is_running = False
        self._lock = asyncio.Lock()  # Prevents shutdown-before-start race
        self.config = get_config()

        # RapidAPI configuration
        self.api_url = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi"
        self.api_key = getattr(self.config, 'RAPIDAPI_FGI_KEY', None)

        logger.info("FGIScheduler initialized")

    async def initialize(self):
        """Initialize database client."""
        if self.pg_client is None:
            try:
                self.pg_client = await get_postgres_client()
                if self.pg_client and self.pg_client.pool:
                    logger.info("PostgreSQL client initialized for FGI scheduler")
                else:
                    logger.warning("PostgreSQL client returned but pool is not initialized")
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL client for FGI scheduler: {e}")
                self.pg_client = None

    async def start(self):
        """Start the scheduler with twice-daily jobs at 8 AM and 2 PM ET on weekdays."""
        async with self._lock:
            if self.is_running:
                logger.warning("Scheduler already running")
                return

            await self.initialize()

            if not self.api_key:
                logger.error("RAPIDAPI_FGI_KEY not configured. FGI scheduler will not start.")
                return

            # Schedule 8 AM ET on weekdays (Monday-Friday)
            self.scheduler.add_job(
                self.fetch_and_store_fgi,
                trigger=CronTrigger(
                    hour=8,
                    minute=0,
                    day_of_week='mon-fri',
                    timezone="America/New_York"
                ),
                id="fgi_8am",
                name="Fear & Greed Index Fetch (8 AM ET)",
                replace_existing=True
            )

            # Schedule 2 PM ET on weekdays (Monday-Friday)
            self.scheduler.add_job(
                self.fetch_and_store_fgi,
                trigger=CronTrigger(
                    hour=14,
                    minute=0,
                    day_of_week='mon-fri',
                    timezone="America/New_York"
                ),
                id="fgi_2pm",
                name="Fear & Greed Index Fetch (2 PM ET)",
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True
            logger.info("FGIScheduler started - Fetching at 8 AM and 2 PM ET on weekdays")

            # Fetch immediately on startup
            await self.fetch_and_store_fgi()

    async def stop(self):
        """Stop the scheduler gracefully."""
        async with self._lock:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("FGIScheduler stopped")

    async def fetch_and_store_fgi(self):
        """
        Fetch Fear & Greed Index from RapidAPI and store in database.
        Called twice daily at 8 AM and 2 PM ET on weekdays.
        """
        fetch_time = datetime.utcnow()
        logger.info(f"Starting Fear & Greed Index fetch at {fetch_time.isoformat()}")

        try:
            # Fetch data from RapidAPI
            fgi_data = await self._fetch_from_api()

            if not fgi_data:
                logger.error("Failed to fetch FGI data from API")
                return

            # Store in database
            await self._store_fgi_data(fgi_data)

            logger.info(
                f"Successfully fetched and stored FGI data: "
                f"value={fgi_data['fgi']['now']['value']}, "
                f"sentiment={fgi_data['fgi']['now']['valueText']}"
            )

        except Exception as e:
            logger.error(f"Error in FGI fetch job: {e}", exc_info=True)

    async def _fetch_from_api(self) -> Optional[Dict[str, Any]]:
        """
        Fetch Fear & Greed Index data from RapidAPI.

        Returns:
            Dict with FGI data or None if fetch fails
        """
        try:
            headers = {
                "x-rapidapi-host": "fear-and-greed-index.p.rapidapi.com",
                "x-rapidapi-key": self.api_key
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.api_url, headers=headers)
                response.raise_for_status()
                data = response.json()

                logger.info(f"Successfully fetched FGI data from RapidAPI")
                return data

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching FGI data: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching FGI data: {e}", exc_info=True)
            return None

    async def _store_fgi_data(self, data: Dict[str, Any]):
        """
        Store Fear & Greed Index data in PostgreSQL.

        Args:
            data: FGI data from RapidAPI
        """
        try:
            # Check if database is available
            if not self.pg_client or not self.pg_client.pool:
                logger.warning("PostgreSQL not available, skipping FGI data storage")
                return

            fgi_now = data["fgi"]["now"]
            fgi_prev = data["fgi"].get("previousClose")
            last_updated = datetime.fromisoformat(
                data["lastUpdated"]["humanDate"].replace("Z", "+00:00")
            )

            # Convert to naive datetime for PostgreSQL TIMESTAMP (without timezone)
            last_updated_naive = last_updated.replace(tzinfo=None)

            async with self.pg_client.pool.acquire() as conn:
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

            logger.info(f"Stored FGI data in database: value={fgi_now['value']}")

        except Exception as e:
            logger.error(f"Error storing FGI data: {e}", exc_info=True)
            raise


# Singleton instance
_fgi_scheduler: Optional[FGIScheduler] = None


async def get_fgi_scheduler() -> FGIScheduler:
    """Get or create the FGI scheduler singleton."""
    global _fgi_scheduler
    if _fgi_scheduler is None:
        _fgi_scheduler = FGIScheduler()
    return _fgi_scheduler
