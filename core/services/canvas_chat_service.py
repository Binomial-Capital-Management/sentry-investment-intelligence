"""Canvas Chat Service.

Encapsulates all business logic for Canvas AI chat streaming:
- Process context loading
- Thread management  
- Agent creation
- SSE event streaming
- Message persistence
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, AsyncIterator, Callable, Awaitable
import asyncio
import json
import logging
import uuid
logger = logging.getLogger(__name__)

# Type aliases for callbacks
TokenCallback = Callable[[str], Awaitable[None]]
EventCallback = Callable[[dict], Awaitable[None]]


@dataclass
class ChatStreamRequest:
    """Request parameters for chat streaming."""
    message: str
    user_id: str
    org_id: str
    process_id: Optional[str] = None
    thread_id: Optional[str] = None
    model: Optional[str] = None
    last_event_id: Optional[str] = None
    data_context: Optional[str] = None


@dataclass
class ProcessContext:
    """Context loaded from a Canvas process."""
    id: str
    name: Optional[str]
    tool_id: Optional[str]
    tickers: List[str] = field(default_factory=list)
    weights: List[float] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metric_cards: List[Dict[str, Any]] = field(default_factory=list)
    stats_table: List[Dict[str, Any]] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    hmm_enabled: bool = False
    current_regime: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for agent consumption."""
        return {
            "id": self.id,
            "name": self.name,
            "tool_id": self.tool_id,
            "tickers": self.tickers,
            "weights": self.weights,
            "metrics": self.metrics,
            "metric_cards": self.metric_cards,
            "stats_table": self.stats_table,
            "params": self.params,
            "hmm_enabled": self.hmm_enabled,
            "current_regime": self.current_regime,
        }


class SSEFormatter:
    """Handles SSE event formatting and sequencing."""
    
    def __init__(self):
        self._seq = 0
    
    @property
    def seq(self) -> int:
        return self._seq
    
    def format_event(self, payload: dict, event_name: Optional[str] = None) -> str:
        """Format a payload as an SSE event string."""
        self._seq += 1
        lines = [f"id: {self._seq}"]
        if event_name:
            lines.append(f"event: {event_name}")
        lines.append(f"data: {json.dumps(payload)}")
        return "\n".join(lines) + "\n\n"
    
    def format_error(self, error_msg: str, fatal: bool = True) -> str:
        """Format an error as an SSE event."""
        payload = {
            "type": "error",
            "error": error_msg,
            "fatal": fatal,
        }
        logger.error(f"Canvas chat stream error (fatal={fatal}): {error_msg}")
        return self.format_event(payload)


