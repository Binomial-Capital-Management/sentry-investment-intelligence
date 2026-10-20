"""
Direct Perplexity web search tool.

Simple, Perplexity-only search that returns an AI-written summary and
structured citations, suitable for chat rendering.

Environment required:
- PERPLEXITY_API_KEY
- PERPLEXITY_MODEL (optional, default: sonar)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

from core.ai.utils.message_compactor import get_provider_from_model

# Load environment variables
load_dotenv()

try:
    from agents.tool import function_tool as tool
except ImportError:
    # Fallback when Agents SDK isn't available
    def tool(func):
        return func

logger = logging.getLogger(__name__)


async def web_search_func(query: str, max_results: int = 20, depth: str = "comprehensive") -> Dict[str, Any]:
    """
    Search the web using Perplexity Sonar.
    Returns a structured response with both formatted text and separate sources.

    Args:
        query: The search query
        max_results: Maximum number of source results to return
        depth: Response depth - "brief", "standard", or "comprehensive" (default)

    Returns:
        Dict with:
        - content: Formatted markdown response
        - sources: List of structured source objects for frontend
        - raw_response: Original AI response
    """
    import os
    import aiohttp
    from openai import OpenAI

    # Detect search provider (separate from agent model)
    search_provider = os.getenv("SEARCH_PROVIDER", "gpt-5.1")
    provider = get_provider_from_model(search_provider)

    current_date = datetime.now().strftime("%B %d, %Y")

    # Use GPT-5 native search for GPT-5 models
    if provider == "openai" and search_provider.startswith("gpt-5"):
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return {
                "content": "OpenAI API key not configured for GPT-5 web search.",
                "sources": [],
                "error": True
            }

        try:
            client = OpenAI(api_key=openai_api_key, timeout=300.0)  # 5 minutes for web search

            # GPT-5 search prompt - optimized for financial news and analysis
            gpt5_search_prompt = f"""You are a web search tool for financial analysis. Today's date is {current_date}.
            MANDATORY: ALL temporal context in searches uses {current_date} as reference.
            - "Latest"/"Recent"/"Today" = relative to {current_date}
            - "This week/month/quarter/year" = period containing {current_date}
            - Date calculations start from {current_date}

            Your role: Search the web and return complete findings. Do not ask follow-up questions or present options.

            Execute the search now and provide all results in your response. Include:
            - All relevant data, metrics, and findings from your search
            - Complete analysis with numbers, dates, and specific details
            - Comprehensive coverage of the topic without requiring further clarification

            **Sources to prioritize:**
            - Financial news: Bloomberg, Reuters, WSJ, FT, CNBC
            - Market data and analysis from reputable sources
            - SEC filings, earnings reports, analyst ratings
            - Economic indicators and central bank data
            - Technical analysis and trading information

            **Output format:**
            - Use ## for main sections, ### for subsections
            - Use **bold** for key metrics, dates, and important points
            - Include specific numbers, percentages, and dates
            - Provide detailed explanations and full context
            - Include all relevant background and analysis
            - Present complete findings - do not ask user to choose between options

            Return comprehensive, verbose results. Include everything you find."""

            # GPT-5 uses Responses API with web_search tool
            response = client.responses.create(
                model=search_provider,
                reasoning={"effort": "medium"},  # Use medium reasoning for financial analysis
                tools=[{
                    "type": "web_search"
                    # No domain filters - GPT-5 will search all relevant sources
                }],
                input=[
                    {
                        "type": "message",
                        "role": "system",
                        "content": gpt5_search_prompt
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": query
                    }
                ]
            )

            # Extract the response from GPT-5 Responses API
            ai_response_parts: List[str] = []
            structured_sources: List[Dict[str, Any]] = []
            seen_urls = set()

            def _from_obj(obj: Any, key: str, default: Any = None):
                if obj is None:
                    return default
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            # Debug logging
            logger.info(f"GPT-5 web search response received, has output: {getattr(response, 'output', None) is not None}")
            
            # Log full response structure for debugging
            try:
                import json as _json
                if hasattr(response, 'model_dump'):
                    resp_dict = response.model_dump()
                else:
                    resp_dict = {"output": str(getattr(response, 'output', None))}
                logger.debug(f"GPT-5 response structure: {_json.dumps(resp_dict, default=str)[:2000]}")
            except Exception as e:
                logger.debug(f"Could not serialize response: {e}")
            
            if getattr(response, "output", None):
                logger.info(f"GPT-5 output has {len(response.output)} items")
                for item_idx, item in enumerate(response.output):
                    content_items = _from_obj(item, "content", [])
                    logger.debug(f"Item {item_idx}: type={type(item)}, has_content={bool(content_items)}")
                    if content_items:
                        for content_item in content_items:
                            text_value = _from_obj(content_item, "text")
                            if text_value:
                                ai_response_parts.append(text_value)

                            annotations = _from_obj(content_item, "annotations", []) or []
                            logger.debug(f"Content item has {len(annotations)} annotations")
                            for ann in annotations:
                                ann_type = _from_obj(ann, "type", "")
                                # OpenAI uses "url_citation" type for web search citations
                                if ann_type != "url_citation":
                                    continue

                                url = _from_obj(ann, "url", "")
                                if not url:
                                    continue
                                if url in seen_urls:
                                    continue
                                if len(structured_sources) >= max_results:
                                    continue

                                seen_urls.add(url)
                                title = _from_obj(ann, "title", "")
                                # Extract only first sentence/line as title (max 100 chars)
                                if title:
                                    # Take first line or sentence
                                    title = title.split('\n')[0].split('. ')[0]
                                    if len(title) > 100:
                                        title = title[:100].rsplit(' ', 1)[0] + "..."
                                snippet = _from_obj(ann, "snippet", "") or _from_obj(ann, "description", "")
                                source = {
                                    "id": len(structured_sources) + 1,  # Use integer ID for frontend compatibility
                                    "title": title or _from_obj(ann, "site_name", "") or "Referenced source",
                                    "url": url,
                                    "snippet": snippet,
                                    "domain": _from_obj(ann, "site_name", "") or urlparse(url).netloc,
                                    "published_date": _from_obj(ann, "published_at") or _from_obj(ann, "published_date"),
                                    "score": _from_obj(ann, "score", 0.9),
                                    "index": len(structured_sources) + 1,
                                }
                                structured_sources.append(source)
                    else:
                        text_value = _from_obj(item, "text")
                        if text_value:
                            ai_response_parts.append(text_value)
                        elif isinstance(item, str):
                            ai_response_parts.append(item)

            # Fallback to legacy citations field if annotations missing
            if not structured_sources:
                citations = getattr(response, "citations", None) or []
                for citation in citations:
                    if len(structured_sources) >= max_results:
                        break
                    url = citation.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    next_index = len(structured_sources) + 1
                    title = citation.get("title", f"Source {next_index}")
                    # Extract only first sentence/line as title (max 100 chars)
                    if title:
                        title = title.split('\n')[0].split('. ')[0]
                        if len(title) > 100:
                            title = title[:100].rsplit(' ', 1)[0] + "..."
                    source = {
                        "id": next_index,  # Use integer ID for frontend compatibility
                        "title": title,
                        "url": url,
                        "snippet": citation.get("snippet", ""),
                        "domain": citation.get("domain", "") or urlparse(url).netloc,
                        "published_date": citation.get("published_date"),
                        "score": citation.get("score", 0.9),
                        "index": next_index,
                    }
                    structured_sources.append(source)

            ai_response = "\n\n".join(part.strip() for part in ai_response_parts if part).strip()
            if not ai_response:
                ai_response = "No response generated from GPT-5 search."

            logger.debug(f"GPT-5 search complete: {len(structured_sources)} sources captured")

            # Format response consistently with Perplexity format
            formatted_content = f"## Search Results for: {query}\n\n"
            formatted_content += ai_response

            if structured_sources:
                formatted_content += "\n\n### Sources Referenced\n\n"
                for source in structured_sources:
                    formatted_content += f"**[{source['index']}]** [{source['title']}]({source['url']})\n"
                    if source.get('snippet'):
                        formatted_content += f"> {source['snippet'][:200]}...\n\n"
                    else:
                        formatted_content += "\n"

            return {
                "content": formatted_content,
                "sources": structured_sources,
                "raw_response": ai_response,
                "error": False,
                "search_provider": "gpt5_native"
            }

        except Exception as e:
            logger.error(f"GPT-5 native search error: {e}")
            return {
                "content": f"GPT-5 search failed: {str(e)}",
                "sources": [],
                "error": True
            }

    if provider == "gemini":
        return await _gemini_google_search(query, search_provider, max_results)

    if provider == "anthropic":
        return await _anthropic_web_search(query, search_provider, max_results, depth)

    if provider == "xai":
        return await _xai_web_search(query, search_provider, max_results, depth)

    if provider == "bedrock":
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    return await _perplexity_search(query, max_results=max_results, depth=depth)


def _env_list(name: str, *, max_items: Optional[int] = None) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return []
    items = [item.strip() for item in raw.split(',') if item.strip()]
    if max_items is not None:
        return items[:max_items]
    return items


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def _env_date(name: str) -> Optional[datetime]:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning("Invalid date for %s: %s (expected ISO 8601)", name, value)
        return None


def _serialize_tool_call(call: Any) -> Dict[str, Any]:
    function = getattr(call, "function", None)
    name = getattr(function, "name", None)
    arguments = getattr(function, "arguments", None)
    try:
        arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
    except Exception:  # pragma: no cover - best effort json parsing
        pass
    return {
        "id": getattr(call, "id", None),
        "name": name,
        "arguments": arguments,
    }


async def _xai_web_search(query: str, model: str, max_results: int, depth: str) -> Dict[str, Any]:
    """Execute xAI Grok agentic search with Web and X tools."""
    try:
        from xai_sdk import Client  # type: ignore
        from xai_sdk.chat import user  # type: ignore
        from xai_sdk.tools import web_search as xai_web_search, x_search as xai_x_search  # type: ignore
    except ImportError:
        logger.error("xai-sdk not installed; falling back to Perplexity search for grok models")
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        logger.error("XAI_API_KEY is not configured; falling back to Perplexity search for grok models")
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    current_date = datetime.now().strftime("%B %d, %Y")

    normalized_model = model or "grok-4-fast"
    normalized_model = normalized_model.lower()
    for prefix in ("litellm/xai/", "xai/"):
        if normalized_model.startswith(prefix):
            normalized_model = normalized_model.split(prefix, 1)[1]
            break
    if normalized_model in {"grok-4-fast-reasoning", "grok-4-fast-non-reasoning"}:
        normalized_model = "grok-4-fast"

    web_allowed = _env_list("XAI_WEB_ALLOWED_DOMAINS", max_items=5)
    web_excluded = []
    if not web_allowed:
        web_excluded = _env_list("XAI_WEB_EXCLUDED_DOMAINS", max_items=5)
    enable_image_understanding = _env_flag("XAI_ENABLE_IMAGE_UNDERSTANDING")

    web_kwargs: Dict[str, Any] = {}
    if web_allowed:
        web_kwargs["allowed_domains"] = web_allowed
    elif web_excluded:
        web_kwargs["excluded_domains"] = web_excluded
    if enable_image_understanding:
        web_kwargs["enable_image_understanding"] = True

    x_allowed = _env_list("XAI_X_ALLOWED_HANDLES", max_items=10)
    x_excluded = []
    if not x_allowed:
        x_excluded = _env_list("XAI_X_EXCLUDED_HANDLES", max_items=10)
    x_from = _env_date("XAI_X_FROM_DATE")
    x_to = _env_date("XAI_X_TO_DATE")
    x_enable_images = _env_flag("XAI_X_ENABLE_IMAGE_UNDERSTANDING") or enable_image_understanding
    x_enable_video = _env_flag("XAI_X_ENABLE_VIDEO_UNDERSTANDING")

    x_kwargs: Dict[str, Any] = {}
    if x_allowed:
        x_kwargs["allowed_x_handles"] = x_allowed
    elif x_excluded:
        x_kwargs["excluded_x_handles"] = x_excluded
    if x_from:
        x_kwargs["from_date"] = x_from
    if x_to:
        x_kwargs["to_date"] = x_to
    if x_enable_images:
        x_kwargs["enable_image_understanding"] = True
    if x_enable_video:
        x_kwargs["enable_video_understanding"] = True

    def _run_agentic_search() -> Dict[str, Any]:
        client = Client(api_key=api_key)
        tools: List[Any] = [xai_web_search(**web_kwargs)]
        tools.append(xai_x_search(**x_kwargs))

        chat = client.chat.create(model=normalized_model, tools=tools)
        chat.append(user(f"{query}\n\nCurrent date: {current_date}\nMANDATORY: ALL temporal context uses {current_date} as reference. \"Latest\"/\"Recent\"/\"Today\" = relative to {current_date}."))

        final_response = None
        content_parts: List[str] = []
        tool_call_log: List[Dict[str, Any]] = []

        for response, chunk in chat.stream():
            final_response = response
            chunk_calls = getattr(chunk, "tool_calls", None)
            if chunk_calls:
                for call in chunk_calls:
                    tool_call_log.append(_serialize_tool_call(call))
            chunk_content = getattr(chunk, "content", None)
            if chunk_content:
                content_parts.append(str(chunk_content))

        if final_response is None:
            raise RuntimeError("xAI web search returned no response")

        final_text = "".join(content_parts).strip()
        if not final_text:
            fallback_content = getattr(final_response, "content", None)
            if isinstance(fallback_content, str):
                final_text = fallback_content.strip()

        citations = list(getattr(final_response, "citations", []) or [])
        usage = getattr(final_response, "usage", None)
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        server_tool_usage = getattr(final_response, "server_side_tool_usage", None)
        if hasattr(server_tool_usage, "model_dump"):
            server_tool_usage = server_tool_usage.model_dump()

        raw_response = None
        if hasattr(final_response, "model_dump"):
            try:
                raw_response = final_response.model_dump()
            except Exception:  # pragma: no cover - best effort serialization
                raw_response = str(final_response)
        else:
            raw_response = str(final_response)

        return {
            "content": final_text,
            "citations": citations,
            "tool_calls": tool_call_log,
            "usage": usage,
            "server_side_tool_usage": server_tool_usage,
            "raw_response": raw_response,
        }

    try:
        result = await asyncio.to_thread(_run_agentic_search)
    except Exception as exc:
        logger.error("xAI agentic search failed: %s", exc, exc_info=True)
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    content = result.get("content") or "No content returned from xAI search."
    citations = result.get("citations") or []
    sources: List[Dict[str, Any]] = []
    for idx, url in enumerate(citations[:max_results], start=1):
        if not isinstance(url, str):
            continue
        sources.append({
            "id": idx,  # Use integer ID for frontend compatibility
            "title": url,
            "url": url,
            "snippet": "",
            "domain": urlparse(url).netloc,
            "index": idx,
        })

    extras: Dict[str, Any] = {
        "tool_calls": result.get("tool_calls"),
        "usage": result.get("usage"),
        "server_side_tool_usage": result.get("server_side_tool_usage"),
    }

    return {
        "content": content,
        "sources": sources,
        "raw_response": result.get("raw_response"),
        "error": False,
        "search_provider": "xai_agentic",
        "extras": extras,
    }


async def _perplexity_search(query: str, max_results: int, depth: str) -> Dict[str, Any]:
    import os
    import aiohttp
    from openai import OpenAI

    current_date = datetime.now().strftime("%B %d, %Y")

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        try:
            load_dotenv()
            api_key = os.getenv("PERPLEXITY_API_KEY")
        except Exception:
            api_key = None

    if not api_key:
        return {
            "content": "Perplexity API key not configured. Unable to perform web search.",
            "sources": [],
            "error": True,
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    system_prompts = {
        "brief": f"Today is {current_date}. MANDATORY: ALL temporal context uses {current_date} as reference. \"Latest\"/\"Recent\"/\"Today\" = relative to {current_date}. You are a search results synthesizer. Provide complete answers directly from the search results. Do not ask follow-up questions or present options. Return thorough findings with all essential information, context, and details.",
        "standard": f"Today is {current_date}. MANDATORY: ALL temporal context uses {current_date} as reference. \"Latest\"/\"Recent\"/\"Today\" = relative to {current_date}. You are a search results synthesizer. Provide complete answers directly from the search results. Do not ask follow-up questions or present options. Return comprehensive findings with extensive context, explanations, and supporting details. Be verbose and thorough - include everything found.",
        "comprehensive": f"Today is {current_date}. MANDATORY: ALL temporal context uses {current_date} as reference. \"Latest\"/\"Recent\"/\"Today\" = relative to {current_date}. \"This week/month/quarter/year\" = period containing {current_date}. Date calculations start from {current_date}. You are a search results synthesizer. Provide complete answers directly from the search results. Do not ask follow-up questions or present options. Return extensive, well-researched findings with in-depth coverage, detailed analysis, and comprehensive evidence. Include all relevant information without requiring further clarification.",
    }
    system_prompt = system_prompts.get(depth, system_prompts["comprehensive"])

    payload = {
        "model": os.getenv("PERPLEXITY_MODEL", "sonar"),
        "query": query,
        "max_results": max_results,
    }

    try:
        # 5 minutes timeout for Perplexity API: allows for complex searches
        timeout = aiohttp.ClientTimeout(total=300.0, connect=30.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.perplexity.ai/search",
                headers=headers,
                json=payload,
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error("Perplexity API error: %s", error)
                    return {
                        "content": f"Search failed with status {response.status}",
                        "sources": [],
                        "error": True,
                    }

                data = await response.json()

        search_results = data.get("results", []) if isinstance(data, dict) else []
        if not search_results:
            return {
                "content": "No search results found.",
                "sources": [],
                "error": False,
            }

        results_text = "\n\n".join(
            f"**[{i + 1}] {item.get('title', '')}**\n{item.get('snippet', '')}\nURL: {item.get('url', '')}\nDate: {item.get('date', '')}"
            for i, item in enumerate(search_results)
        )

        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=300.0)  # 5 minutes for web search synthesis
        synthesis = openai_client.chat.completions.create(
            model=os.getenv("AGENT_MODEL", "gpt-5.1"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Search results:\n\n{results_text}\n\nQuery: {query}"},
            ],
        )
        ai_response = synthesis.choices[0].message.content if synthesis.choices else ""

        structured_sources: List[Dict[str, Any]] = []
        for idx, result in enumerate(search_results, 1):
            url = result.get("url", "")
            domain = urlparse(url).netloc if url else ""
            title = result.get("title", f"Source {idx}")
            # Extract only first sentence/line as title (max 100 chars)
            if title:
                title = title.split('\n')[0].split('. ')[0]
                if len(title) > 100:
                    title = title[:100].rsplit(' ', 1)[0] + "..."
            structured_sources.append(
                {
                    "id": idx,  # Use integer ID for frontend compatibility
                    "title": title,
                    "url": url,
                    "snippet": result.get("snippet", ""),
                    "domain": domain,
                    "published_date": result.get("date"),
                    "score": 0.9,
                    "index": idx,
                }
            )

        formatted_content = f"## Search Results for: {query}\n\n" + (ai_response or "No response generated.")
        if structured_sources:
            formatted_content += "\n\n### Sources Referenced\n\n"
            for source in structured_sources:
                formatted_content += f"**[{source['index']}]** [{source['title']}]({source['url']})\n"
                snippet = source.get("snippet")
                if snippet:
                    formatted_content += f"> {snippet[:200]}...\n\n"
                else:
                    formatted_content += "\n"

        return {
            "content": formatted_content,
            "sources": structured_sources,
            "raw_response": ai_response,
            "error": False,
            "search_provider": "perplexity",
        }

    except asyncio.TimeoutError:
        logger.error("Perplexity search timed out after 300 seconds")
        return {
            "content": "Web search timed out. Please try again with a simpler query.",
            "sources": [],
            "error": True,
        }
    except aiohttp.ClientError as exc:
        logger.error("Perplexity network error: %s", exc)
        return {
            "content": f"Network error during web search. Please try again.",
            "sources": [],
            "error": True,
        }
    except Exception as exc:
        logger.error("Perplexity search error: %s", exc, exc_info=True)
        return {
            "content": f"Search error: {exc}",
            "sources": [],
            "error": True,
        }


async def _anthropic_web_search(query: str, model: str, max_results: int, depth: str) -> Dict[str, Any]:
    import os

    try:
        import anthropic
    except ImportError:
        logger.error("anthropic SDK not installed; cannot execute Claude web search.")
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is not configured. Falling back to Perplexity search.")
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    normalized_model = model
    if normalized_model.startswith("litellm/anthropic/"):
        normalized_model = normalized_model.split("litellm/anthropic/", 1)[1]
    elif normalized_model.startswith("anthropic/"):
        normalized_model = normalized_model.split("anthropic/", 1)[1]

    if not normalized_model:
        normalized_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    max_tokens = int(os.getenv("ANTHROPIC_WEB_SEARCH_MAX_TOKENS", "1024"))
    max_uses = int(os.getenv("ANTHROPIC_WEB_SEARCH_MAX_USES", "5"))

    client = anthropic.AsyncAnthropic(api_key=api_key)

    current_date = datetime.now().strftime("%B %d, %Y")
    system_prompt = (
        f"You are a senior financial analyst with access to Claude web search. Today's date is {current_date}. "
        f"MANDATORY: ALL temporal context uses {current_date} as reference. \"Latest\"/\"Recent\"/\"Today\" = relative to {current_date}. "
        "\"This week/month/quarter/year\" = period containing {current_date}. Date calculations start from {current_date}. "
        "Provide real-time market insights and include citations for each claim."
    )

    try:
        response = await client.messages.create(
            model=normalized_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": query},
            ],
            system=system_prompt,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_uses,
            }],
        )
    except anthropic.RateLimitError as exc:
        logger.warning(f"Claude web search rate limited: {exc}")
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = str(exc)
        return fallback
    except anthropic.APIError as exc:
        logger.error(f"Claude web search API error: {exc}")
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = str(exc)
        return fallback
    except Exception as exc:
        logger.exception("Unexpected Claude web search error")
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = str(exc)
        return fallback

def _normalize_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: _normalize_obj(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_normalize_obj(item) for item in obj]
    if hasattr(obj, "model_dump"):
        try:
            return _normalize_obj(obj.model_dump())
        except Exception:
            pass
    return obj


def _find_grounding_metadata(obj: Any) -> Optional[Dict[str, Any]]:
    normalized = _normalize_obj(obj)
    if isinstance(normalized, dict):
        if ("grounding_chunks" in normalized and ("grounding_supports" in normalized or "groundingSupports" in normalized)) or (
            "webSearchQueries" in normalized and "groundingChunks" in normalized
        ):
            return normalized
        for key in ("grounding_metadata", "groundingMetadata"):
            if key in normalized:
                found = _find_grounding_metadata(normalized[key])
                if isinstance(found, dict):
                    return found
        for value in normalized.values():
            found = _find_grounding_metadata(value)
            if isinstance(found, dict):
                return found
    elif isinstance(normalized, list):
        for item in normalized:
            found = _find_grounding_metadata(item)
            if isinstance(found, dict):
                return found
    return None


def _collect_web_results(obj: Any) -> List[Dict[str, Any]]:
    normalized = _normalize_obj(obj)
    results: List[Dict[str, Any]] = []
    if isinstance(normalized, dict):
        if normalized.get("type") == "web_search_result":
            url = normalized.get("url") or normalized.get("uri")
            if url:
                results.append({
                    "url": url,
                    "title": normalized.get("title"),
                    "snippet": normalized.get("summary") or normalized.get("snippet") or normalized.get("description"),
                })
        for key in ("web_search_results", "webSearchResults", "groundingChunks", "webResults"):
            if key in normalized and isinstance(normalized[key], list):
                for entry in normalized[key]:
                    results.extend(_collect_web_results(entry))
        for value in normalized.values():
            results.extend(_collect_web_results(value))
    elif isinstance(normalized, list):
        for item in normalized:
            results.extend(_collect_web_results(item))
    return results


async def _anthropic_web_search(query: str, model: str, max_results: int, depth: str) -> Dict[str, Any]:
    import os

    try:
        import anthropic
    except ImportError:
        logger.error("anthropic SDK not installed; cannot execute Claude web search.")
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is not configured. Falling back to Perplexity search.")
        return await _perplexity_search(query, max_results=max_results, depth=depth)

    normalized_model = model
    if normalized_model.startswith("litellm/anthropic/"):
        normalized_model = normalized_model.split("litellm/anthropic/", 1)[1]
    elif normalized_model.startswith("anthropic/"):
        normalized_model = normalized_model.split("anthropic/", 1)[1]

    if not normalized_model:
        normalized_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    max_tokens = int(os.getenv("ANTHROPIC_WEB_SEARCH_MAX_TOKENS", "1024"))
    max_uses = int(os.getenv("ANTHROPIC_WEB_SEARCH_MAX_USES", "5"))

    client = anthropic.AsyncAnthropic(api_key=api_key)

    current_date = datetime.now().strftime("%B %d, %Y")
    system_prompt = (
        f"You are a senior financial analyst with access to Claude web search. Today's date is {current_date}. "
        f"MANDATORY: ALL temporal context uses {current_date} as reference. \"Latest\"/\"Recent\"/\"Today\" = relative to {current_date}. "
        "\"This week/month/quarter/year\" = period containing {current_date}. Date calculations start from {current_date}. "
        "Provide real-time market insights and include citations for each claim."
    )

    try:
        response = await client.messages.create(
            model=normalized_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": query},
            ],
            system=system_prompt,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_uses,
            }],
        )
    except anthropic.RateLimitError as exc:
        logger.warning(f"Claude web search rate limited: {exc}")
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = str(exc)
        return fallback
    except anthropic.APIError as exc:
        logger.error(f"Claude web search API error: {exc}")
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = str(exc)
        return fallback
    except Exception as exc:
        logger.exception("Unexpected Claude web search error")
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = str(exc)
        return fallback

    content_blocks = getattr(response, "content", None)
    if not isinstance(content_blocks, list):
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = "anthropic_response_empty"
        return fallback
    normalized_blocks: List[Dict[str, Any]] = []
    for block in content_blocks:
        normalized = _normalize_obj(block)
        if isinstance(normalized, dict):
            normalized_blocks.append(normalized)

    if not normalized_blocks:
        fallback = await _perplexity_search(query, max_results=max_results, depth=depth)
        fallback["search_provider"] = "anthropic_fallback_perplexity"
        fallback["fallback_error"] = "anthropic_response_empty"
        return fallback

    text_parts: List[str] = []
    sources_map: Dict[str, Dict[str, Any]] = {}

    for block in normalized_blocks:
        block_type = block.get("type")
        if block_type == "text":
            text_field = block.get("text", "")
            if isinstance(text_field, str):
                if text_field:
                    text_parts.append(text_field)
            elif isinstance(text_field, list):
                for part in text_field:
                    if isinstance(part, dict):
                        seg_text = part.get("text")
                        if isinstance(seg_text, str) and seg_text:
                            text_parts.append(seg_text)
                    elif isinstance(part, str) and part:
                        text_parts.append(part)
            for citation in block.get("citations", []) or []:
                citation_data = citation if isinstance(citation, dict) else _normalize_obj(citation)
                if isinstance(citation_data, dict):
                    url = citation_data.get("url")
                    if url:
                        sources_map.setdefault(url, {
                            "title": citation_data.get("title", url),
                            "snippet": citation_data.get("cited_text", ""),
                        })
        elif block_type == "web_search_tool_result":
            for entry in block.get("content", []) or []:
                entry_data = entry if isinstance(entry, dict) else _normalize_obj(entry)
                if isinstance(entry_data, dict) and entry_data.get("type") == "web_search_result":
                    url = entry_data.get("url")
                    if not url:
                        continue
                    info = sources_map.setdefault(url, {})
                    info.setdefault("title", entry_data.get("title", url))
                    info.setdefault("snippet", entry_data.get("summary", "") or entry_data.get("description", ""))

    structured_sources: List[Dict[str, Any]] = []
    for idx, (url, data) in enumerate(list(sources_map.items())[:max_results], 1):
        domain = urlparse(url).netloc if url else ""
        structured_sources.append(
            {
                "id": f"claude_source_{idx}",
                "title": data.get("title") or f"Source {idx}",
                "url": url,
                "snippet": data.get("snippet", ""),
                "domain": domain,
                "index": idx,
            }
        )

    summary_text = "".join(text_parts) or "No response generated."
    formatted_content = f"## Search Results for: {query}\n\n{summary_text}"
    if structured_sources:
        formatted_content += "\n\n### Sources Referenced\n\n"
        for source in structured_sources:
            formatted_content += f"**[{source['index']}]** [{source['title']}]({source['url']})\n"
            snippet = source.get("snippet")
            if snippet:
                formatted_content += f"> {snippet[:200]}...\n\n"
            else:
                formatted_content += "\n"

    return {
        "content": formatted_content,
        "sources": structured_sources,
        "raw_response": summary_text,
        "error": False,
        "search_provider": "anthropic_web_search",
        "grounding_metadata": normalized_blocks,
    }


async def _gemini_google_search(query: str, model: str, max_results: int) -> Dict[str, Any]:
    import os

    try:
        from litellm import acompletion
    except ImportError:
        logger.error("LiteLLM not installed; cannot execute Gemini grounded search.")
        return {
            "content": "LiteLLM is required for Gemini grounded search.",
            "sources": [],
            "error": True
        }

    if not os.getenv("GEMINI_API_KEY"):
        return {
            "content": "GEMINI_API_KEY is not configured. Unable to perform grounded Google Search.",
            "sources": [],
            "error": True
        }

    current_date = datetime.now().strftime("%B %d, %Y")
    system_prompt = (
        f"You are a senior financial analyst with access to Google Search grounding. Today's date is {current_date}. "
        f"MANDATORY: ALL temporal context uses {current_date} as reference. \"Latest\"/\"Recent\"/\"Today\" = relative to {current_date}. "
        "\"This week/month/quarter/year\" = period containing {current_date}. Date calculations start from {current_date}. "
        "Provide timely, source-backed insights and include inline citations."
    )

    normalized_model = model
    if normalized_model.startswith("litellm/"):
        normalized_model = normalized_model.split("litellm/", 1)[1]

    try:
        response = await acompletion(
            model=normalized_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            tools=[{"googleSearch": {}}],
        )
    except Exception as exc:
        logger.error(f"Gemini grounded search error: {exc}")
        fallback = await _perplexity_search(query, max_results=max_results, depth="comprehensive")
        fallback["error"] = False
        fallback["search_provider"] = "gemini_fallback_perplexity"
        fallback["fallback_error"] = str(exc)
        return fallback

    message = _extract_litellm_message(response)
    if not message:
        return {
            "content": "Gemini search returned an empty response.",
            "sources": [],
            "error": True
        }

    ai_response = _extract_litellm_text(message)

    response_model_extra = getattr(response, "model_extra", None)

    if not ai_response:
        extra_text_candidates = [
            getattr(response, "output_text", None),
            getattr(response, "text", None),
        ]
        if isinstance(response_model_extra, dict):
            extra_text_candidates.extend([
                response_model_extra.get("output_text"),
                response_model_extra.get("outputText"),
                response_model_extra.get("text"),
            ])
        ai_response = next((val for val in extra_text_candidates if isinstance(val, str) and val), "")

    response_dict: Dict[str, Any] = {}
    if hasattr(response, "model_dump"):
        try:
            response_dict = _normalize_obj(response.model_dump())
        except Exception:
            response_dict = {}
    elif hasattr(response, "dict"):
        try:
            response_dict = _normalize_obj(response.dict())
        except Exception:
            response_dict = {}
    elif isinstance(response, dict):
        response_dict = _normalize_obj(response)
    elif hasattr(response, "__dict__"):
        response_dict = _normalize_obj({key: value for key, value in vars(response).items() if not key.startswith("_")})

    metadata_candidates = [
        message,
        message.get("metadata") if isinstance(message.get("metadata"), (dict, list)) else None,
        message.get("_model_extra"),
        response_model_extra,
        response_dict,
    ]

    metadata: Dict[str, Any] = {}
    for candidate in metadata_candidates:
        potential = _find_grounding_metadata(candidate)
        if isinstance(potential, dict):
            metadata = potential
            break

    structured_sources: List[Dict[str, Any]] = []
    url_to_source: Dict[str, Dict[str, Any]] = {}
    seen_urls: set[str] = set()

    def _add_source(url: Optional[str], title: Optional[str], snippet: Optional[str]) -> Optional[Dict[str, Any]]:
        if not url:
            return None
        if url in seen_urls:
            return url_to_source.get(url)

        seen_urls.add(url)
        entry = {
            "id": f"gemini_source_{len(structured_sources) + 1}",
            "title": title or url,
            "url": url,
            "snippet": snippet or "",
            "domain": urlparse(url).netloc if url else "",
            "index": len(structured_sources) + 1,
        }
        structured_sources.append(entry)
        url_to_source[url] = entry
        return entry

    content_blocks = message.get("content")
    if isinstance(content_blocks, list):
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                for citation in block.get("citations", []) or []:
                    if isinstance(citation, dict):
                        _add_source(
                            citation.get("url"),
                            citation.get("title"),
                            citation.get("cited_text") or citation.get("snippet"),
                        )
            elif btype == "web_search_result":
                _add_source(block.get("url"), block.get("title"), block.get("summary") or block.get("snippet"))
            elif btype == "web_search_tool_result":
                for entry in block.get("content", []) or []:
                    if isinstance(entry, dict) and entry.get("type") == "web_search_result":
                        _add_source(entry.get("url"), entry.get("title"), entry.get("summary") or entry.get("snippet"))

    chunk_idx_to_url: Dict[int, str] = {}
    chunks = metadata.get("grounding_chunks") or metadata.get("groundingChunks") or []
    for idx, chunk in enumerate(chunks):
        if len(structured_sources) >= max_results:
            break
        if not isinstance(chunk, dict):
            continue
        web_info = chunk.get("web", {}) if isinstance(chunk, dict) else {}
        if not isinstance(web_info, dict):
            continue
        chunk_url = web_info.get("uri") or web_info.get("url")
        entry = _add_source(
            chunk_url,
            web_info.get("title"),
            web_info.get("snippet") or web_info.get("description"),
        )
        if chunk_url:
            chunk_idx_to_url[idx] = chunk_url
        if entry and not entry.get("snippet"):
            entry["snippet"] = web_info.get("snippet") or web_info.get("description") or ""

    supports = metadata.get("grounding_supports") or metadata.get("groundingSupports") or []
    for support in supports:
        if not isinstance(support, dict):
            continue
        segment = support.get("segment") or {}
        segment_text = ""
        if isinstance(segment, dict):
            segment_text = segment.get("text") or ""
            if not segment_text and isinstance(segment.get("content"), str):
                segment_text = segment["content"]
        indices = support.get("grounding_chunk_indices") or support.get("groundingChunkIndices") or []
        if not isinstance(indices, list):
            continue
        for idx in indices:
            if not isinstance(idx, int):
                continue
            url = chunk_idx_to_url.get(idx)
            if not url:
                continue
            entry = url_to_source.get(url)
            if entry and segment_text and not entry.get("snippet"):
                # Prefer explicit segment text for citation snippets
                entry["snippet"] = segment_text

    structured_sources = structured_sources[:max_results]
    for idx, source in enumerate(structured_sources, 1):
        source["index"] = idx

    if len(structured_sources) < max_results:
        fallback_results = []
        fallback_results.extend(_collect_web_results(message.get("_model_extra")))
        fallback_results.extend(_collect_web_results(response_model_extra))
        fallback_results.extend(_collect_web_results(response_dict))
        for result in fallback_results:
            if len(structured_sources) >= max_results:
                break
            created = _add_source(result.get("url"), result.get("title"), result.get("snippet"))
            if created:
                created["index"] = len(structured_sources)
        structured_sources = structured_sources[:max_results]
        for idx, source in enumerate(structured_sources, 1):
            source["index"] = idx

    formatted_content = f"## Search Results for: {query}\n\n" + (ai_response or "No response generated.")
    if structured_sources:
        formatted_content += "\n\n### Sources Referenced\n\n"
        for source in structured_sources:
            formatted_content += f"**[{source['index']}]** [{source['title']}]({source['url']})\n"
            snippet = source.get("snippet")
            if snippet:
                formatted_content += f"> {snippet[:200]}...\n\n"
            else:
                formatted_content += "\n"

    return {
        "content": formatted_content,
        "sources": structured_sources,
        "raw_response": ai_response,
        "error": False,
        "search_provider": "gemini_google_search",
        "grounding_metadata": metadata,
    }


def _extract_litellm_message(response: Any) -> Dict[str, Any]:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        return {}

    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, dict):
        message = first.get("message")

    if hasattr(message, "model_dump"):
        data = message.model_dump()
        extra = getattr(message, "model_extra", None)
        if isinstance(extra, dict):
            # Preserve provider-specific extras for downstream parsing
            data["_model_extra"] = extra
            for key, value in extra.items():
                if key not in data:
                    data[key] = value
        return _normalize_obj(data)
    if hasattr(message, "dict"):
        data = message.dict()
        extra = getattr(message, "model_extra", None)
        if isinstance(extra, dict):
            data["_model_extra"] = extra
            for key, value in extra.items():
                if key not in data:
                    data[key] = value
        return _normalize_obj(data)
    if isinstance(message, dict):
        return _normalize_obj(message)
    return {}


def _extract_litellm_text(message: Dict[str, Any]) -> str:
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    collected: List[str] = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if text:
                    collected.append(text)
                parts_field = part.get("parts")
                if isinstance(parts_field, list):
                    for sub in parts_field:
                        if isinstance(sub, dict):
                            sub_text = sub.get("text")
                            if sub_text:
                                collected.append(sub_text)
                        elif isinstance(sub, str):
                            collected.append(sub)
            elif isinstance(part, str):
                collected.append(part)
    elif isinstance(content, str):
        collected.append(content)

    if not collected:
        parts_field = message.get("parts")
        if isinstance(parts_field, list):
            for part in parts_field:
                if isinstance(part, dict):
                    text = part.get("text")
                    if text:
                        collected.append(text)
                elif isinstance(part, str):
                    collected.append(part)

    if collected:
        return "".join(collected)

    text = message.get("text")
    if isinstance(text, str) and text:
        return text

    extra = message.get("_model_extra")
    if isinstance(extra, dict):
        extra_text = extra.get("text") or extra.get("output_text") or extra.get("outputText")
        if isinstance(extra_text, str) and extra_text:
            return extra_text

    return ""


# Expose as an agent tool
web_search = tool(web_search_func)
