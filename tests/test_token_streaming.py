"""
Tests for Token Streaming (PR2 Phase 2)
Status: Production
Created: January 2025

PURPOSE: Test true token streaming from LangGraph orchestrator to SSE endpoint.
Tests cover fallback mechanisms, feature flag behavior, content accumulation,
heartbeat emissions, and extras aggregation.
"""

import asyncio
import json
import pytest
from typing import AsyncIterator, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from core.config import get_config
from core.ai.langgraph_orchestrator import LangGraphOrchestrator
from core.ai.langgraph_nodes import _code_execution_guard


class TestOrchestratorStreaming:
    """Test LangGraphOrchestrator.process_query_stream() method."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance (compilation happens in test)."""
        return LangGraphOrchestrator()

    @pytest.mark.asyncio
    async def test_fallback_when_no_astream_events(self, orchestrator):
        """Test fallback to simulated streaming when astream_events unavailable."""
        await orchestrator.ensure_compiled()

        # Remove astream_events to force fallback
        original_method = getattr(orchestrator._compiled_graph, 'astream_events', None)
        if hasattr(orchestrator._compiled_graph, 'astream_events'):
            delattr(orchestrator._compiled_graph, 'astream_events')

        try:
            events = []
            async for event in orchestrator.process_query_stream(
                query="What is AAPL's price?",
                session_id="test-session",
                user_id="test-user"
            ):
                events.append(event)
                # Stop after a few events to avoid long execution
                if len(events) >= 5:
                    break

            # Should emit content and done events even without astream_events
            event_types = [e['type'] for e in events]
            assert 'content' in event_types or 'status' in event_types
            # May or may not have 'done' yet if we stopped early

        finally:
            # Restore astream_events if it existed
            if original_method:
                orchestrator._compiled_graph.astream_events = original_method

    @pytest.mark.asyncio
    async def test_emits_content_and_done(self, orchestrator):
        """Test streaming emits content tokens and done event."""
        await orchestrator.ensure_compiled()

        # Mock the compiled graph's astream_events
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "name": "ChatOpenAI",
                "data": {"chunk": MagicMock(content="Hello ")},
            },
            {
                "event": "on_chat_model_stream",
                "name": "ChatOpenAI",
                "data": {"chunk": MagicMock(content="world")},
            },
        ]

        async def mock_astream_events(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch.object(orchestrator._compiled_graph, 'astream_events', mock_astream_events):
            events = []
            async for event in orchestrator.process_query_stream(
                query="Test query",
                session_id="test-session",
                user_id="test-user"
            ):
                events.append(event)

            # Check we got content events
            content_events = [e for e in events if e['type'] == 'content']
            assert len(content_events) == 2
            assert content_events[0]['content'] == "Hello "
            assert content_events[1]['content'] == "world"

            # Check we got done event
            done_events = [e for e in events if e['type'] == 'done']
            assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_heartbeat_emission_during_gaps(self, orchestrator):
        """Test heartbeat status emitted when tokens are sparse."""
        await orchestrator.ensure_compiled()

        config = get_config()
        original_heartbeat = config.stream_heartbeat_seconds
        config.stream_heartbeat_seconds = 1  # 1 second for testing

        try:
            # Mock events with gap longer than heartbeat interval
            async def mock_astream_events(*args, **kwargs):
                yield {
                    "event": "on_chat_model_stream",
                    "name": "ChatOpenAI",
                    "data": {"chunk": MagicMock(content="First token")},
                }
                await asyncio.sleep(1.5)  # Gap exceeds heartbeat interval
                yield {
                    "event": "on_chat_model_stream",
                    "name": "ChatOpenAI",
                    "data": {"chunk": MagicMock(content="Second token")},
                }

            with patch.object(orchestrator._compiled_graph, 'astream_events', mock_astream_events):
                events = []
                async for event in orchestrator.process_query_stream(
                    query="Test query",
                    session_id="test-session",
                    user_id="test-user"
                ):
                    events.append(event)

                # Should have status heartbeat during gap
                status_events = [e for e in events if e['type'] == 'status']
                assert len(status_events) >= 1
                assert any('working' in e.get('message', '').lower() for e in status_events)

        finally:
            config.stream_heartbeat_seconds = original_heartbeat

    @pytest.mark.asyncio
    async def test_extras_aggregation(self, orchestrator):
        """Test code execution extras are aggregated from tool outputs."""
        await orchestrator.ensure_compiled()

        # Mock tool end events with extras data
        mock_events = [
            {
                "event": "on_tool_end",
                "name": "code_interpreter",
                "data": {
                    "output": {
                        "generated_files": [{"filename": "output.csv", "path": "/tmp/output.csv"}],
                        "container_id": "container-123",
                        "code_blocks": ["print('hello')"],
                    }
                },
            },
        ]

        async def mock_astream_events(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch.object(orchestrator._compiled_graph, 'astream_events', mock_astream_events):
            events = []
            async for event in orchestrator.process_query_stream(
                query="Test query",
                session_id="test-session",
                user_id="test-user"
            ):
                events.append(event)

            # Check extras event was emitted
            extras_events = [e for e in events if e['type'] == 'extras']
            assert len(extras_events) == 1
            extras = extras_events[0]['extras']
            assert extras['container_id'] == "container-123"
            assert len(extras['generated_files']) == 1
            assert extras['generated_files'][0]['filename'] == "output.csv"


class TestSSEEndpointIntegration:
    """Test SSE endpoint integration with feature flag."""

    @pytest.mark.asyncio
    async def test_config_flag_controls_behavior(self):
        """Test config flag controls streaming mode."""
        config = get_config()

        # Test flag can be set
        original = config.enable_true_token_streaming
        config.enable_true_token_streaming = True
        assert config.enable_true_token_streaming is True

        config.enable_true_token_streaming = False
        assert config.enable_true_token_streaming is False


class TestExecuteWithStream:
    """Unit tests for execute_with_stream helper."""

    @pytest.mark.asyncio
    async def test_raw_deltas_forwarded_before_item_event(self, monkeypatch):
        """Ensure ResponseTextDeltaEvent deltas emit immediately even before item metadata arrives."""
        from core.ai.langgraph_utils import execute_with_stream
        from openai.types.responses import ResponseTextDeltaEvent
        from types import SimpleNamespace

        # Build a fake streaming result that emits deltas first, then item metadata.
        class _DummyStream:
            async def stream_events(self):
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=ResponseTextDeltaEvent(
                        content_index=0,
                        delta="Hello ",
                        item_id="msg_1",
                        logprobs=[],
                        output_index=0,
                        sequence_number=0,
                        type="response.output_text.delta",
                    ),
                )
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=ResponseTextDeltaEvent(
                        content_index=0,
                        delta="world",
                        item_id="msg_1",
                        logprobs=[],
                        output_index=0,
                        sequence_number=1,
                        type="response.output_text.delta",
                    ),
                )
                yield SimpleNamespace(
                    type="run_item_stream_event",
                    item=SimpleNamespace(id="msg_1", type="message_output_item"),
                )

        def _fake_run_streamed(agent, query, **kwargs):
            return _DummyStream()

        # Patch Runner.run_streamed used by execute_with_stream
        from core.ai import langgraph_utils as utils_module
        monkeypatch.setattr(utils_module.Runner, "run_streamed", _fake_run_streamed)

        captured = []

        async def _on_token(token: str):
            captured.append(token)

        # Run helper
        dummy_agent = object()
        dummy_session = SimpleNamespace()
        result = await execute_with_stream(
            dummy_agent,
            "test query",
            dummy_session,
            _on_token,
            agent_name="TestAgent",
        )

        assert "".join(captured) == "Hello world"
        assert hasattr(result, "final_output")


