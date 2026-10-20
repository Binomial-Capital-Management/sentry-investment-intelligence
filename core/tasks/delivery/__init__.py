"""
Delivery adapter registry for tasks.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

from core.tasks.types import TaskDeliveryChannel, TaskDeliveryStep

if TYPE_CHECKING:
    from core.tasks.executor import TaskRunContext

from .email_adapter import EmailDeliveryAdapter
from .save_to_sentry_adapter import SaveToSentryAdapter
from .slack_adapter import SlackDeliveryAdapter
from .teams_adapter import TeamsDeliveryAdapter


class NotImplementedAdapter:
    async def deliver(self, step: TaskDeliveryStep, context: 'TaskRunContext') -> Dict[str, Any]:
        return {
            "status": "skipped",
            "detail": f"Delivery channel {step.channel.value} not implemented",
        }


ADAPTERS: Dict[TaskDeliveryChannel, Any] = {
    TaskDeliveryChannel.EMAIL: EmailDeliveryAdapter(),
    TaskDeliveryChannel.SLACK: SlackDeliveryAdapter(),
    TaskDeliveryChannel.TEAMS: TeamsDeliveryAdapter(),
    TaskDeliveryChannel.SAVE_TO_SENTRY: SaveToSentryAdapter(),
}


async def deliver(step: TaskDeliveryStep, context: 'TaskRunContext') -> Dict[str, Any]:
    adapter = ADAPTERS.get(step.channel)
    if not adapter:
        return {"status": "skipped", "detail": f"No adapter for {step.channel.value}"}
    return await adapter.deliver(step, context)
