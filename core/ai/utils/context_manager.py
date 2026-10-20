"""
Context Manager Utility
Manages conversation context for agents and routing decisions

Memory Notebook integration: Memory notes are injected at the TOP of context
and are NEVER compacted. See docs/memory-notebook-feature-spec.md
"""

from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


async def _load_memory_notes(session_id: Optional[str], user_id: Optional[str]) -> List[Dict]:
    """
    Load memory notes for a session.
    
    Returns empty list if session_id/user_id missing or DB not enabled.
    This is async but we handle it gracefully in sync contexts.
    """
    if not session_id or not user_id:
        return []
    
    try:
        from core.services.memory_service import get_memory_service
        service = get_memory_service()
        result = await service.get_session_notes(user_id=user_id, session_id=session_id)
        if result.get("status") == "success":
            return result.get("notes", [])
    except Exception as e:
        logger.debug(f"Could not load memory notes: {e}")
    
    return []


async def _retrieve_relevant_chunks(
    session_id: Optional[str],
    user_id: Optional[str],
    query: Optional[str],
    top_k: int = 5
) -> List[Dict]:
    """
    Retrieve relevant chunks from indexed memory notes.
    
    This is called at context injection time to get semantically relevant
    chunks from large indexed files/notes.
    
    Args:
        session_id: Chat session UUID
        user_id: User ID for RLS
        query: Query text (typically last user message)
        top_k: Number of chunks to retrieve
        
    Returns:
        List of chunk dicts with content and metadata
    """
    if not session_id or not user_id or not query:
        return []
    
    try:
        from core.services.memory_chunk_service import get_memory_chunk_service
        service = get_memory_chunk_service()
        chunks = await service.retrieve_relevant(
            session_id=session_id,
            user_id=user_id,
            query=query,
            top_k=top_k
        )
        return chunks
    except Exception as e:
        logger.debug(f"Could not retrieve memory chunks: {e}")
    
    return []


def _format_chunks_for_injection(chunks: List[Dict]) -> str:
    """
    Format retrieved chunks for context injection.
    
    Chunks are formatted as a separate section after the main memory notes.
    """
    if not chunks:
        return ""
    
    lines = ["", "=== 🔍 RETRIEVED CONTEXT (from indexed files) ===", ""]
    
    # Group by parent note
    by_note: Dict[str, List[Dict]] = {}
    for chunk in chunks:
        note_id = chunk.get("memory_note_id", "unknown")
        if note_id not in by_note:
            by_note[note_id] = []
        by_note[note_id].append(chunk)
    
    for note_id, note_chunks in by_note.items():
        # Get metadata from first chunk
        first = note_chunks[0]
        ref_meta = first.get("reference_metadata") or {}
        filename = ref_meta.get("filename", "indexed content")
        
        lines.append(f"📎 From \"{filename}\":")
        
        for chunk in sorted(note_chunks, key=lambda c: c.get("chunk_idx", 0)):
            content = chunk.get("content", "")
            score = chunk.get("score", 0)
            # Truncate very long chunks for display
            if len(content) > 1500:
                content = content[:1500] + "..."
            lines.append(f"  [{score:.2f}] {content}")
        
        lines.append("")
    
    lines.append("=" * 50)
    lines.append("")
    
    return "\n".join(lines)


# Unique markers for memory injection - used to strip old injections before adding new
MEMORY_START_MARKER = "<!-- SENTRY_MEMORY_START -->"
MEMORY_END_MARKER = "<!-- SENTRY_MEMORY_END -->"


def _strip_previous_memory_injection(text: str) -> str:
    """
    Remove any previous memory injection from text.
    
    This prevents duplicate memory blocks from accumulating in context.
    """
    if not text or MEMORY_START_MARKER not in text:
        return text
    
    import re
    # Remove everything between (and including) the markers
    pattern = re.escape(MEMORY_START_MARKER) + r".*?" + re.escape(MEMORY_END_MARKER)
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    # Clean up any resulting double newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def _strip_memory_from_messages(messages: List[Dict]) -> List[Dict]:
    """
    Strip memory injection markers from all messages in history.
    
    This ensures we don't accumulate duplicate memory blocks across turns.
    """
    cleaned = []
    for msg in messages:
        if not isinstance(msg, dict):
            cleaned.append(msg)
            continue
        
        content = msg.get("content", "")
        if isinstance(content, str) and MEMORY_START_MARKER in content:
            new_msg = dict(msg)
            new_msg["content"] = _strip_previous_memory_injection(content)
            # Skip if content is now empty
            if new_msg["content"].strip():
                cleaned.append(new_msg)
        else:
            cleaned.append(msg)
    
    return cleaned


