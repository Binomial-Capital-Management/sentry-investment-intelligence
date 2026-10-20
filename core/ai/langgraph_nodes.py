"""
LangGraph Node Implementations
Status: Production
Created: August 2025

PURPOSE: Contains all node implementations for LangGraph orchestrator.
Extracted from langgraph_orchestrator.py to keep file sizes manageable.
"""

from typing import Dict, Any, Literal, Optional, List
import logging
from datetime import datetime

# OpenAI Agents SDK imports
from agents import Runner, SQLiteSession

# Import utilities
from core.ai.utils.cache_manager import cache_manager
from core.ai.utils.context_manager import build_shared_context
from core.ai.utils.message_compactor import get_provider_from_model, maybe_inject_on_switch
from core.ai.langgraph_utils import trim_sqlite_session_history
from core.ai.langgraph_utils import _categorize_error
from core.ai.langgraph_utils import inject_tool_priority
from core.utils.context_utils import user_context, session_context, get_token_sink, get_cancel_event
from core.agents.memory_tools import set_memory_context, clear_memory_context


async def emit_status(message: str, state: Optional[Dict[str, Any]] = None) -> None:
    """Helper to emit status messages during agent execution"""
    # Get token_sink from context variables (not stored in state to avoid msgpack serialization errors)
    stream_sink = get_token_sink()
    if stream_sink is not None:
        try:
            await stream_sink.put({"type": "status", "message": message})
            logger.debug(f"[STATUS] Emitted: {message}")
        except Exception as e:
            logger.warning(f"[STATUS] Failed to emit status: {e}")
from core.config import config as app_config

# File handling imports
# Import the raw async function directly (not the wrapped version)
try:
    from core.agents.file_tools import read_file_content_raw as read_file_content_async
except ImportError:
    read_file_content_async = None

from core.agents.file_retrieval_tools import search_file_chunks_async

logger = logging.getLogger(__name__)


def _record_error(state: Dict[str, Any], agent: str, exc: Exception) -> None:
    """Attach a structured error envelope to state for downstream surfacing."""
    if state is None:
        return
    category, retryable, user_msg = _categorize_error(exc)
    state.setdefault("errors", []).append(
        {
            "agent": agent,
            "category": category,
            "retryable": retryable,
            "message": user_msg,
            "detail": str(exc),
        }
    )


def _build_file_context(file_ids: Optional[List[str]], user_id: Optional[str], purpose: str) -> str:
    """Generate a consistent instruction block for agents to read all attached files."""
    if not file_ids:
        return ""

    display_limit = 5
    shown_ids = ", ".join(f"'{fid}'" for fid in file_ids[:display_limit])
    remaining = max(len(file_ids) - display_limit, 0)
    if remaining > 0:
        shown_ids = f"{shown_ids}, plus {remaining} more"

    if user_id:
        user_hint = f"'{user_id}'"
        placeholder_note = ""
    else:
        user_hint = "<user_id>"
        placeholder_note = " Replace <user_id> with the actual user identifier from the current request when calling the tool."

    purpose_clause = f" {purpose.strip()}" if purpose else ""

    return (
        f"\n\nUser has attached {len(file_ids)} file(s) (IDs: {shown_ids}). "
        f"Use read_file_content(file_id=<target_id>, user_id={user_hint}) for each document you need; "
        f"the tool supports PDFs, Word documents, spreadsheets, CSVs, plain text, and images.{purpose_clause}{placeholder_note}"
    )


def _inject_portfolio_context(query: str, state: Dict[str, Any], agent_name: str) -> str:
    """
    Inject portfolio context into the query if available.
    This ensures all agents can see the user's attached portfolio.
    """
    portfolio_state = state.get("portfolio_state")
    if isinstance(portfolio_state, dict) and portfolio_state:
        try:
            import json as _json
            compact_pf = {}
            for k, v in portfolio_state.items():
                if isinstance(v, list) and len(v) > 50:
                    compact_pf[k] = v[:50] + ["...", f"len={len(v)}"]
                else:
                    compact_pf[k] = v
            portfolio_json = _json.dumps(compact_pf, default=str)
            logger.info(f"[PORTFOLIO DEBUG {agent_name}] Injecting portfolio context")
            return f"[ATTACHED PORTFOLIO]\n{portfolio_json}\n\n{query}"
        except Exception as e:
            logger.warning(f"[{agent_name}] Failed to serialize portfolio_state: {e}")
    return query


def _attach_code_execution_metadata(state: Dict[str, Any], agent: str, payload: Dict[str, Any]) -> None:
    """
    If the current state contains code execution metadata for the specified agent,
    attach it to the outgoing message payload in the format the frontend expects.
    """
    code_exec = state.get("code_execution_data")
    if not isinstance(code_exec, dict):
        return

    owner = code_exec.get("agent")
    if owner is not None and owner != agent:
        return

    payload["code_execution_data"] = code_exec

    extras: Dict[str, Any] = {}
    if code_exec.get("generated_files"):
        extras["generated_files"] = code_exec["generated_files"]
    if code_exec.get("container_id"):
        extras["container_id"] = code_exec["container_id"]
    if code_exec.get("code_blocks"):
        extras["code_blocks"] = code_exec["code_blocks"]

    if extras:
        payload["extras"] = extras


def _infer_file_type(filename: Optional[str]) -> str:
    """Infer file type from filename extension. Used by all code execution extraction."""
    if not filename:
        return 'file'
    lower = filename.lower()
    # Images
    if lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico')):
        return 'image'
    # Spreadsheets
    if lower.endswith(('.csv', '.xlsx', '.xls', '.tsv')):
        return 'spreadsheet'
    # Documents
    if lower.endswith(('.docx', '.doc', '.pdf', '.txt', '.rtf', '.odt')):
        return 'document'
    # Presentations
    if lower.endswith(('.pptx', '.ppt', '.odp')):
        return 'presentation'
    # Data files
    if lower.endswith(('.json', '.xml', '.yaml', '.yml', '.parquet', '.feather')):
        return 'data'
    # Code files
    if lower.endswith(('.py', '.js', '.ts', '.html', '.css', '.sql', '.r', '.ipynb')):
        return 'code'
    # Archives
    if lower.endswith(('.zip', '.tar', '.gz', '.7z', '.rar')):
        return 'archive'
    return 'file'


def _extract_code_execution_data(result: Any, agent_name: str) -> Optional[Dict[str, Any]]:
    """
    Centralized extraction of code execution data from agent results.

    Extracts container_id, generated_files, and code_blocks from:
    - result.new_items with type='code_interpreter_call'
    - result.new_items[].raw_item with type='code_interpreter_call'
    - result.tool_outputs (legacy pattern)

    Args:
        result: The agent execution result object
        agent_name: Name of the agent for logging

    Returns:
        Dict with container_id, generated_files, code_blocks, agent or None if nothing found
    """
    if not result:
        return None

    container_id: Optional[str] = None
    generated_files: List[Dict[str, Any]] = []
    code_blocks: List[Dict[str, Any]] = []

    def _extract_files_from_outputs(outputs: Any, current_container_id: Optional[str]) -> None:
        """Extract files from code_interpreter outputs list."""
        nonlocal container_id, generated_files
        if not outputs:
            return
        for output in outputs:
            # Handle both object and dict forms
            output_type = getattr(output, 'type', None) or (output.get('type') if isinstance(output, dict) else None)
            if output_type == 'file':
                file_id = getattr(output, 'file_id', None) or (output.get('file_id') if isinstance(output, dict) else None)
                filename = getattr(output, 'filename', None) or (output.get('filename') if isinstance(output, dict) else None)
                if not filename and file_id:
                    filename = f"file_{file_id}"
                if file_id:
                    generated_files.append({
                        'file_id': file_id,
                        'filename': filename,
                        'type': _infer_file_type(filename),
                        'container_id': current_container_id or container_id
                    })
                    logger.info(f"[{agent_name.upper()}] Found file: {filename} ({file_id})")

    # Pattern 1: Check result.new_items for code_interpreter_call
    if hasattr(result, 'new_items') and result.new_items:
        for item in result.new_items:
            item_type = getattr(item, 'type', None)

            # Direct code_interpreter_call item
            if item_type == 'code_interpreter_call':
                # Extract container_id
                if hasattr(item, 'container_id') and item.container_id:
                    container_id = container_id or item.container_id
                    logger.info(f"[{agent_name.upper()}] Found container_id: {item.container_id}")

                # Extract files from outputs
                if hasattr(item, 'outputs') and item.outputs:
                    _extract_files_from_outputs(item.outputs, getattr(item, 'container_id', None))

                # Extract code
                if hasattr(item, 'code') and item.code:
                    code_blocks.append({"code": item.code, "output": "", "language": "python"})

            # Check raw_item fallback
            raw = getattr(item, 'raw_item', None)
            if raw:
                raw_type = getattr(raw, 'type', None) or (raw.get('type') if isinstance(raw, dict) else None)
                if raw_type == 'code_interpreter_call':
                    # Container from raw
                    raw_container = getattr(raw, 'container_id', None) or (raw.get('container_id') if isinstance(raw, dict) else None)
                    if raw_container:
                        container_id = container_id or raw_container

                    # Files from raw outputs
                    try:
                        raw_outputs = getattr(raw, 'outputs', None) or (raw.get('outputs') if isinstance(raw, dict) else None)
                        if raw_outputs:
                            _extract_files_from_outputs(raw_outputs, raw_container)
                    except Exception:
                        pass

                    # Code from raw
                    try:
                        raw_code = getattr(raw, 'code', None) or (raw.get('code') if isinstance(raw, dict) else None)
                        if isinstance(raw_code, str) and raw_code.strip():
                            code_blocks.append({"code": raw_code, "output": "", "language": "python"})
                    except Exception:
                        pass

    # Pattern 2: Legacy result.tool_outputs pattern
    if hasattr(result, 'tool_outputs') and result.tool_outputs:
        for tool_output in result.tool_outputs:
            if hasattr(tool_output, 'name') and tool_output.name == 'code_interpreter':
                if hasattr(tool_output, 'container_id'):
                    container_id = container_id or tool_output.container_id
                if hasattr(tool_output, 'outputs'):
                    _extract_files_from_outputs(tool_output.outputs, getattr(tool_output, 'container_id', None))
                if hasattr(tool_output, 'code'):
                    code_blocks.append({"code": tool_output.code, "output": "", "language": "python"})

    # Deduplicate files by file_id or filename
    if generated_files:
        seen = set()
        unique_files = []
        for f in generated_files:
            key = f.get('file_id') or f.get('filename')
            if key and key not in seen:
                seen.add(key)
                unique_files.append(f)
        generated_files = unique_files

    # Return data if anything was found
    if container_id or generated_files or code_blocks:
        logger.info(f"[{agent_name.upper()}] Code execution data: container={bool(container_id)}, files={len(generated_files)}, code_blocks={len(code_blocks)}")
        return {
            "container_id": container_id,
            "generated_files": generated_files,
            "code_blocks": code_blocks,
            "agent": agent_name,
        }

    return None


def _apply_compaction_summary(state: Dict[str, Any], provider: str) -> None:
    """Append a cross-provider recap message to the conversation state when present."""
    comp_meta = state.pop("_compaction_meta", None)
    if not comp_meta:
        return

    summary_text = comp_meta.get("summary_text")
    if not summary_text:
        return

    from_provider = comp_meta.get("from_provider", "previous provider")
    content = (
        f"Cross-provider recap from {from_provider} conversation:\n"
        f"{summary_text}"
    )

    state.setdefault("messages", []).append(
        {
            "role": "assistant",
            "content": content,
            "agent": "cross_provider_summary",
            "provider": provider,
        }
    )

    # Persist for orchestrator metadata/analytics
    state["_cross_provider_summary"] = summary_text


