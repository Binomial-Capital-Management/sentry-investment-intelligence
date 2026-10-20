"""
SEC Vector Search Module
Hybrid search implementation for SEC filing embeddings
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import voyageai
from core.config import get_config
from core.database import get_postgres_client

logger = logging.getLogger(__name__)
config = get_config()


class SECVectorSearch:
    """Hybrid search for SEC filing embeddings"""
    
    def __init__(self, model: str = None, dims: int = None):
        """
        Initialize search with embedding model and dimensions
        
        Args:
            model: Embedding model name
            dims: Embedding dimensions (must match database)
        """
        self.embedding_provider = getattr(config, 'sec_embedding_provider', 'openai')
        self.embedding_model = model or config.sec_embedding_model
        self.embedding_dims = dims or config.sec_embedding_dims
        
        # Initialize appropriate embedding client
        if self.embedding_provider == 'voyage':
            self.voyage_client = voyageai.AsyncClient(api_key=config.voyage_api_key)
            self.openai_client = None
        else:
            self.openai_client = AsyncOpenAI(api_key=config.openai_api_key)
            self.voyage_client = None
        
        self.pg_client = None
        
    async def hybrid_search(self, query: str, top_k: int = 30, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Hybrid search using chunk_preview for keywords
        Score = 0.6 * cosine + 0.4 * keyword (trigram similarity)
        
        Args:
            query: Search query string
            top_k: Number of results to return
            user_id: User ID for RLS context (optional, SELECT policy allows all reads)
            
        Returns:
            List of search results with metadata
        """
        try:
            # Ensure database client is initialized
            if not self.pg_client:
                self.pg_client = await get_postgres_client()
            
            if not self.pg_client or not self.pg_client.pool:
                logger.warning("PostgreSQL client not available for SEC vector search")
                return []
            
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            # Run searches with separate connections to avoid concurrency issues
            # Pass user_id for RLS context (though SELECT policy allows all reads)
            async def run_semantic():
                async with self.pg_client.acquire_with_user_context(user_id) as conn:
                    return await self._semantic_search(conn, query_embedding, top_k * 2)
            
            async def run_keyword():
                async with self.pg_client.acquire_with_user_context(user_id) as conn:
                    return await self._keyword_search(conn, query, top_k * 2)
            
            # Execute searches in parallel with separate connections
            semantic_results, keyword_results = await asyncio.gather(
                run_semantic(),
                run_keyword()
            )
            
            # Combine and rerank results
            combined = self._combine_results(semantic_results, keyword_results)
            
            # Filter low scores and return top k
            # Use config value for minimum score (GPT-5 P1 fix)
            MIN_SCORE = config.sec_min_score
            results = [r for r in combined if r['final_score'] >= MIN_SCORE][:top_k]
            
            logger.info(f"Hybrid search returned {len(results)} results for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    async def _semantic_search(self, conn, query_embedding: List[float], limit: int) -> List[Dict]:
        """
        Semantic search using vector similarity
        
        Args:
            conn: Database connection
            query_embedding: Query vector
            limit: Max results
            
        Returns:
            List of semantic search results
        """
        try:
            # Convert embedding to text literal for safer binding (GPT-5 P0 fix)
            query_vec = f"[{','.join(map(str, query_embedding))}]"
            
            # Use dynamic cast type from config
            cast_type = config.sec_vector_cast
            
            # Determine which column to use based on provider (dual-column support)
            use_v2 = self.embedding_provider == 'voyage'
            embedding_col = 'embedding_v2' if use_v2 else 'embedding'
            
            # Cast text to PostgreSQL vector type with explicit ::vector cast
            results = await conn.fetch(f"""
                SELECT 
                    id,
                    ticker,
                    filing_type,
                    filing_date,
                    accession_number,
                    filing_url,
                    section_name,
                    chunk_index,
                    chunk_preview,
                    1 - ({embedding_col} <=> $1::{cast_type}) as cosine_similarity
                FROM sec_filing_embeddings
                WHERE {embedding_col} IS NOT NULL
                ORDER BY {embedding_col} <=> $1::{cast_type}
                LIMIT $2
            """, query_vec, limit)
            
            return [dict(r) for r in results]
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def _keyword_search(self, conn, query: str, limit: int) -> List[Dict]:
        """
        Keyword search using trigram similarity on chunk_preview
        
        Args:
            conn: Database connection
            query: Search query
            limit: Max results
            
        Returns:
            List of keyword search results
        """
        try:
            # Use trigram similarity for keyword matching
            results = await conn.fetch("""
                SELECT 
                    id,
                    ticker,
                    filing_type,
                    filing_date,
                    accession_number,
                    filing_url,
                    section_name,
                    chunk_index,
                    chunk_preview,
                    similarity(chunk_preview, $1) as keyword_score
                FROM sec_filing_embeddings
                WHERE chunk_preview % $1  -- Trigram similarity operator
                ORDER BY similarity(chunk_preview, $1) DESC
                LIMIT $2
            """, query, limit)
            
            return [dict(r) for r in results]
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    def _combine_results(self, semantic_results: List[Dict], keyword_results: List[Dict]) -> List[Dict]:
        """
        Combine semantic and keyword results with weighted scoring
        
        Args:
            semantic_results: Results from vector search
            keyword_results: Results from keyword search
            
        Returns:
            Combined and reranked results
        """
        combined = {}
        
        # Add semantic results (60% weight)
        for result in semantic_results:
            result_id = str(result['id'])
            combined[result_id] = {
                **result,
                'final_score': float(result.get('cosine_similarity', 0)) * config.sec_semantic_weight,
                'has_semantic': True,
                'has_keyword': False
            }
        
        # Add/merge keyword results (40% weight)
        for result in keyword_results:
            result_id = str(result['id'])
            if result_id in combined:
                # Result found by both methods - add keyword score
                keyword_score = result.get('keyword_score')
                if keyword_score is not None:
                    combined[result_id]['final_score'] += float(keyword_score) * config.sec_keyword_weight
                combined[result_id]['has_keyword'] = True
            else:
                # Result found only by keyword search
                keyword_score = result.get('keyword_score', 0)
                if keyword_score is None:
                    keyword_score = 0
                combined[result_id] = {
                    **result,
                    'final_score': float(keyword_score) * config.sec_keyword_weight,
                    'has_semantic': False,
                    'has_keyword': True
                }
        
        # Sort by final score
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x['final_score'],
            reverse=True
        )
        
        # Clean up results for return
        for result in sorted_results:
            # Remove database-specific fields
            result.pop('cosine_similarity', None)
            result.pop('keyword_score', None)
            
            # Truncate preview for response
            if 'chunk_preview' in result and result['chunk_preview']:
                result['chunk_preview'] = result['chunk_preview'][:200] + '...'
        
        return sorted_results
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using configured provider
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            if self.embedding_provider == 'voyage':
                # Use Voyage for query embedding
                result = await self.voyage_client.embed(
                    texts=[text],
                    model=self.embedding_model,
                    input_type="query",  # Mark as query for better search
                    output_dimension=self.embedding_dims,
                    output_dtype="float"
                )
                embedding = result.embeddings[0]
            else:
                # Fallback to OpenAI
                response = await self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=text
                )
                embedding = response.data[0].embedding
            
            # Validate dimensions
            if len(embedding) != self.embedding_dims:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.embedding_dims}, "
                    f"got {len(embedding)} from {self.embedding_model}"
                )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise