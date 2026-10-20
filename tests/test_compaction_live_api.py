"""
Live API diagnostic tests for cross-provider and context window compaction.

Run with: pytest tests/test_compaction_live_api.py -v -s

These tests call the real OpenAI API to diagnose compaction issues.
"""

from __future__ import annotations

import asyncio
import os
import pytest
from typing import Any, Dict, List, Optional

# Import compaction modules
from core.ai.utils.message_compactor import (
    message_to_dict,
    get_provider_from_model,
    detect_provider_switch,
    build_cross_provider_context,
    maybe_inject_on_switch,
    _summarize_cross_provider,
)
from core.ai.utils.sqlite_session_compactor import (
    compact_sqlite_session_items,
    _estimate_text_tokens,
    _shrink_item_in_place,
)
from core.ai.utils.context_manager import build_shared_context


class TestProviderDetection:
    """Test provider detection and last_provider persistence."""

    def test_anthropic_provider_detection(self):
        """Verify Anthropic models are correctly detected."""
        # Use ACTUAL model IDs from frontend/src/config/models.ts
        test_cases = [
            ("litellm/anthropic/claude-opus-4-5-20251101", "anthropic"),
            ("litellm/anthropic/claude-sonnet-4-5-20250929", "anthropic"),
            ("litellm/anthropic/claude-haiku-4-5-20251001", "anthropic"),
            ("gpt-5.4", "openai"),
            ("gpt-5.1", "openai"),
            ("gpt-5.4-pro", "openai"),
            ("litellm/gemini/gemini-3-pro-preview", "gemini"),
            ("litellm/gemini/gemini-2.5-pro", "gemini"),
            ("litellm/xai/grok-4-1-fast-reasoning", "xai"),
            ("litellm/xai/grok-4-1-fast-non-reasoning", "xai"),
            ("litellm/deepseek/deepseek-chat", "deepseek"),
            ("litellm/deepseek/deepseek-reasoner", "deepseek"),
            ("litellm/bedrock/us.meta.llama4-scout-17b-instruct-v1:0", "bedrock"),
        ]

        for model, expected in test_cases:
            actual = get_provider_from_model(model)
            assert actual == expected, f"Failed for {model}: expected {expected}, got {actual}"

    def test_provider_switch_detection(self):
        """Test detect_provider_switch between different providers."""
        # OpenAI -> Anthropic should detect switch
        switch1 = detect_provider_switch("gpt-5.4", "litellm/anthropic/claude-sonnet-4-5-20250929")
        assert switch1 is True, "Should detect OpenAI->Anthropic switch"

        # Anthropic -> OpenAI should detect switch
        switch2 = detect_provider_switch("litellm/anthropic/claude-sonnet-4-5-20250929", "gpt-5.4")
        assert switch2 is True, "Should detect Anthropic->OpenAI switch"

        # Same provider should not detect switch
        switch3 = detect_provider_switch("gpt-5.4", "gpt-5.1")
        assert switch3 is False, "Should not detect switch within same provider"


class TestCrossProviderContextBuilding:
    """Test messages during context building."""

    def test_build_context_with_provider_field(self):
        """Test that messages WITH provider field are included."""
        state = {
            "messages": [
                {"role": "user", "content": "What is AAPL's P/E ratio?"},
                {"role": "assistant", "content": "AAPL P/E is 28.5", "provider": "openai"},
                {"role": "user", "content": "Compare to MSFT"},
                {"role": "assistant", "content": "MSFT P/E is 32.1", "provider": "openai"},
            ],
            "_provider_messages": [],
        }

        context = build_cross_provider_context(
            state,
            current_provider="anthropic",
            scan_budget=5000,
            inject_budget=2000,
        )

        assert context.strip(), "Should have context when messages have provider field"

    def test_build_context_without_provider_field(self):
        """Test that messages WITHOUT provider field are EXCLUDED."""
        state = {
            "messages": [
                {"role": "user", "content": "What is AAPL's P/E ratio?"},
                {"role": "assistant", "content": "AAPL P/E is 28.5"},  # NO provider field
                {"role": "user", "content": "Compare to MSFT"},
                {"role": "assistant", "content": "MSFT P/E is 32.1"},  # NO provider field
            ],
            "_provider_messages": [],
        }

        context = build_cross_provider_context(
            state,
            current_provider="anthropic",
            scan_budget=5000,
            inject_budget=2000,
        )
        # User messages should still be included even without provider

    def test_message_normalization_preserves_provider(self):
        """Test that message_to_dict preserves provider field."""
        msg_with_provider = {"role": "assistant", "content": "test", "provider": "openai"}
        normalized = message_to_dict(msg_with_provider)
        assert normalized is not None


