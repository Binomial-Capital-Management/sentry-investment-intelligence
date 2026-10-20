"""LitellmModel subclass that injects Anthropic prompt caching breakpoints.

Adds ``cache_control: {"type": "ephemeral"}`` to the system prompt, last tool
definition, and last user message before calling ``litellm.acompletion()``.
This yields ~90 % cost reduction on cached tokens after the first API call in
a multi-turn session.

Only activates for Anthropic / Claude models; all other providers fall through
to the parent implementation unchanged.
"""

from __future__ import annotations

import json
import logging
import time
from copy import copy
from typing import Any, Literal, overload

import litellm
from openai import AsyncStream, NotGiven, omit
from openai.types.chat import ChatCompletionChunk
from openai.types.responses import Response

from agents import _debug
from agents.extensions.models.litellm_model import LitellmModel
from agents.handoffs import Handoff
from agents.agent_output import AgentOutputSchemaBase
from agents.items import TResponseInputItem
from agents.model_settings import ModelSettings
from agents.models.chatcmpl_converter import Converter
from agents.models.fake_id import FAKE_RESPONSES_ID
from agents.models.interface import ModelTracing
from agents.models.openai_responses import Converter as OpenAIResponsesConverter
from agents.tool import Tool
from agents.tracing.span_data import GenerationSpanData
from agents.tracing.spans import Span
from agents.util._json import _to_dump_compatible

logger = logging.getLogger(__name__)

CACHE_CONTROL_EPHEMERAL = {"type": "ephemeral"}


