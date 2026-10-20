"""
Insight Scheduler Service
Runs daily at 6 AM ET to generate personalized insights for all users.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.database.postgres_client import get_postgres_client
from core.services.insight_service import get_insight_service
from core.config import get_config

logger = logging.getLogger(__name__)


class InsightScheduler:
    """Manages scheduled insight generation for all users."""

    def __init__(self, concurrency: int = None):
        """
        Initialize scheduler with controlled concurrency for optimal database performance.
        With bulk inserts, 15 concurrent users = ~70 connections (well within 100 pool limit).

        Args:
            concurrency: Max concurrent user insight generations (default: 15)
        """
        cfg = get_config()
        # Use provided value or config; fallback to a higher default now that DB cap is lifted
        self.concurrency = concurrency or int(getattr(cfg, "insight_scheduler_concurrency", 20))
        self.scheduler = AsyncIOScheduler()
        self.pg_client = None
        self.insight_service = None
        self.is_running = False
        self._lock = asyncio.Lock()  # Prevents shutdown-before-start race
        self._instance_id = id(self)  # Unique instance identifier for debugging

        logger.info(f"InsightScheduler initialized with concurrency={concurrency}, instance_id={self._instance_id}")

    async def initialize(self):
        """Initialize database client and insight service."""
        if self.pg_client is None:
            self.pg_client = await get_postgres_client()
            logger.info("PostgreSQL client initialized for scheduler")

        if self.insight_service is None:
            try:
                self.insight_service = await get_insight_service()
                logger.info("InsightService initialized for scheduler")
            except RuntimeError as e:
                logger.critical(f"Failed to initialize InsightService: {e}")
                raise RuntimeError("InsightScheduler cannot start - InsightService initialization failed") from e

    async def start(self):
        """Start the scheduler with daily 6 AM ET cron job."""
        async with self._lock:
            if self.is_running:
                logger.warning(f"Scheduler instance {self._instance_id} already running")
                return

            await self.initialize()

            # Schedule daily insights generation at 6 AM ET
            self.scheduler.add_job(
                self.generate_daily_insights,
                trigger=CronTrigger(
                    hour=6,
                    minute=0,
                    timezone="America/New_York"
                ),
                id="daily_insights_6am",
                name="Daily Insights Generation (6 AM ET)",
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True
            logger.info(f"InsightScheduler instance {self._instance_id} started - Daily insights at 6 AM ET")

    async def stop(self):
        """Stop the scheduler gracefully."""
        async with self._lock:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("InsightScheduler stopped")

    async def generate_daily_insights(self):
        """
        Generate insights for all users with high concurrency.
        Called daily at 6 AM ET by scheduler.
        
        Uses PostgreSQL advisory lock to ensure only one worker runs the job
        in multi-worker deployments.
        """
        start_time = datetime.utcnow()
        logger.info(f"Daily insight generation triggered at {start_time.isoformat()} (instance {self._instance_id})")

        # Use PostgreSQL advisory lock to prevent multiple workers from running simultaneously
        # Lock ID 987654321 is a unique identifier for the insight scheduler job
        INSIGHT_SCHEDULER_LOCK_ID = 987654321
        
        try:
            # Try to acquire advisory lock (non-blocking)
            lock_acquired = await self.pg_client.try_advisory_lock(INSIGHT_SCHEDULER_LOCK_ID)
            if not lock_acquired:
                logger.info(f"Another worker is already running insight generation - skipping (instance {self._instance_id})")
                return
            
            logger.info(f"Acquired advisory lock, starting insight generation (instance {self._instance_id})")
        except Exception as e:
            # If we can't check the lock (e.g., DB issue), proceed anyway to not skip the job entirely
            logger.warning(f"Could not acquire advisory lock, proceeding anyway: {e}")

        try:
            # Get all user IDs
            user_ids = await self.pg_client.get_all_users()
            total_users = len(user_ids)
            logger.info(f"Processing insights for {total_users} users with concurrency={self.concurrency}")

            if total_users == 0:
                logger.warning("No users found for insight generation")
                return

            # Process users with high concurrency using semaphore
            semaphore = asyncio.Semaphore(self.concurrency)
            tasks = [
                self._generate_user_insights_with_semaphore(user_id, semaphore)
                for user_id in user_ids
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results
            success_count = 0
            error_count = 0
            total_insights = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"User {user_ids[i]} failed: {result}", exc_info=result)
                    error_count += 1
                elif result:
                    success_count += 1
                    total_insights += result.get("insights_created", 0)

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Daily insight generation completed in {duration:.2f}s: "
                f"{success_count}/{total_users} users succeeded, "
                f"{total_insights} insights created, "
                f"{error_count} errors"
            )

        except Exception as e:
            logger.error(f"Fatal error in daily insight generation: {e}", exc_info=True)

    async def _generate_user_insights_with_semaphore(
        self,
        user_id: str,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """
        Generate insights for a single user with semaphore control.

        Args:
            user_id: Clerk user ID
            semaphore: Asyncio semaphore for concurrency control

        Returns:
            Result dictionary with status and counts
        """
        async with semaphore:
            try:
                # Check if service is disabled
                if hasattr(self.insight_service, 'service_disabled') and self.insight_service.service_disabled:
                    logger.warning(f"Skipping user {user_id} - InsightService is disabled")
                    return {
                        "user_id": user_id,
                        "insights_created": 0,
                        "errors": ["Service disabled due to connection failures"]
                    }

                logger.debug(f"Generating insights for user {user_id}")
                result = await self.insight_service.generate_user_insights(user_id)
                logger.debug(
                    f"User {user_id}: {result['insights_created']} insights created"
                )
                return result
            except RuntimeError as e:
                if "disabled" in str(e).lower():
                    logger.error(f"InsightService disabled, skipping user {user_id}")
                    return {
                        "user_id": user_id,
                        "insights_created": 0,
                        "errors": ["Service disabled"]
                    }
                logger.error(f"Failed to generate insights for user {user_id}: {e}", exc_info=True)
                return {
                    "user_id": user_id,
                    "insights_created": 0,
                    "errors": [str(e)]
                }
            except Exception as e:
                logger.error(f"Failed to generate insights for user {user_id}: {e}", exc_info=True)
                return {
                    "user_id": user_id,
                    "insights_created": 0,
                    "errors": [str(e)]
                }

    async def generate_insights_now(
        self,
        user_id: str = None,
        page_type: str = None,
        region: str = None
    ) -> Dict[str, Any]:
        """
        Manual trigger for insight generation (testing or on-demand).

        Args:
            user_id: Optional specific user ID. If None, generates for all users.
            page_type: Optional page type filter ('markets', 'crypto', 'macro')
            region: Optional region filter (for markets: 'us', 'eu', 'china', 'korea', 'japan')

        Returns:
            Result dictionary with status and counts
        """
        await self.initialize()

        if user_id:
            # Generate for single user (with optional page_type/region filter)
            logger.info(f"Manual insight generation for user {user_id}, page_type={page_type}, region={region}")
            return await self.insight_service.generate_user_insights(
                user_id=user_id,
                page_type=page_type,
                region=region
            )
        else:
            # Generate for all users (same as daily job)
            logger.info("Manual insight generation for all users")
            await self.generate_daily_insights()
            return {"status": "completed", "message": "Check logs for details"}


# Global instance and lock to prevent race conditions
_scheduler = None
_scheduler_lock = asyncio.Lock()


async def get_insight_scheduler(concurrency: int = 15) -> InsightScheduler:
    """
    Get or create the global InsightScheduler instance (thread-safe).

    Args:
        concurrency: Max concurrent user operations (default: 15)

    Returns:
        InsightScheduler instance
    """
    global _scheduler

    # Thread-safe singleton pattern with async lock
    async with _scheduler_lock:
        if _scheduler is None:
            logger.info(f"Creating new InsightScheduler instance with concurrency={concurrency}")
            _scheduler = InsightScheduler(concurrency=concurrency)
            await _scheduler.initialize()
            logger.info(f"InsightScheduler instance created: id={id(_scheduler)}")
        else:
            logger.debug(f"Reusing existing InsightScheduler instance: id={id(_scheduler)}")

        return _scheduler
