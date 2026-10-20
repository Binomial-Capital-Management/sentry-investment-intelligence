"""
Save-to-Sentry delivery adapter.
Persists the current task output so the history tab can render it later.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from core.tasks.db import TasksRepository
from core.tasks.types import TaskDeliveryStep

if TYPE_CHECKING:
    from core.tasks.executor import TaskRunContext


class SaveToSentryAdapter:
    """Writes the final task output to the task_saved_outputs table."""

    def __init__(self, repository: Optional[TasksRepository] = None) -> None:
        self.repository = repository or TasksRepository()

    async def deliver(self, step: TaskDeliveryStep, context: "TaskRunContext") -> Dict[str, Any]:
        metadata = {
            "channel": step.channel.value,
            "params": step.params or {},
        }
        await self.repository.save_run_output(
            user_id=context.user_id,
            task_id=context.task.id,
            run_id=context.run_id,
            output=context.current_output,
            artifacts=context.artifacts,
            delivery_metadata=metadata,
        )
        return {
            "status": "stored",
            "detail": "Saved task output to history",
        }