class CachingLitellmModel(LitellmModel):
    """LitellmModel with Anthropic prompt-caching breakpoints."""

    # ------------------------------------------------------------------
    # Cache injection
    # ------------------------------------------------------------------

    @property
    def _is_anthropic(self) -> bool:
        model_lower = self.model.lower()
        return "anthropic" in model_lower or "claude" in model_lower

    @staticmethod
    def _inject_cache_breakpoints(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> None:
        """Mutate *messages* and *tools* in-place to add cache_control markers."""
        cc = CACHE_CONTROL_EPHEMERAL

        # 1. System prompt (first in prefix order after tools)
        for msg in messages:
            if msg.get("role") == "system":
                content = msg["content"]
                if isinstance(content, str):
                    msg["content"] = [
                        {"type": "text", "text": content, "cache_control": cc}
                    ]
                elif isinstance(content, list) and content:
                    content[-1]["cache_control"] = cc
                break

        # 2. Last tool definition
        if tools:
            tools[-1]["cache_control"] = cc

        # 3. Last user message (enables multi-turn prefix caching)
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg["content"]
                if isinstance(content, str):
                    msg["content"] = [
                        {"type": "text", "text": content, "cache_control": cc}
                    ]
                elif isinstance(content, list) and content:
                    content[-1]["cache_control"] = cc
                break

    # ------------------------------------------------------------------
    # Overridden _fetch_response — identical to parent except for the
    # _inject_cache_breakpoints call before litellm.acompletion().
    # Pinned to openai-agents==0.6.4.
    # ------------------------------------------------------------------

    @overload
    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        span: Span[GenerationSpanData],
        tracing: ModelTracing,
        stream: Literal[True],
        prompt: Any | None = None,
    ) -> tuple[Response, AsyncStream[ChatCompletionChunk]]: ...

    @overload
    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        span: Span[GenerationSpanData],
        tracing: ModelTracing,
        stream: Literal[False],
        prompt: Any | None = None,
    ) -> litellm.types.utils.ModelResponse: ...

    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        span: Span[GenerationSpanData],
        tracing: ModelTracing,
        stream: bool = False,
        prompt: Any | None = None,
    ) -> litellm.types.utils.ModelResponse | tuple[Response, AsyncStream[ChatCompletionChunk]]:
        if not self._is_anthropic:
            return await super()._fetch_response(
                system_instructions, input, model_settings, tools,
                output_schema, handoffs, span, tracing, stream, prompt,
            )

        # -- Begin copied logic from LitellmModel._fetch_response (v0.12.5) --

        preserve_thinking_blocks = (
            model_settings.reasoning is not None
            and model_settings.reasoning.effort is not None
        )

        converted_messages = Converter.items_to_messages(
            input,
            preserve_thinking_blocks=preserve_thinking_blocks,
            preserve_tool_output_all_content=True,
            model=self.model,
        )

        converted_messages = self._fix_tool_message_ordering(converted_messages)

        if system_instructions:
            converted_messages.insert(
                0,
                {
                    "content": system_instructions,
                    "role": "system",
                },
            )
        converted_messages = _to_dump_compatible(converted_messages)

        if tracing.include_data():
            span.span_data.input = converted_messages

        parallel_tool_calls = (
            True
            if model_settings.parallel_tool_calls and tools and len(tools) > 0
            else False
            if model_settings.parallel_tool_calls is False
            else None
        )
        tool_choice = Converter.convert_tool_choice(model_settings.tool_choice)
        response_format = Converter.convert_response_format(output_schema)

        converted_tools = [Converter.tool_to_openai(tool) for tool in tools] if tools else []

        for handoff in handoffs:
            converted_tools.append(Converter.convert_handoff_tool(handoff))

        converted_tools = _to_dump_compatible(converted_tools)

        # ---- PROMPT CACHING INJECTION ----
        self._inject_cache_breakpoints(converted_messages, converted_tools)
        logger.debug("[CachingLitellmModel] Injected Anthropic cache breakpoints")

        if _debug.DONT_LOG_MODEL_DATA:
            logger.debug("Calling LLM")
        else:
            messages_json = json.dumps(converted_messages, indent=2, ensure_ascii=False)
            tools_json = json.dumps(converted_tools, indent=2, ensure_ascii=False)
            logger.debug(
                f"Calling Litellm model: {self.model}\n"
                f"{messages_json}\n"
                f"Tools:\n{tools_json}\n"
                f"Stream: {stream}\n"
                f"Tool choice: {tool_choice}\n"
                f"Response format: {response_format}\n"
            )

        reasoning_effort: dict[str, Any] | str | None = None
        if model_settings.reasoning:
            if model_settings.reasoning.summary is not None:
                reasoning_effort = {
                    "effort": model_settings.reasoning.effort,
                    "summary": model_settings.reasoning.summary,
                }
            elif model_settings.reasoning.effort is not None:
                reasoning_effort = model_settings.reasoning.effort

        if (
            reasoning_effort is None
            and isinstance(model_settings.extra_body, dict)
            and "reasoning_effort" in model_settings.extra_body
        ):
            reasoning_effort = model_settings.extra_body["reasoning_effort"]
        if (
            reasoning_effort is None
            and model_settings.extra_args
            and "reasoning_effort" in model_settings.extra_args
        ):
            reasoning_effort = model_settings.extra_args["reasoning_effort"]

        stream_options = None
        if stream and model_settings.include_usage is not None:
            stream_options = {"include_usage": model_settings.include_usage}

        extra_kwargs = {}
        if model_settings.extra_query:
            extra_kwargs["extra_query"] = copy(model_settings.extra_query)
        if model_settings.metadata:
            extra_kwargs["metadata"] = copy(model_settings.metadata)
        if model_settings.extra_body and isinstance(model_settings.extra_body, dict):
            extra_kwargs.update(model_settings.extra_body)

        if model_settings.extra_args:
            extra_kwargs.update(model_settings.extra_args)

        extra_kwargs.pop("reasoning_effort", None)

        ret = await litellm.acompletion(
            model=self.model,
            messages=converted_messages,
            tools=converted_tools or None,
            temperature=model_settings.temperature,
            top_p=model_settings.top_p,
            frequency_penalty=model_settings.frequency_penalty,
            presence_penalty=model_settings.presence_penalty,
            max_tokens=model_settings.max_tokens,
            tool_choice=self._remove_not_given(tool_choice),
            response_format=self._remove_not_given(response_format),
            parallel_tool_calls=parallel_tool_calls,
            stream=stream,
            stream_options=stream_options,
            reasoning_effort=reasoning_effort,
            top_logprobs=model_settings.top_logprobs,
            extra_headers=self._merge_headers(model_settings),
            api_key=self.api_key,
            base_url=self.base_url,
            **extra_kwargs,
        )

        # -- End copied logic --

        if isinstance(ret, litellm.types.utils.ModelResponse):
            return ret

        responses_tool_choice = OpenAIResponsesConverter.convert_tool_choice(
            model_settings.tool_choice
        )
        if responses_tool_choice is None or responses_tool_choice is omit:
            responses_tool_choice = "auto"

        response = Response(
            id=FAKE_RESPONSES_ID,
            created_at=time.time(),
            model=self.model,
            object="response",
            output=[],
            tool_choice=responses_tool_choice,
            top_p=model_settings.top_p,
            temperature=model_settings.temperature,
            tools=[],
            parallel_tool_calls=parallel_tool_calls or False,
            reasoning=model_settings.reasoning,
        )
        return response, ret
