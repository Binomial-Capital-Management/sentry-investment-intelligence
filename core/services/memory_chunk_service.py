"""
Memory Chunk Service

Standalone service for semantic chunking and vector retrieval of large memory notes.
This service is decoupled from FileMemoryService - chunking is an optional post-processing
step triggered by the API router.

See docs/memory-notebook-feature-spec.md for full specification.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class MemoryChunkService:
    """
    Standalone service for chunking and semantic retrieval of memory notes.
    
    Key responsibilities:
    - Chunk large text content into smaller pieces
    - Embed chunks using configured embedding provider
    - Store chunks in memory_chunks table
    - Retrieve relevant chunks via vector similarity search
    """
    
    def __init__(self):
        """Initialize service."""
        pass
    
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
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text to chunk
            chunk_size: Target tokens per chunk
            overlap: Tokens shared between adjacent chunks
            
        Returns:
            List of dicts with 'text' and 'token_count' keys
        """
        if not text:
            return []
        
        from core.config import get_config
        cfg = get_config()
        encoding_name = getattr(cfg, 'sec_tokenizer_encoding', 'cl100k_base')
        max_chunks = getattr(cfg, 'memory_chunk_max_count', 1000)
        
        try:
            import tiktoken
            enc = tiktoken.get_encoding(encoding_name)
            tokens = enc.encode(text)
        except Exception:
            # Fallback: approximate with chars
            tokens = list(text)
            chunk_size = chunk_size * 4  # Approximate chars per token
            overlap = overlap * 4
            enc = None
        
        chunks = []
        step = max(1, chunk_size - overlap)
        i = 0
        n = len(tokens)
        
        while i < n:
            chunk_tokens = tokens[i:i + chunk_size]
            
            # Decode back to text if using tiktoken
            if enc is not None:
                try:
                    chunk_text = enc.decode(chunk_tokens)
                except Exception:
                    chunk_text = text[i:i + chunk_size]
            else:
                chunk_text = ''.join(chunk_tokens) if isinstance(chunk_tokens[0], str) else text[i:i + chunk_size]
            
            chunks.append({
                'text': chunk_text,
                'token_count': len(chunk_tokens)
            })
            
            i += step
            
            # Safety cap from config
            if len(chunks) >= max_chunks:
                logger.warning(f"Hit chunk limit ({max_chunks}), stopping")
                break
        
        return chunks
    
    async def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed texts using configured provider.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        from core.config import get_config
        
        cfg = get_config()
        provider = cfg.memory_embedding_provider
        model = cfg.memory_embedding_model
        dims = cfg.memory_embedding_dims
        
        try:
            if provider == "voyage":
                import voyageai
                client = voyageai.AsyncClient(api_key=cfg.voyage_api_key)
                resp = await client.embed(
                    texts=texts,
                    model=model,
                    input_type="document",
                    output_dimension=dims,
                    output_dtype="float"
                )
                return resp.embeddings
            else:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=cfg.openai_api_key)
                resp = await client.embeddings.create(model=model, input=texts)
                return [d.embedding for d in resp.data]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise
    
    async def _embed_query(self, query: str) -> List[float]:
        """
        Embed a query string for similarity search.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector
        """
        from core.config import get_config
        
        cfg = get_config()
        provider = cfg.memory_embedding_provider
        model = cfg.memory_embedding_model
        dims = cfg.memory_embedding_dims
        
        try:
            if provider == "voyage":
                import voyageai
                client = voyageai.AsyncClient(api_key=cfg.voyage_api_key)
                resp = await client.embed(
                    texts=[query],
                    model=model,
                    input_type="query",
                    output_dimension=dims,
                    output_dtype="float"
                )
                return resp.embeddings[0]
            else:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=cfg.openai_api_key)
                resp = await client.embeddings.create(model=model, input=query)
                return resp.data[0].embedding
        except Exception as e:
            logger.error(f"Query embedding error: {e}")
            raise
    
    def _should_index(self, content: str) -> tuple[bool, int, Optional[str]]:
        """
        Check if content should be indexed.
        
        Args:
            content: Text content to check
            
        Returns:
            Tuple of (should_index, token_count, skip_reason)
        """
        from core.config import get_config
        cfg = get_config()
        
        if not cfg.enable_postgres:
            return False, 0, "Database not enabled"
        
        if not cfg.memory_chunk_enabled:
            return False, 0, "Memory chunking disabled"
        
        token_count = self._safe_token_count(content)
        if token_count < cfg.memory_chunk_threshold:
            return False, token_count, "Content below threshold"
        
        return True, token_count, None
    
    async def _embed_chunks_safe(self, chunks: List[Dict[str, Any]]) -> Optional[List[List[float]]]:
        """
        Embed chunks with error handling.
        
        Args:
            chunks: List of chunk dicts with 'text' key
            
        Returns:
            List of embeddings or None on error
        """
        try:
            chunk_texts = [c['text'] for c in chunks]
            return await self._embed_texts(chunk_texts)
        except Exception as e:
            logger.error(f"Failed to embed chunks: {e}")
            return None
    
    async def _store_chunks_in_db(
        self,
        memory_note_id: str,
        session_id: str,
        user_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> Dict[str, Any]:
        """
        Store chunks in database.
        
        Args:
            memory_note_id: Parent note UUID
            session_id: Session UUID
            user_id: User ID for RLS
            chunks: List of chunk dicts
            embeddings: List of embedding vectors
            
        Returns:
            Dict with status and counts
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        cfg = get_config()
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                # Delete existing chunks (idempotent)
                await conn.execute(
                    "DELETE FROM memory_chunks WHERE memory_note_id = $1",
                    UUID(memory_note_id)
                )
                
                # Insert new chunks
                total_tokens = 0
                for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    vec_text = f"[{','.join(map(str, embedding))}]"
                    await conn.execute(
                        f"""
                        INSERT INTO memory_chunks (
                            memory_note_id, session_id, user_id, chunk_idx,
                            content, token_count, embedding
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7::{cfg.memory_vector_cast})
                        """,
                        UUID(memory_note_id),
                        UUID(session_id),
                        user_id,
                        idx,
                        chunk['text'],
                        chunk['token_count'],
                        vec_text
                    )
                    total_tokens += chunk['token_count']
                
                # Mark parent note as chunked
                await conn.execute(
                    "UPDATE chat_memory_notes SET is_chunked = TRUE WHERE id = $1",
                    UUID(memory_note_id)
                )
            
            logger.info(f"Stored {len(chunks)} chunks ({total_tokens} tokens) for note {memory_note_id}")
            return {"status": "success", "chunk_count": len(chunks), "total_tokens": total_tokens}
            
        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            return {"status": "error", "message": f"Storage failed: {str(e)}"}
    
    async def index_note(
        self,
        memory_note_id: str,
        content: str,
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Chunk and embed content for a memory note.
        
        Called AFTER note is created. Main entry point for indexing large content.
        
        Args:
            memory_note_id: UUID of the parent memory note
            content: Full text content to chunk and index
            session_id: Chat session UUID
            user_id: User ID for RLS
            
        Returns:
            Dict with status, chunk_count, and total_tokens
        """
        from uuid import UUID as UUIDType
        from core.config import get_config
        cfg = get_config()
        
        # Validate UUIDs
        try:
            UUIDType(memory_note_id)
            UUIDType(session_id)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid UUID format: memory_note_id={memory_note_id}, session_id={session_id}")
            return {"status": "error", "message": f"Invalid UUID format: {e}"}
        
        # 1. Check if should index
        should_index, token_count, skip_reason = self._should_index(content)
        if not should_index:
            if skip_reason == "Content below threshold":
                logger.info(f"Content below threshold ({token_count} < {cfg.memory_chunk_threshold}), skipping")
                return {"status": "skipped", "message": skip_reason, "token_count": token_count}
            return {"status": "skipped" if "disabled" in (skip_reason or "") else "error", "message": skip_reason}
        
        # 2. Chunk the content
        chunks = self._chunk_text(content, cfg.memory_chunk_size, cfg.memory_chunk_overlap)
        if not chunks:
            return {"status": "error", "message": "No chunks generated"}
        
        logger.info(f"Generated {len(chunks)} chunks for memory note {memory_note_id}")
        
        # 3. Embed chunks
        embeddings = await self._embed_chunks_safe(chunks)
        if embeddings is None:
            return {"status": "error", "message": "Embedding failed"}
        
        # 4. Store in database
        return await self._store_chunks_in_db(memory_note_id, session_id, user_id, chunks, embeddings)
    
    async def _embed_query_safe(self, query: str) -> Optional[List[float]]:
        """
        Embed query with error handling.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector or None on error
        """
        try:
            return await self._embed_query(query)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return None
    
    async def _execute_vector_search(
        self,
        session_id: str,
        user_id: str,
        query_vec: List[float],
        k: int
    ) -> List[Dict[str, Any]]:
        """
        Execute vector similarity search in database.
        
        Args:
            session_id: Session UUID
            user_id: User ID for RLS
            query_vec: Embedded query
            k: Number of results
            
        Returns:
            List of chunk dicts with scores
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        cfg = get_config()
        pg = await get_postgres_rls_client()
        vec_text = f"[{','.join(map(str, query_vec))}]"
        
        async with pg.acquire_with_user_context(user_id) as conn:
            rows = await conn.fetch(
                f"""
                SELECT 
                    mc.id, mc.memory_note_id, mc.chunk_idx, mc.content, mc.token_count,
                    1 - (mc.embedding <=> $1::{cfg.memory_vector_cast}) as score,
                    mn.section, mn.reference_type, mn.reference_metadata
                FROM memory_chunks mc
                JOIN chat_memory_notes mn ON mc.memory_note_id = mn.id
                WHERE mc.session_id = $2
                ORDER BY mc.embedding <=> $1::{cfg.memory_vector_cast}
                LIMIT $3
                """,
                vec_text, UUID(session_id), k
            )
        
        return [
            {
                "id": str(row["id"]),
                "memory_note_id": str(row["memory_note_id"]),
                "chunk_idx": row["chunk_idx"],
                "content": row["content"],
                "token_count": row["token_count"],
                "score": float(row["score"] or 0.0),
                "section": row["section"],
                "reference_type": row["reference_type"],
                "reference_metadata": row["reference_metadata"]
            }
            for row in rows
        ]
    
    async def retrieve_relevant(
        self,
        session_id: str,
        user_id: str,
        query: str,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant chunks for a query.
        
        Called by ContextManager at injection time to get relevant chunks.
        
        Args:
            session_id: Chat session UUID
            user_id: User ID for RLS
            query: Query text (typically last user message)
            top_k: Number of chunks to retrieve (default from config)
            
        Returns:
            List of chunk dicts with content, score, and metadata
        """
        from core.config import get_config
        cfg = get_config()
        
        if not cfg.enable_postgres or not cfg.memory_chunk_enabled:
            return []
        
        k = top_k or cfg.memory_chunk_top_k
        
        # Embed the query
        query_vec = await self._embed_query_safe(query)
        if query_vec is None:
            return []
        
        # Execute vector search
        try:
            results = await self._execute_vector_search(session_id, user_id, query_vec, k)
            logger.info(f"Retrieved {len(results)} relevant chunks for session {session_id}")
            return results
        except Exception as e:
            logger.error(f"Chunk retrieval failed: {e}")
            return []
    
    async def delete_chunks_for_note(
        self,
        memory_note_id: str,
        user_id: str
    ) -> int:
        """
        Delete all chunks for a memory note.
        
        Called when a note is deleted or re-indexed.
        
        Args:
            memory_note_id: UUID of the parent memory note
            user_id: User ID for RLS
            
        Returns:
            Number of chunks deleted
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        cfg = get_config()
        
        if not cfg.enable_postgres:
            return 0
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                result = await conn.execute(
                    "DELETE FROM memory_chunks WHERE memory_note_id = $1",
                    UUID(memory_note_id)
                )
                
                # Parse "DELETE N" to get count
                count = int(result.split()[-1]) if result else 0
                
                # Update parent note
                await conn.execute(
                    "UPDATE chat_memory_notes SET is_chunked = FALSE WHERE id = $1",
                    UUID(memory_note_id)
                )
            
            logger.info(f"Deleted {count} chunks for note {memory_note_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            return 0
    
    async def get_chunk_stats(
        self,
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get chunk statistics for a session.
        
        Args:
            session_id: Chat session UUID
            user_id: User ID for RLS
            
        Returns:
            Dict with total_chunks, total_tokens, chunked_notes_count
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        cfg = get_config()
        
        if not cfg.enable_postgres:
            return {
                "total_chunks": 0,
                "total_tokens": 0,
                "chunked_notes_count": 0
            }
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                row = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_chunks,
                        COALESCE(SUM(token_count), 0) as total_tokens,
                        COUNT(DISTINCT memory_note_id) as chunked_notes_count
                    FROM memory_chunks
                    WHERE session_id = $1
                    """,
                    UUID(session_id)
                )
            
            return {
                "total_chunks": int(row["total_chunks"]),
                "total_tokens": int(row["total_tokens"]),
                "chunked_notes_count": int(row["chunked_notes_count"])
            }
            
        except Exception as e:
            logger.error(f"Failed to get chunk stats: {e}")
            return {
                "total_chunks": 0,
                "total_tokens": 0,
                "chunked_notes_count": 0
            }


# Singleton instance
_memory_chunk_service: Optional[MemoryChunkService] = None


def get_memory_chunk_service() -> MemoryChunkService:
    """Get or create the memory chunk service singleton."""
    global _memory_chunk_service
    if _memory_chunk_service is None:
        _memory_chunk_service = MemoryChunkService()
    return _memory_chunk_service

