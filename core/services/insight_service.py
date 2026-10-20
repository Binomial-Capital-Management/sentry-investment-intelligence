"""
Insight Generation Service
Generates personalized Quick Insights for users using InsightGeneratorAgent.
Called by InsightScheduler for batch processing.
"""

import asyncio
import logging
import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os

import httpx
from agents import Runner, set_default_openai_client
from openai import AsyncOpenAI
from core.database.postgres_client import get_postgres_client
from core.agents.InsightGeneratorAgent import create_insight_generator_agent
from core.utils.context_utils import ContextManager
from core.config import get_config

logger = logging.getLogger(__name__)

# Get configured timeout (default 240s to match agent timeout)
_insight_timeout = float(os.getenv("INSIGHT_OPENAI_TIMEOUT_SECONDS", "240"))

# Configure OpenAI client with NO automatic retries to prevent bill explosion
# When insight generation fails, we handle it at the service level, not SDK level
_insight_openai_client = AsyncOpenAI(
    api_key=get_config().openai_api_key,
    max_retries=0,  # CRITICAL: Disable SDK-level retries
    timeout=httpx.Timeout(
        connect=30.0,      # Connection timeout
        read=_insight_timeout,  # Read timeout - must be >= agent timeout
        write=30.0,        # Write timeout
        pool=30.0,         # Pool timeout
    ),
)