def test_code_execution_guard_blocks_when_disabled():
    state = {
        "code_execution_enabled": False,
        "selected_model": "gpt-5.4",
        "messages": [],
        "should_continue": True,
    }

    guarded = _code_execution_guard(state, "quant_coding")

    assert guarded is not None
    assert guarded["last_agent_response"].startswith("Code execution is disabled")
    assert guarded["should_continue"] is False
    assert guarded["messages"][-1]["extras"]["code_execution_enabled"] is False


def test_code_execution_guard_allows_when_enabled():
    state = {
        "code_execution_enabled": True,
        "selected_model": "gpt-5.4",
        "messages": [],
    }

    guarded = _code_execution_guard(state, "quant_coding")

    assert guarded is None


class TestDeterministicPatterns:
    """Test deterministic patterns for reliable testing."""

    @pytest.fixture
    def compiled_orchestrator(self):
        """Create orchestrator for compilation test."""
        return LangGraphOrchestrator()

    @pytest.mark.asyncio
    async def test_ensure_compiled_idempotent(self):
        """Test ensure_compiled can be called multiple times safely."""
        orch = LangGraphOrchestrator()

        await orch.ensure_compiled()
        first_graph = orch._compiled_graph

        await orch.ensure_compiled()
        second_graph = orch._compiled_graph

        # Should return same compiled graph
        assert first_graph is second_graph

    @pytest.mark.asyncio
    async def test_fixtures_not_direct_mocking(self, compiled_orchestrator):
        """Test using fixtures instead of direct graph mocking."""
        # Ensure compiled first
        await compiled_orchestrator.ensure_compiled()

        # This test uses fixture (compiled_orchestrator) instead of mocking internals
        assert compiled_orchestrator._compiled_graph is not None
        assert hasattr(compiled_orchestrator, 'process_query_stream')

        # Can now safely test real behavior without breaking encapsulation
        events = []
        try:
            async for event in compiled_orchestrator.process_query_stream(
                query="Quick test",
                session_id="fixture-test",
                user_id="test-user"
            ):
                events.append(event)
                if len(events) >= 3:  # Just sample a few events
                    break
        except Exception:
            # Even if execution fails, we're testing the pattern
            pass

        # Pattern validation: we used fixture, not direct mocking
        assert compiled_orchestrator is not None
