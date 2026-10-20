from __future__ import annotations
from typing import List, Dict, Optional
import aiosqlite
from core.config import get_config
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
config = get_config()

def _ensure_parent_dir(file_path: str) -> None:
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Failed to create parent directory for %s: %s", file_path, e)

async def init_conversation_store() -> None:
    _ensure_parent_dir(config.conversation_db_path)
    async with aiosqlite.connect(config.conversation_db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_session_created ON messages(session_id, created_at)")
        await db.commit()

async def load_recent_history(session_id: str, limit: int = 20) -> List[Dict[str, str]]:
    history: List[Dict[str, str]] = []
    try:
        _ensure_parent_dir(config.conversation_db_path)
        async with aiosqlite.connect(config.conversation_db_path) as db:
            async with db.execute(
                """
                SELECT id, role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        turns = []
        for id_, role, content, created_at in rows:
            if role in ("user", "assistant") and content:
                turns.append({
                    "id": id_,
                    "role": role,
                    "content": content,
                    "created_at": created_at,
                })
        turns.reverse()
        approx_budget = int(config.model_context_max_tokens * config.context_budget_ratio)
        approx_used = 0
        kept: List[Dict[str, str]] = []
        for t in turns[-config.min_history_turns:]:
            kept.append(t)
            approx_used += max(1, len(t["content"]) // 4)
        for t in reversed(turns[:-config.min_history_turns]):
            tokens = max(1, len(t["content"]) // 4)
            if approx_used + tokens > approx_budget:
                break
            kept.insert(0, t)
            approx_used += tokens
        history = kept
    except Exception as e:
        logger.warning("Failed to load history: %s", e)
    return history

async def get_last_user_message(session_id: str) -> Optional[str]:
    try:
        _ensure_parent_dir(config.conversation_db_path)
        async with aiosqlite.connect(config.conversation_db_path) as db:
            async with db.execute(
                """
                SELECT content FROM messages 
                WHERE session_id = ? AND role = 'user' 
                ORDER BY datetime(created_at) DESC 
                LIMIT 2
                """,
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                if len(rows) > 1:
                    return rows[1][0]
    except Exception as e:
        logger.warning("Failed to get last user message: %s", e)
    return None

async def insert_message(id_: str, session_id: str, role: str, content: str, created_at: str) -> None:
    try:
        _ensure_parent_dir(config.conversation_db_path)
        async with aiosqlite.connect(config.conversation_db_path) as db:
            await db.execute(
                "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (id_, session_id, role, content, created_at),
            )
            await db.commit()
    except Exception as e:
        logger.warning("Failed to persist message (%s): %s", role, e)