def _format_memory_for_injection(notes: List[Dict]) -> str:
    """
    Format memory notes for context injection.
    
    This is placed at the TOP of context and is NEVER compacted.
    Uses unique markers so previous injections can be stripped.
    """
    if not notes:
        return ""
    
    # Group by section
    sections: Dict[str, List[Dict]] = {}
    for note in notes:
        sec = note.get("section", "general")
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(note)
    
    # Build formatted output with markers
    lines = [MEMORY_START_MARKER]
    lines.append("=== 📓 PINNED MEMORY (Always Preserved) ===")
    lines.append("")
    
    section_order = ["entities", "context", "decisions", "preferences", "general"]
    section_labels = {
        "entities": "🏷️ ENTITIES",
        "context": "📋 CONTEXT", 
        "decisions": "✅ DECISIONS",
        "preferences": "⚙️ PREFERENCES",
        "general": "📝 GENERAL"
    }
    
    for sec in section_order:
        if sec not in sections:
            continue
        
        lines.append(f"[{section_labels.get(sec, sec.upper())}]")
        
        for note in sorted(sections[sec], key=lambda n: -n.get("priority", 5)):
            content = note.get("content", "")
            ref_type = note.get("reference_type", "text")
            ref_meta = note.get("reference_metadata") or {}
            
            # Format based on reference type
            if ref_type == "file":
                filename = ref_meta.get("filename", "file")
                lines.append(f"• 📎 File \"{filename}\": {content}")
            elif ref_type == "portfolio":
                name = ref_meta.get("name", "portfolio")
                lines.append(f"• 📊 Portfolio \"{name}\": {content}")
            elif ref_type == "chart":
                title = ref_meta.get("title", "chart")
                lines.append(f"• 📈 Chart \"{title}\": {content}")
            elif ref_type == "message_excerpt":
                lines.append(f"• 💬 \"{content}\"")
            else:
                lines.append(f"• {content}")
        
        lines.append("")
    
    lines.append("=" * 50)
    lines.append(MEMORY_END_MARKER)
    lines.append("")
    
    return "\n".join(lines)


