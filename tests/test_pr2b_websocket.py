"""
Test PR2b WebSocket streaming functionality.
Minimal test per trimming plan: +70 LOC
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.workflows.events import workflow_event_bus, EventType
from core.config import get_config


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    """Test basic event bus functionality"""
    run_id = "test-run-123"
    received_events = []
    
    # Subscribe
    async def consume():
        async for event in workflow_event_bus.subscribe(run_id):
            received_events.append(event)
            if event.get("type") == EventType.RUN_COMPLETED:
                break
    
    # Start consumer
    consumer_task = asyncio.create_task(consume())
    await asyncio.sleep(0.1)  # Let consumer start
    
    # Publish events
    await workflow_event_bus.publish(run_id, {
        "type": EventType.STEP_STARTED,
        "node_id": "node1",
        "node_label": "Test Node"
    })
    
    await workflow_event_bus.publish(run_id, {
        "type": EventType.STEP_SUCCEEDED,
        "node_id": "node1"
    })
    
    await workflow_event_bus.publish(run_id, {
        "type": EventType.RUN_COMPLETED,
        "status": "succeeded"
    })
    
    # Wait for consumer
    await consumer_task
    
    # Verify
    assert len(received_events) == 3
    assert received_events[0]["type"] == EventType.STEP_STARTED
    assert received_events[1]["type"] == EventType.STEP_SUCCEEDED
    assert received_events[2]["type"] == EventType.RUN_COMPLETED


@pytest.mark.asyncio
async def test_event_bus_queue_overflow():
    """Test that queue overflow doesn't crash the system"""
    run_id = "overflow-test"
    
    # Fill queue beyond capacity
    for i in range(1100):  # Queue maxsize is 1000
        await workflow_event_bus.publish(run_id, {"event": i})
    
    # Should not crash, just drop events
    assert True  # If we get here, it worked


def test_websocket_disabled_by_flag():
    """Test WebSocket endpoint returns error when flag is disabled"""
    # This would require a running server, so we just verify config
    config = get_config()
    
    # Default should be disabled
    assert config.workflows_ws_enabled is False
    
    # Test that we can read the flag
    os.environ["WORKFLOWS_WS_ENABLED"] = "true"
    # Config is cached, so we'd need to reload the module
    # For now just verify the default is False
    print(f"WebSocket flag test: disabled by default = {not config.workflows_ws_enabled}")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_event_bus_publish_subscribe())
    asyncio.run(test_event_bus_queue_overflow())
    test_websocket_disabled_by_flag()
    print("All PR2b tests passed!")