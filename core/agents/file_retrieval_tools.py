"""
File Retrieval Tools for AI Agents (separate from SEC)
- search_file_chunks: vector (and later hybrid) search over files_chunks with RLS
"""

from typing import List, Dict, Any, Optional
import logging

try:
    from agents import function_tool
except ImportError:
    def function_tool(func):
        return func

logger = logging.getLogger(__name__)

# Store reference to the actual async function before potential wrapping
search_file_chunks_async = None


async def _query_embeddings(text: str) -> List[float]:
    from core.config import get_config
    cfg = get_config()
    provider = cfg.file_embedding_provider
    model = cfg.file_embedding_model
    dims = cfg.file_embedding_dims
    try:
        if provider == "voyage":
            import voyageai
            client = voyageai.AsyncClient(api_key=cfg.voyage_api_key)
            resp = await client.embed(texts=[text], model=model, input_type="query", output_dimension=dims, output_dtype="float")
            return resp.embeddings[0]
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=cfg.openai_api_key)
            resp = await client.embeddings.create(model=model, input=text)
            return resp.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding query error: {e}")
        raise


async def search_file_chunks(query: str, file_ids: Optional[List[str]] = None, top_k: Optional[int] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Search uploaded file chunks by semantic similarity (separate from SEC).
    Enforces RLS by user context; returns top snippets with minimal metadata.
    """
    from core.config import get_config
    cfg = get_config()
    k = int(top_k or cfg.file_top_k)

    # Get user context with fallback to passed parameter
    try:
        from core.utils.context_utils import user_context
        context_user_id = user_context.get()
        if not context_user_id and user_id:
            context_user_id = user_id  # Use passed parameter as fallback
            logger.info(f"Using fallback user_id for file retrieval: {user_id}")
        if not context_user_id:
            logger.error("No user context for file retrieval")
            return {"status": "error", "message": "Authentication required for file access"}
        user_id = context_user_id
    except Exception as e:
        logger.error(f"Error getting user context: {e}")
        if not user_id:
            return {"status": "error", "message": "Authentication required for file access"}
        # Use the passed user_id if context failed

    # Build embedding
    vec = await _query_embeddings(query)
    vec_text = f"[{','.join(map(str, vec))}]"

    # Query DB under RLS
    logger.info(f"Searching file chunks for user {user_id} with query: {query[:50]}...")
    try:
        from core.database.postgres_client import get_postgres_rls_client
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            if file_ids:
                rows = await conn.fetch(
                    f"""
                    SELECT id, file_id, chunk_id, content,
                           1 - (embedding <=> $1::{cfg.file_vector_cast}) as score
                    FROM files_chunks
                    WHERE file_id = ANY($2::uuid[])
                    ORDER BY embedding <=> $1::{cfg.file_vector_cast}
                    LIMIT $3
                    """,
                    vec_text,
                    file_ids,
                    k,
                )
            else:
                rows = await conn.fetch(
                    f"""
                    SELECT id, file_id, chunk_id, content,
                           1 - (embedding <=> $1::{cfg.file_vector_cast}) as score
                    FROM files_chunks
                    ORDER BY embedding <=> $1::{cfg.file_vector_cast}
                    LIMIT $2
                    """,
                    vec_text,
                    k,
                )
    except Exception as e:
        logger.error(f"files_chunks search failed: {e}")
        return {"status": "error", "message": "Search failed"}

    results = []
    for r in rows:
        preview = (r["content"] or "")
        if len(preview) > 400:
            preview = preview[:400] + "..."
        results.append({
            "id": str(r["id"]),
            "file_id": str(r["file_id"]),
            "chunk_id": r["chunk_id"],
            "snippet": preview,
            "score": float(r["score"] or 0.0),
        })
    logger.info(f"Found {len(results)} matching chunks for user {user_id}")
    return {"status": "success", "results": results}


# Store reference to the actual async function
search_file_chunks_async = search_file_chunks

# Create a tool-wrapped version for agent use
search_file_chunks_tool = function_tool(search_file_chunks)