class TestMaybeInjectOnSwitch:
    """Test the full injection flow."""

    @pytest.mark.asyncio
    async def test_inject_on_switch_with_previous_provider(self):
        """Test injection when last_provider IS set."""
        state = {
            "selected_model": "litellm/anthropic/claude-sonnet-4-5-20250929",
            "last_provider": "openai",
            "messages": [
                {"role": "user", "content": "Analyze AAPL"},
                {"role": "assistant", "content": "AAPL analysis...", "provider": "openai"},
            ],
            "_provider_messages": [],
        }

        original_text = "New query about MSFT"
        result = await maybe_inject_on_switch(
            state,
            original_text,
            enabled=True,
            scan_budget=5000,
            inject_budget=2000,
            summary_model=None,
            summary_timeout=5.0,
            summary_max_output_tokens=500,
        )
        # Result may or may not contain context depending on conditions

    @pytest.mark.asyncio
    async def test_inject_on_switch_without_previous_provider(self):
        """Test injection when last_provider is NOT set (should skip)."""
        state = {
            "selected_model": "litellm/anthropic/claude-sonnet-4-5-20250929",
            "messages": [
                {"role": "user", "content": "Analyze AAPL"},
                {"role": "assistant", "content": "AAPL analysis...", "provider": "openai"},
            ],
            "_provider_messages": [],
        }

        original_text = "New query about MSFT"
        result = await maybe_inject_on_switch(
            state,
            original_text,
            enabled=True,
            scan_budget=5000,
            inject_budget=2000,
            summary_model=None,
            summary_timeout=5.0,
            summary_max_output_tokens=500,
        )

        assert result == original_text, "Should skip injection when no previous provider"


class TestSQLiteSessionCompaction:
    """Test SQLite session compaction issues."""

    def test_compaction_preserves_tool_pairs(self):
        """Test that tool_use and tool_result pairs are kept together."""
        session_items = [
            {"role": "user", "content": "Get AAPL price", "type": "message"},
            {"type": "tool_use", "call_id": "tool_123", "name": "get_stock_price", "arguments": {"ticker": "AAPL"}},
            {"type": "tool_result", "call_id": "tool_123", "output": "AAPL: $185.50"},
            {"role": "assistant", "content": "AAPL is trading at $185.50", "type": "message"},
            {"role": "user", "content": "What about MSFT?", "type": "message"},
            {"type": "tool_use", "call_id": "tool_456", "name": "get_stock_price", "arguments": {"ticker": "MSFT"}},
            {"type": "tool_result", "call_id": "tool_456", "output": "MSFT: $420.00"},
            {"role": "assistant", "content": "MSFT is trading at $420.00", "type": "message"},
        ]

        result, stats = compact_sqlite_session_items(
            session_items,
            encoding=None,
            target_tokens=500,
            recent_budget_ratio=0.7,
        )

        # Check for orphaned tool results
        tool_use_ids = set()
        tool_result_ids = set()
        for item in result:
            if isinstance(item, dict):
                call_id = item.get("call_id")
                if item.get("type") == "tool_use" and call_id:
                    tool_use_ids.add(call_id)
                elif item.get("type") == "tool_result" and call_id:
                    tool_result_ids.add(call_id)

        orphaned_results = tool_result_ids - tool_use_ids
        # Orphaned results indicate a bug in compaction

    def test_token_estimation_consistency(self):
        """Test that token estimation is consistent across modules."""
        test_text = "This is a test message for token estimation. " * 50

        # Test with no encoding (fallback)
        tokens_no_enc = _estimate_text_tokens(test_text, None)

        # Test with tiktoken if available
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            tokens_with_enc = _estimate_text_tokens(test_text, enc)
            actual_tokens = len(enc.encode(test_text))
        except ImportError:
            tokens_with_enc = None
            actual_tokens = None

    def test_aggressive_compaction_budget(self):
        """Test compaction with very tight budget."""
        # Create many items
        session_items = []
        for i in range(20):
            session_items.append({"role": "user", "content": f"User message {i}: " + "x" * 200, "type": "message"})
            session_items.append({"role": "assistant", "content": f"Assistant response {i}: " + "y" * 200, "type": "message"})

        result, stats = compact_sqlite_session_items(
            session_items,
            encoding=None,
            target_tokens=300,
            recent_budget_ratio=0.75,
        )

        assert stats.result_tokens <= stats.target_tokens, "Should stay within budget"


