"""
Task Scheduler
Automated task execution scheduler using APScheduler with native trigger-based scheduling.
Each task is registered as its own APScheduler job, similar to portfolio_scheduler.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from core.database.postgres_client import get_postgres_rls_client
from core.tasks.db import TasksRepository
from core.tasks.service import TasksService
from core.tasks.types import (
    TaskFrequency,
    TaskRecord,
    TaskStatus,
    TaskScheduleConfig,
    TaskTriggerType,
)

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Manages automated task execution with APScheduler using native triggers."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(
            timezone=pytz.UTC,  # Internal scheduler uses UTC
            job_defaults={
                "misfire_grace_time": int(os.getenv("TASK_SCHEDULER_MISFIRE_GRACE", "300")),  # 5 minutes
                "coalesce": True,  # Collapse multiple misfires
                "max_instances": 1,  # Prevent concurrent executions of same task
            },
        )
        self.is_running = False
        self._lock = asyncio.Lock()  # Prevents shutdown-before-start race
        self.repository = TasksRepository()
        self.service = TasksService(self.repository)
        self.max_concurrent_workers = int(os.getenv("TASK_SCHEDULER_MAX_CONCURRENT_WORKERS", "20"))
        self.execution_semaphore = asyncio.Semaphore(self.max_concurrent_workers)

    async def execute_task(self, task: TaskRecord, user_id: str):
        """
        Execute a single task with concurrency control.

        Flow:
        1. Trigger task execution via TasksService
        2. Update last_run_at timestamp
        3. Handle errors gracefully
        """
        task_id = task.id
        logger.info(f"Executing scheduled task: {task.name} (ID: {task_id})")

        async with self.execution_semaphore:
            try:
                # Create background tasks context for APScheduler
                class FakeBackgroundTasks:
                    """Minimal BackgroundTasks interface for APScheduler context."""

                    def add_task(self, func):
                        asyncio.create_task(func())

                bg_tasks = FakeBackgroundTasks()

                # Trigger execution
                current_run_time = datetime.now(pytz.UTC)

                # Create run record first
                run = await self.repository.create_run(task.id, user_id, TaskTriggerType.SCHEDULED, org_id=task.org_id)

                # Pass run to service (not trigger_type)
                await self.service.trigger_run(task, run, bg_tasks)

                # Update last_run_at in database
                await self.repository.update_next_run(
                    user_id=user_id,
                    task_id=task_id,
                    next_run_at=None,  # APScheduler handles next run internally
                    last_run_at=current_run_time,
                    org_id=task.org_id,
                )

                logger.info(f"Task {task.name} executed successfully")

            except Exception as e:
                logger.error(
                    f"Failed to execute task {task.name} (ID: {task_id}): {e}",
                    exc_info=True,
                )
                # Don't re-raise - scheduler continues for other tasks

    def _build_trigger(self, schedule: TaskScheduleConfig):
        """
        Convert TaskScheduleConfig to APScheduler trigger.

        Args:
            schedule: TaskScheduleConfig with frequency, time, timezone, etc.

        Returns:
            APScheduler trigger (CronTrigger or DateTrigger) or None if invalid
        """
        try:
            # Get task timezone
            task_tz = pytz.timezone(schedule.timezone)

            # Parse target time from schedule (e.g., "14:30" or "02:30 PM")
            time_str = schedule.time or "09:00"
            hour, minute = self._parse_time(time_str)

            # ONCE frequency: Use DateTrigger for one-time execution
            if schedule.frequency == TaskFrequency.ONCE:
                if not schedule.start_date:
                    logger.warning(f"ONCE frequency requires start_date, skipping task")
                    return None

                # Parse start_date and combine with time
                start_dt = self._parse_start_date(schedule.start_date, task_tz)
                run_date = start_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # Only schedule if in the future
                if run_date <= datetime.now(task_tz):
                    logger.warning(f"ONCE task scheduled time {run_date} is in the past, skipping")
                    return None

                return DateTrigger(run_date=run_date, timezone=task_tz)

            # DAILY: Run every day at specified time
            if schedule.frequency == TaskFrequency.DAILY:
                return CronTrigger(hour=hour, minute=minute, timezone=task_tz)

            # WEEKDAYS: Run Monday-Friday at specified time
            if schedule.frequency == TaskFrequency.WEEKDAYS:
                return CronTrigger(
                    day_of_week='mon-fri',
                    hour=hour,
                    minute=minute,
                    timezone=task_tz
                )

            # WEEKLY: Run on specific days of week
            if schedule.frequency == TaskFrequency.WEEKLY:
                if not schedule.days_of_week:
                    logger.warning("WEEKLY frequency requires days_of_week")
                    return None

                # Convert [0=Sun, 1=Mon, ..., 6=Sat] to APScheduler format
                day_names = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
                days = ','.join([day_names[d] for d in schedule.days_of_week])

                return CronTrigger(
                    day_of_week=days,
                    hour=hour,
                    minute=minute,
                    timezone=task_tz
                )

            # BIWEEKLY: Run every 2 weeks on specific days
            if schedule.frequency == TaskFrequency.BIWEEKLY:
                # For biweekly, we use a custom approach with week parameter
                # APScheduler doesn't natively support "every 2 weeks", so we'll use weekly
                # and track the start_date to determine which weeks to run
                # This is a limitation - we'll treat it as weekly for now
                logger.warning("BIWEEKLY treated as WEEKLY in this implementation")
                if not schedule.days_of_week:
                    logger.warning("BIWEEKLY frequency requires days_of_week")
                    return None

                day_names = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
                days = ','.join([day_names[d] for d in schedule.days_of_week])

                return CronTrigger(
                    day_of_week=days,
                    hour=hour,
                    minute=minute,
                    timezone=task_tz
                )

            # MONTHLY: Run on specific day of month
            if schedule.frequency == TaskFrequency.MONTHLY:
                if not schedule.day_of_month:
                    logger.warning("MONTHLY frequency requires day_of_month")
                    return None

                return CronTrigger(
                    day=schedule.day_of_month,
                    hour=hour,
                    minute=minute,
                    timezone=task_tz
                )

            # CUSTOM: Use cron expression directly
            if schedule.frequency == TaskFrequency.CUSTOM:
                if not schedule.cron_expression:
                    logger.warning("CUSTOM frequency requires cron_expression")
                    return None

                return CronTrigger.from_crontab(schedule.cron_expression, timezone=task_tz)

            logger.error(f"Unsupported frequency: {schedule.frequency}")
            return None

        except Exception as e:
            logger.error(f"Error building trigger: {e}", exc_info=True)
            return None

    def _parse_time(self, time_str: str) -> tuple[int, int]:
        """
        Parse time string to (hour, minute) tuple.
        Supports formats: "14:30", "02:30 PM", "2:30 PM"
        """
        try:
            time_str = time_str.strip()

            # Handle AM/PM format
            if 'AM' in time_str.upper() or 'PM' in time_str.upper():
                is_pm = 'PM' in time_str.upper()
                time_str = time_str.upper().replace('AM', '').replace('PM', '').strip()

                parts = time_str.split(':')
                hour = int(parts[0])
                minute = int(parts[1])

                # Convert to 24-hour format
                if is_pm and hour != 12:
                    hour += 12
                elif not is_pm and hour == 12:
                    hour = 0

                return (hour, minute)

            # Handle 24-hour format
            parts = time_str.split(':')
            return (int(parts[0]), int(parts[1]))

        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid time format '{time_str}', using 09:00. Error: {e}")
            return (9, 0)

    def _parse_start_date(self, date_str: str, tz: pytz.BaseTzInfo) -> datetime:
        """Parse ISO8601 start date or use current time as fallback."""
        try:
            # Parse ISO8601 and localize to task timezone
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.astimezone(tz)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid start_date '{date_str}', using current time. Error: {e}")
            return datetime.now(tz)

    def _register_task_job(self, task: TaskRecord):
        """
        Register a single task as an APScheduler job.

        Args:
            task: TaskRecord to register
        """
        try:
            trigger = self._build_trigger(task.schedule_config)

            if not trigger:
                logger.warning(f"Could not build trigger for task {task.name} (ID: {task.id})")
                return

            # Register job with APScheduler
            self.scheduler.add_job(
                func=self.execute_task,
                trigger=trigger,
                args=[task, task.user_id],
                id=f"task_{task.id}",
                name=f"Task: {task.name}",
                replace_existing=True,
                misfire_grace_time=300,  # 5 minutes
            )

            logger.info(f"Registered task: {task.name} (ID: {task.id}) with frequency {task.schedule_config.frequency}")

        except Exception as e:
            logger.error(f"Failed to register task {task.name} (ID: {task.id}): {e}", exc_info=True)

    def unregister_task_job(self, task_id: str):
        """
        Remove a task from the scheduler.

        Args:
            task_id: Task ID to unregister
        """
        try:
            job_id = f"task_{task_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"Unregistered task: {task_id}")
        except Exception as e:
            logger.debug(f"Job {task_id} not found in scheduler: {e}")

    async def _load_active_tasks(self):
        """
        Load all active tasks from database across all users.

        Returns:
            List of TaskRecord objects
        """
        try:
            pg = await get_postgres_rls_client()

            # Step 1: Get all user IDs (users table has no RLS)
            async with pg.pool.acquire() as conn:
                users = await conn.fetch("SELECT id FROM users WHERE id IS NOT NULL")

            user_ids = [str(u['id']) for u in users]
            logger.info(f"Loading tasks for {len(user_ids)} users")

            # Step 2: Load active tasks respecting RLS per user
            tasks: list[TaskRecord] = []
            semaphore = asyncio.Semaphore(10)

            async def _load_for_user(uid: str):
                async with semaphore:
                    try:
                        user_tasks = await self.repository.list_tasks(
                            uid,
                            limit=500,
                            offset=0,
                            status=TaskStatus.ACTIVE,
                        )
                        tasks.extend(user_tasks)
                    except Exception as e:
                        logger.warning("Failed to load tasks for user %s: %s", uid, e)

            await asyncio.gather(*[_load_for_user(uid) for uid in user_ids])

            logger.info(f"Loaded {len(tasks)} active tasks")
            return tasks

        except Exception as e:
            logger.error(f"Failed to load active tasks: {e}", exc_info=True)
            return []

    async def start(self):
        """
        Start the scheduler and register all active tasks.
        Loads tasks from database and registers each as an APScheduler job.
        """
        async with self._lock:
            if self.is_running:
                logger.warning("Task scheduler already running")
                return

            try:
                # Load all active tasks from database
                tasks = await self._load_active_tasks()

                # Register each task as an APScheduler job
                for task in tasks:
                    self._register_task_job(task)

                # Start the scheduler
                self.scheduler.start()
                self.is_running = True

                logger.info(
                    f"Task scheduler started with {len(tasks)} active tasks, "
                    f"max {self.max_concurrent_workers} concurrent workers"
                )

            except Exception as e:
                logger.error(f"Failed to start task scheduler: {e}", exc_info=True)

    async def stop(self):
        """Stop the scheduler gracefully."""
        async with self._lock:
            if self.is_running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("Task scheduler stopped")


# Global scheduler instance
task_scheduler = TaskScheduler()


async def start_task_scheduler():
    """Initialize and start the task scheduler."""
    enabled = os.getenv("TASK_SCHEDULER_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("Task scheduler disabled by TASK_SCHEDULER_ENABLED flag")
        return

    try:
        await task_scheduler.start()
        logger.info("Task scheduler initialized")
    except Exception as e:
        logger.error(f"Failed to start task scheduler: {e}", exc_info=True)


async def stop_task_scheduler():
    """Stop the task scheduler gracefully."""
    try:
        await task_scheduler.stop()
        logger.info("Task scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping task scheduler: {e}", exc_info=True)
