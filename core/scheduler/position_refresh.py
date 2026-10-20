"""
Background scheduler for refreshing IBKR positions.

Runs TWICE DAILY (not every 15 min!):
- 12:00 PM ET (midday refresh)
- 5:30 PM ET (after market close)

Respects IBKR rate limits with conservative concurrency (10 max).
Skips users who synced in last 4 hours to avoid waste.

Following CODING_RULES.md: KISS, DRY, YAGNI.
"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logging.warning("apscheduler not installed - background refresh unavailable")

from core.database.postgres_client import get_postgres_rls_client
from core.integrations.ibkr_service import get_ibkr_service

logger = logging.getLogger(__name__)


class PositionRefreshScheduler:
    """
    Background scheduler for IBKR position refresh.

    Key Design:
    - Runs TWICE daily (not every 15 min) per IBKR guidance
    - Conservative concurrency (10 max) to avoid rate limits
    - Skips recently-synced users (< 4 hours ago)
    - Comprehensive logging for monitoring
    """

    def __init__(self):
        if not APSCHEDULER_AVAILABLE:
            logger.warning("APScheduler not available - scheduler disabled")
            self.enabled = False
            return

        self.scheduler = AsyncIOScheduler()
        self.ibkr_service = get_ibkr_service()
        self.is_running = False
        self._lock = asyncio.Lock()  # Prevents shutdown-before-start race

        # Conservative settings to respect IBKR limits
        # IBKR allows 50 req/sec but recommends "not suitable for active polling"
        self.max_concurrent = int(os.getenv('IBKR_MAX_CONCURRENT', '10'))

        # Timezone for market hours
        self.timezone = os.getenv('IBKR_SCHEDULER_TIMEZONE', 'America/New_York')

        self.enabled = self.ibkr_service.enabled

        if self.enabled:
            logger.info(
                f"PositionRefreshScheduler initialized "
                f"(max_concurrent={self.max_concurrent}, tz={self.timezone})"
            )
        else:
            logger.warning("PositionRefreshScheduler disabled (IBKRService not available)")

    async def start(self) -> None:
        """Start the background scheduler with twice-daily jobs."""
        async with self._lock:
            if not self.enabled:
                logger.info("Scheduler not starting (disabled)")
                return

            if self.is_running:
                logger.warning("Scheduler already running")
                return

            # Midday refresh: 12:00 PM ET
            self.scheduler.add_job(
                self.refresh_all_users,
                trigger=CronTrigger(
                    hour=12,
                    minute=0,
                    timezone=self.timezone
                ),
                id='ibkr_midday_refresh',
                name='IBKR midday position refresh',
                replace_existing=True
            )

            # Evening refresh: 5:30 PM ET (after market close)
            self.scheduler.add_job(
                self.refresh_all_users,
                trigger=CronTrigger(
                    hour=17,
                    minute=30,
                    timezone=self.timezone
                ),
                id='ibkr_evening_refresh',
                name='IBKR evening position refresh',
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True
            logger.info(
                f"Position refresh scheduler started: "
                f"12:00 PM and 5:30 PM {self.timezone} "
                f"(max concurrent: {self.max_concurrent})"
            )

    async def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        async with self._lock:
            if not self.enabled or not hasattr(self, 'scheduler'):
                return

            if not self.is_running:
                return

            try:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("Position refresh scheduler stopped gracefully")
            except Exception as e:
                logger.error(f"Error shutting down scheduler: {e}")

    async def refresh_all_users(self) -> None:
        """
        Refresh positions for all active IBKR connections.

        Called automatically by scheduler at 12 PM and 5:30 PM ET.
        Skips users who synced in last 4 hours to avoid waste.
        Processes users in parallel with concurrency limit.
        """
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("Starting IBKR position refresh job")
        logger.info("=" * 60)

        try:
            # Get users needing refresh (skip recent syncs)
            users = await self._get_users_needing_refresh()

            if not users:
                logger.info("No users need refresh (all synced recently)")
                return

            logger.info(f"Refreshing {len(users)} user(s)")

            # Create semaphore to limit concurrent IBKR API calls
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def refresh_one_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
                """Refresh one user with concurrency limit."""
                user_id = user_data['user_id']
                last_sync = user_data.get('last_sync_at')

                async with semaphore:
                    try:
                        logger.debug(f"Refreshing user {user_id} (last sync: {last_sync})")

                        # Use the SAME function the API uses!
                        positions = await self.ibkr_service.get_user_positions(
                            user_id,
                            use_cache=False  # Force fresh fetch
                        )

                        return {
                            'user_id': user_id,
                            'success': True,
                            'positions_count': len(positions)
                        }

                    except Exception as e:
                        logger.error(f"Refresh failed for user {user_id}: {e}")
                        await self._mark_connection_error(user_id, str(e))

                        return {
                            'user_id': user_id,
                            'success': False,
                            'error': str(e)
                        }

            # Execute all refreshes in parallel
            results = await asyncio.gather(*[
                refresh_one_user(u) for u in users
            ], return_exceptions=True)

            # Count successes and failures
            successes = sum(
                1 for r in results
                if isinstance(r, dict) and r.get('success')
            )
            failures = len(results) - successes

            # Calculate timing
            duration = (datetime.now() - start_time).total_seconds()
            avg_per_user = duration / len(users) if users else 0

            # Log summary
            logger.info("=" * 60)
            logger.info("IBKR position refresh completed")
            logger.info(f"  Total users: {len(users)}")
            logger.info(f"  Successes: {successes}")
            logger.info(f"  Failures: {failures}")
            logger.info(f"  Total time: {duration:.1f}s")
            logger.info(f"  Avg per user: {avg_per_user:.2f}s")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"IBKR refresh job failed with error: {e}", exc_info=True)

    async def _get_users_needing_refresh(self) -> List[Dict[str, Any]]:
        """
        Get users who need position refresh.

        Skips users who synced in last 4 hours to avoid wasting API calls.
        Prioritizes users who never synced or synced longest ago.
        """
        pg = await get_postgres_rls_client()

        # No user context needed - we're reading all active connections
        async with pg.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch("""
                    SELECT
                        user_id,
                        last_sync_at,
                        EXTRACT(EPOCH FROM (NOW() - last_sync_at)) / 3600 as hours_since_sync
                    FROM broker_connections
                    WHERE status = 'active'
                      AND broker_type = 'ibkr'
                      AND (
                          last_sync_at IS NULL
                          OR last_sync_at < NOW() - INTERVAL '4 hours'
                      )
                    ORDER BY
                        CASE WHEN last_sync_at IS NULL THEN 0 ELSE 1 END,
                        last_sync_at ASC
                """)

                return [dict(row) for row in rows]

    async def _mark_connection_error(self, user_id: str, error_message: str) -> None:
        """Mark connection as having an error."""
        pg = await get_postgres_rls_client()

        try:
            async with pg.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE broker_connections
                        SET
                            status = 'error',
                            error_message = $1,
                            updated_at = NOW()
                        WHERE user_id = $2
                          AND broker_type = 'ibkr'
                    """, error_message[:500], user_id)  # Truncate error to 500 chars
        except Exception as e:
            logger.error(f"Failed to mark connection error for {user_id}: {e}")


# Singleton instance
_scheduler: Optional[PositionRefreshScheduler] = None


def get_position_refresh_scheduler() -> PositionRefreshScheduler:
    """Get singleton scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = PositionRefreshScheduler()
    return _scheduler