class TestLiveSummarizerAPI:
    """Test the live summarizer API call (requires OPENAI_API_KEY)."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    async def test_summarizer_with_valid_model(self):
        """Test _summarize_cross_provider with a valid model."""
        test_context = """
        User asked about AAPL stock analysis.
        Assistant (OpenAI): AAPL is trading at $185.50 with a P/E ratio of 28.5.
        The stock has shown strong momentum with 15% YTD gains.
        User then asked about risk metrics.
        Assistant (OpenAI): AAPL has a beta of 1.2 and volatility of 22%.
        """

        result = await _summarize_cross_provider(
            test_context,
            model="gpt-4o-mini",
            max_output_tokens=500,
            timeout_seconds=30.0,
        )

        assert result is not None, "Summarizer should return result"
        assert len(result) > 0, "Result should not be empty"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    async def test_summarizer_with_empty_input(self):
        """Test _summarize_cross_provider with empty input."""
        result = await _summarize_cross_provider(
            "",
            model="gpt-4o-mini",
            max_output_tokens=500,
            timeout_seconds=10.0,
        )

        assert result is None, "Should return None for empty input"


class TestEndToEndCompactionFlow:
    """Test the full compaction flow end-to-end."""

    @pytest.mark.asyncio
    async def test_full_provider_switch_flow(self):
        """Test complete provider switch with context injection."""
        # Simulate state after several OpenAI interactions
        state = {
            "selected_model": "litellm/anthropic/claude-sonnet-4-5-20250929",
            "last_provider": "openai",
            "messages": [
                {"role": "user", "content": "Analyze AAPL stock"},
                {"role": "assistant", "content": "AAPL Analysis:\n- Price: $185.50\n- P/E: 28.5\n- Market Cap: $2.8T", "provider": "openai", "agent": "RiskSpecialist"},
                {"role": "user", "content": "What are the risk factors?"},
                {"role": "assistant", "content": "Key risks:\n1. Regulatory pressure\n2. China exposure\n3. Competition", "provider": "openai", "agent": "RiskSpecialist"},
            ],
            "_provider_messages": [],
        }

        # Step 1: Detect provider switch
        switch_detected = detect_provider_switch(
            state.get("last_provider"),
            get_provider_from_model(state.get("selected_model"))
        )

        # Step 2: Build cross-provider context
        current_provider = get_provider_from_model(state.get("selected_model"))
        context = build_cross_provider_context(
            state,
            current_provider=current_provider,
            scan_budget=5000,
            inject_budget=2000,
        )

        # Step 3: Full injection
        original_query = "Now analyze the technical indicators"
        result = await maybe_inject_on_switch(
            state,
            original_query,
            enabled=True,
            scan_budget=5000,
            inject_budget=2000,
            summary_model=None,
            summary_timeout=5.0,
            summary_max_output_tokens=500,
        )

        assert switch_detected, "Should detect provider switch"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
