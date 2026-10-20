"""
Memory Notebook Tools for Agents

These tools allow agents to save important information to the user's
memory notebook and recall what's been pinned.

See docs/memory-notebook-feature-spec.md for full specification.
"""

from typing import Optional, Dict, Any, List
from agents import function_tool
import logging
import contextvars

logger = logging.getLogger(__name__)

# Context variable for passing session info to tools - DEFINED EARLY to avoid circular import
_memory_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    '_memory_context', default=None
)


@function_tool
async def save_to_memory(
    content: str,
    section: str = "general",
    priority: int = 5,
) -> str:
    """
    Save important information to the user's memory notebook.
    
    Use this when the user asks to "remember", "save", "pin", or "note" something,
    or when you identify critical information that should persist across the conversation.
    
    Args:
        content: The information to save (be concise but complete)
        section: Category - one of: entities, decisions, preferences, context, general
        priority: 1-10, higher = more important (default 5)
    
    Returns:
        Status message
    """
    # Get context from runtime (injected by orchestrator)
    ctx = _memory_context.get(None)
    if not ctx:
        return "Error: Memory context not available - cannot save"
    
    session_id = ctx.get("session_id")
    user_id = ctx.get("user_id")
    org_id = ctx.get("org_id")
    
    if not session_id or not user_id:
        return "Error: Session or user context not available"
    
    # Validate section
    valid_sections = ["entities", "decisions", "preferences", "context", "general"]
    if section not in valid_sections:
        section = "general"
    
    # Validate priority
    priority = max(1, min(10, priority))
    
    try:
        from core.services.memory_service import get_memory_service
        
        service = get_memory_service()
        
        # Directly await the async service method
        result = await service.create_note(
            user_id=user_id,
            session_id=session_id,
            content=content,
            section=section,
            priority=priority,
            source="ai",
            org_id=org_id
        )
        
        if result.get("status") == "success":
            return f"Saved to memory [{section}]: {content[:50]}..."
        else:
            return f"Error: {result.get('message', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Failed to save to memory: {e}")
        return f"Error: {str(e)}"


@function_tool
async def recall_memory(section: Optional[str] = None) -> str:
    """
    Recall what's been pinned to the user's memory notebook.
    
    Use this to check what important information has been saved,
    especially when you need to reference prior decisions or context.
    
    Args:
        section: Optional filter - entities, decisions, preferences, context, general.
                 If not provided, returns all sections.
    
    Returns:
        Summary of saved notes
    
    Note: Memory is also automatically injected into your context,
    so you may not need to call this explicitly.
    """
    ctx = _memory_context.get(None)
    if not ctx:
        return "Error: Memory context not available"
    
    session_id = ctx.get("session_id")
    user_id = ctx.get("user_id")
    
    if not session_id or not user_id:
        return "Error: Session or user context not available"
    
    try:
        from core.services.memory_service import get_memory_service
        
        service = get_memory_service()
        
        # Directly await the async service method
        result = await service.get_session_notes(
            user_id=user_id,
            session_id=session_id,
            section=section
        )
        
        if result.get("status") == "success":
            notes = result.get("notes", [])
            
            if not notes:
                return "No notes saved in memory yet."
            
            # Format notes for display
            lines = [f"Memory Notebook ({len(notes)} notes):"]
            for note in notes:
                sec = note.get("section", "general")
                note_content = note.get("content", "")
                lines.append(f"  [{sec}] {note_content}")
            
            return "\n".join(lines)
        else:
            return f"Error: {result.get('message', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Failed to recall memory: {e}")
        return f"Error: {str(e)}"


def set_memory_context(session_id: str, user_id: str, org_id: Optional[str] = None):
    """Set the memory context for tool execution."""
    _memory_context.set({
        "session_id": session_id,
        "user_id": user_id,
        "org_id": org_id
    })


def clear_memory_context():
    """Clear the memory context after tool execution."""
    _memory_context.set(None)


# Export tools as a list for easy import
MEMORY_TOOLS = [save_to_memory, recall_memory]