class InsightService:
    """Manages insight generation for users."""

    # Page types to generate insights for
    PAGE_TYPES = ["markets", "crypto", "macro"]

    # Market regions for markets page
    MARKET_REGIONS = ["us", "eu", "china", "korea", "japan"]

    def __init__(self):
        self.pg_client = None
        self.market_server = None
        self.economic_server = None
        self.connection_failures = 0
        self.max_connection_failures = 3
        self.service_disabled = False
        cfg = get_config()
        # Cap per-page runs to 240s by default (can raise via config/env if needed)
        self.agent_timeout_seconds = int(os.getenv("INSIGHT_PAGE_TIMEOUT_SECONDS", getattr(cfg, "insight_agent_timeout_seconds", 240)))
        # Prevent concurrent runs per user to avoid cost explosions
        self._user_locks: Dict[str, asyncio.Lock] = {}

    async def initialize(self):
        """Initialize database client and MCP servers with retry logic."""
        if self.service_disabled:
            raise RuntimeError("InsightService disabled due to repeated connection failures")

        if self.pg_client is None:
            self.pg_client = await get_postgres_client()
        if not self.pg_client or not self.pg_client.pool:
            raise RuntimeError("Postgres client unavailable for insights")

        # Initialize MCP servers with retry logic
        max_retries = 3
        retry_delay = 2  # seconds

        # Connect FMP Market Server
        if self.market_server is None:
            from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
            self.market_server = FMPMarketDataServer()

            for attempt in range(1, max_retries + 1):
                try:
                    await self.market_server.connect()
                    logger.info("FMP Market Server initialized and connected for insights")
                    self.connection_failures = 0  # Reset on success
                    break
                except Exception as e:
                    logger.error(f"FMP Market Server connection failed (attempt {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay * attempt)  # Exponential backoff
                    else:
                        self.connection_failures += 1
                        if self.connection_failures >= self.max_connection_failures:
                            self.service_disabled = True
                            logger.critical(f"InsightService DISABLED after {self.max_connection_failures} connection failures")
                            raise RuntimeError("FMP Market Server connection failed after all retries")
                        raise

        # Connect Economic Server
        if self.economic_server is None:
            from core.mcp_servers.EconomicDataServer import EconomicDataServer
            self.economic_server = EconomicDataServer()

            for attempt in range(1, max_retries + 1):
                try:
                    await self.economic_server.connect()
                    logger.info("Economic Server initialized and connected for insights")
                    break
                except Exception as e:
                    logger.error(f"Economic Server connection failed (attempt {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay * attempt)
                    else:
                        logger.warning("Economic Server connection failed, continuing with FMP only")
                        self.economic_server = None  # Disable economic data
                        break

    async def generate_user_insights(
        self,
        user_id: str,
        page_type: Optional[str] = None,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate insights for a single user.

        Args:
            user_id: Clerk user ID
            page_type: Optional filter ('markets', 'crypto', 'macro'). If None, generates for all.
            region: Optional region ('us', 'eu', 'china', 'korea', 'japan'). Only for markets page.

        Returns:
            Dict with status and counts
        """
        await self.initialize()
        if self.service_disabled:
            return {
                "user_id": user_id,
                "generated_at": datetime.utcnow().isoformat(),
                "insights_created": 0,
                "errors": ["InsightService disabled due to prior failures"],
            }

        # Single-flight per user to avoid runaway parallel costs
        lock = self._user_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            return await self._generate_user_insights_locked(user_id, page_type, region)

    async def _generate_user_insights_locked(
        self,
        user_id: str,
        page_type: Optional[str],
        region: Optional[str],
    ) -> Dict[str, Any]:

        results = {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat(),
            "insights_created": 0,
            "errors": []
        }

        try:
            # Step 1: Delete old insights (older than 24 hours)
            deleted_count = await self.pg_client.delete_old_insights(user_id, older_than_hours=24)
            logger.info(f"Deleted {deleted_count} old insights for user {user_id}")

            # Step 2: Determine which pages/regions to generate
            if page_type and region:
                # Generate for specific page + region (e.g., markets/us)
                logger.info(f"Generating insights for {user_id} / {page_type}/{region}")
                try:
                    insights = await self._generate_page_insights(user_id, page_type, region)
                    results["insights_created"] += len(insights)
                except Exception as e:
                    error_msg = f"Failed to generate insights for {user_id} / {page_type}/{region}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results["errors"].append(error_msg)
            elif page_type == "markets" and not region:
                # Generate for all market regions with rate limiting between regions
                logger.info(f"Generating insights for {user_id} / markets (all regions)")
                for i, market_region in enumerate(self.MARKET_REGIONS):
                    try:
                        # Add 2s delay between regions to prevent FMP API overload (skip first region)
                        if i > 0:
                            logger.debug(f"Rate limiting: waiting 2s before processing markets/{market_region}")
                            await asyncio.sleep(2)

                        insights = await self._generate_page_insights(user_id, "markets", market_region)
                        results["insights_created"] += len(insights)
                        logger.debug(f"Generated {len(insights)} insights for {user_id} / markets/{market_region}")
                    except Exception as e:
                        error_msg = f"Failed to generate markets/{market_region} insights: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        results["errors"].append(error_msg)
                        # Stop further regions on failure to avoid additional cost
                        break
            elif page_type:
                # Generate for specific non-markets page (crypto or macro)
                logger.info(f"Generating insights for {user_id} / {page_type}")
                try:
                    insights = await self._generate_page_insights(user_id, page_type, None)
                    results["insights_created"] += len(insights)
                except Exception as e:
                    error_msg = f"Failed to generate insights for {user_id} / {page_type}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    results["errors"].append(error_msg)
            else:
                # Generate for all page types (default for daily job)
                logger.info(f"Generating insights for {user_id} / all pages")
                page_count = 0
                for pt in self.PAGE_TYPES:
                    if pt == "markets":
                        # Generate for all market regions with rate limiting
                        for i, market_region in enumerate(self.MARKET_REGIONS):
                            try:
                                # Add 2s delay between regions to prevent FMP API overload
                                if page_count > 0:
                                    logger.debug(f"Rate limiting: waiting 2s before processing {pt}/{market_region}")
                                    await asyncio.sleep(2)

                                insights = await self._generate_page_insights(user_id, pt, market_region)
                                results["insights_created"] += len(insights)
                                logger.debug(f"Generated {len(insights)} insights for {user_id} / {pt}/{market_region}")
                                page_count += 1
                            except Exception as e:
                                error_msg = f"Failed to generate {pt}/{market_region} insights: {str(e)}"
                                logger.error(error_msg, exc_info=True)
                                results["errors"].append(error_msg)
                                break
                    else:
                        # Generate for crypto or macro (no region)
                        try:
                            # Add 2s delay between page types to prevent FMP API overload
                            if page_count > 0:
                                logger.debug(f"Rate limiting: waiting 2s before processing {pt}")
                                await asyncio.sleep(2)

                            insights = await self._generate_page_insights(user_id, pt, None)
                            results["insights_created"] += len(insights)
                            logger.debug(f"Generated {len(insights)} insights for {user_id} / {pt}")
                            page_count += 1
                        except Exception as e:
                            error_msg = f"Failed to generate {pt} insights: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            results["errors"].append(error_msg)
                            break

            return results

        except Exception as e:
            error_msg = f"Failed to generate insights for user {user_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results["errors"].append(error_msg)
            return results

    async def _generate_page_insights(
        self,
        user_id: str,
        page_type: str,
        region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate 6 insights for a specific page type/region using InsightGeneratorAgent.
        Retries up to 3 times on failure with exponential backoff, then cancels to prevent infinite loops.

        Args:
            user_id: Clerk user ID
            page_type: "markets", "crypto", or "macro"
            region: Optional region for markets page (us, eu, china, korea, japan)

        Returns:
            List of created insight records (empty list if all retries fail)
        """
        # Hard stop: single attempt per invocation to avoid costly retry loops
        max_retries = 1
        base_retry_delay = 5  # Unused with max_retries=1 (kept for compatibility)
        overall_timeout_seconds = self.agent_timeout_seconds  # Align with per-page cap
        start_time = time.monotonic()
        overall_deadline = start_time + overall_timeout_seconds  # Hard cap to prevent infinite loops
        semaphore = getattr(self, "_insight_semaphore", None)
        if semaphore is None:
            # Limit concurrent page/region jobs to avoid connection bursts
            # Default higher now that DB cap is lifted; still configurable
            default_concurrency = int(get_config().insight_max_concurrency or 10)
            self._insight_semaphore = asyncio.Semaphore(default_concurrency)
            semaphore = self._insight_semaphore

        for attempt in range(1, max_retries + 1):
            try:
                if time.monotonic() >= overall_deadline:
                    elapsed = time.monotonic() - start_time
                    raise TimeoutError(f"Insight generation exceeded {overall_timeout_seconds}s deadline for {page_type}/{region} (elapsed {elapsed:.1f}s)")

                logger.info(f"Generating insights for {page_type}/{region} (attempt {attempt}/{max_retries})")

                # Create agent instance for this page type/region
                agent = create_insight_generator_agent(
                    market_server=self.market_server,
                    economic_server=self.economic_server,
                    page_type=page_type,
                    region=region
                )

                # Run agent with timeout to prevent hanging
                async with semaphore:
                    async with ContextManager.async_set_context(user_id=user_id):
                        # Use client with max_retries=0 to prevent OpenAI SDK auto-retries
                        # This prevents bill explosion when API fails
                        set_default_openai_client(_insight_openai_client)
                        
                        # Execute agent with timeout cap to avoid infinite loops
                        result = await asyncio.wait_for(
                            Runner.run(agent, "Generate 6 insights"),
                            timeout=self.agent_timeout_seconds,
                        )

                # Extract final output from result
                response = result.final_output if hasattr(result, 'final_output') else str(result)
                logger.debug(f"Agent response type: {type(response)}, length: {len(str(response))}")

                # Parse agent response (expecting JSON)
                insights_data = self._parse_agent_response(response)

                if not insights_data or len(insights_data) == 0:
                    logger.warning(f"Agent returned no insights for {page_type}/{region} (attempt {attempt}/{max_retries})")

                    # Retry if we have attempts left with exponential backoff
                    if attempt < max_retries:
                        retry_delay = base_retry_delay * (2 ** (attempt - 1))  # 5s, 10s, 20s
                        logger.info(f"Retrying after {retry_delay}s exponential backoff delay...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        error_msg = f"Failed to generate insights for {page_type}/{region} after {max_retries} attempts (no data returned)"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)

                # Success! Store insights in database using bulk insert
                logger.info(f"Successfully generated {len(insights_data)} insights for {page_type}/{region}")

                # Prepare insights for bulk insert
                insights_to_create = []
                for insight_item in insights_data[:6]:  # Limit to 6
                    insights_to_create.append({
                        "page_type": page_type,
                        "region": region,
                        "title": insight_item.get("title", "Market Insight"),
                        "content": insight_item.get("content", {}),
                        "priority": insight_item.get("priority", 5),
                        "metadata": insight_item.get("metadata", {})
                    })

                # Bulk insert all insights in a single transaction
                created_count = await self.pg_client.bulk_create_insights(
                    user_id=user_id,
                    insights=insights_to_create
                )

                logger.info(f"Stored {created_count} insights for {page_type}/{region}")
                # Return list of dicts for compatibility with existing code
                return insights_to_create[:created_count]

            except (asyncio.TimeoutError, httpx.ReadTimeout, httpx.TimeoutException) as timeout_err:
                timeout_type = type(timeout_err).__name__
                logger.error(f"{timeout_type} ({self.agent_timeout_seconds}s) generating insights for {page_type}/{region} (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    retry_delay = base_retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.info(f"Retrying after {retry_delay}s exponential backoff delay...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    elapsed = time.monotonic() - start_time
                    error_msg = f"{timeout_type} after {max_retries} attempts ({elapsed:.1f}s elapsed) - cancelling {page_type}/{region}"
                    logger.error(error_msg)
                    raise TimeoutError(error_msg)

            except Exception as e:
                # Check if it's a timeout error that wasn't caught above
                error_msg_lower = str(e).lower()
                is_timeout = any(keyword in error_msg_lower for keyword in ["timeout", "timed out", "readtimeout"])
                if is_timeout:
                    logger.error(f"Uncaught timeout error for {page_type}/{region} (attempt {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        retry_delay = base_retry_delay * (2 ** (attempt - 1))
                        logger.info(f"Retrying after {retry_delay}s exponential backoff delay...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        elapsed = time.monotonic() - start_time
                        error_msg = f"Timeout after {max_retries} attempts ({elapsed:.1f}s elapsed) - cancelling {page_type}/{region}"
                        logger.error(error_msg)
                        raise TimeoutError(error_msg) from e
                
                # Check if it's an FMP rate limit error
                is_rate_limit = any(keyword in error_msg_lower for keyword in ["rate limit", "429", "too many requests", "quota exceeded"])
                is_conn_error = "too many connections" in error_msg_lower or "connection" in error_msg_lower

                if is_rate_limit:
                    logger.error(f"FMP API rate limit hit for {page_type}/{region} (attempt {attempt}/{max_retries})")
                elif is_conn_error:
                    logger.error(f"Connection-related error for {page_type}/{region} (attempt {attempt}/{max_retries}): {e}")
                else:
                    logger.error(f"Agent execution failed for {page_type}/{region} (attempt {attempt}/{max_retries}): {e}", exc_info=True)

                if attempt < max_retries:
                    # Longer delay for rate limits
                    retry_delay = base_retry_delay * (2 ** (attempt - 1)) * (3 if is_rate_limit else 1)
                    logger.info(f"Retrying after {retry_delay}s delay ({'rate limit backoff' if is_rate_limit else 'exponential backoff'})...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    elapsed = time.monotonic() - start_time
                    final_msg = f"Failed after {max_retries} attempts ({elapsed:.1f}s elapsed) - cancelling {page_type}/{region}: {e}"
                    logger.error(final_msg)
                    raise RuntimeError(final_msg) from e
        
        # Should never reach here, but return empty list as safety
        return []

    def _parse_agent_response(self, response: Any) -> List[Dict[str, Any]]:
        """
        Parse agent response to extract insights JSON with robust error handling.

        Args:
            response: Agent response object (can be dict, list, str, or RunResult)

        Returns:
            List of insight dictionaries (empty list on parse failure)
        """
        try:
            # Log raw response for debugging (truncated)
            response_preview = str(response)[:200] if response else "None"
            logger.debug(f"Parsing response: type={type(response).__name__}, preview={response_preview}")
            
            # Handle list directly
            if isinstance(response, list):
                logger.debug(f"Response is list with {len(response)} items")
                return response

            # Handle dict
            if isinstance(response, dict):
                # Standard format: {"insights": [...]}
                if "insights" in response:
                    insights = response["insights"]
                    logger.debug(f"Found 'insights' key with {len(insights)} items")
                    return insights
                # Single insight wrapped as dict
                logger.debug("Response is single dict, wrapping in list")
                return [response]

            # Handle string (most common case with JSON mode)
            if isinstance(response, str):
                # Strip whitespace
                response_clean = response.strip()
                
                # Early detection of obviously truncated/incomplete responses
                if len(response_clean) < 10:
                    logger.error(f"Response too short to be valid JSON ({len(response_clean)} chars): '{response_clean}'")
                    return []
                
                # Check for incomplete JSON (missing closing braces)
                if response_clean.startswith("{") and not response_clean.endswith("}"):
                    logger.error(f"Truncated JSON response detected (starts with '{{' but doesn't end with '}}'). Length: {len(response_clean)}")
                    logger.error(f"Truncated response preview: {response_clean[:200]}...")
                    return []
                
                if response_clean.startswith("[") and not response_clean.endswith("]"):
                    logger.error(f"Truncated JSON array response detected (starts with '[' but doesn't end with ']'). Length: {len(response_clean)}")
                    logger.error(f"Truncated response preview: {response_clean[:200]}...")
                    return []
                
                # Remove markdown code blocks if present (shouldn't happen with json_object mode)
                if response_clean.startswith("```"):
                    logger.warning("Agent returned markdown code blocks despite json_object mode")
                    lines = response_clean.split("\n")
                    # Skip first and last lines (```)
                    json_lines = [l for l in lines[1:-1] if not l.startswith("```")]
                    response_clean = "\n".join(json_lines).strip()
                    logger.debug("Stripped markdown code blocks")
                
                # Try to parse as JSON (strict=False allows control characters in strings)
                try:
                    parsed = json.loads(response_clean, strict=False)
                    
                    if isinstance(parsed, list):
                        logger.debug(f"Parsed JSON list with {len(parsed)} items")
                        return parsed
                    
                    if isinstance(parsed, dict):
                        if "insights" in parsed:
                            insights = parsed["insights"]
                            logger.debug(f"Parsed JSON dict with 'insights': {len(insights)} items")
                            return insights
                        # Single insight as dict
                        logger.debug("Parsed JSON dict (single insight), wrapping in list")
                        return [parsed]
                    
                    logger.warning(f"Parsed JSON but unexpected type: {type(parsed)}")
                    return []
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse error at position {e.pos}: {e.msg}, attempting sanitization")
                    # Try sanitizing control characters and re-parsing
                    try:
                        # Replace common control characters that break JSON
                        sanitized = response_clean.replace('\r\n', '\\n').replace('\r', '\\n')
                        # Remove other control characters (except \n, \t which are handled by strict=False)
                        sanitized = ''.join(c if ord(c) >= 32 or c in '\n\t' else ' ' for c in sanitized)
                        parsed = json.loads(sanitized, strict=False)
                        logger.info("Successfully parsed JSON after sanitization")
                        if isinstance(parsed, list):
                            return parsed
                        if isinstance(parsed, dict):
                            return parsed.get("insights", [parsed])
                        return []
                    except json.JSONDecodeError as e2:
                        logger.warning(f"JSON parse error after basic sanitization: {e2.msg}, attempting structural repair")
                        # Try structural JSON repair for common LLM errors
                        repaired = self._repair_json_structure(sanitized)
                        if repaired:
                            try:
                                parsed = json.loads(repaired, strict=False)
                                logger.info("Successfully parsed JSON after structural repair")
                                if isinstance(parsed, list):
                                    return parsed
                                if isinstance(parsed, dict):
                                    return parsed.get("insights", [parsed])
                            except json.JSONDecodeError as e3:
                                logger.warning(f"Structural repair failed: {e3.msg}")
                        
                        # Last resort: extract individual insight objects
                        logger.warning("Attempting to extract individual insight objects from malformed JSON")
                        extracted = self._extract_insight_objects(response_clean)
                        if extracted:
                            logger.info(f"Extracted {len(extracted)} insights from malformed JSON")
                            return extracted
                        
                        logger.error(f"All JSON recovery methods failed")
                        logger.error(f"Failed JSON string (first 500 chars): {response_clean[:500]}")
                        logger.error(f"Full response length: {len(response_clean)} chars")
                        return []

            # Handle OpenAI RunResult object
            if hasattr(response, 'final_output'):
                logger.debug("Response has final_output attribute, recursing")
                return self._parse_agent_response(response.final_output)
            
            if hasattr(response, 'messages') and response.messages:
                logger.debug("Response has messages, extracting last message content")
                last_message = response.messages[-1]
                if hasattr(last_message, 'content'):
                    return self._parse_agent_response(last_message.content)

            # Unknown format
            logger.warning(f"Unexpected response format: {type(response).__name__}")
            logger.warning(f"Response value: {str(response)[:500]}")
            return []

        except Exception as e:
            logger.error(f"Failed to parse agent response: {e}", exc_info=True)
            logger.error(f"Response was: {str(response)[:500] if response else 'None'}")
            return []

    def _repair_json_structure(self, json_str: str) -> Optional[str]:
        """
        Attempt to repair common structural JSON errors from LLM output.
        
        Handles:
        - Missing commas between array elements
        - Trailing commas before closing brackets
        - Unbalanced brackets (truncated responses)
        
        Returns repaired JSON string or None if repair not possible.
        """
        try:
            repaired = json_str.strip()
            
            # Fix missing commas between objects in arrays: }{ -> },{
            repaired = re.sub(r'\}\s*\{', '},{', repaired)
            
            # Fix missing commas between array elements: ]\s*[ -> ],[
            repaired = re.sub(r'\]\s*\[', '],[', repaired)
            
            # Fix trailing commas before closing brackets: ,] -> ]
            repaired = re.sub(r',\s*\]', ']', repaired)
            
            # Fix trailing commas before closing braces: ,} -> }
            repaired = re.sub(r',\s*\}', '}', repaired)
            
            # Fix missing commas after string values followed by quotes: "value""key" -> "value","key"
            repaired = re.sub(r'"\s*"(?=[a-zA-Z_])', '","', repaired)
            
            # Fix missing commas after numbers followed by quotes: 5"key" -> 5,"key"
            repaired = re.sub(r'(\d)\s*"(?=[a-zA-Z_])', r'\1,"', repaired)
            
            # Fix missing commas after booleans/null followed by quotes
            repaired = re.sub(r'(true|false|null)\s*"(?=[a-zA-Z_])', r'\1,"', repaired)
            
            # Count brackets to detect truncation
            open_braces = repaired.count('{')
            close_braces = repaired.count('}')
            open_brackets = repaired.count('[')
            close_brackets = repaired.count(']')
            
            # If truncated, try to close properly
            if open_braces > close_braces or open_brackets > close_brackets:
                logger.debug(f"Detected truncated JSON: {{ {open_braces}/{close_braces}, [ {open_brackets}/{close_brackets}")
                # Add missing closing brackets/braces
                repaired += ']' * (open_brackets - close_brackets)
                repaired += '}' * (open_braces - close_braces)
            
            # Only return if we actually made changes
            if repaired != json_str.strip():
                return repaired
            return None
            
        except Exception as e:
            logger.debug(f"JSON structure repair failed: {e}")
            return None

    def _extract_insight_objects(self, json_str: str) -> List[Dict[str, Any]]:
        """
        Extract valid individual insight objects from malformed JSON.
        
        This is a last-resort recovery that finds complete insight objects
        even when the overall JSON structure is broken.
        
        Returns list of successfully parsed insight dicts.
        """
        insights = []
        
        try:
            # Pattern to match complete insight objects
            # Looks for objects with title, content, priority, metadata structure
            # Non-greedy matching to get individual objects
            pattern = r'\{\s*"title"\s*:\s*"[^"]*"\s*,\s*"content"\s*:\s*\{[^}]+\}\s*,\s*"priority"\s*:\s*\d+\s*,\s*"metadata"\s*:\s*\{[^}]*\}\s*\}'
            
            matches = re.findall(pattern, json_str, re.DOTALL)
            
            for match in matches:
                try:
                    parsed = json.loads(match, strict=False)
                    # Validate it has the expected structure
                    if "title" in parsed and "content" in parsed:
                        insights.append(parsed)
                        logger.debug(f"Extracted insight: {parsed.get('title', 'unknown')[:50]}")
                except json.JSONDecodeError:
                    continue
            
            # If regex didn't work, try a more aggressive approach
            if not insights:
                # Find all { ... } blocks and try to parse each
                depth = 0
                start = -1
                for i, char in enumerate(json_str):
                    if char == '{':
                        if depth == 0 or (depth == 1 and start == -1):
                            start = i
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0 and start >= 0:
                            candidate = json_str[start:i+1]
                            try:
                                parsed = json.loads(candidate, strict=False)
                                # Check if it looks like an insight
                                if isinstance(parsed, dict) and "title" in parsed and "content" in parsed:
                                    insights.append(parsed)
                                    logger.debug(f"Extracted insight (bracket method): {parsed.get('title', 'unknown')[:50]}")
                            except json.JSONDecodeError:
                                pass
                            start = -1
            
            return insights
            
        except Exception as e:
            logger.debug(f"Insight extraction failed: {e}")
            return []


# Global instance and lock to prevent race conditions
_insight_service = None
_insight_service_lock = asyncio.Lock()


async def get_insight_service() -> InsightService:
    """Get or create the global InsightService instance (thread-safe)."""
    global _insight_service

    # Thread-safe singleton pattern with async lock
    async with _insight_service_lock:
        if _insight_service is None:
            logger.info("Creating new InsightService instance")
            _insight_service = InsightService()
            await _insight_service.initialize()
            logger.info(f"InsightService instance created: id={id(_insight_service)}")
        else:
            logger.debug(f"Reusing existing InsightService instance: id={id(_insight_service)}")

        return _insight_service
