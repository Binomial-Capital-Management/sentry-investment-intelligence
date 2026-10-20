"""
Memory Notebook Service Layer

Handles all memory note database operations with proper RLS.
See docs/memory-notebook-feature-spec.md for full specification.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

# Context windows per provider, matched by substring on the selected model ID.
# Each entry: (provider, provider markers, default limit, per-model overrides).
# Order matters: the final entry is a catch-all ("" matches every model ID).
_MODEL_CONTEXT_LIMITS: tuple[tuple[str, tuple[str, ...], int, tuple[tuple[str, int], ...]], ...] = (
    ("anthropic", ("anthropic", "claude"), 1_000_000, (("haiku", 200_000),)),
    ("google", ("gemini",), 1_000_000, ()),
    ("deepseek", ("deepseek",), 75_000, ()),
    ("bedrock", ("bedrock", "llama4"), 3_200_000, ()),
    ("xai", ("xai", "grok"), 1_000_000, (("grok-4.7", 500_000), ("grok-4.6", 500_000), ("grok-4.5", 500_000))),
    ("moonshot", ("moonshot", "kimi"), 262_144, (("kimi-k3", 1_048_576),)),
    ("qwen", ("dashscope", "qwen"), 1_000_000, ()),
    ("zai", ("/zai/", "glm-"), 200_000, ()),
    ("openai", ("",), 300_000, (("gpt-6", 1_050_000),)),
)


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _parse_uuid_or_none(value: str) -> Optional[UUID]:
    """Parse string to UUID or return None for legacy IDs."""
    try:
        return UUID(value)
    except (ValueError, TypeError):
        return None


class MemoryService:
    """Service layer for memory notebook operations with RLS enforcement."""
    
    def __init__(self):
        """Initialize service. DB client obtained per-request for proper RLS."""
        pass
    
    async def get_session_notes(
        self, 
        user_id: str, 
        session_id: str,
        section: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all memory notes for a session.
        
        Args:
            user_id: User ID for RLS context
            session_id: Chat session UUID
            section: Optional filter by section
            
        Returns:
            Dict with notes list and metadata
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        from core.utils.dto_utils import record_to_dict
        
        config = get_config()
        
        if not user_id:
            return {"status": "error", "message": "User ID required"}
        
        if not config.enable_postgres:
            return {"status": "success", "notes": [], "total_count": 0, "sections": [], "session_id": session_id}
        
        # Handle legacy non-UUID session IDs gracefully
        session_uuid = _parse_uuid_or_none(session_id)
        if session_uuid is None:
            logger.debug(f"Legacy session_id format, returning empty notes: {session_id}")
            return {"status": "success", "notes": [], "total_count": 0, "sections": [], "session_id": session_id}
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                if section:
                    rows = await conn.fetch("""
                        SELECT * FROM chat_memory_notes 
                        WHERE session_id = $1 AND section = $2
                        ORDER BY priority DESC, created_at DESC
                    """, session_uuid, section)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM chat_memory_notes 
                        WHERE session_id = $1
                        ORDER BY priority DESC, created_at DESC
                    """, session_uuid)
            
            notes = [record_to_dict(row) for row in rows]
            sections = list(set(note.get("section", "general") for note in notes))
            
            return {
                "status": "success",
                "session_id": session_id,
                "notes": notes,
                "total_count": len(notes),
                "sections": sorted(sections)
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory notes for session {session_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def create_note(
        self,
        user_id: str,
        session_id: str,
        content: str,
        section: str = "general",
        priority: int = 5,
        source: str = "user",
        source_message_id: Optional[str] = None,
        reference_type: str = "text",
        reference_id: Optional[str] = None,
        reference_metadata: Optional[Dict] = None,
        org_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new memory note.
        
        Args:
            user_id: User ID for RLS context
            session_id: Chat session UUID
            content: Note content
            section: Category (entities, decisions, preferences, context, general)
            priority: 1-10, higher = more important
            source: Who created (user, ai, tool)
            source_message_id: Optional message UUID that triggered this
            reference_type: Type of reference (text, file, portfolio, etc.)
            reference_id: UUID of referenced object
            reference_metadata: Additional context
            org_id: Optional organization ID
            
        Returns:
            Created note or error
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        from core.utils.dto_utils import record_to_dict
        import json
        
        config = get_config()
        
        if not user_id:
            return {"status": "error", "message": "User ID required"}
        
        if not config.enable_postgres:
            return {"status": "error", "message": "Database not enabled"}
        
        # Reject legacy non-UUID session IDs for writes
        session_uuid = _parse_uuid_or_none(session_id)
        if session_uuid is None:
            return {"status": "error", "message": "Memory notes require a valid session. Please create a new chat."}
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                # Check if session exists for this user (RLS filters)
                existing = await conn.fetchval(
                    "SELECT id FROM chat_sessions WHERE id = $1",
                    session_uuid
                )
                
                if not existing:
                    # Auto-create session with proper RLS context
                    # Uses ON CONFLICT to be idempotent
                    try:
                        await conn.execute(
                            """
                            INSERT INTO chat_sessions (id, user_id, org_id, title)
                            VALUES ($1::uuid, $2, $3, $4)
                            ON CONFLICT (id) DO NOTHING
                            """,
                            session_uuid, user_id, org_id, 'New Chat'
                        )
                        logger.info(f"Auto-created session {session_uuid} for user {user_id}")
                    except Exception as create_err:
                        logger.warning(f"Could not auto-create session {session_uuid}: {create_err}")
                        return {
                            "status": "error", 
                            "message": "Could not initialize chat session. Please try again."
                        }
                
                # Sanitize content: remove NULL bytes which Postgres rejects
                safe_content = content.replace('\x00', '') if content else content
                
                row = await conn.fetchrow("""
                    INSERT INTO chat_memory_notes (
                        session_id, user_id, org_id, content, section, priority,
                        source, source_message_id, reference_type, reference_id, 
                        reference_metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING *
                """,
                    session_uuid,
                    user_id,
                    org_id,
                    safe_content,
                    section,
                    priority,
                    source,
                    UUID(source_message_id) if source_message_id else None,
                    reference_type,
                    UUID(reference_id) if reference_id else None,
                    json.dumps(reference_metadata) if reference_metadata else None
                )
            
            note = record_to_dict(row)
            return {"status": "success", "note": note}
            
        except Exception as e:
            logger.error(f"Failed to create memory note: {e}")
            return {"status": "error", "message": str(e)}
    
    def _build_update_query(
        self,
        content: Optional[str],
        section: Optional[str],
        priority: Optional[int],
        summary: Optional[str],
        reference_metadata: Optional[Dict]
    ) -> tuple[list[str], list]:
        """
        Build dynamic UPDATE query parts.
        
        Returns:
            Tuple of (update clauses, params list)
        """
        import json
        
        updates = []
        params = []
        param_idx = 1
        
        if content is not None:
            updates.append(f"content = ${param_idx}")
            params.append(content)
            param_idx += 1
        
        if section is not None:
            updates.append(f"section = ${param_idx}")
            params.append(section)
            param_idx += 1
        
        if priority is not None:
            updates.append(f"priority = ${param_idx}")
            params.append(priority)
            param_idx += 1
        
        if summary is not None:
            updates.append(f"summary = ${param_idx}")
            params.append(summary)
            param_idx += 1
        
        if reference_metadata is not None:
            updates.append(f"reference_metadata = ${param_idx}")
            params.append(json.dumps(reference_metadata))
            param_idx += 1
        
        return updates, params
    
    async def update_note(
        self,
        user_id: str,
        session_id: str,
        note_id: str,
        content: Optional[str] = None,
        section: Optional[str] = None,
        priority: Optional[int] = None,
        summary: Optional[str] = None,
        reference_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update an existing memory note.
        
        Args:
            user_id: User ID for RLS context
            session_id: Chat session UUID (for validation)
            note_id: Note UUID to update
            content: Optional new content
            section: Optional new section
            priority: Optional new priority
            summary: Optional AI-generated summary
            reference_metadata: Optional new metadata
            
        Returns:
            Updated note or error
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        from core.utils.dto_utils import record_to_dict
        
        config = get_config()
        
        if not user_id:
            return {"status": "error", "message": "User ID required"}
        
        if not config.enable_postgres:
            return {"status": "error", "message": "Database not enabled"}
        
        # Build update query
        updates, params = self._build_update_query(content, section, priority, summary, reference_metadata)
        if not updates:
            return {"status": "error", "message": "No updates provided"}
        
        # Validate UUIDs
        session_uuid = _parse_uuid_or_none(session_id)
        note_uuid = _parse_uuid_or_none(note_id)
        if session_uuid is None or note_uuid is None:
            return {"status": "error", "message": "Invalid session or note ID"}
        
        # Add note_id and session_id to params
        param_idx = len(params) + 1
        params.append(note_uuid)
        params.append(session_uuid)
        
        query = f"""
            UPDATE chat_memory_notes 
            SET {', '.join(updates)}
            WHERE id = ${param_idx} AND session_id = ${param_idx + 1}
            RETURNING *
        """
        
        try:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                row = await conn.fetchrow(query, *params)
            
            if not row:
                return {"status": "error", "message": "Note not found or access denied"}
            
            return {"status": "success", "note": record_to_dict(row)}
        except Exception as e:
            logger.error(f"Failed to update memory note {note_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def delete_note(
        self,
        user_id: str,
        session_id: str,
        note_id: str
    ) -> Dict[str, Any]:
        """
        Delete a memory note.
        
        Args:
            user_id: User ID for RLS context
            session_id: Chat session UUID (for validation)
            note_id: Note UUID to delete
            
        Returns:
            Success or error
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        config = get_config()
        
        if not user_id:
            return {"status": "error", "message": "User ID required"}
        
        if not config.enable_postgres:
            return {"status": "error", "message": "Database not enabled"}
        
        # Validate UUIDs
        session_uuid = _parse_uuid_or_none(session_id)
        note_uuid = _parse_uuid_or_none(note_id)
        if session_uuid is None or note_uuid is None:
            return {"status": "error", "message": "Invalid session or note ID"}
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                result = await conn.execute("""
                    DELETE FROM chat_memory_notes 
                    WHERE id = $1 AND session_id = $2
                """, note_uuid, session_uuid)
            
            # Check if anything was deleted
            deleted_count = int(result.split()[-1]) if result else 0
            
            if deleted_count == 0:
                return {"status": "error", "message": "Note not found or access denied"}
            
            return {"status": "success", "deleted": True}
            
        except Exception as e:
            logger.error(f"Failed to delete memory note {note_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def clear_session_memory(
        self,
        user_id: str,
        session_id: str,
        section: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Clear all memory notes for a session (optionally by section).
        
        Args:
            user_id: User ID for RLS context
            session_id: Chat session UUID
            section: Optional - only clear this section
            
        Returns:
            Count of deleted notes
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        config = get_config()
        
        if not user_id:
            return {"status": "error", "message": "User ID required"}
        
        if not config.enable_postgres:
            return {"status": "error", "message": "Database not enabled"}
        
        # Validate UUID
        session_uuid = _parse_uuid_or_none(session_id)
        if session_uuid is None:
            # For legacy IDs, nothing to clear
            return {"status": "success", "deleted_count": 0, "session_id": session_id, "section": section}
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                if section:
                    result = await conn.execute("""
                        DELETE FROM chat_memory_notes 
                        WHERE session_id = $1 AND section = $2
                    """, session_uuid, section)
                else:
                    result = await conn.execute("""
                        DELETE FROM chat_memory_notes 
                        WHERE session_id = $1
                    """, session_uuid)
            
            deleted_count = int(result.split()[-1]) if result else 0
            
            return {
                "status": "success",
                "deleted_count": deleted_count,
                "session_id": session_id,
                "section": section
            }
            
        except Exception as e:
            logger.error(f"Failed to clear memory for session {session_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    # =========================================================================
    # Token Stats Methods
    # =========================================================================
    
    def get_memory_token_count(self, notes: List[Dict]) -> int:
        """
        Count tokens used by memory notes.
        
        Args:
            notes: List of memory note dicts
            
        Returns:
            Token count
        """
        if not notes:
            return 0
        
        formatted = self.format_memory_for_injection(notes)
        return self._safe_token_count(formatted)
    
    def _safe_token_count(self, text: str) -> int:
        """Approximate token count with fallback."""
        if not text:
            return 0
        try:
            import tiktoken
            from core.config import get_config
            cfg = get_config()
            encoding_name = getattr(cfg, 'sec_tokenizer_encoding', 'cl100k_base')
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text) // 4)
    
    def format_memory_for_injection(self, notes: List[Dict]) -> str:
        """
        Format memory notes for context injection.
        
        Delegates to the canonical implementation in context_manager to ensure
        consistent markers for deduplication.
        
        Args:
            notes: List of memory note dicts
            
        Returns:
            Formatted string ready for context injection
        """
        from core.ai.utils.context_manager import _format_memory_for_injection
        return _format_memory_for_injection(notes)
    
    def _get_model_limits(self, selected_model: Optional[str]) -> tuple[str, int]:
        """
        Determine provider and context limit for model.
        
        Args:
            selected_model: Model identifier
            
        Returns:
            Tuple of (provider, context_limit)
        """
        model_lower = (selected_model or "").lower()

        for provider, markers, default_limit, overrides in _MODEL_CONTEXT_LIMITS:
            if any(marker in model_lower for marker in markers):
                for model_marker, limit in overrides:
                    if model_marker in model_lower:
                        return provider, limit
                return provider, default_limit

        raise AssertionError("_MODEL_CONTEXT_LIMITS must end with a catch-all entry")
    
    def _calculate_pressure_level(self, usage_percent: float) -> str:
        """Determine context pressure level."""
        if usage_percent < 50:
            return "low"
        elif usage_percent < 75:
            return "medium"
        elif usage_percent < 90:
            return "high"
        return "critical"
    
    async def get_context_token_stats(
        self,
        user_id: str,
        session_id: str,
        selected_model: Optional[str] = None,
        state: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Calculate full token breakdown for context window.
        
        Args:
            user_id: User ID
            session_id: Session UUID
            selected_model: Current model identifier
            state: Conversation state dict
            
        Returns:
            ContextTokenStats as dict
        """
        state = state or {}
        
        # Get provider and limit
        provider, context_limit = self._get_model_limits(selected_model)
        
        # Get memory token count
        result = await self.get_session_notes(user_id, session_id)
        notes = result.get("notes", []) if result.get("status") == "success" else []
        memory_tokens = self.get_memory_token_count(notes)
        
        # Message history tokens
        messages = state.get("messages", [])
        history_tokens = sum(self._safe_token_count(str(m.get("content", ""))) for m in messages)
        
        # Compaction summary tokens
        summary = state.get("compaction_summary", "")
        summary_tokens = self._safe_token_count(summary) if summary else 0
        
        # Calculate totals
        system_tokens = 3000
        total_used = memory_tokens + summary_tokens + history_tokens + system_tokens
        remaining = max(0, context_limit - total_used)
        usage_percent = (total_used / context_limit) * 100
        
        return {
            "provider": provider,
            "model": selected_model or "default",
            "context_limit": context_limit,
            "memory_notebook_tokens": memory_tokens,
            "compaction_summary_tokens": summary_tokens,
            "message_history_tokens": history_tokens,
            "system_prompt_tokens": system_tokens,
            "total_used": total_used,
            "remaining": remaining,
            "usage_percent": round(usage_percent, 1),
            "pressure_level": self._calculate_pressure_level(usage_percent)
        }


# Singleton instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get or create the memory service singleton."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
