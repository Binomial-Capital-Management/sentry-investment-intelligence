"""
Tasks service layer orchestrating validation, persistence, and execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from core.tasks.db import TasksRepository
from core.tasks.delivery import ADAPTERS
from core.tasks.executor import TaskExecutor
from core.tasks.types import TaskRecord, TaskRunRecord, TaskTriggerType

logger = logging.getLogger(__name__)


class TasksService:
    def __init__(self, repository: Optional[TasksRepository] = None) -> None:
        self.repository = repository or TasksRepository()
        self.executor = TaskExecutor(repository=self.repository, delivery_adapters=ADAPTERS)

    async def trigger_run(
        self,
        task: TaskRecord,
        run: TaskRunRecord,
        background_tasks: any,
    ) -> None:
        """Execute task in background with FastAPI tracking."""
        async def _runner() -> None:
            try:
                await self.executor.run_task(task, run)
            except Exception as e:
                logger.exception("Task execution failed: task=%s run=%s", task.id, run.id)
                # CRITICAL: Update run status to FAILED
                try:
                    from core.tasks.types import TaskRunStatus
                    await self.repository.mark_run_status(
                        run.id,
                        task.user_id,
                        TaskRunStatus.FAILED,
                        error_message=str(e),
                        org_id=task.org_id,
                    )
                except Exception as update_error:
                    logger.exception("Failed to update run status: %s", update_error)

        background_tasks.add_task(_runner)
