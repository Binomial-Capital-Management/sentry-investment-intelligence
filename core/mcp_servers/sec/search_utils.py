"""
Search utilities for in-memory semantic search
Used by session cache for fast follow-up queries
"""

import numpy as np
import logging
from typing import List, Dict, Any
from core.config import get_config

logger = logging.getLogger(__name__)
config = get_config()


async def search_in_memory(query: str, chunks: List[Dict[str, Any]], 
                          embeddings: List[List[float]], top_k: int = 10) -> List[Dict]:
    """
    Perform semantic search on in-memory chunks and embeddings.
    
    Args:
        query: Search query text
        chunks: List of chunk dictionaries with text and metadata
        embeddings: List of embedding vectors corresponding to chunks
        top_k: Number of top results to return
        
    Returns:
        List of top matching chunks with scores
    """
    try:
        # Generate query embedding
        from core.mcp_servers.sec.embedding_service import EmbeddingService
        embedding_service = EmbeddingService(config)
        
        # Generate single embedding for query
        query_embedding = await embedding_service.generate_embedding(query)
        
        # Convert to numpy arrays for efficient computation
        query_vec = np.array(query_embedding)
        chunk_vecs = np.array(embeddings)
        
        # Compute cosine similarities
        # Normalize vectors
        query_norm = query_vec / np.linalg.norm(query_vec)
        chunk_norms = chunk_vecs / np.linalg.norm(chunk_vecs, axis=1, keepdims=True)
        
        # Compute dot product (cosine similarity for normalized vectors)
        similarities = np.dot(chunk_norms, query_norm)
        
        # Get top candidates (3x for reranking)
        candidate_count = min(top_k * 3, len(chunks))
        top_indices = np.argsort(similarities)[::-1][:candidate_count]
        
        # Build results - trust semantic similarity, minimal reranking
        results = []
        query_lower = query.lower()
        
        for idx in top_indices:
            base_score = float(similarities[idx])
            if base_score < config.sec_min_score:
                continue  # Skip low-scoring results
                
            chunk = chunks[idx].copy()
            rerank_score = base_score
            metadata = chunk.get('metadata', {})
            section = chunk.get('section', '').upper()
            text_lower = chunk.get('text', '').lower()[:500]
            
            # Penalty for header-heavy chunks (navigation content)
            if metadata.get('header_penalty', False):
                rerank_score *= 0.75
            
            # Penalty for very short chunks (likely headers or fragments)
            if len(chunk.get('text', '')) < 150:
                rerank_score *= 0.70
            
            # Small boost if query terms appear in section name (direct match)
            query_terms = query_lower.split()
            section_lower = section.lower()
            if any(term in section_lower for term in query_terms):
                rerank_score *= 1.10  # 10% boost for section name match
            
            chunk['similarity_score'] = base_score
            chunk['rerank_score'] = rerank_score
            chunk['match_type'] = 'semantic'
            chunk['section'] = section
            results.append((rerank_score, chunk))
        
        # Sort by reranked score and take top-k
        results.sort(key=lambda x: x[0], reverse=True)
        
        # Log top results for debugging
        logger.info(f"[SEC SEARCH] Query: '{query[:50]}...' | Candidates: {len(results)}")
        for i, (score, chunk) in enumerate(results[:5]):
            section = chunk.get('section', 'UNKNOWN')
            text_preview = chunk.get('text', '')[:80].replace('\n', ' ')
            logger.info(f"[SEC SEARCH] #{i+1}: section={section}, score={score:.3f}, text='{text_preview}...'")
        
        # Truncate text in results to avoid overwhelming LLM context
        final_results = []
        for _, chunk in results[:top_k]:
            result = chunk.copy()
            # Keep first 800 chars of text (enough for context, not too much for LLM)
            if 'text' in result and len(result['text']) > 800:
                result['text'] = result['text'][:800] + '...'
            final_results.append(result)
        
        logger.info(f"[SEC SEARCH] Returning {len(final_results)} results (text truncated to 800 chars)")
        return final_results
        
    except Exception as e:
        logger.error(f"Error in in-memory search: {e}")
        # Fallback to simple text matching
        return simple_text_search(query, chunks, top_k)


def simple_text_search(query: str, chunks: List[Dict[str, Any]], top_k: int = 10) -> List[Dict]:
    """
    Simple text-based search fallback.
    
    Args:
        query: Search query text
        chunks: List of chunk dictionaries
        top_k: Number of results to return
        
    Returns:
        List of matching chunks
    """
    query_lower = query.lower()
    scored_chunks = []
    
    for chunk in chunks:
        text = chunk.get('text', '').lower()
        # Simple scoring based on query term frequency
        score = sum(1 for word in query_lower.split() if word in text)
        if score > 0:
            result = chunk.copy()
            result['similarity_score'] = score / len(query_lower.split())
            result['match_type'] = 'keyword'
            scored_chunks.append(result)
    
    # Sort by score
    scored_chunks.sort(key=lambda x: x['similarity_score'], reverse=True)
    
    return scored_chunks[:top_k]