def trim_messages_before_agent(state: Dict[str, Any], max_tokens: int = None) -> Dict[str, Any]:
    """
    Trim messages in state to stay under token limit before agent execution.
    Handles both dict and LangChain message objects.
    Prevents context_length_exceeded errors by keeping only recent messages.

    Auto-detects model provider and uses appropriate token limit:
    - Claude (Anthropic): 200K tokens
    - DeepSeek Fast: 75K tokens
    - xAI Grok Fast: 1M tokens
    - OpenAI: 320K tokens
    - Gemini: 1M tokens
    """
    import tiktoken

    # Auto-detect provider and set appropriate limit
    # QUOTA-AWARE: Aggressive trimming to prevent quota exhaustion
    if max_tokens is None:
        selected_model = state.get("selected_model")
        selected_model_str = (selected_model or "").lower()
        if "anthropic" in selected_model_str or "claude" in selected_model_str:
            max_tokens = 150000  # 150K for Claude
        elif "gemini" in selected_model_str:
            max_tokens = 700000  # 700K for Gemini
        elif "deepseek" in selected_model_str:
            max_tokens = 75000  # 75K for DeepSeek fast variants
        elif "bedrock" in selected_model_str or "llama4" in selected_model_str:
            max_tokens = 3_200_000  # 3.2M for Llama 4 Scout on Bedrock
        elif "xai" in selected_model_str or "grok" in selected_model_str:
            max_tokens = 1_000_000  # 1M for xAI Grok fast variants
        elif "dashscope" in selected_model_str or "qwen" in selected_model_str:
            max_tokens = 1_000_000  # 1M for Qwen 3.6
        else:
            max_tokens = 300000  # 300K for ChatGPT/OpenAI

        logger.info(f"[TRIM] Auto-detected token limit: {max_tokens:,} tokens for model {selected_model or 'default'}")

    encoding = tiktoken.get_encoding("cl100k_base")
    messages = state.get("messages", [])

    if not messages:
        return state

    # Helper to extract content from both dict and LangChain message objects
    def get_content(msg):
        if hasattr(msg, 'content'):
            return str(msg.content)
        return str(msg.get("content", ""))

    # Calculate total tokens
    total_tokens = sum(len(encoding.encode(get_content(msg))) for msg in messages)

    if total_tokens <= max_tokens:
        logger.info(f"[TRIM] Messages within limit: {len(messages)} messages, {total_tokens} tokens")
        return state

    logger.warning(f"[TRIM] Messages exceed limit: {len(messages)} messages, {total_tokens} tokens - trimming to {max_tokens}")

    # Keep most recent messages that fit under limit
    trimmed_messages = []
    current_tokens = 0

    for msg in reversed(messages):
        msg_tokens = len(encoding.encode(get_content(msg)))
        if current_tokens + msg_tokens > max_tokens:
            break
        trimmed_messages.insert(0, msg)
        current_tokens += msg_tokens

    state["messages"] = trimmed_messages
    logger.info(f"[TRIM] Trimmed to {len(trimmed_messages)} messages ({current_tokens} tokens)")
    return state


async def supervisor_node(state: Dict[str, Any], structured_router) -> Dict[str, Any]:
    """
    Supervisor makes routing decisions using LLM reasoning.
    No more hardcoded keywords - the LLM understands context and intent.
    WITH CACHING for performance.
    Now respects user-selected agent_mode for direct routing.
    """

    # ✅ CHECK CANCELLATION: Stop routing if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] supervisor_node cancelled before routing")
        state["should_continue"] = False
        state["next_agent"] = None
        return state

    query = state["current_user_query"]
    last_response = state.get("last_agent_response", "")
    agent_mode = state.get("agent_mode", "auto")
    force_web_search = state.get("force_web_search", False)

    hop_limit = state.get("deep_analysis_hop_limit") or app_config.deep_analysis_max_hops
    state["deep_analysis_hop_limit"] = hop_limit
    state["multi_agent_hops"] = int(state.get("multi_agent_hops") or 0)

    if state.get("deep_analysis_mode") and state["multi_agent_hops"] >= hop_limit:
        logger.info(
            "[MULTI-AGENT] Hop limit reached (%s) - disabling deep analysis mode for the remainder of this session",
            hop_limit,
        )
        state["deep_analysis_mode"] = False

    def record_routing(decision: str, reasoning: str, increment: bool = True) -> None:
        if "routing_history" not in state:
            state["routing_history"] = []
        state["routing_history"].append({
            "query": query,
            "decision": decision,
            "reasoning": reasoning,
        })
        if increment and decision and decision != "end":
            state["multi_agent_hops"] = int(state.get("multi_agent_hops", 0)) + 1

    # Force generalist routing for /search command (overrides agent_mode)
    if force_web_search and not last_response:
        logger.info(f"[COMMAND] Forcing generalist routing for /search command: {query}")
        state["should_continue"] = True
        state["next_agent"] = "generalist"
        state["status_message"] = "Searching the web..."
        record_routing(
            "generalist",
            "/search command detected - forcing web search via generalist",
        )

        # Emit status message
        await emit_status("Searching the web...", state)

        return state

    # End immediately after any agent finishes during a workflow run
    if last_response and state.get("workflow_context") is not None:
        logger.info("[WORKFLOW] Early return triggered - ending workflow after agent response")
        state["should_continue"] = False
        state["next_agent"] = None
        return state
    
    # Debug why early return might not trigger
    if state.get("workflow_context") is not None:
        logger.info(f"[WORKFLOW] Early return check: last_response={bool(last_response)}, workflow_context present")
    
    # Direct routing based on user-selected agent mode
    if agent_mode != "auto" and not last_response:
        # User has selected a specific mode - route directly
        mode_to_agent = {
            "risk": "risk_specialist",
            "web": "generalist",  # Generalist has web search
            "market": "generalist",  # Generalist has market data access
            "filings": "document_analyst",  # Document analyst for filings
            "multiples": "comparable_companies",  # Comparable companies for valuation analysis
            "charts": "chart_analyst",  # Chart analyst for technical analysis
            "code": "quant_coding",  # Quant coding for custom Python implementations
            "quant": "quant_coding",  # Frontend AgentMode compatibility
            "structuring": "structuring_analyst",  # Derivatives structuring desk
            "dcf": "dcf_agent",  # DCF valuation agent
            "options": "options_coding",  # Listed options analytics
            "alternatives": "alternatives_coding",  # Alternatives data (crypto/forex/commodities)
            "derivatives": "options_coding",  # Legacy alias for options workflows
            "institutional": "institutional_activity",  # Institutional/insider trading
            "funds_products": "funds_products_analyst",  # Funds & products analysis
            "prediction_markets": "prediction_markets_analyst",  # Prediction markets analysis
            "private_markets": "private_markets",  # Private equity/M&A research
            "portfolio_semantic": "portfolio_semantic_agent",  # Portfolio knowledge graph
            # Also support canonical agent IDs directly
            "generalist": "generalist",
            "risk_specialist": "risk_specialist",
            "document_analyst": "document_analyst",
            "comparable_companies": "comparable_companies",
            "chart_analyst": "chart_analyst",
            "quant_coding": "quant_coding",
            "structuring_analyst": "structuring_analyst",
            "options_coding": "options_coding",
            "alternatives_coding": "alternatives_coding",
            "institutional_activity": "institutional_activity",
            "dcf_agent": "dcf_agent",
            "funds_products_analyst": "funds_products_analyst",
            "prediction_markets_analyst": "prediction_markets_analyst",
            "private_markets": "private_markets",
            "portfolio_semantic_agent": "portfolio_semantic_agent",
        }
        
        selected_agent = mode_to_agent.get(agent_mode, "generalist")
        logger.info(f"Direct routing based on agent_mode '{agent_mode}' -> {selected_agent}")

        # Generate mode-specific status message
        mode_status_map = {
            "risk": "Analyzing portfolio risk...",
            "document": "Processing document...",
            "comparable": "Analyzing comparable companies...",
            "chart": "Creating chart...",
            "quant": "Running quantitative analysis...",
            "structuring": "Pricing derivatives...",
            "options": "Analyzing options...",
            "alternatives": "Analyzing alternatives...",
            "institutional": "Analyzing institutional activity...",
            "dcf": "Calculating DCF valuation...",
            "funds": "Analyzing funds...",
            "prediction": "Analyzing prediction markets...",
        }

        state["should_continue"] = True
        state["next_agent"] = selected_agent
        state["status_message"] = mode_status_map.get(agent_mode, "Processing request...")
        record_routing(
            selected_agent,
            f"User selected {agent_mode} mode - direct routing",
        )

        # Emit status message
        await emit_status(state["status_message"], state)

        return state

    # PRIORITY 0: Hardcoded routing for explicit agent keywords (BYPASS LLM ENTIRELY)
    # These keywords ALWAYS route to their respective agents when detected in query
    query_lower = (query or "").lower()
    explicit_agent_keywords = {
        # All agents can be explicitly called
        "generalist-agent": "generalist",
        "generalist agent": "generalist",
        "risk-agent": "risk_specialist",
        "risk agent": "risk_specialist",
        "risk-specialist": "risk_specialist",
        "risk specialist": "risk_specialist",
        "document-agent": "document_analyst",
        "document agent": "document_analyst",
        "document-analyst": "document_analyst",
        "document analyst": "document_analyst",
        "comparable-companies": "comparable_companies",
        "comparable companies": "comparable_companies",
        "comp-agent": "comparable_companies",
        "comp agent": "comparable_companies",
        "dcf-agent": "dcf_agent",
        "dcf agent": "dcf_agent",
        "chart-analyst": "chart_analyst",
        "chart analyst": "chart_analyst",
        "quant-agent": "quant_coding",
        "quant agent": "quant_coding",
        "structuring-agent": "structuring_analyst",
        "structuring agent": "structuring_analyst",
        "structuring-desk": "structuring_analyst",
        "structuring desk": "structuring_analyst",
        "options-agent": "options_coding",
        "options agent": "options_coding",
        "options-coder": "options_coding",
        "options coder": "options_coding",
        "derivatives-agent": "options_coding",
        "derivatives agent": "options_coding",
        "alternatives-agent": "alternatives_coding",
        "alternatives agent": "alternatives_coding",
        "institutional-agent": "institutional_activity",
        "institutional agent": "institutional_activity",
        "funds-agent": "funds_products_analyst",
        "funds agent": "funds_products_analyst",
        "funds-products-analyst": "funds_products_analyst",
        "funds products analyst": "funds_products_analyst",
        "prediction-markets-agent": "prediction_markets_analyst",
        "prediction markets agent": "prediction_markets_analyst",
        "prediction-markets-analyst": "prediction_markets_analyst",
        "prediction markets analyst": "prediction_markets_analyst",
        "predictive-agent": "prediction_markets_analyst",
        "predictive agent": "prediction_markets_analyst",
        "private-markets-agent": "private_markets",
        "private markets agent": "private_markets",
        "private-markets": "private_markets",
        "private markets": "private_markets",
        "pe-agent": "private_markets",
        "pe agent": "private_markets",
        "portfolio-semantic-agent": "portfolio_semantic_agent",
        "portfolio semantic agent": "portfolio_semantic_agent",
        "semantic-agent": "portfolio_semantic_agent",
        "semantic agent": "portfolio_semantic_agent",
    }

    # Check for explicit agent keywords in query
    for keyword, target_agent in explicit_agent_keywords.items():
        if keyword in query_lower:
            # Only apply hardcoded routing if this is a fresh query (no last_response)
            if not last_response:
                logger.info(f"🔒 PRIORITY 0 HARDCODED OVERRIDE: '{keyword}' detected → routing to {target_agent}")

                # Generate agent-specific status message
                agent_status_map = {
                    "generalist": "Processing your request...",
                    "risk_specialist": "Analyzing risk metrics...",
                    "document_analyst": "Analyzing document...",
                    "comparable_companies": "Finding comparable companies...",
                    "chart_analyst": "Creating chart...",
                    "quant_coding": "Running code analysis...",
                    "structuring_analyst": "Pricing derivatives...",
                    "options_coding": "Analyzing options...",
                    "alternatives_coding": "Analyzing alternatives...",
                    "institutional_activity": "Analyzing institutional activity...",
                    "dcf_agent": "Calculating DCF valuation...",
                    "funds_products_analyst": "Analyzing funds...",
                    "prediction_markets_analyst": "Analyzing prediction markets...",
                    "private_markets": "Analyzing private markets...",
                    "portfolio_semantic_agent": "Searching portfolio...",
                }

                state.update({
                    "next_agent": target_agent,
                    "should_continue": True,
                    "status_message": agent_status_map.get(target_agent, "Processing request...")
                })
                record_routing(
                    target_agent,
                    f"PRIORITY 0 HARDCODED OVERRIDE: Explicit keyword '{keyword}' detected",
                )

                # Emit status message
                await emit_status(state["status_message"], state)

                return state

    # Early check for END signal - bypass cache entirely
    if state.get("next") == "END":
        logger.info("END signal detected - bypassing cache and ending conversation")
        state.update({
            "should_continue": False,
            "next_agent": None
        })
        return state
    
    # Terminal agent check - end by default after these agents respond
    # Extract last agent that responded from messages
    last_agent = next((m.get("agent") for m in reversed(state.get("messages", []))
                       if isinstance(m, dict) and m.get("role") == "assistant" and m.get("agent")), None)
    
    # These agents are terminal by default (unless they explicitly request handoff)
    terminal_agents = {
        "generalist",
        "document_analyst",
        "comparable_companies",
        "chart_analyst",
        "quant_coding",
        "options_coding",
        "alternatives_coding",
        "institutional_activity",
        "dcf_agent",
        "funds_products_analyst",
        "prediction_markets_analyst",
        "private_markets",
        "portfolio_semantic_agent",
    }
    if last_response and last_agent in terminal_agents and not state.get("next_agent") and not state.get("handback_pending"):
        logger.info(f"Terminal agent {last_agent} completed - ending conversation")
        state["should_continue"] = False
        state["next_agent"] = None
        return state

    # Check for permanent agent failure - end immediately to prevent retry loops
    if state.get("agent_failed"):
        logger.error("Agent failed permanently - ending conversation to prevent retry loops")
        if not state.get("errors"):
            state["errors"] = [{
                "agent": "unknown",
                "category": "unknown",
                "retryable": False,
                "message": "Agent failed unexpectedly.",
                "detail": "agent_failed flag set without structured error",
            }]
        state["should_continue"] = False
        state["next_agent"] = None
        return state

    # CACHE CHECK - Create cache key for routing decisions
    cache_key = {
        "query": query[:200],  # First 200 chars
        "has_response": bool(last_response),
        "agent_mode": agent_mode,  # Include agent_mode to prevent incorrect cache hits
        "response_hash": hash(last_response[:100]) if last_response else 0,
        "message_count": len(state.get("messages", [])),  # Breaks cache loops
        "next_signal": state.get("next", "")  # Include completion signals
    }
    
    cached_decision = cache_manager.get("routing", "supervisor", cache_key)
    if cached_decision:
        logger.info("Cache HIT for supervisor routing")
        state["should_continue"] = cached_decision["should_continue"]
        state["next_agent"] = cached_decision.get("next_agent")
        state["status_message"] = cached_decision.get("status_message", "Processing cached request...")
        if cached_decision.get("routing_history"):
            state["routing_history"] = cached_decision["routing_history"]
        if "multi_agent_hops" in cached_decision:
            state["multi_agent_hops"] = cached_decision["multi_agent_hops"]
        return state
    
    # Import the supervisor routing prompt
    from core.agents.prompts.supervisor_routing_prompt import get_supervisor_routing_prompt
    
    # Build context for the routing decision with SHARED context
    shared_context = build_shared_context(state, max_tokens=50000)  # Extended context for comprehensive routing history

    # Check if files are attached and add routing context
    if state.get("file_ids"):
        logger.info(f"Files attached: {state['file_ids']}, adding routing context")
        # Check if user explicitly mentioned a specific agent (with dashes)
        query_lower = (query or "").lower()
        explicit_agent_mentioned = (
            "chart-analyst" in query_lower or
            "document-analyst" in query_lower or
            "risk-specialist" in query_lower or
            "comparable-companies" in query_lower or
            "quant-agent" in query_lower
        )

        if explicit_agent_mentioned:
            # If user explicitly requested a specific agent with dashes, respect that choice
            query = query + f"\n[Context: User has uploaded {len(state['file_ids'])} files and explicitly requested a specific agent. Honor the explicit agent request.]"
        else:
            # Only suggest generalist if no explicit agent was mentioned
            query = query + f"\n[Context: User has uploaded {len(state['file_ids'])} files. These are user-uploaded files that need the generalist agent's file reading tools.]"

    # Get the routing prompt with context
    available_agents_list = [
        "generalist",
        "risk_specialist",
        "document_analyst",
        "comparable_companies",
        "chart_analyst",
        "quant_coding",
        "options_coding",
        "alternatives_coding",
        "institutional_activity",
        "dcf_agent",
        "funds_products_analyst",
        "prediction_markets_analyst",
        "private_markets",
        "portfolio_semantic_agent",
        "end",
    ]
    logger.info(f"[SUPERVISOR DEBUG] Available agents being passed: {available_agents_list}")
    routing_prompt = get_supervisor_routing_prompt({
        "available_agents": available_agents_list,
        "has_files": bool(state.get("file_ids")),  # Pass file context to routing prompt
        "deep_analysis_mode": state.get("deep_analysis_mode", False)  # Pass multi-agent mode flag
    })
    
    # Add conversation context to the prompt
    full_prompt = routing_prompt
    if shared_context:
        full_prompt = f"{routing_prompt}\n\n<conversation-context>\n{shared_context}\n</conversation-context>"
    
    messages = [
        {
            "role": "system", 
            "content": full_prompt
        }
    ]
    
    # Add the current query
    logger.info(f"[SUPERVISOR DEBUG] Query being analyzed: {query}")
    messages.append({"role": "user", "content": f"Current query: {query}"})
    
    # Extract last agent that responded
    last_agent = next(
        (m.get("agent") for m in reversed(state.get("messages", []))
         if isinstance(m, dict) and m.get("role") == "assistant" and m.get("agent")),
        None
    )
    
    # Add preference hint for last agent (but let router override)
    if last_agent and state.get("workflow_context") is None and state.get("agent_mode", "auto") == "auto":
        messages.append({
            "role": "system",
            "content": f"Preference: The last agent was '{last_agent}'. If the user's message is a brief confirmation, continue with '{last_agent}'. If the topic clearly changed, route accordingly."
        })
    
    # If we have a response from an agent, we need to check if conversation should end
    if last_response:
        # Check if this is from Risk Specialist or if we have calculation results
        # Safely handle None state
        state_messages = state.get("messages", []) if state else []
        is_risk_specialist = any(msg.get("agent") == "risk_specialist" for msg in state_messages if isinstance(msg, dict))
        
        # Don't truncate Risk Specialist responses or calculation results
        calc_results = state.get("calculation_results") if state else None
        if is_risk_specialist or calc_results:
            response_content = f"Last agent response: {last_response}"
        else:
            response_content = f"Last agent response: {last_response[:500]}..."  # Limit length for other agents
        
        messages.append({
            "role": "assistant", 
            "content": response_content
        })
        
        # Check if agent suggested next routing
        if state.get("next") == "END":
            messages.append({
                "role": "user",
                "content": "The agent completed its task successfully. Consider routing to 'end'."
            })
        # Check handback flag
        elif state.get("handback_pending", False):
            messages.append({
                "role": "user",
                "content": "The Risk Specialist has completed their analysis and indicated they want to hand back control. Route to 'end'."
            })
        else:
            # Only add END nudge if no last_agent context
            if not last_agent:
                messages.append({
                    "role": "user",
                    "content": "The agent has provided a response. Consider if the conversation is complete."
                })
    
    # Get routing decision from LangChain router with timeout
    try:
        import asyncio
        import os
        timeout = float(os.getenv('LANGGRAPH_ROUTER_TIMEOUT_S', '20'))
        decision = await asyncio.wait_for(
            structured_router.ainvoke(messages),
            timeout=timeout
        )
        
        # Log the decision and reasoning
        logger.info(f"Supervisor routing decision: {decision.next_agent}")
        logger.info(f"Reasoning: {decision.reasoning}")
        
        # Update state based on decision
        if decision.next_agent == "end" or decision.is_complete:
            state["should_continue"] = False
            state["next_agent"] = None
            logger.info("Supervisor decided to END conversation")
            record_routing("end", decision.reasoning, increment=False)
        else:
            state["should_continue"] = True
            state["next_agent"] = decision.next_agent
            state["status_message"] = decision.status_message  # Store contextual status message
            logger.info(f"Supervisor routing to: {decision.next_agent} with status: {decision.status_message}")
            record_routing(decision.next_agent, decision.reasoning)

            # Emit status message to frontend via token sink
            await emit_status(decision.status_message, state)

        # CACHE THE ROUTING DECISION
        cache_data = {
            "should_continue": state["should_continue"],
            "next_agent": state.get("next_agent"),
            "status_message": state.get("status_message", "Processing request..."),
            "routing_history": state.get("routing_history"),
            "multi_agent_hops": state.get("multi_agent_hops", 0),
        }
        cache_manager.set("routing", "supervisor", cache_key, cache_data, ttl=20)  # 20 sec cache to prevent loops
        
    except asyncio.TimeoutError:
        # Get last agent for fallback
        last_agent = next(
            (m.get("agent") for m in reversed(state.get("messages", []))
             if isinstance(m, dict) and m.get("role") == "assistant" and m.get("agent")),
            "generalist"  # Default to generalist if no last agent
        )
        logger.warning(f"Router timeout after {timeout}s, falling back to {last_agent}")
        state["should_continue"] = True
        state["next_agent"] = last_agent
        state["status_message"] = "Processing your request..."
        record_routing(last_agent, f"Router timeout after {timeout}s", increment=True)

        # Emit status message
        await emit_status("Processing your request...", state)

    except Exception as e:
        logger.error(f"Router LLM failed: {e}, falling back to generalist")
        # Simple fallback - route to generalist
        state["should_continue"] = True
        state["next_agent"] = "generalist"
        state["status_message"] = "Processing your request..."
        record_routing("generalist", "Router LLM error fallback", increment=True)

        # Emit status message
        await emit_status("Processing your request...", state)

    return state


async def dcf_agent_node(state: Dict[str, Any], dcf_agent, execute_with_retry) -> Dict[str, Any]:
    """Execute DCF agent for discounted cash flow valuation analysis"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] dcf_agent_node cancelled before execution")
        raise asyncio.CancelledError("dcf_agent_node cancelled by user")

    # Code Interpreter guard is now handled in langgraph_utils.py by removing the tool

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)

    logger.info(f"DCF Agent processing: {query[:100]}...")

    # Set context for file tools using tokens
    org_id = state.get("org_id")

    # Set context with tokens for proper cleanup
    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    # Check if files are attached and add context
    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Load whichever attachments contain the valuation inputs you need before modeling."
    )
    enhanced_query = query + file_context if file_context else query

    enhanced_query = await maybe_inject_on_switch(
        state,
        enhanced_query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    enhanced_query = _inject_portfolio_context(enhanced_query, state, "DCF")

    # Inject tool priority if user specified prioritized tools
    enhanced_query = inject_tool_priority(enhanced_query, state)

    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Use SQLite session for persistence with provider-scoped IDs
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for dcf_agent with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "dcf_agent")

        result = None
        # Fetch streaming token sink from context (if streaming is enabled)
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass

                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    dcf_agent,
                    enhanced_query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="DCF Agent",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[dcf_agent_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[dcf_agent_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            # Execute the DCF agent
            result = await execute_with_retry(
                dcf_agent,
                enhanced_query,  # Use enhanced query with file context
                session,
                max_turns=40,  # Increased to handle complex DCF calculations
                agent_name="DCF Agent",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "dcf_agent")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            logger.info(f"[DCF-AGENT] Processing {len(result.new_items)} new_items for charts")
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                charts_key = output_obj.get('charts')
                                if isinstance(charts_key, list) and charts_key:
                                    logger.info(f"[DCF-AGENT] Found charts array with {len(charts_key)} items")
                                    charts_from_tool.extend(charts_key)
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except Exception as e:
                            logger.warning(f"[DCF-AGENT] Failed to parse tool output: {e}")
        else:
            logger.info("[DCF-AGENT] No new_items to process for charts")

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[DCF-AGENT] Extracted {len(charts_from_tool)} charts from tool output")
        else:
            logger.info("[DCF-AGENT] No charts found in tool outputs")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None  # Clear next_agent for terminal agents
        msg_payload: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "dcf_agent",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "dcf_agent", msg_payload)

        if state.get("charts"):
            msg_payload["charts"] = state["charts"]

        state["messages"].append(msg_payload)
        state["last_provider"] = provider

        # Computed completion signal based on actual results
        if result and hasattr(result, 'final_output') and result.final_output:
            state["next"] = "END"  # Signal completion based on successful output
            logger.info("DCF agent completed with results - signaling END")

        logger.info("DCF agent completed analysis")

    except Exception as e:
        logger.error(f"DCF agent node error: {e}")
        _record_error(state, "dcf_agent", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error performing DCF analysis: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "dcf_agent",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        # Always reset context to prevent leakage (idempotent)
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def funds_products_analyst_node(state: Dict[str, Any], funds_products_analyst, execute_with_retry) -> Dict[str, Any]:
    """Execute funds & products analyst for fund and financial product analysis"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] funds_products_analyst_node cancelled before execution")
        raise asyncio.CancelledError("funds_products_analyst_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    logger.info(f"Funds Products Analyst processing: {query[:100]}...")

    # Set context with tokens for proper cleanup
    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    # Check if files are attached and add context
    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Review each attached prospectus or fact sheet before forming conclusions."
    )
    enhanced_query = query + file_context if file_context else query

    enhanced_query = await maybe_inject_on_switch(
        state,
        enhanced_query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    enhanced_query = _inject_portfolio_context(enhanced_query, state, "FUNDS_PRODUCTS")

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Use SQLite session for persistence with provider-scoped IDs
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for funds_products_analyst with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "funds_products_analyst")

        result = None
        # Fetch streaming token sink from context (if streaming is enabled)
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass

                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    funds_products_analyst,
                    enhanced_query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="Funds Products Analyst",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[funds_products_analyst_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[funds_products_analyst_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            # Execute the funds products analyst
            result = await execute_with_retry(
                funds_products_analyst,
                enhanced_query,  # Use enhanced query with file context
                session,
                max_turns=40,  # Increased to handle complex fund analysis
                agent_name="Funds Products Analyst",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "funds_products_analyst")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[FUNDS-PRODUCTS-ANALYST] Extracted {len(charts_from_tool)} charts from tool output")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None  # Clear next_agent for terminal agents
        msg_payload: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "funds_products_analyst",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "funds_products_analyst", msg_payload)

        if state.get("charts"):
            msg_payload["charts"] = state["charts"]

        state["messages"].append(msg_payload)
        state["last_provider"] = provider

        # Computed completion signal based on actual results
        if result and hasattr(result, 'final_output') and result.final_output:
            state["next"] = "END"  # Signal completion based on successful output
            logger.info("Funds products analyst completed with results - signaling END")

        logger.info("Funds products analyst completed analysis")

    except Exception as e:
        logger.error(f"Funds products analyst node error: {e}")
        _record_error(state, "funds_products_analyst", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error analyzing funds and products: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "funds_products_analyst",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        # Always reset context to prevent leakage (idempotent)
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


def supervisor_routing(state: Dict[str, Any]) -> Literal[
    "generalist",
    "risk_specialist",
    "document_analyst",
    "comparable_companies",
    "chart_analyst",
    "quant_coding",
    "structuring_analyst",
    "options_coding",
    "alternatives_coding",
    "institutional_activity",
    "dcf_agent",
    "funds_products_analyst",
    "prediction_markets_analyst",
    "private_markets",
    "portfolio_semantic_agent",
    "end",
]:
    """Determine next node based on supervisor decision"""

    # Check if we should continue
    if not state.get("should_continue", True):
        logger.info("Routing to END - should_continue is False")
        return "end"

    # Check if we have a response and this is the initial query
    if state.get("last_agent_response") and not state.get("next_agent"):
        logger.info("Routing to END - have response and no next agent specified")
        return "end"

    next_agent = state.get("next_agent")
    if next_agent == "risk_specialist":
        logger.info("Routing to risk_specialist")
        return "risk_specialist"
    elif next_agent == "document_analyst":
        logger.info("Routing to document_analyst")
        return "document_analyst"
    elif next_agent == "comparable_companies":
        logger.info("Routing to comparable_companies")
        return "comparable_companies"
    elif next_agent == "chart_analyst":
        logger.info("Routing to chart_analyst")
        return "chart_analyst"
    elif next_agent == "quant_coding":
        logger.info("Routing to quant_coding")
        return "quant_coding"
    elif next_agent == "structuring_analyst":
        logger.info("Routing to structuring_analyst")
        return "structuring_analyst"
    elif next_agent == "options_coding":
        logger.info("Routing to options_coding")
        return "options_coding"
    elif next_agent == "alternatives_coding":
        logger.info("Routing to alternatives_coding")
        return "alternatives_coding"
    elif next_agent == "institutional_activity":
        logger.info("Routing to institutional_activity")
        return "institutional_activity"
    elif next_agent == "dcf_agent":
        logger.info("Routing to dcf_agent")
        return "dcf_agent"
    elif next_agent == "funds_products_analyst":
        logger.info("Routing to funds_products_analyst")
        return "funds_products_analyst"
    elif next_agent == "prediction_markets_analyst":
        logger.info("Routing to prediction_markets_analyst")
        return "prediction_markets_analyst"
    elif next_agent == "private_markets":
        logger.info("Routing to private_markets")
        return "private_markets"
    elif next_agent == "portfolio_semantic_agent":
        logger.info("Routing to portfolio_semantic_agent")
        return "portfolio_semantic_agent"
    elif next_agent == "generalist":
        logger.info("Routing to generalist")
        return "generalist"
    else:
        logger.info("Routing to END - no valid next_agent")
        return "end"


async def generalist_node(state: Dict[str, Any], main_agent, execute_with_retry) -> Dict[str, Any]:
    """Execute generalist agent using existing OpenAI SDK implementation WITH CACHING and context transcript"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] generalist_node cancelled before execution")
        raise asyncio.CancelledError("generalist_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]
    
    # Process workflow context for file attachments
    workflow_context = state.get("workflow_context")
    if workflow_context is None:
        workflow_context = {}
    attachments = workflow_context.get("attachments", [])
    
    # Enhance query with attachment and portfolio context when present
    enhanced_query = query

    # Add web search priority when /search command is used
    force_web_search = state.get("force_web_search", False)
    if force_web_search:
        web_search_instruction = "\n\n[SYSTEM INSTRUCTION: User has explicitly requested web search. You MUST use web_search() tool as your primary tool for this query. Do not attempt to use other data sources first - go directly to web search for current, comprehensive information.]"
        enhanced_query = query + web_search_instruction
        logger.info("[COMMAND] Added web search priority instruction to generalist query")

    if attachments:
        logger.info(f"Processing {len(attachments)} file attachments in generalist node")
        formatted = []
        for att in attachments:
            name = att.get("name", "Unnamed file")
            content_type = att.get("type") or "unknown type"
            size = att.get("size")
            if isinstance(size, (int, float)):
                size_str = f"{int(size)} bytes"
            elif size:
                size_str = str(size)
            else:
                size_str = "size unknown"
            source = att.get("source", "upload")
            formatted.append(f"- {name} ({content_type}, {size_str}, source: {source})")
        attachment_context = "\n\nAttached files for analysis:\n" + "\n".join(formatted)
        enhanced_query = query + attachment_context
    else:
        enhanced_query = query

    # Inject cross-provider transcript only when switching providers
    enhanced_query = await maybe_inject_on_switch(
        state,
        enhanced_query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Inject inline portfolio context so the Generalist can reference it without portfolio tools
    portfolio_state = state.get("portfolio_state")
    logger.info(f"[PORTFOLIO DEBUG GENERALIST] portfolio_state from state: {portfolio_state}")
    if isinstance(portfolio_state, dict) and portfolio_state:
        try:
            import json as _json
            # Keep payload compact and deterministic
            # Limit long arrays to avoid token bloat
            compact = {}
            for k, v in portfolio_state.items():
                if isinstance(v, list) and len(v) > 50:
                    compact[k] = v[:50] + ["...", f"len={len(v)}"]
                else:
                    compact[k] = v
            portfolio_json = _json.dumps(compact, sort_keys=True, default=str)
            logger.info(f"[PORTFOLIO DEBUG GENERALIST] Injecting portfolio context into prompt: {portfolio_json}")
            enhanced_query = (
                f"{enhanced_query}\n\n"
                f"Portfolio context (provided with the request; use it if relevant):\n"
                f"{portfolio_json}\n"
            )
            logger.info(f"[PORTFOLIO DEBUG GENERALIST] Enhanced query now includes portfolio")
        except Exception as e:
            logger.warning(f"[generalist_node] Failed to serialize portfolio_state for prompt: {e}")
    else:
        logger.warning(f"[PORTFOLIO DEBUG GENERALIST] No portfolio_state in state or invalid format")
    
    # CACHE CHECK for agent responses
    # Use stable cache keys (sha256 of normalized payload) - include attachments in cache key
    import hashlib, json as _json
    # Include a stable digest of portfolio_state to avoid stale caching across different inline portfolios
    try:
        portfolio_digest = None
        if isinstance(state.get("portfolio_state"), dict) and state["portfolio_state"]:
            portfolio_digest = hashlib.sha256(
                _json.dumps(state["portfolio_state"], sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
    except Exception:
        portfolio_digest = None

    _payload = {
        "agent": "generalist",
        "query": enhanced_query,
        "session": session_id,
        "attachments": bool(attachments),
        "portfolio": portfolio_digest,
    }
    cache_key = hashlib.sha256(_json.dumps(_payload, sort_keys=True).encode("utf-8")).hexdigest()
    
    cached_response = cache_manager.get("agent", "generalist", cache_key)
    if cached_response:
        logger.info("Cache HIT for generalist response")
        state["last_agent_response"] = cached_response["response"]
        state["next_agent"] = None  # Clear next_agent for terminal agents
        state["messages"].append({
            "role": "assistant",
            "content": cached_response["response"],
            "agent": "generalist",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
        return state

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    # Emit initial status
    await emit_status("Processing request...", state)

    result = None

    try:
        # Use file-based SQLite for persistence across queries with provider-scoped IDs
        # Use separate database for OpenAI sessions
        # IMPORTANT: The SQLiteSession automatically loads previous conversation history
        # from the database when created with the same session_id.
        # Do NOT manually add items - the SDK handles this automatically!
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for generalist with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "generalist")

        # Set context for portfolio tools to work using tokens
        user_id = state.get("user_id")
        org_id = state.get("org_id")
        
        # Set context with tokens for proper cleanup
        tok_u = user_context.set(user_id) if user_id else None
        tok_s = session_context.set(session_id)
        
        # Set memory context for memory tools
        set_memory_context(session_id, user_id, org_id)
        
        # Save active/default portfolio into session context for tools to discover
        try:
            portfolio_state = state.get("portfolio_state")
            if portfolio_state and isinstance(portfolio_state, dict):
                # Keep a compact JSON string to avoid heavy context propagation
                import json as _json
                session_context_portfolio = context_key = None  # placeholder to satisfy linter
                # Store on the state so risk node sees it too
                state["portfolio_state"] = portfolio_state
        except Exception:
            pass
        
        # Check if files are attached and add context
        file_ids = state.get("file_ids")
        if file_ids:
            logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
        file_context = _build_file_context(
            file_ids,
            user_id,
            "Load every attached data file before running risk calculations."
        )
        if file_context:
            enhanced_query += file_context
        
        # Track FMP attempts per query to force web fallback
        import hashlib
        query_hash = hashlib.md5(enhanced_query.encode()).hexdigest()[:8]
        attempt_key = f"{session_id}:{query_hash}"
        
        # Use a persistent storage mechanism (state) instead of session attribute
        # The state persists across the workflow
        if 'fmp_attempts' not in state:
            state['fmp_attempts'] = {}
            
        current_attempts = state['fmp_attempts'].get(attempt_key, 0)
        
        # Inject fallback instruction if at limit
        if current_attempts >= app_config.fmp_max_attempts:
            enhanced_query += "\n[SYSTEM: FMP attempts exhausted. USE web_search for any missing data.]"
            logger.info(f"Forcing web search fallback for {attempt_key} after {current_attempts} FMP attempts")
        
        try:
            # If streaming sink is provided, stream tokens via Agents SDK
            stream_sink = get_token_sink()
            logger.warning(f"[STREAMING DEBUG] stream_sink received: {stream_sink is not None}, type: {type(stream_sink)}")
            if stream_sink is not None:
                try:
                    from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                    # Emit status before execution
                    await emit_status("Analyzing data...", state)

                    async def _on_token(t: str):
                        try:
                            await stream_sink.put(t)
                        except Exception:
                            pass
                    async def _on_event(evt: Dict[str, Any]):
                        if stream_sink is None:
                            return
                        try:
                            await stream_sink.put({"type": "stream_event", "event": evt})
                        except Exception:
                            pass
                    result = await _exec_stream(
                        main_agent,
                        enhanced_query,
                        session,
                        _on_token,
                        on_event=_on_event,
                        max_turns=40,
                        agent_name="Generalist",
                        selected_model=state.get("selected_model"),
                    )
                except Exception as e:
                    import traceback
                    logger.warning(f"[generalist_node] Streaming path failed, falling back to non-streaming: {e}")
                    logger.warning(f"[generalist_node] Streaming traceback:\n{traceback.format_exc()}")
                    result = await execute_with_retry(
                        main_agent,
                        enhanced_query,
                        session,
                        max_turns=40,
                        agent_name="Generalist",
                        selected_model=state.get("selected_model"),
                    )
            else:
                # Non-streaming path (existing)
                result = await execute_with_retry(
                    main_agent,
                    enhanced_query,  # Pass enhanced query with attachment context
                    session,
                    max_turns=40,  # Increased to handle complex multi-tool workflows
                    agent_name="Generalist",
                    selected_model=state.get("selected_model"),  # Pass selected model for override
                )
        finally:
            # Always reset context to prevent leakage (idempotent)
            try:
                if tok_u:
                    user_context.reset(tok_u)
            except Exception:
                pass
            try:
                if tok_s:
                    session_context.reset(tok_s)
            except Exception:
                pass
            try:
                clear_memory_context()
            except Exception:
                pass
        
        response = result.final_output if hasattr(result, 'final_output') else str(result)
        
        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "generalist")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data
        
        # Track FMP tool usage for this query
        if result and hasattr(result, 'new_items'):
            for item in result.new_items:
                # Debug: log item types to understand structure
                item_type = getattr(item, 'type', None)
                if item_type:
                    logger.debug(f"Item type: {item_type}")
                
                # Check for tool calls (handle both direct tools and MCP tools)
                if item_type in ('tool_call_item', 'tool_call'):
                    tool_name = getattr(item, 'name', None)
                    logger.debug(f"Tool called: {tool_name}")
                    if tool_name in ['discover_fields', 'get_fields', 'discover_valuation_fields']:
                        new_count = current_attempts + 1
                        state['fmp_attempts'][attempt_key] = new_count
                        logger.info(f"FMP attempt {new_count} for {attempt_key} (tool: {tool_name})")
                        # Update current_attempts for next check
                        current_attempts = new_count
                        break

        # Extract structured outputs from tool calls (e.g., web_search returns content + sources, charts)
        try:
            if result and hasattr(result, 'new_items'):
                # Aggregate any tool outputs that include 'sources' or 'content'
                aggregated_sources: List[Dict[str, Any]] = []
                aggregated_charts: List[Dict[str, Any]] = []
                preferred_content: Optional[str] = None
                for item in result.new_items:
                    if getattr(item, 'type', None) in ('tool_call_output_item', 'tool_call_output'):
                        output_obj = getattr(item, 'output', None)
                        # Tools often return JSON strings; parse when needed
                        if isinstance(output_obj, str):
                            try:
                                import json as _json
                                parsed_obj = _json.loads(output_obj)
                                logger.info(f"[generalist_node] Successfully parsed JSON from tool output")
                                # Check if this is a chart
                                if isinstance(parsed_obj, dict) and 'plotly' in parsed_obj:
                                    logger.info(f"[generalist_node] Chart detected with ID: {parsed_obj.get('id')}")
                                    if 'data' in parsed_obj.get('plotly', {}):
                                        traces = parsed_obj['plotly']['data']
                                        logger.info(f"[generalist_node] Chart has {len(traces)} traces")
                                        if traces and len(traces) > 0:
                                            first_trace = traces[0]
                                            x_len = len(first_trace.get('x', []))
                                            y_len = len(first_trace.get('y', []))
                                            logger.info(f"[generalist_node] First trace has {x_len} x points and {y_len} y points")
                                output_obj = parsed_obj
                            except Exception as e:
                                logger.warning(f"[generalist_node] Failed to parse JSON from tool: {e}")
                                logger.warning(f"[generalist_node] Raw output was: {output_obj[:500] if len(output_obj) > 500 else output_obj}")
                                # Don't set to None - keep the string for debugging
                        if isinstance(output_obj, dict):
                            # Capture sources array when present
                            if isinstance(output_obj.get('sources'), list) and output_obj['sources']:
                                aggregated_sources.extend(output_obj['sources'])
                            # Capture charts array or single chart when present
                            if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                aggregated_charts.extend(output_obj['charts'])
                            elif all(k in output_obj for k in ("id", "plotly")):
                                # Single chart object returned directly by chart tools
                                aggregated_charts.append(output_obj)
                            # Prefer explicit content from tool when available
                            if isinstance(output_obj.get('content'), str) and output_obj['content'].strip():
                                preferred_content = output_obj['content']
                if aggregated_sources:
                    state["search_sources"] = aggregated_sources
                if aggregated_charts:
                    # Attach charts to the latest assistant message for frontend rendering
                    # and also store at state level for API response assembly
                    logger.info(f"[generalist_node] Aggregated {len(aggregated_charts)} charts")
                    for chart in aggregated_charts:
                        logger.info(f"[generalist_node] Chart ID: {chart.get('id')}, Title: {chart.get('title')}")
                    state["charts"] = aggregated_charts
                if preferred_content:
                    response = preferred_content
        except Exception as parse_err:
            logger.warning(f"[generalist_node] Failed to parse tool outputs for sources: {parse_err}")
        
        # CACHE THE RESPONSE (avoid reusing long content when charts exist)
        cache_data = {"response": response if not state.get("charts") else ""}
        cache_manager.set("agent", "generalist", cache_key, cache_data, ttl=5)  # cache for 5 seconds
        
        # Don't overwrite calculation_results if they exist
        if not state.get("calculation_results"):
            state["last_agent_response"] = response
        
        # Clear next_agent for terminal agents
        state["next_agent"] = None
        
        # Attach charts if present
        msg: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "generalist",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "generalist", msg)
        if state.get("charts"):
            msg["charts"] = state["charts"]
        state["messages"].append(msg)
        state["last_provider"] = provider

        logger.info("Generalist completed processing")

    except Exception as e:
        logger.error(f"Generalist node error: {e}")
        _record_error(state, "generalist", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "generalist",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        # Always reset context to prevent leakage (idempotent)
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def risk_specialist_node(state: Dict[str, Any], risk_specialist, execute_with_retry) -> Dict[str, Any]:
    """Execute risk specialist with enhanced multi-tool workflow support WITH CACHING and context transcript"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] risk_specialist_node cancelled before execution")
        raise asyncio.CancelledError("risk_specialist_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]
    
    # Process workflow context for file attachments
    workflow_context = state.get("workflow_context")
    if workflow_context is None:
        workflow_context = {}
    attachments = workflow_context.get("attachments", [])
    
    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)

    # Enhance query with attachment context if present
    enhanced_query = query
    if attachments:
        logger.info(f"Processing {len(attachments)} file attachments in risk specialist node")
        formatted = []
        for att in attachments:
            name = att.get("name", "Unnamed file")
            content_type = att.get("type") or "unknown type"
            size = att.get("size")
            if isinstance(size, (int, float)):
                size_str = f"{int(size)} bytes"
            elif size:
                size_str = str(size)
            else:
                size_str = "size unknown"
            source = att.get("source", "upload")
            formatted.append(f"- {name} ({content_type}, {size_str}, source: {source})")
        attachment_context = "\n\nAttached files for analysis:\n" + "\n".join(formatted)
        enhanced_query = query + attachment_context
    enhanced_query = await maybe_inject_on_switch(
        state,
        enhanced_query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject inline portfolio context similar to generalist
    portfolio_state = state.get("portfolio_state")
    if isinstance(portfolio_state, dict) and portfolio_state:
        try:
            import json as _json
            compact_pf = {}
            for k, v in portfolio_state.items():
                if isinstance(v, list) and len(v) > 50:
                    compact_pf[k] = v[:50] + ["...", f"len={len(v)}"]
                else:
                    compact_pf[k] = v
            portfolio_json = _json.dumps(compact_pf, sort_keys=True, default=str)
            enhanced_query = (
                f"{enhanced_query}\n\n"
                f"Portfolio context (provided with the request or loaded by server; use it for calculations):\n"
                f"{portfolio_json}\n"
            )
        except Exception as e:
            logger.warning(f"[risk_specialist_node] Failed to serialize portfolio_state for prompt: {e}")

    # Inject tool priority if user specified prioritized tools
    enhanced_query = inject_tool_priority(enhanced_query, state)

    # CACHE CHECK for risk calculations
    # Stable cache key for risk calculations - include attachments
    import hashlib, json as _json
    _risk_payload = {
        "agent": "risk_specialist",
        "query": enhanced_query,
        "portfolio": state.get("portfolio_state", None),
        "attachments": bool(attachments)
    }
    cache_key = hashlib.sha256(_json.dumps(_risk_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    
    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    # Emit initial status
    await emit_status("Preparing analysis...", state)

    tok_u = None
    tok_s = None

    try:
        # Use file-based SQLite for persistence across queries with provider-scoped IDs
        # Use separate database for OpenAI sessions
        # IMPORTANT: The SQLiteSession automatically loads previous conversation history
        # from the database when created with the same session_id.
        # Since generalist runs first, its output is already in the database,
        # so risk_specialist will see it automatically!
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for risk_specialist with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "risk_specialist")
        
        # Set context for portfolio tools using tokens
        user_id = state.get("user_id")
        org_id = state.get("org_id")
        
        # Set context with tokens for proper cleanup
        tok_u = user_context.set(user_id) if user_id else None
        tok_s = session_context.set(session_id)
        
        # Set memory context for memory tools
        set_memory_context(session_id, user_id, org_id)
        
        # Ensure portfolio context is available to tools
        try:
            if not state.get("portfolio_state"):
                # Attempt to load default portfolio as fallback
                from core.services import get_portfolio_service
                service = get_portfolio_service()
                portfolios = await service.list_user_portfolios(user_id) if user_id else {"count": 0}
                default_id = portfolios.get("default_portfolio_id") if isinstance(portfolios, dict) else None
                if default_id:
                    pf = await service.get_portfolio(user_id, default_id)
                    if pf and pf.get("status") == "success":
                        state["portfolio_state"] = {
                            "tickers": pf["portfolio"].get("tickers", []),
                            "weights": pf["portfolio"].get("weights", []),
                            "value": pf["portfolio"].get("value")
                        }
        except Exception as _e:
            logger.debug(f"[risk_specialist_node] Failed to preload default portfolio: {_e}")

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                # Emit status before execution
                await emit_status("Running calculations...", state)

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    risk_specialist,
                    enhanced_query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="Risk Specialist",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                # ModelBehaviorError ("Model did not produce a final response") is expected when 
                # the agent uses many tool calls. The fallback to non-streaming handles this gracefully.
                is_model_behavior_error = "ModelBehaviorError" in type(e).__name__ or "final response" in str(e).lower()
                if is_model_behavior_error:
                    logger.info(f"[risk_specialist_node] Streaming exhausted turns with tool calls; using non-streaming fallback")
                else:
                    logger.warning(f"[risk_specialist_node] Streaming path failed, falling back to non-streaming: {e}")
                    logger.debug(f"[risk_specialist_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                risk_specialist,
                enhanced_query,  # Pass enhanced query with attachment context
                session,
                max_turns=40,  # Increased to handle complex multi-tool workflows
                agent_name="Risk Specialist",
                selected_model=state.get("selected_model"),  # Pass selected model for override
            )
    except Exception as e:
        logger.error(f"Risk specialist node error: {e}")
        _record_error(state, "risk_specialist", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error during risk calculation: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "risk_specialist",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
        return state
    finally:
        # Always reset context to prevent leakage (idempotent)
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    response = result.final_output if hasattr(result, 'final_output') else str(result)

    # Extract code execution data using centralized function
    code_exec_data = _extract_code_execution_data(result, "risk_specialist")
    if code_exec_data:
        state["code_execution_data"] = code_exec_data

    # Emit final status
    await emit_status("Generating results...", state)

    # Parse and aggregate results from multi-tool workflows (including charts)
    if result and hasattr(result, 'new_items'):
        # Extract portfolio state and risk results from structured tool outputs
        risk_results = {}
        aggregated_charts: List[Dict[str, Any]] = []
        for item in result.new_items:
            if getattr(item, 'type', None) in ('tool_call_output_item', 'tool_call_output'):
                output_obj = getattr(item, 'output', None)
                # Tools may return JSON strings; parse if needed
                if isinstance(output_obj, str):
                    try:
                        import json as _json
                        output_obj = _json.loads(output_obj)
                    except Exception:
                        output_obj = None
                if isinstance(output_obj, dict):
                    for key, value in output_obj.items():
                        if key not in risk_results:
                            risk_results[key] = []
                        risk_results[key].append(value)
                    # Capture charts from risk tool outputs too
                    if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                        aggregated_charts.extend(output_obj['charts'])
                    elif all(k in output_obj for k in ("id", "plotly")):
                        aggregated_charts.append(output_obj)

        if risk_results:
            state["risk_results"] = risk_results
            logger.info(f"Aggregated risk results from {len(risk_results)} tool outputs")
        if aggregated_charts:
            state["charts"] = aggregated_charts
        
        # Store calculation results
        state["calculation_results"] = response
        state["handback_pending"] = True
        
        # CACHE THE CALCULATION (1 hour for risk calculations)
        cache_data = {
            "response": response,
            "calculation_results": response,
            "handback_pending": True,
            "risk_results": state.get("risk_results")
        }
        # DISABLED: Risk calculations should not be cached - they need fresh market data
        # cache_manager.set("risk", "calculation", cache_key, cache_data, ttl=3600)  # 1 hour cache
        
        # Update portfolio state if optimization was performed
        if "optimization" in response.lower() or "optimal" in response.lower():
            if not state.get("optimization_suggestions"):
                state["optimization_suggestions"] = {}
            state["optimization_suggestions"]["latest"] = response
        
        state["last_agent_response"] = response
        # Attach charts if present
        msg2: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "risk_specialist",
            "provider": provider,
            "model": selected_model,
            "multi_tool_workflow": bool(state.get("risk_results"))
        }
        _attach_code_execution_metadata(state, "risk_specialist", msg2)
        if state.get("charts"):
            msg2["charts"] = state["charts"]
        state["messages"].append(msg2)
        state["last_provider"] = provider
        
        logger.info("Risk specialist completed multi-tool workflow processing")
    
    return state


async def document_analyst_node(state: Dict[str, Any], document_analyst, execute_with_retry) -> Dict[str, Any]:
    """Execute document analyst agent for SEC filings and transcripts"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] document_analyst_node cancelled before execution")
        raise asyncio.CancelledError("document_analyst_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")  # Get user_id from state if available

    logger.info(f"Document Analyst processing: {query[:100]}...")
    logger.info(f"Session context: session_id={session_id}, user_id={user_id}")

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)

    # Set context for file tools using tokens
    org_id = state.get("org_id")

    # Set context with tokens for proper cleanup
    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    # Check if files are attached and add context
    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Review every attached filing or transcript instead of assuming only the first document matters."
    )
    enhanced_query = query + file_context if file_context else query

    enhanced_query = await maybe_inject_on_switch(
        state,
        enhanced_query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    enhanced_query = _inject_portfolio_context(enhanced_query, state, "DOCUMENT_ANALYST")

    # Set session context on SEC server if available
    if document_analyst and hasattr(document_analyst, 'mcp_servers'):
        for server in document_analyst.mcp_servers:
            if hasattr(server, 'set_session_context'):
                logger.info(f"Setting session context on {server.__class__.__name__}")
                server.set_session_context(session_id, user_id)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Extract provider from selected model
        selected_model = state.get("selected_model", "gpt-5.4")
        provider = get_provider_from_model(selected_model)

        # Use SQLite session for persistence with provider-scoped IDs
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for document_analyst with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "document_analyst")

        # Emit status for document analysis
        await emit_status("Reading SEC filings...", state)

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    document_analyst,
                    enhanced_query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="Document Analyst",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[document_analyst_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[document_analyst_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                document_analyst,
                enhanced_query,  # Use enhanced query with file context
                session,
                max_turns=40,  # Increased to handle complex multi-tool workflows
                agent_name="Document Analyst",
                selected_model=state.get("selected_model"),  # Pass selected model for override
            )
        
        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "document_analyst")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[DOCUMENT-ANALYST] Extracted {len(charts_from_tool)} charts from tool output")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None  # Clear next_agent for terminal agents
        msg_doc: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "document_analyst",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "document_analyst", msg_doc)

        if state.get("charts"):
            msg_doc["charts"] = state["charts"]

        state["messages"].append(msg_doc)
        state["last_provider"] = provider
        
        logger.info("Document analyst completed analysis")
        
    except Exception as e:
        logger.error(f"Document analyst node error: {e}")
        _record_error(state, "document_analyst", e)
        state["last_agent_response"] = f"I encountered an error accessing documents: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "document_analyst",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
        return state
    finally:
        # Always reset context to prevent leakage (idempotent)
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def comparable_companies_node(state: Dict[str, Any], comparable_companies, execute_with_retry) -> Dict[str, Any]:
    """Execute comparable companies agent for valuation analysis"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] comparable_companies_node cancelled before execution")
        raise asyncio.CancelledError("comparable_companies_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]

    logger.info(f"Comparable Companies processing: {query[:100]}...")

    # Inject cross-provider transcript only when a provider switch occurs
    query = await maybe_inject_on_switch(
        state,
        query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    query = _inject_portfolio_context(query, state, "COMPARABLE_COMPANIES")

    # Inject tool priority if user specified prioritized tools
    query = inject_tool_priority(query, state)

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Use SQLite session for persistence with provider-scoped IDs
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for comparable_companies with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "comparable_companies")

        # Emit status for comparable companies analysis
        await emit_status("Comparing peer valuations...", state)

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    comparable_companies,
                    query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="Comparable Companies",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[comparable_companies_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[comparable_companies_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                comparable_companies,
                query,
                session,
                max_turns=40,  # Increased to handle complex multi-tool workflows
                agent_name="Comparable Companies",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "comparable_companies")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[COMPARABLE-COMPANIES] Extracted {len(charts_from_tool)} charts from tool output")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None  # Clear next_agent for terminal agents
        msg_comp: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "comparable_companies",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "comparable_companies", msg_comp)

        if state.get("charts"):
            msg_comp["charts"] = state["charts"]

        state["messages"].append(msg_comp)
        state["last_provider"] = provider

        # Computed completion signal based on actual results
        if result and hasattr(result, 'final_output') and result.final_output:
            state["next"] = "END"  # Signal completion based on successful output
            logger.info("Comparable companies completed with results - signaling END")

        logger.info("Comparable companies completed analysis")

    except Exception as e:
        logger.error(f"Comparable companies node error: {e}")
        _record_error(state, "comparable_companies", e)
        state["last_agent_response"] = f"I encountered an error analyzing comparable companies: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "comparable_companies",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider

    return state


async def chart_analyst_node(state: Dict[str, Any], chart_analyst, execute_with_retry) -> Dict[str, Any]:
    """Execute chart analyst agent for technical analysis and chart pattern recognition"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] chart_analyst_node cancelled before execution")
        raise asyncio.CancelledError("chart_analyst_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)

    logger.info(f"Chart Analyst processing: {query[:100]}...")

    # Process workflow context for file attachments
    workflow_context = state.get("workflow_context")
    if workflow_context is None:
        workflow_context = {}
    attachments = workflow_context.get("attachments", [])

    # Enhance query with attachment context if present
    enhanced_query = query
    if attachments:
        logger.info(f"Processing {len(attachments)} file attachments in chart analyst node")
        formatted = []
        for att in attachments:
            name = att.get("name", "Unnamed file")
            content_type = att.get("type") or "unknown type"
            size = att.get("size")
            if isinstance(size, (int, float)):
                size_str = f"{int(size)} bytes"
            elif size:
                size_str = str(size)
            else:
                size_str = "size unknown"
            source = att.get("source", "upload")
            formatted.append(f"- {name} ({content_type}, {size_str}, source: {source})")
        attachment_context = "\n\nAttached files for analysis:\n" + "\n".join(formatted)
        enhanced_query = query + attachment_context

    # Inject cross-provider transcript when switching providers
    enhanced_query = await maybe_inject_on_switch(
        state,
        enhanced_query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    enhanced_query = _inject_portfolio_context(enhanced_query, state, "CHART_ANALYST")

    # Set context for file tools to work using tokens
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    # Check if files are attached and add context
    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Open each chart image you need before describing setups or patterns."
    )
    if file_context:
        enhanced_query += file_context

    logger.info(f"[CHART DEBUG AUTH] user_id from state: {user_id}")
    logger.info(f"[CHART DEBUG AUTH] file_ids: {file_ids}")

    # Set context with tokens for proper cleanup
    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    logger.info(f"[CHART DEBUG AUTH] Context tokens set - user: {tok_u}, session: {tok_s}")

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Use SQLite session for persistence with provider-scoped IDs
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for chart_analyst with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "chart_analyst")

        # Emit status for chart analysis
        await emit_status("Analyzing chart patterns...", state)

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    chart_analyst,
                    enhanced_query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="Chart Analyst",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[chart_analyst_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[chart_analyst_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                chart_analyst,
                enhanced_query,  # Pass enhanced query with attachment context
                session,
                max_turns=40,  # Increased to handle complex multi-tool workflows
                agent_name="Chart Analyst",
                selected_model=state.get("selected_model"),  # Pass selected model for override
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "chart_analyst")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Parse and aggregate any chart results from tool outputs
        if result and hasattr(result, 'new_items'):
            aggregated_charts: List[Dict[str, Any]] = []
            for item in result.new_items:
                if getattr(item, 'type', None) in ('tool_call_output_item', 'tool_call_output'):
                    output_obj = getattr(item, 'output', None)
                    # Tools may return JSON strings; parse if needed
                    if isinstance(output_obj, str):
                        try:
                            import json as _json
                            output_obj = _json.loads(output_obj)
                        except Exception:
                            output_obj = None
                    if isinstance(output_obj, dict):
                        # Capture charts from tool outputs
                        if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                            aggregated_charts.extend(output_obj['charts'])
                        elif all(k in output_obj for k in ("id", "plotly")):
                            aggregated_charts.append(output_obj)

            if aggregated_charts:
                state["charts"] = aggregated_charts
                logger.info(f"Chart analyst aggregated {len(aggregated_charts)} charts")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None  # Clear next_agent for terminal agents

        # Attach charts if present
        msg: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "chart_analyst",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "chart_analyst", msg)
        if state.get("charts"):
            msg["charts"] = state["charts"]
        state["messages"].append(msg)
        state["last_provider"] = provider

        logger.info("Chart analyst completed technical analysis")

    except Exception as e:
        logger.error(f"Chart analyst node error: {e}")
        _record_error(state, "chart_analyst", e)
        state["last_agent_response"] = f"I encountered an error analyzing the chart: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "chart_analyst",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        # Always reset context to prevent leakage (idempotent)
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def quant_coding_node(state: Dict[str, Any], quant_coding, execute_with_retry) -> Dict[str, Any]:
    """Execute quant coding agent for custom quantitative implementations"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] quant_coding_node cancelled before execution")
        raise asyncio.CancelledError("quant_coding_node cancelled by user")

    # Code Interpreter guard is now handled in langgraph_utils.py by removing the tool

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    # Import context utilities (like other agent nodes)

    # Set context
    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    # Check if files are attached and add context
    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Inspect every attached dataset (CSV, XLSX, DOCX, PDF) before coding."
    )
    if file_context:
        query += file_context

    query = await maybe_inject_on_switch(
        state,
        query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    query = _inject_portfolio_context(query, state, "QUANT_CODING")

    # Inject tool priority if user specified prioritized tools
    query = inject_tool_priority(query, state)

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Use SQLite session for persistence with provider-scoped IDs (like other agents)
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for quant_coding with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "quant_coding")

        # Emit status for quant coding
        await emit_status("Running Python code...", state)

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    quant_coding,
                    query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="QuantCoding",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[quant_coding_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[quant_coding_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            # Execute agent with session (like other agents)
            result = await execute_with_retry(
                quant_coding,
                query,
                session,
                max_turns=40,
                agent_name="QuantCoding",
                selected_model=state.get("selected_model"),  # Pass selected model for override
            )

        # Update state with response (using final_output like other agents)
        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Pass 1: Prefer structured tool outputs from custom execute_python_code
        try:
            container_id_tool = None
            generated_files_tool: List[Dict[str, Any]] = []
            code_blocks_tool: List[Dict[str, Any]] = []
            charts_from_tool: List[Dict[str, Any]] = []  # Accumulate charts across all tool outputs

            if hasattr(result, 'new_items') and result.new_items:
                for item in result.new_items:
                    item_type = getattr(item, 'type', None)
                    if item_type in ('tool_call_output_item', 'tool_call_output'):
                        output_obj = getattr(item, 'output', None)
                        if isinstance(output_obj, str):
                            try:
                                import json as _json
                                output_obj = _json.loads(output_obj)
                            except Exception:
                                output_obj = None
                        if isinstance(output_obj, dict):
                            gf = output_obj.get('generated_files') or []
                            cid = output_obj.get('container_id')
                            cb = output_obj.get('code_blocks') or []

                            # Extract charts from tool output
                            # Check for charts array (from wrap_plotly_charts)
                            if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                charts_from_tool.extend(output_obj['charts'])
                                logger.info(f"[QUANT-CODING] Found {len(output_obj['charts'])} charts in 'charts' key")
                            # Check for unwrapped Plotly chart (has id + plotly)
                            elif all(k in output_obj for k in ("id", "plotly")):
                                charts_from_tool.append(output_obj)
                                logger.info("[QUANT-CODING] Found unwrapped Plotly chart")
                            # Check for wrapped chart handle (has chart_id, from register_chart_handle)
                            elif "chart_id" in output_obj and "id" in output_obj:
                                charts_from_tool.append(output_obj)
                                logger.info(f"[QUANT-CODING] Found wrapped chart handle: {output_obj.get('chart_id')}")

                            if gf or cid or cb:
                                for f in gf:
                                    fid = f.get('file_id')
                                    fname = f.get('filename') or (f"file_{fid}" if fid else None)
                                    f['filename'] = fname
                                    if not f.get('type'):
                                        f['type'] = _infer_file_type(fname)
                                generated_files_tool.extend(gf)
                                if cid and not container_id_tool:
                                    container_id_tool = cid
                                if isinstance(cb, list) and cb:
                                    code_blocks_tool.extend(cb)

            # Add charts to state if found (outside the loop to capture all charts)
            if charts_from_tool:
                state["charts"] = charts_from_tool
                logger.info(f"[QUANT-CODING] Extracted {len(charts_from_tool)} total charts from tool outputs")

            if container_id_tool or generated_files_tool or code_blocks_tool:
                # Deduplicate files
                seen = set()
                uniq_files: List[Dict[str, Any]] = []
                for f in generated_files_tool:
                    k = f.get('file_id') or f.get('filename')
                    if k and k not in seen:
                        seen.add(k)
                        uniq_files.append(f)
                state["code_execution_data"] = {
                    "container_id": container_id_tool,
                    "generated_files": uniq_files,
                    "code_blocks": code_blocks_tool,
                    "agent": "quant_coding",
                }
                logger.info(f"[QUANT-CODING] Extracted from tool outputs: files={len(uniq_files)}, code_blocks={len(code_blocks_tool)}")
        except Exception as e:
            logger.warning(f"[QUANT-CODING] Failed structured output extraction: {e}")

        # Pass 2: Use centralized extraction for code_interpreter_call items
        if not state.get("code_execution_data"):
            centralized_data = _extract_code_execution_data(result, "quant_coding")
            if centralized_data:
                state["code_execution_data"] = centralized_data
                logger.info(f"[QUANT-CODING] Extracted via centralized function: files={len(centralized_data.get('generated_files', []))}")

        # Pass 3: Additional fallbacks for regex patterns and Containers API
        # These supplement the centralized extraction with unique quant_coding fallbacks
        try:
            import re
            container_id = None
            generated_files = []
            code_blocks = []

            # Get any data already extracted
            existing_data = state.get("code_execution_data")
            if existing_data:
                container_id = existing_data.get("container_id")
                generated_files = list(existing_data.get("generated_files") or [])
                code_blocks = list(existing_data.get("code_blocks") or [])

            # Look for container ID in the response text (unique fallback)
            if not container_id:
                container_match = re.search(r'\[CONTAINER_METADATA\] container_id: (cntr_[a-f0-9]{32})', str(response))
                if not container_match:
                    container_match = re.search(r'cntr_[a-f0-9]{32}', str(response))

                if container_match:
                    container_id = container_match.group(1) if container_match.lastindex else container_match.group(0)
                    logger.info(f"[QUANT-CODING] Found container_id in response: {container_id}")

            # Look for file metadata markers from our custom tool
            file_metadata_matches = re.findall(r'\[FILE_METADATA\] file_id: (cfile_[a-f0-9]{32}), filename: ([^\n]+)', str(response))
            if file_metadata_matches:
                for file_id, filename in file_metadata_matches:
                    file_info = {
                        'container_id': container_id,
                        'file_id': file_id,
                        'filename': filename.strip(),
                        'type': 'file'
                    }
                    generated_files.append(file_info)
                    logger.info(f"[QUANT-CODING] Found file from metadata: {filename} ({file_id})")

            # Fallback: Look for file IDs and filenames in sandbox links
            # Pattern: [filename](sandbox:/mnt/data/filename)
            if not generated_files:
                file_pattern = r'\[([^\]]+)\]\(sandbox:/mnt/data/([^\)]+)\)'
                file_matches = re.findall(file_pattern, str(response))

                if file_matches:
                    # If we have files and container, list them from the container
                    if container_id:
                        try:
                            import openai
                            from core.config import get_config
                            config = get_config()
                            client = openai.OpenAI(api_key=config.openai_api_key)

                            files_response = client.containers.files.list(container_id)
                            for file_obj in files_response.data:
                                filename = file_obj.path.split('/')[-1] if file_obj.path else f"file_{file_obj.id}"
                                # Match the filename with our regex matches
                                for match_text, match_filename in file_matches:
                                    if filename == match_filename or filename in match_filename:
                                        file_info = {
                                            'container_id': container_id,
                                            'file_id': file_obj.id,
                                            'filename': filename,
                                            'type': 'file'
                                        }
                                        generated_files.append(file_info)
                                        logger.info(f"[QUANT-CODING] Matched file: {filename} ({file_obj.id})")
                                        break
                        except Exception as e:
                            logger.warning(f"[QUANT-CODING] Could not list container files: {e}")

                # If container_id still not found, scan recent session items as a fallback
                try:
                    if not container_id and 'session' in locals() and session:
                        try:
                            session_items = await session.get_items()  # type: ignore[attr-defined]
                        except Exception:
                            session_items = []
                        for it in reversed(session_items or []):
                            raw = None
                            try:
                                # Support both object-like and dict-like items
                                raw = getattr(it, 'raw_item', None) or (it.get('raw_item') if isinstance(it, dict) else None)
                            except Exception:
                                raw = None
                            raw_type = getattr(raw, 'type', None) or (raw.get('type') if isinstance(raw, dict) else None)
                            if raw_type == 'code_interpreter_call':
                                cid = getattr(raw, 'container_id', None) or (raw.get('container_id') if isinstance(raw, dict) else None)
                                if cid:
                                    container_id = cid
                                    logger.info(f"[QUANT-CODING] Found container_id from session history: {container_id}")
                                    break
                except Exception:
                    pass

                # Collect text outputs for sandbox path parsing (unique fallback)
            collected_texts: List[str] = []
            if isinstance(response, str):
                collected_texts.append(response)

            # Gather assistant text content for sandbox path parsing
            if hasattr(result, 'new_items') and result.new_items:
                for item in result.new_items:
                    content = getattr(item, 'content', None)
                    if content and isinstance(content, (list, tuple)):
                        for content_item in content:
                            text_val = getattr(content_item, 'text', None)
                            if text_val is None and isinstance(content_item, dict):
                                text_val = content_item.get('text') or content_item.get('value')
                            if isinstance(text_val, str) and text_val:
                                collected_texts.append(text_val)

            # Parse sandbox:/mnt/data/<filename> references from collected texts
            parsed_filenames: List[str] = []
            try:
                import re as _re
                text_blob = "\n".join(t for t in collected_texts if isinstance(t, str))
                # Allow common filename characters; stop at whitespace or unmatched )
                matches = set(_re.findall(r"sandbox:/mnt/data/([A-Za-z0-9_\-.() ]+)", text_blob))
                parsed_filenames = [m.strip() for m in matches if m and not m.endswith('/')]
            except Exception as _e:
                logger.debug(f"[MULTI-AGENT] Sandbox filename parsing skipped: {_e}")

            # If we have a container, resolve file_ids via Containers API by listing files
            if container_id:
                try:
                    import openai as _openai
                    from core.config import get_config as _get_config
                    _client = _openai.OpenAI(api_key=_get_config().openai_api_key)

                    files_resp = _client.containers.files.list(container_id)
                    files_list = getattr(files_resp, 'data', []) or []

                    # Build lookup by basename
                    def _basename(p: Optional[str]) -> str:
                        try:
                            return p.split('/')[-1] if p else ''
                        except Exception:
                            return ''

                    base_to_file = { _basename(getattr(fo, 'path', None)) or getattr(fo, 'id', None): fo for fo in files_list }

                    # If filenames were referenced in text, match to resolve ids
                    for fname in parsed_filenames:
                        fo = base_to_file.get(fname)
                        if fo:
                            generated_files.append({
                                "file_id": getattr(fo, 'id', None),
                                "filename": fname,
                                "type": _infer_file_type(fname),
                                "container_id": container_id
                            })

                    # Fallback: if no matches resolved but files exist, include all for discoverability
                    if files_list and not generated_files:
                        for fo in files_list:
                            fname = _basename(getattr(fo, 'path', None)) or getattr(fo, 'id', None)
                            generated_files.append({
                                "file_id": getattr(fo, 'id', None),
                                "filename": fname or f"file_{getattr(fo, 'id', '')}",
                                "type": _infer_file_type(fname),
                                "container_id": container_id
                            })
                except Exception as list_err:
                    logger.warning(f"[MULTI-AGENT] Failed to resolve files via Containers API: {list_err}")

            # Fallback code block extraction from fenced blocks
            if not code_blocks and isinstance(response, str) and response:
                try:
                    import re as _re2
                    code_matches = _re2.findall(r"```(?:python|Python)?\s*\n(.*?)\n?```", response, _re2.DOTALL | _re2.MULTILINE)
                    for cm in code_matches:
                        if isinstance(cm, str) and cm.strip():
                            code_blocks.append({"code": cm, "output": "", "language": "python"})
                except Exception:
                    pass

            # Deduplicate generated files by file_id or filename
            _seen_keys = set()
            _unique_files = []
            for gf in generated_files:
                key = gf.get('file_id') or gf.get('filename')
                if key and key not in _seen_keys:
                    _seen_keys.add(key)
                    _unique_files.append(gf)

            if _unique_files or container_id or code_blocks:
                existing = state.get("code_execution_data")
                if isinstance(existing, dict) and existing.get("agent") == "quant_coding":
                    if container_id and not existing.get("container_id"):
                        existing["container_id"] = container_id
                    if _unique_files:
                        seen_files = {f.get("file_id") or f.get("filename") for f in existing.get("generated_files", [])}
                        merged_files = existing.get("generated_files", [])
                        for gf in _unique_files:
                            key = gf.get("file_id") or gf.get("filename")
                            if key and key not in seen_files:
                                seen_files.add(key)
                                merged_files.append(gf)
                        existing["generated_files"] = merged_files
                    if code_blocks:
                        existing_blocks = existing.get("code_blocks", [])
                        existing["code_blocks"] = existing_blocks + code_blocks
                else:
                    state["code_execution_data"] = {
                        "container_id": container_id,
                        "generated_files": _unique_files,
                        "code_blocks": code_blocks,
                        "agent": "quant_coding",
                    }
                logger.info(f"[MULTI-AGENT] QuantCoding parsed (fallback): container={bool(container_id)}, files={len(_unique_files)}, code_blocks={len(code_blocks)}")
        except Exception as e:
            logger.warning(f"[MULTI-AGENT] Failed to process QuantCoding native CI output: {e}")

        state["last_agent_response"] = response
        state["quant_coding_response"] = response

        # Log successful execution
        logger.info(f"[MULTI-AGENT] QuantCoding agent completed code execution")

        # Add to messages (like other agents, not history)
        message_payload: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "quant_coding",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "quant_coding", message_payload)

        # Attach charts to message if present (matching generalist/risk_specialist pattern)
        if state.get("charts"):
            message_payload["charts"] = state["charts"]
            logger.info(f"[QUANT-CODING] Attached {len(state['charts'])} charts to message")

        state["messages"].append(message_payload)
        state["last_provider"] = provider

        # Terminal agent - no handoff needed
        state["next_agent"] = None

        logger.info("[MULTI-AGENT] QuantCoding code_execution_data in state: %s", state.get("code_execution_data"))
        logger.info("[MULTI-AGENT] QuantCoding message_payload has extras: %s", "code_execution_data" in message_payload)

    except Exception as e:
        logger.error(f"[MULTI-AGENT] QuantCoding agent error: {str(e)}")
        _record_error(state, "quant_coding", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error executing the custom quantitative code. Let me try a different approach."
        state["quant_coding_error"] = str(e)
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "quant_coding",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        # Always reset context to prevent leakage (idempotent)
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def options_coding_node(state: Dict[str, Any], options_coding, execute_with_retry) -> Dict[str, Any]:
    """Execute options coding agent for listed options analysis"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] options_coding_node cancelled before execution")
        raise asyncio.CancelledError("options_coding_node cancelled by user")

    # Code Interpreter guard is now handled in langgraph_utils.py by removing the tool

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Load every attached chain export or briefing before writing options code."
    )
    if file_context:
        query += file_context

    query = await maybe_inject_on_switch(
        state,
        query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    query = _inject_portfolio_context(query, state, "OPTIONS_CODING")

    # Inject tool priority if user specified prioritized tools
    query = inject_tool_priority(query, state)

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)
        logger.info(f"[DEBUG] Created SQLiteSession for options_coding with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "options_coding")

        # Emit status for options analysis
        await emit_status("Analyzing options data...", state)

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    options_coding,
                    query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="OptionsCoding",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[options_coding_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[options_coding_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                options_coding,
                query,
                session,
                max_turns=40,
                agent_name="OptionsCoding",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                # Extract charts from tool output
                                # Check for charts array (from wrap_plotly_charts)
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                # Check for unwrapped Plotly chart (has id + plotly)
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                                # Check for wrapped chart handle (has chart_id, from register_chart_handle)
                                elif "chart_id" in output_obj and "id" in output_obj:
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            state["_full_charts"] = charts_from_tool  # For orchestrator extraction
            logger.info(f"[OPTIONS-CODING] Stored {len(charts_from_tool)} charts in state and _full_charts")

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "options_coding")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        state["last_agent_response"] = response
        logger.info(f"[MULTI-AGENT] OptionsCoding agent completed")

        msg_options: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "options_coding",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "options_coding", msg_options)

        # Attach chart references to message (lightweight for agent context)
        if state.get("charts"):
            msg_options["charts"] = state["charts"]

        # Attach full charts to metadata (for database storage and frontend rendering)
        if state.get("_full_charts"):
            if "metadata" not in msg_options:
                msg_options["metadata"] = {}
            msg_options["metadata"]["full_charts"] = state["_full_charts"]
            logger.info(f"[OPTIONS-CODING] Attached {len(state['_full_charts'])} full charts to message metadata")

        state["messages"].append(msg_options)

        state["next_agent"] = None
        state["last_provider"] = provider

    except Exception as e:
        logger.error(f"[MULTI-AGENT] OptionsCoding agent error: {str(e)}")
        _record_error(state, "options_coding", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error analyzing options data. Let me try a different approach."
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "options_coding",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def alternatives_coding_node(state: Dict[str, Any], alternatives_coding, execute_with_retry) -> Dict[str, Any]:
    """Execute alternatives coding agent for crypto, forex, and commodities analysis"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] alternatives_coding_node cancelled before execution")
        raise asyncio.CancelledError("alternatives_coding_node cancelled by user")

    # Code Interpreter guard is now handled in langgraph_utils.py by removing the tool

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Open every attached dataset or brief before building alternatives/crypto code."
    )
    if file_context:
        query += file_context

    query = await maybe_inject_on_switch(
        state,
        query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    query = _inject_portfolio_context(query, state, "ALTERNATIVES_CODING")

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)
        logger.info(f"[DEBUG] Created SQLiteSession for alternatives_coding with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "alternatives_coding")

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    alternatives_coding,
                    query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="AlternativesCoding",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[alternatives_coding_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[alternatives_coding_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                alternatives_coding,
                query,
                session,
                max_turns=40,
                agent_name="AlternativesCoding",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                # Check for charts array (from wrap_plotly_charts)
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                # Check for unwrapped Plotly chart (has id + plotly)
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                                # Check for wrapped chart handle (has chart_id, from register_chart_handle)
                                elif "chart_id" in output_obj and "id" in output_obj:
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[ALTERNATIVES-CODING] Extracted {len(charts_from_tool)} charts from tool output")

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "alternatives_coding")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        state["last_agent_response"] = response
        logger.info(f"[MULTI-AGENT] AlternativesCoding agent completed")

        msg_alt: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "alternatives_coding",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "alternatives_coding", msg_alt)

        if state.get("charts"):
            msg_alt["charts"] = state["charts"]

        state["messages"].append(msg_alt)

        state["next_agent"] = None
        state["last_provider"] = provider

    except Exception as e:
        logger.error(f"[MULTI-AGENT] AlternativesCoding agent error: {str(e)}")
        _record_error(state, "alternatives_coding", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error analyzing alternative assets. Let me try a different approach."
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "alternatives_coding",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def institutional_activity_node(state: Dict[str, Any], institutional_activity, execute_with_retry) -> Dict[str, Any]:
    """Execute institutional activity agent for insider trading, institutional ownership, and congressional data"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] institutional_activity_node cancelled before execution")
        raise asyncio.CancelledError("institutional_activity_node cancelled by user")

    # Code Interpreter guard is now handled in langgraph_utils.py by removing the tool

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Load every attached ownership report or briefing before comparing flows."
    )
    if file_context:
        query += file_context

    query = await maybe_inject_on_switch(
        state,
        query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    query = _inject_portfolio_context(query, state, "INSTITUTIONAL_ACTIVITY")

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)
        logger.info(f"[DEBUG] Created SQLiteSession for institutional_activity with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "institutional_activity")

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    institutional_activity,
                    query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="InstitutionalActivity",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[institutional_activity_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[institutional_activity_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                institutional_activity,
                query,
                session,
                max_turns=40,
                agent_name="InstitutionalActivity",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "institutional_activity")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[INSTITUTIONAL-ACTIVITY] Extracted {len(charts_from_tool)} charts from tool output")

        state["last_agent_response"] = response
        logger.info(f"[MULTI-AGENT] InstitutionalActivity agent completed")

        msg_inst: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "institutional_activity",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "institutional_activity", msg_inst)

        if state.get("charts"):
            msg_inst["charts"] = state["charts"]

        state["messages"].append(msg_inst)

        state["next_agent"] = None
        state["last_provider"] = provider

    except Exception as e:
        logger.error(f"[MULTI-AGENT] InstitutionalActivity agent error: {str(e)}")
        _record_error(state, "institutional_activity", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error analyzing institutional trading data. Let me try a different approach."
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "institutional_activity",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def prediction_markets_analyst_node(state: Dict[str, Any], prediction_markets_analyst, execute_with_retry) -> Dict[str, Any]:
    """Execute prediction markets analyst for prediction market analysis"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] prediction_markets_analyst_node cancelled before execution")
        raise asyncio.CancelledError("prediction_markets_analyst_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    logger.info(f"Prediction Markets Analyst processing: {query[:100]}...")

    # Set context with tokens for proper cleanup
    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    # Check if files are attached and add context
    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached: {len(file_ids)} files with IDs: {file_ids}")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Load each attached market brief before comparing prediction markets."
    )
    enhanced_query = query + file_context if file_context else query

    enhanced_query = await maybe_inject_on_switch(
        state,
        enhanced_query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    enhanced_query = _inject_portfolio_context(enhanced_query, state, "PREDICTION_MARKETS")

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Use SQLite session for persistence with provider-scoped IDs
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for prediction_markets_analyst with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "prediction_markets_analyst")

        result = None
        # Fetch streaming token sink from context (if streaming is enabled)
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass

                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    prediction_markets_analyst,
                    enhanced_query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="Prediction Markets Analyst",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[prediction_markets_analyst_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[prediction_markets_analyst_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            # Execute the prediction markets analyst
            result = await execute_with_retry(
                prediction_markets_analyst,
                enhanced_query,
                session,
                max_turns=40,
                agent_name="Prediction Markets Analyst",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "prediction_markets_analyst")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[PREDICTION-MARKETS-ANALYST] Extracted {len(charts_from_tool)} charts from tool output")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None
        msg_payload: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "prediction_markets_analyst",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "prediction_markets_analyst", msg_payload)

        if state.get("charts"):
            msg_payload["charts"] = state["charts"]

        state["messages"].append(msg_payload)
        state["last_provider"] = provider

        if result and hasattr(result, 'final_output') and result.final_output:
            state["next"] = "END"
            logger.info("Prediction markets analyst completed with results - signaling END")

        logger.info("Prediction markets analyst completed analysis")

    except Exception as e:
        logger.error(f"Prediction markets analyst node error: {e}")
        _record_error(state, "prediction_markets_analyst", e)
        state.pop("code_execution_data", None)
        state["last_agent_response"] = f"I encountered an error analyzing prediction markets: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "prediction_markets_analyst",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state


async def private_markets_node(state: Dict[str, Any], private_markets, execute_with_retry) -> Dict[str, Any]:
    """Execute private markets agent for PE/M&A research and analysis"""

    # ✅ CHECK CANCELLATION: Stop execution if cancelled
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] private_markets_node cancelled before execution")
        raise asyncio.CancelledError("private_markets_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]

    logger.info(f"Private Markets processing: {query[:100]}...")

    # Inject cross-provider transcript only when a provider switch occurs
    query = await maybe_inject_on_switch(
        state,
        query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    query = _inject_portfolio_context(query, state, "PRIVATE_MARKETS")

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages to prevent context overflow
    state = trim_messages_before_agent(state)

    try:
        # Use SQLite session for persistence with provider-scoped IDs
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        logger.info(f"[DEBUG] Created SQLiteSession for private_markets with sdk_session_id: {sdk_session_id} (provider: {provider})")

        await trim_sqlite_session_history(session, selected_model, "private_markets")

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            logger.warning(f"[STREAMING DEBUG] stream_sink received: True, type: {type(stream_sink)}")
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    private_markets,
                    query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="Private Markets",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[private_markets_node] Streaming path failed, falling back to non-streaming: {e}")
                logger.warning(f"[private_markets_node] Streaming traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                private_markets,
                query,
                session,
                max_turns=40,  # Complex PE/M&A research may require multiple tool calls
                agent_name="Private Markets",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "private_markets")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[PRIVATE-MARKETS] Extracted {len(charts_from_tool)} charts from tool output")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None  # Clear next_agent for terminal agents
        msg_pm: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "private_markets",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "private_markets", msg_pm)

        if state.get("charts"):
            msg_pm["charts"] = state["charts"]

        state["messages"].append(msg_pm)
        state["last_provider"] = provider

        # Computed completion signal based on actual results
        if result and hasattr(result, 'final_output') and result.final_output:
            state["next"] = "END"  # Signal completion based on successful output
            logger.info("Private markets completed with results - signaling END")

        logger.info("Private markets completed analysis")

    except Exception as e:
        logger.error(f"Private markets node error: {e}")
        _record_error(state, "private_markets", e)
        state["last_agent_response"] = f"I encountered an error analyzing private markets: {str(e)}"
        state["agent_failed"] = True  # Signal permanent failure to prevent retry loops
        state["next_agent"] = None  # Ensure no routing continues
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "private_markets",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider

    return state


async def structuring_analyst_node(state: Dict[str, Any], structuring_analyst, execute_with_retry) -> Dict[str, Any]:
    """Execute structuring analyst agent for derivatives pricing and structured products"""

    # ✅ CHECK CANCELLATION
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info("[CANCEL] structuring_analyst_node cancelled before execution")
        raise asyncio.CancelledError("structuring_analyst_node cancelled by user")

    query = state["current_user_query"]
    session_id = state["session_id"]
    user_id = state.get("user_id")
    org_id = state.get("org_id")

    # Set context
    tok_u = user_context.set(user_id) if user_id else None
    tok_s = session_context.set(session_id)
    
    # Set memory context for memory tools
    set_memory_context(session_id, user_id, org_id)

    # Check if files are attached (term sheets, pricing documents)
    file_ids = state.get("file_ids")
    if file_ids:
        logger.info(f"Files attached for structuring: {len(file_ids)} files")
    file_context = _build_file_context(
        file_ids,
        user_id,
        "Use read_file_content to analyze every attached term sheet or pricing document."
    )
    if file_context:
        query += file_context

    # Cross-provider compaction
    query = await maybe_inject_on_switch(
        state,
        query,
        enabled=app_config.cross_provider_compaction_enabled,
        scan_budget=app_config.cross_provider_compaction_scan_tokens,
        inject_budget=app_config.cross_provider_compaction_inject_tokens,
        summary_model=app_config.cross_provider_compaction_summary_model,
        summary_timeout=app_config.cross_provider_compaction_summary_timeout_sec,
        summary_max_output_tokens=app_config.cross_provider_compaction_summary_max_output_tokens,
    )

    # Inject portfolio context
    query = _inject_portfolio_context(query, state, "STRUCTURING")

    # Inject tool priority if user specified prioritized tools
    query = inject_tool_priority(query, state)

    selected_model = state.get("selected_model")
    provider = get_provider_from_model(selected_model)
    _apply_compaction_summary(state, provider)

    # Trim messages
    state = trim_messages_before_agent(state)

    try:
        sdk_session_id = f"{session_id}::{provider}"
        session = SQLiteSession(sdk_session_id, app_config.openai_sessions_db_path)

        await trim_sqlite_session_history(session, selected_model, "structuring_analyst")

        # Emit status
        await emit_status("Pricing derivatives...", state)

        result = None
        stream_sink = get_token_sink()
        if stream_sink is not None:
            try:
                from core.ai.langgraph_utils import execute_with_stream as _exec_stream

                async def _on_token(t: str):
                    try:
                        await stream_sink.put(t)
                    except Exception:
                        pass
                async def _on_event(evt: Dict[str, Any]):
                    if stream_sink is None:
                        return
                    try:
                        await stream_sink.put({"type": "stream_event", "event": evt})
                    except Exception:
                        pass

                result = await _exec_stream(
                    structuring_analyst,
                    query,
                    session,
                    _on_token,
                    on_event=_on_event,
                    max_turns=40,
                    agent_name="StructuringDesk",
                    selected_model=state.get("selected_model"),
                )
            except Exception as e:
                import traceback
                logger.warning(f"[structuring_analyst_node] Streaming failed: {e}")
                logger.warning(f"[structuring_analyst_node] Traceback:\n{traceback.format_exc()}")

        if result is None:
            result = await execute_with_retry(
                structuring_analyst,
                query,
                session,
                max_turns=40,
                agent_name="StructuringDesk",
                selected_model=state.get("selected_model"),
            )

        response = result.final_output if hasattr(result, 'final_output') else str(result)

        # Extract code execution data using centralized function
        code_exec_data = _extract_code_execution_data(result, "structuring_analyst")
        if code_exec_data:
            state["code_execution_data"] = code_exec_data

        # Extract charts from tool output
        charts_from_tool = []
        if hasattr(result, 'new_items') and result.new_items:
            for item in result.new_items:
                item_type = getattr(item, 'type', None)
                if item_type in ('tool_call_output_item', 'tool_call_output'):
                    item_output = getattr(item, 'output', None)
                    if item_output:
                        try:
                            output_obj = json.loads(item_output) if isinstance(item_output, str) else item_output
                            if isinstance(output_obj, dict):
                                if isinstance(output_obj.get('charts'), list) and output_obj['charts']:
                                    charts_from_tool.extend(output_obj['charts'])
                                elif all(k in output_obj for k in ("id", "plotly")):
                                    charts_from_tool.append(output_obj)
                        except:
                            pass

        if charts_from_tool:
            state["charts"] = charts_from_tool
            logger.info(f"[STRUCTURING-ANALYST] Extracted {len(charts_from_tool)} charts from tool output")

        # Update state
        state["last_agent_response"] = response
        state["next_agent"] = None

        msg: Dict[str, Any] = {
            "role": "assistant",
            "content": response,
            "agent": "structuring_analyst",
            "provider": provider,
            "model": selected_model,
        }
        _attach_code_execution_metadata(state, "structuring_analyst", msg)

        if state.get("charts"):
            msg["charts"] = state["charts"]

        state["messages"].append(msg)
        state["last_provider"] = provider

        logger.info("Structuring analyst completed derivatives pricing")

    except Exception as e:
        logger.error(f"Structuring analyst node error: {e}")
        _record_error(state, "structuring_analyst", e)
        state["last_agent_response"] = f"I encountered an error pricing derivatives: {str(e)}"
        state["agent_failed"] = True
        state["next_agent"] = None
        state["messages"].append({
            "role": "assistant",
            "content": state["last_agent_response"],
            "agent": "structuring_analyst",
            "provider": provider,
            "model": selected_model,
        })
        state["last_provider"] = provider
    finally:
        try:
            if tok_u:
                user_context.reset(tok_u)
        except Exception:
            pass
        try:
            if tok_s:
                session_context.reset(tok_s)
        except Exception:
            pass
        try:
            clear_memory_context()
        except Exception:
            pass

    return state