class CanvasChatService:
    """Service for Canvas AI chat streaming operations."""
    
    # Content event types to skip (handled by token callback)
    CONTENT_EVENT_TYPES = {
        "output_text.delta", "response.output_text.delta",
        "output_text.done", "response.output_text.done",
    }
    
    # Streaming-capable providers (LiteLLM handles streaming for all major providers)
    STREAMING_PROVIDERS = {"openai", "anthropic"}
    
    # Timeout in seconds
    STREAM_TIMEOUT_SECONDS = 600
    
    # Title generation prompt
    TITLE_GENERATION_PROMPT = """Generate a concise chat title (5-10 words max) that summarizes the user's request. 
Return ONLY the title text, no quotes or explanation.

User message: {message}

Title:"""
    
    def __init__(self, pg_client):
        """
        Initialize service with database client.
        
        Args:
            pg_client: PostgresClient instance
        """
        self.pg = pg_client
    
    async def generate_chat_title(self, message: str) -> str:
        """
        Generate a concise title for a chat thread using AI.
        
        Args:
            message: User's first message
            
        Returns:
            Generated title (5-10 words)
        """
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI()
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap for title generation
                messages=[{
                    "role": "user",
                    "content": self.TITLE_GENERATION_PROMPT.format(message=message[:500])  # Limit input
                }],
                max_tokens=30,
                temperature=0.3,
            )
            
            title = response.choices[0].message.content.strip()
            # Remove quotes if present
            title = title.strip('"\'')
            # Truncate if somehow too long
            if len(title) > 100:
                title = title[:97] + "..."
            
            logger.info(f"Generated chat title: {title}")
            return title
            
        except Exception as e:
            logger.warning(f"Failed to generate chat title: {e}")
            # Fallback to first 50 chars
            return message[:50] + ("..." if len(message) > 50 else "")
    
    async def update_thread_title(
        self,
        thread_id: uuid.UUID,
        user_id: str,
        org_id: str,
        title: str,
    ) -> None:
        """Update thread title in database."""
        async with self.pg.acquire_with_org_context(user_id, org_id) as conn:
            await conn.execute(
                "UPDATE canvas_chat_threads SET title = $1 WHERE id = $2 AND user_id = $3",
                title,
                thread_id,
                user_id,
            )
    
    async def is_first_message(
        self,
        thread_id: uuid.UUID,
        user_id: str,
        org_id: str,
    ) -> bool:
        """Check if this is the first message in the thread."""
        async with self.pg.acquire_with_org_context(user_id, org_id) as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM canvas_chat_messages WHERE thread_id = $1 AND user_id = $2",
                thread_id,
                user_id,
            )
            return count == 0
    
    async def _generate_and_update_title(
        self,
        thread_id: uuid.UUID,
        user_id: str,
        org_id: str,
        message: str,
    ) -> Optional[str]:
        """Generate title and update thread. Returns the new title."""
        try:
            title = await self.generate_chat_title(message)
            await self.update_thread_title(thread_id, user_id, org_id, title)
            return title
        except Exception as e:
            logger.error(f"Failed to generate/update title: {e}")
            return None
    
    async def load_process_context(
        self,
        process_id: str,
        user_id: str,
        org_id: str,
    ) -> Optional[ProcessContext]:
        """
        Load process context from database.
        
        Args:
            process_id: Canvas process UUID
            user_id: User ID for RLS
            org_id: Org ID for RLS
            
        Returns:
            ProcessContext if found, None otherwise
        """
        process_row = await self.pg.get_canvas_process(
            user_id=user_id,
            process_id=process_id,
            org_id=org_id,
        )
        
        if not process_row:
            return None
        
        metrics = process_row.get("metrics", {})
        return ProcessContext(
            id=str(process_row.get("id")),
            name=process_row.get("name"),
            tool_id=process_row.get("tool_id"),
            tickers=process_row.get("tickers", []),
            weights=process_row.get("weights", []),
            metrics=metrics,
            metric_cards=metrics.get("_metric_cards", []),
            stats_table=process_row.get("stats_table", []),
            params=process_row.get("params", {}),
            hmm_enabled=process_row.get("hmm_enabled", False),
            current_regime=process_row.get("current_regime"),
        )
    
    def parse_data_context(self, data_context: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Parse JSON data context string.
        
        Args:
            data_context: JSON string with data context
            
        Returns:
            Parsed dict or None if invalid/empty
        """
        if not data_context:
            return None
        
        try:
            parsed = json.loads(data_context)
            ctx_type = parsed.get('type', 'NO_TYPE')
            logger.info(f"[PARSE_V3] data_context type={ctx_type}, keys={list(parsed.keys())[:5]}")
            return parsed
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse data_context: {data_context[:100]}")
            return None
    
    async def create_canvas_agent(
        self,
        process_context: Optional[ProcessContext],
        data_context: Optional[Dict[str, Any]],
        model: str,
        user_id: str,
        org_id: str,
    ):
        """
        Create Canvas agent with MCP servers.
        
        Args:
            process_context: Optional loaded process context
            data_context: Optional parsed data context
            model: Model name to use
            user_id: User ID
            org_id: Org ID
            
        Returns:
            Configured Canvas agent
        """
        from core.agents.CanvasAgent import create_canvas_agent
        from api.orchestrator import get_v6_orchestrator
        
        # Get MCP servers from orchestrator
        orchestrator = get_v6_orchestrator()
        market_server = (
            getattr(orchestrator, 'fmp_market_server', None) or 
            getattr(orchestrator, 'yfinance_server', None)
        )
        economic_server = getattr(orchestrator, 'economic_server', None)
        alternatives_server = getattr(orchestrator, 'fmp_alternatives_server', None)
        
        return create_canvas_agent(
            process_context=process_context.to_dict() if process_context else None,
            data_context=data_context,
            model=model,
            user_id=user_id,
            org_id=org_id,
            market_server=market_server,
            economic_server=economic_server,
            alternatives_server=alternatives_server,
        )
    
    @staticmethod
    def to_uuid(value) -> uuid.UUID:
        """Safely convert value to UUID, handling asyncpg UUID objects."""
        if value is None:
            raise ValueError("UUID value cannot be None")
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
    
    async def get_or_create_thread(
        self,
        user_id: str,
        org_id: str,
        thread_id: Optional[str],
        process_id: Optional[str],
        process_context: Optional[ProcessContext],
    ) -> uuid.UUID:
        """
        Get existing thread or create a new one.
        
        Args:
            user_id: User ID
            org_id: Org ID  
            thread_id: Optional existing thread ID to validate
            process_id: Optional process ID for thread metadata
            process_context: Optional process context for tool_id
            
        Returns:
            UUID of active thread
        """
        async with self.pg.acquire_with_org_context(user_id, org_id) as conn:
            active_thread_id = None
            
            if thread_id:
                try:
                    thread_uuid = self.to_uuid(thread_id)
                    thread_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM canvas_chat_threads WHERE id = $1 AND user_id = $2)",
                        thread_uuid, user_id
                    )
                    if thread_exists:
                        active_thread_id = thread_uuid
                    else:
                        logger.warning(f"Thread {thread_id} not found for user {user_id}; creating new thread")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid thread_id format: {thread_id}; creating new thread")
            
            if not active_thread_id:
                active_thread_id = await conn.fetchval("""
                    INSERT INTO canvas_chat_threads (user_id, org_id, title, last_process_id, last_tool_id)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, 
                    user_id, 
                    org_id or '', 
                    "New Chat",
                    uuid.UUID(process_id) if process_id else None,
                    process_context.tool_id if process_context else None
                )
                logger.info(f"Created new canvas thread {active_thread_id} for user {user_id}")
            
            return active_thread_id
    
    async def save_user_message(
        self,
        thread_id: uuid.UUID,
        user_id: str,
        org_id: str,
        message: str,
        process_id: Optional[str],
        tool_id: Optional[str],
    ) -> None:
        """Save user message to database."""
        async with self.pg.acquire_with_org_context(user_id, org_id) as conn:
            await conn.execute("""
                INSERT INTO canvas_chat_messages (thread_id, user_id, org_id, role, content, process_id, tool_id)
                VALUES ($1, $2, $3, 'user', $4, $5, $6)
            """, 
                self.to_uuid(thread_id), 
                user_id, 
                org_id or '', 
                message,
                uuid.UUID(process_id) if process_id else None,
                tool_id
            )
    
    async def save_assistant_message(
        self,
        thread_id: uuid.UUID,
        user_id: str,
        org_id: str,
        content: str,
        process_id: Optional[str],
        tool_id: Optional[str],
        metadata: Optional[dict] = None,
    ) -> None:
        """Save assistant message and update thread timestamp.
        
        Args:
            thread_id: The chat thread ID
            user_id: User ID for RLS
            org_id: Organization ID for RLS
            content: Message content
            process_id: Optional process context ID
            tool_id: Optional tool ID
            metadata: Optional metadata dict (e.g., {"toolEvents": [...]})
        """
        import json
        _metadata_json = json.dumps(metadata) if metadata else None
        async with self.pg.acquire_with_org_context(user_id, org_id) as conn:
            await conn.execute("""
                INSERT INTO canvas_chat_messages (thread_id, user_id, org_id, role, content, process_id, tool_id, metadata)
                VALUES ($1, $2, $3, 'assistant', $4, $5, $6, $7::jsonb)
            """, 
                self.to_uuid(thread_id), 
                user_id, 
                org_id or '', 
                content,
                uuid.UUID(process_id) if process_id else None,
                tool_id,
                _metadata_json,
            )
            
            await conn.execute("""
                UPDATE canvas_chat_threads SET updated_at = NOW() WHERE id = $1
            """, self.to_uuid(thread_id))
    
    def transform_event(self, event: dict) -> Optional[dict]:
        """
        Transform raw agent event to frontend-compatible format.
        
        Args:
            event: Raw event from agent
            
        Returns:
            Transformed payload or None if event should be skipped
        """
        event_type = event.get("type")
        
        # Skip content events (handled by token callback)
        if event_type in self.CONTENT_EVENT_TYPES:
            return None
        
        # Tool calls
        if event_type in ("tool_call.started", "response.tool_call.started"):
            event_payload = {
                "item_id": event.get("item_id"),
                "tool_name": event.get("tool_name"),
                "name": event.get("tool_name"),
            }
            if event.get("arguments"):
                event_payload["arguments"] = event["arguments"]
            return {
                "type": "tool_call_started",
                "event": event_payload,
            }
        elif event_type in ("tool_call.output", "response.tool_call.output"):
            return {
                "type": "tool_call_output",
                "event": {
                    "item_id": event.get("item_id"),
                    "output": event.get("output"),
                    "tool_name": event.get("tool_name"),
                }
            }
        # Reasoning events (handle both raw and normalized event types)
        elif event_type in ("response.reasoning_summary_text.delta", "reasoning.delta", "reasoning_delta"):
            return {
                "type": "reasoning_delta",
                "event": {"delta": event.get("delta", "")}
            }
        elif event_type in ("response.reasoning_summary_text.done", "reasoning.done", "reasoning_done"):
            return {
                "type": "reasoning_summary_done",
                "event": event
            }
        # ============================================================
        # AGENTIC ARCHITECTURE: Pass through agent_action/agent_error events
        # These are emitted by the agentic hooks system, not from tool_call.output
        # ============================================================
        elif event_type == "agent_action":
            # Pass through directly without wrapping
            return event
        elif event_type == "agent_error":
            # Pass through directly without wrapping
            return event
        else:
            return {
                "type": event_type,
                "event": event
            }
    
    def can_stream(self, model: str) -> bool:
        """Check if the model supports streaming."""
        from core.ai.utils.message_compactor import get_provider_from_model
        provider = get_provider_from_model(model) if model else "openai"
        return provider in self.STREAMING_PROVIDERS
    
    async def _get_action_feedback(
        self,
        thread_id: str,
        user_id: str,
        org_id: str,
    ) -> Optional[str]:
        """
        Get and format pending action results for AI feedback.
        
        Fetches unprocessed action results and formats them as a system message
        to be prepended to the user's next message. Marks results as processed.
        
        Returns:
            Formatted feedback string or None if no pending results
        """
        try:
            # Fetch pending results
            pending = await self.pg.get_pending_canvas_action_results(
                thread_id=thread_id,
                user_id=user_id,
                org_id=org_id,
            )
            
            if not pending:
                return None
            
            # Format results
            lines = ["[Previous Action Results]"]
            for result in pending:
                action_type = result.get("action_type", "unknown")
                symbol = result.get("symbol", "")
                success = result.get("success", False)
                error = result.get("error")
                cancelled = result.get("cancelled", False)
                
                if cancelled:
                    status = "⚠️ Cancelled by user"
                elif success:
                    status = "✓ Success"
                else:
                    status = f"✗ Failed: {error}" if error else "✗ Failed"
                
                action_desc = f"{action_type}({symbol})" if symbol else action_type
                lines.append(f"- {action_desc}: {status}")
            
            # Mark as processed so they won't be injected again
            await self.pg.mark_canvas_action_results_processed(
                thread_id=thread_id,
                user_id=user_id,
                org_id=org_id,
            )
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to get action feedback: {e}")
            return None
    
    async def stream_chat(self, request: ChatStreamRequest) -> AsyncIterator[str]:
        """
        Main streaming chat generator.
        
        Args:
            request: ChatStreamRequest with all parameters
            
        Yields:
            SSE-formatted event strings
        """
        formatter = SSEFormatter()
        content_chunks: List[str] = []
        collected_tool_events: List[dict] = []  # Collect tool events for persistence
        reasoning_segments: List[str] = []  # Collect reasoning text segments for persistence
        current_reasoning_buffer: List[str] = []  # Buffer for current reasoning segment
        queue: asyncio.Queue[str] = asyncio.Queue()
        stream_start_time = datetime.now()
        
        def check_timeout() -> bool:
            elapsed = (datetime.now() - stream_start_time).total_seconds()
            return elapsed > self.STREAM_TIMEOUT_SECONDS
        
        try:
            # Handle resume requests early
            if request.last_event_id:
                logger.info(f"Canvas chat resume request (last_event_id={request.last_event_id}) - returning early")
                yield formatter.format_event({
                    'type': 'resume_rejected', 
                    'message': 'Please wait for current response'
                })
                return
            
            # Load process context
            process_context = None
            if request.process_id:
                process_context = await self.load_process_context(
                    request.process_id, request.user_id, request.org_id
                )
                if process_context:
                    logger.info(f"Loaded process context for {request.process_id}: {process_context.name}")
            
            # Parse data context — always parse when present (supports unified workspace
            # where both process_context and data_context coexist)
            parsed_data_context = None
            if request.data_context:
                parsed_data_context = self.parse_data_context(request.data_context)

                # Handle unsaved_process type - convert to ProcessContext
                if parsed_data_context and parsed_data_context.get("type") == "unsaved_process":
                    logger.info(f"Converting unsaved_process data_context to ProcessContext")
                    process_context = ProcessContext(
                        id="unsaved",  # Marker for unsaved process
                        name=parsed_data_context.get("name"),
                        tool_id=parsed_data_context.get("tool_id"),
                        tickers=parsed_data_context.get("tickers", []),
                        weights=parsed_data_context.get("weights", []),
                        metrics=parsed_data_context.get("metrics", {}),
                        metric_cards=parsed_data_context.get("metric_cards", []),
                        stats_table=parsed_data_context.get("stats_table", []),
                        params=parsed_data_context.get("params", {}),
                        hmm_enabled=parsed_data_context.get("hmm_enabled", False),
                        current_regime=parsed_data_context.get("current_regime"),
                    )
                    parsed_data_context = None  # Clear since we're using process_context now
            
            # Get model choice
            from core.config import get_config
            config = get_config()
            model_choice = request.model or config.agent_model
            
            # Create agent
            canvas_agent = await self.create_canvas_agent(
                process_context=process_context,
                data_context=parsed_data_context,
                model=model_choice,
                user_id=request.user_id,
                org_id=request.org_id,
            )
            
            # Get or create thread
            active_thread_id = await self.get_or_create_thread(
                user_id=request.user_id,
                org_id=request.org_id,
                thread_id=request.thread_id,
                process_id=request.process_id,
                process_context=process_context,
            )
            
            # Fetch pending action results for AI feedback loop
            action_feedback = await self._get_action_feedback(
                thread_id=str(active_thread_id),
                user_id=request.user_id,
                org_id=request.org_id,
            )
            
            # Prepend feedback to message if present
            enhanced_message = request.message
            if action_feedback:
                enhanced_message = f"{action_feedback}\n\n{request.message}"
                logger.info(f"[FEEDBACK] Injected action feedback into message")
            
            # Check if this is the first message (before saving)
            is_first = await self.is_first_message(
                thread_id=active_thread_id,
                user_id=request.user_id,
                org_id=request.org_id,
            )
            
            # Save user message
            await self.save_user_message(
                thread_id=active_thread_id,
                user_id=request.user_id,
                org_id=request.org_id,
                message=request.message,
                process_id=request.process_id,
                tool_id=process_context.tool_id if process_context else None,
            )
            
            # Generate AI title for first message in thread
            title_task = None
            if is_first:  # First message in any thread
                title_task = asyncio.create_task(
                    self._generate_and_update_title(
                        thread_id=active_thread_id,
                        user_id=request.user_id,
                        org_id=request.org_id,
                        message=request.message,
                    )
                )
            
            # Queue helper
            async def enqueue(payload: dict, event_name: Optional[str] = None):
                await queue.put(formatter.format_event(payload, event_name))
            
            # Token callback
            async def on_token(content: str):
                if not content:
                    return
                content_chunks.append(content)
                await enqueue({"type": "content", "content": content})
            
            # Event callback - also collects tool events for persistence
            async def on_event(event: dict):
                payload = self.transform_event(event)
                if payload:
                    await enqueue(payload)
                    event_type = payload.get("type")

                    # Collect reasoning text for persistence
                    if event_type == "reasoning_delta":
                        delta = (payload.get("event") or {}).get("delta", "")
                        if delta:
                            current_reasoning_buffer.append(delta)
                    elif event_type == "reasoning_summary_done":
                        # Finalize current reasoning segment
                        if current_reasoning_buffer:
                            reasoning_segments.append("".join(current_reasoning_buffer))
                            current_reasoning_buffer.clear()

                    # Collect tool-related events for persistence
                    if event_type in ("tool_call_started", "tool_call_output", "agent_action", "agent_error"):
                        # Finalize any buffered reasoning before the tool event
                        if current_reasoning_buffer:
                            reasoning_segments.append("".join(current_reasoning_buffer))
                            current_reasoning_buffer.clear()
                        # Track content position for proper restoration positioning
                        content_position = len("".join(content_chunks))
                        payload_with_position = {**payload, "contentPosition": content_position}
                        collected_tool_events.append(payload_with_position)
            
            # Send thread_id to frontend
            await enqueue({"type": "thread_id", "thread_id": str(active_thread_id)})
            
            # Create session for conversation memory
            from agents import SQLiteSession
            sqlite_session = SQLiteSession(str(active_thread_id), config.openai_sessions_db_path)
            
            can_stream = self.can_stream(model_choice)
            
            if can_stream:
                # Streaming execution
                async for event in self._execute_streaming(
                    canvas_agent=canvas_agent,
                    message=enhanced_message,
                    session=sqlite_session,
                    model=model_choice,
                    queue=queue,
                    formatter=formatter,
                    content_chunks=content_chunks,
                    on_token=on_token,
                    on_event=on_event,
                    check_timeout=check_timeout,
                ):
                    yield event
            else:
                # Non-streaming execution
                logger.info(f"[canvas_chat] Provider not streaming-capable; using non-stream execution")
                async for event in self._execute_non_streaming(
                    canvas_agent=canvas_agent,
                    message=enhanced_message,
                    model=model_choice,
                    queue=queue,
                    formatter=formatter,
                    content_chunks=content_chunks,
                    enqueue=enqueue,
                    check_timeout=check_timeout,
                ):
                    yield event
            
            # Save assistant response with tool events metadata
            # Finalize any remaining reasoning buffer
            if current_reasoning_buffer:
                reasoning_segments.append("".join(current_reasoning_buffer))
                current_reasoning_buffer.clear()

            full_response = "".join(content_chunks)
            if full_response or collected_tool_events:
                # Build metadata with collected tool events and reasoning
                metadata = None
                if collected_tool_events or reasoning_segments:
                    metadata = {}
                    if collected_tool_events:
                        metadata["toolEvents"] = collected_tool_events
                    if reasoning_segments:
                        metadata["reasoningSegments"] = reasoning_segments
                    logger.info(f"Saving {len(collected_tool_events)} tool events and {len(reasoning_segments)} reasoning segments with assistant message")
                
                await self.save_assistant_message(
                    thread_id=active_thread_id,
                    user_id=request.user_id,
                    org_id=request.org_id,
                    content=full_response,
                    process_id=request.process_id,
                    tool_id=process_context.tool_id if process_context else None,
                    metadata=metadata,
                )
            
            # Wait for title generation and send update if ready
            if title_task:
                try:
                    new_title = await asyncio.wait_for(title_task, timeout=5.0)
                    if new_title:
                        await enqueue({"type": "title_update", "title": new_title, "thread_id": str(active_thread_id)})
                except asyncio.TimeoutError:
                    logger.warning("Title generation timed out")
                except Exception as e:
                    logger.warning(f"Title generation failed: {e}")
            
            # Send done event (must use event_name="done" so the browser routes
            # it to addEventListener('done', ...) instead of generic onmessage)
            await queue.put(formatter.format_event(
                {"type": "done", "full_content": full_response, "thread_id": str(active_thread_id)},
                event_name="done",
            ))
            while not queue.empty():
                yield await queue.get()
            
            logger.info(f"Canvas chat completed for user {request.user_id}, thread {active_thread_id}")
            
        except Exception as e:
            logger.error(f"Canvas chat stream error: {e}", exc_info=True)
            yield formatter.format_error(str(e), fatal=True)
    
    async def _execute_streaming(
        self,
        canvas_agent,
        message: str,
        session,
        model: str,
        queue: asyncio.Queue,
        formatter: SSEFormatter,
        content_chunks: List[str],
        on_token: TokenCallback,
        on_event: EventCallback,
        check_timeout: Callable[[], bool],
    ) -> AsyncIterator[str]:
        """Execute with streaming and yield events."""
        from core.ai.langgraph_utils import execute_with_stream
        
        stream_task = asyncio.create_task(
            execute_with_stream(
                agent=canvas_agent,
                query=message,
                session=session,
                on_token=on_token,
                on_event=on_event,
                max_turns=30,  # Increased for complex multi-ticker, multi-chart requests
                agent_name="canvas",
                selected_model=model,
            )
        )
        
        try:
            while True:
                if check_timeout():
                    logger.warning(f"Canvas chat stream timeout after {self.STREAM_TIMEOUT_SECONDS}s")
                    stream_task.cancel()
                    yield formatter.format_error(
                        f"Chat timed out after {self.STREAM_TIMEOUT_SECONDS // 60} minutes", 
                        fatal=True
                    )
                    return
                
                if stream_task.done() and queue.empty():
                    break
                    
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=0.25)
                    yield payload
                except asyncio.TimeoutError:
                    continue
            
            # Check for errors
            try:
                await stream_task
            except asyncio.CancelledError:
                logger.info("Canvas chat cancelled")
                yield formatter.format_event({"type": "cancelled"})
                while not queue.empty():
                    yield await queue.get()
                return
            except Exception as stream_error:
                logger.error(f"Canvas agent streaming failed: {stream_error}", exc_info=True)
                yield formatter.format_event({
                    "type": "error", 
                    "error": str(stream_error), 
                    "fatal": True
                })
                while not queue.empty():
                    yield await queue.get()
                return
                
        finally:
            pass  # Cleanup if needed
    
    async def _execute_non_streaming(
        self,
        canvas_agent,
        message: str,
        model: str,
        queue: asyncio.Queue,
        formatter: SSEFormatter,
        content_chunks: List[str],
        enqueue: Callable[[dict, Optional[str]], Awaitable[None]],
        check_timeout: Callable[[], bool],
    ) -> AsyncIterator[str]:
        """Execute without streaming (for non-OpenAI providers)."""
        from core.ai.langgraph_utils import execute_with_retry
        
        heartbeat_interval = 5
        
        task = asyncio.create_task(
            execute_with_retry(
                canvas_agent,
                message,
                session=None,
                max_turns=30,  # Increased for complex multi-ticker, multi-chart requests
                agent_name="canvas",
                selected_model=model,
            )
        )
        
        try:
            while True:
                if check_timeout():
                    logger.warning(f"Canvas chat timeout after {self.STREAM_TIMEOUT_SECONDS}s")
                    task.cancel()
                    yield formatter.format_error(
                        f"Chat timed out after {self.STREAM_TIMEOUT_SECONDS // 60} minutes", 
                        fatal=True
                    )
                    return
                
                done, _ = await asyncio.wait(
                    {task}, return_when=asyncio.FIRST_COMPLETED, timeout=heartbeat_interval
                )
                if task in done:
                    break
                await enqueue({"type": "status", "message": "working..."}, None)
                
                # Yield any queued events
                while not queue.empty():
                    yield await queue.get()
            
            # Get result
            try:
                result = await task
            except asyncio.CancelledError:
                logger.info("Canvas chat cancelled")
                yield formatter.format_event({"type": "cancelled"})
                while not queue.empty():
                    yield await queue.get()
                return
            
            final_text = getattr(result, "final_output", None) or str(result)
            
            # Send as single content chunk
            await enqueue({"type": "content", "content": final_text}, None)
            content_chunks.append(final_text)
            
            # Yield remaining events
            while not queue.empty():
                yield await queue.get()
                
        except Exception as task_error:
            logger.error(f"Canvas agent non-stream failed: {task_error}", exc_info=True)
            yield formatter.format_event({
                "type": "error", 
                "error": str(task_error), 
                "fatal": True
            })


# Factory function for easy instantiation
async def get_canvas_chat_service() -> CanvasChatService:
    """Get CanvasChatService instance with database client."""
    from core.database.postgres_client import get_postgres_client
    pg = await get_postgres_client()
    return CanvasChatService(pg)