def _safe_token_count(model_encoding: str, text: str) -> int:
    """Approximate token count with fallback to character heuristic.
    Respect CODING_RULES: no heavy deps, keep fast path.
    """
    try:
        # Optional: use tiktoken if present
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding(model_encoding)
        return len(enc.encode(text))
    except Exception:
        # Fallback heuristic ~ 1 token per 4 chars
        return max(1, len(text) // 4)

def _clip_lines(s: str, max_lines: int) -> str:
    lines = [ln for ln in s.splitlines() if ln is not None]
    if len(lines) <= max_lines:
        return s
    head = lines[: max_lines // 2]
    tail = lines[-(max_lines - len(head)) :]
    return "\n".join(head + [f"... ({len(lines)-max_lines} lines omitted) ..."] + tail)


def build_shared_context(
    state: Dict[str, Any], 
    max_tokens: int = 399990,
    memory_notes: Optional[List[Dict]] = None
) -> str:
    """Build a shared conversation context that all agents can use.

    This ensures all agents see the same conversation history and context.
    All agents should use this function instead of building their own transcripts.

    With 399,990 tokens (~80,000 words), this can hold extensive conversation history for GPT-5 models.
    Note: The supervisor explicitly overrides this with max_tokens=50000 for routing decisions.
    
    MEMORY NOTEBOOK: If memory_notes is provided (or pre-loaded in state['_memory_notes']),
    they are injected at the TOP of context and are NEVER compacted.
    
    Args:
        state: The conversation state containing messages and other context
        max_tokens: Maximum tokens to include in context (default 399990)
        memory_notes: Optional pre-loaded memory notes (avoids async call)
        
    Returns:
        Formatted conversation context string
    """
    # Check for pre-loaded memory notes in state or parameter
    notes = memory_notes or state.get("_memory_notes", [])
    memory_block = _format_memory_for_injection(notes) if notes else ""
    
    # Also include retrieved memory chunks if pre-loaded
    memory_chunks = state.get("_memory_chunks", [])
    chunks_block = _format_chunks_for_injection(memory_chunks) if memory_chunks else ""
    
    # Combine memory block and chunks block
    if chunks_block:
        memory_block = memory_block + chunks_block if memory_block else chunks_block
    
    # Strip previous memory injections from message history to prevent duplication
    # This ensures we don't accumulate duplicate memory blocks across turns
    history_raw = state.get("messages", [])
    messages_cleaned = _strip_memory_from_messages(history_raw)
    
    # Load budgets from config
    try:
        from core.config import get_config
        cfg = get_config()
        enabled = getattr(cfg, 'enable_context_packer', True)
        sys_ratio = getattr(cfg, 'context_system_ratio', 0.2)
        pin_ratio = getattr(cfg, 'context_pinned_ratio', 0.1)
        cur_ratio = getattr(cfg, 'context_current_ratio', 0.2)
        rec_ratio = getattr(cfg, 'context_recent_ratio', 0.45)
        scr_ratio = getattr(cfg, 'context_scratch_ratio', 0.05)
        max_hist_msgs = getattr(cfg, 'context_max_history_messages', 50)
        pinned_max_lines = getattr(cfg, 'context_pinned_max_lines', 12)
        summary_max_tokens = getattr(cfg, 'context_summary_max_tokens', 1500)
        # Model encoding guess; use OpenAI cl100k as default
        model_encoding = getattr(cfg, 'sec_tokenizer_encoding', 'cl100k_base')
    except Exception:
        enabled = True
        sys_ratio = 0.2; pin_ratio = 0.1; cur_ratio = 0.2; rec_ratio = 0.45; scr_ratio = 0.05
        max_hist_msgs = 50; pinned_max_lines = 12; summary_max_tokens = 1500
        model_encoding = 'cl100k_base'

    def _estimate_tokens(text: str) -> int:
        return _safe_token_count(model_encoding, text)
    
    # Use cleaned messages (previous memory injections stripped)
    history = messages_cleaned
    pairs: List[Tuple[str, str, str]] = []
    
    # Extract user and assistant messages
    for msg in history:
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
            # Include agent info as third element in tuple
            pairs.append((msg["role"], str(msg.get("content", "")), msg.get("agent", "")))
    
    # Build context within token limit (reverse order to keep recent messages)
    used = 0
    kept: List[Tuple[str, str, str]] = []
    
    for role, content, agent in reversed(pairs):
        t = _estimate_tokens(content)
        if used + t > max_tokens:
            break
        kept.append((role, content, agent))
        used += t
    
    kept.reverse()
    
    lines = []
    
    # Add conversation history
    if kept:
        lines.append("=== Conversation Context (IMPORTANT: Use this to understand what the user is referring to) ===")
        for role, content, agent in kept:
            if role == "user":
                prefix = "User"
            else:
                prefix = f"Assistant[{agent}]" if agent else "Assistant"
            lines.append(f"{prefix}: {content}")
        
        # Add a note about context usage
        lines.append("\n=== CRITICAL: When the user uses pronouns (it, that, this) or references (the chart, the stock), look at the conversation above to understand what they mean. ===")
    
    # Dynamically add any additional state fields
    # These are the common state fields that agents might need to share
    state_fields_to_share = [
        ("portfolio_state", "Portfolio State"),
        ("risk_results", "Previous Risk Results"),
        ("calculation_results", "Calculation Results"),
        ("search_sources", "Search Sources"),
        ("optimization_suggestions", "Optimization Suggestions"),
        ("routing_history", "Routing History")
    ]
    
    # Pinned memory block (always present, clipped)
    def _render_pinned() -> List[str]:
        pinned: List[str] = []
        # Portfolio digest
        pf = state.get('portfolio_state')
        if isinstance(pf, dict) and pf:
            import json
            pinned.append("=== Portfolio Snapshot ===")
            try:
                digest = {
                    'tickers': pf.get('tickers', [])[:15],
                    'weights': pf.get('weights', [])[:15],
                    'value': pf.get('value'),
                }
                pinned.append(_clip_lines(json.dumps(digest, indent=2, default=str), pinned_max_lines))
            except Exception:
                pinned.append(_clip_lines(str(pf), pinned_max_lines))
        # Last answer TL;DR
        if state.get('last_agent_response'):
            pinned.append("\n=== Last Answer (TL;DR) ===")
            pinned.append(_clip_lines(str(state['last_agent_response'])[:2000], pinned_max_lines))
        # Entities (from recent messages)
        if kept:
            import re
            text_cat = "\n".join(
                item[1] for item in kept[-8:]
                if isinstance(item, (list, tuple)) and len(item) >= 2
            )
            tickers = sorted(set(re.findall(r"\b[A-Z]{1,5}\b", text_cat)))[:20]
            if tickers:
                pinned.append("\n=== Entities ===")
                pinned.append("Tickers: " + ", ".join(tickers))
        return pinned

    # Assemble with section budgets if enabled
    if enabled:
        budget_tokens = max(1000, int(max_tokens))
        system_budget = int(sys_ratio * budget_tokens)
        pinned_budget = int(pin_ratio * budget_tokens)
        current_budget = int(cur_ratio * budget_tokens)
        recent_budget = int(rec_ratio * budget_tokens)
        scratch_budget = int(scr_ratio * budget_tokens)

        assembled: List[str] = []
        # Conversation context (recent) within budget
        convo_block = []
        if kept:
            convo_block.append("=== Conversation Context ===")
            # Trim history if enormous before tokenizing
            # Replace the convo_block loop with a tolerant version that handles both 2 and 3 element tuples
            recent_pairs = kept[-max_hist_msgs:]
            for item in recent_pairs:
                if len(item) == 3:
                    role, content, agent = item
                    label = "User" if role == "user" else (f"Assistant[{agent}]" if agent else "Assistant")
                else:
                    role, content = item
                    label = "User" if role == "user" else "Assistant"
                convo_block.append(f"{label}: {content}")
            # Fit to recent_budget
            while _estimate_tokens("\n".join(convo_block)) > recent_budget and len(recent_pairs) > 0:
                # Summarize oldest pair: replace with shorter stub
                recent_pairs = recent_pairs[1:]
                convo_block = ["=== Conversation Context ==="] + [
                    f"{'User' if item[0]=='user' else (f'Assistant[{item[2]}]' if len(item)==3 and item[2] else 'Assistant')}: {item[1]}"
                    for item in recent_pairs
                ]
        # Pinned memory
        pinned_block = _render_pinned()
        while _estimate_tokens("\n".join(pinned_block)) > pinned_budget and pinned_block:
            # Trim last sections if overflow
            pinned_block = pinned_block[:-1]
        # Rolling summary (optional) when convo exceeds budget
        summary_block: List[str] = []
        if kept and _estimate_tokens("\n".join(convo_block)) > recent_budget:
            summary_block = ["\n=== Conversation Summary ===", "(summary omitted in this build)"]
            # Note: full semantic summarization would require model/tool; keep placeholder per coding rules
            # Reserve summary_max_tokens within pinned budget when implemented

        # Assemble - MEMORY NOTEBOOK GOES FIRST (never compacted)
        if memory_block:
            assembled.append(memory_block)
        assembled.extend(pinned_block)
        assembled.extend(summary_block)
        assembled.extend(convo_block)

        # Add selected state fields compactly (if room)
        for field_key, field_label in state_fields_to_share:
            if field_key in ('routing_history',) and not state.get('debug_mode'):
                continue
            val = state.get(field_key)
            if not val:
                continue
            from json import dumps as _dumps
            block = [f"\n=== {field_label} ==="]
            try:
                block.append(_clip_lines(_dumps(val, indent=2, default=str), pinned_max_lines))
            except Exception:
                block.append(_clip_lines(str(val), pinned_max_lines))
            candidate = "\n".join(assembled + block)
            if _estimate_tokens(candidate) <= budget_tokens - scratch_budget:
                assembled.extend(block)
            else:
                break

        return "\n".join(assembled)
    
    # Return empty string if no content
    if not lines and not memory_block:
        return ""
    
    # Non-enabled path: still prepend memory block if present
    if memory_block:
        return memory_block + "\n".join(lines)
    
    return "\n".join(lines)


async def build_shared_context_with_memory(
    state: Dict[str, Any],
    max_tokens: int = 399990
) -> str:
    """
    Async version that loads memory notes and retrieves relevant chunks.
    
    Use this when you have async context available and want automatic
    memory loading from the database plus semantic chunk retrieval.
    
    Args:
        state: Conversation state (must include session_id and user_id)
        max_tokens: Maximum tokens for context
        
    Returns:
        Formatted context with memory notes at top and relevant chunks
    """
    session_id = state.get("session_id")
    user_id = state.get("user_id")
    
    # Load memory notes (non-chunked notes are injected verbatim)
    memory_notes = await _load_memory_notes(session_id, user_id)
    
    # Filter out chunked notes (they'll be retrieved via semantic search)
    non_chunked_notes = [n for n in memory_notes if not n.get("is_chunked", False)]
    
    # Get last user message as query for chunk retrieval
    messages = state.get("messages", [])
    last_user_query = None
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user_query = msg.get("content", "")
            break
    
    # Retrieve relevant chunks from indexed notes
    relevant_chunks = []
    if last_user_query:
        relevant_chunks = await _retrieve_relevant_chunks(
            session_id=session_id,
            user_id=user_id,
            query=last_user_query,
            top_k=5
        )
    
    # Store in state for potential reuse
    state["_memory_notes"] = non_chunked_notes
    state["_memory_chunks"] = relevant_chunks
    
    # Build base context with non-chunked notes
    base_context = build_shared_context(state, max_tokens, memory_notes=non_chunked_notes)
    
    # Append retrieved chunks if any
    if relevant_chunks:
        chunks_block = _format_chunks_for_injection(relevant_chunks)
        # Insert chunks after memory block but before conversation
        # Find the end of memory block marker
        if MEMORY_END_MARKER in base_context:
            # Insert chunks right after memory block
            parts = base_context.split(MEMORY_END_MARKER, 1)
            base_context = parts[0] + MEMORY_END_MARKER + chunks_block + parts[1]
        else:
            # No memory block, prepend chunks
            base_context = chunks_block + base_context
    
    return base_context
