"""
Database operations for SEC filing storage
Handles PostgreSQL with pgvector and RLS
"""

import json
import logging
from typing import Dict, List, Optional, Any
from core.database import get_postgres_client

logger = logging.getLogger(__name__)


class SECDatabaseOps:
    """Database operations for SEC filing embeddings"""
    
    def __init__(self, config):
        """
        Initialize database operations
        
        Args:
            config: Configuration object with database settings
        """
        self.config = config
        self.pg_client = None
    
    async def ensure_connection(self):
        """Ensure database connection is available"""
        if not self.pg_client:
            self.pg_client = await get_postgres_client()
        return self.pg_client
    
    async def is_indexed(self, accession_number: str) -> bool:
        """Check if a filing is already indexed in the database"""
        await self.ensure_connection()
        
        if not self.pg_client:
            return False
        
        try:
            async with self.pg_client.pool.acquire() as conn:
                # Check appropriate column based on provider
                use_v2 = self.config.sec_embedding_provider == 'voyage'
                embedding_col = 'embedding_v2' if use_v2 else 'embedding'
                
                count = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM sec_filing_embeddings
                    WHERE accession_number = $1 AND {embedding_col} IS NOT NULL
                    LIMIT 1
                """, accession_number)
                
                return count > 0
        except Exception as e:
            logger.error(f"Error checking if filing indexed: {e}")
            return False
    
    async def upsert_chunks(self, chunks: List[Dict], embeddings: List[List[float]], 
                          filing_meta: Dict, user_id: Optional[str] = None) -> int:
        """Insert or update filing chunks with embeddings"""
        await self.ensure_connection()
        
        if not self.pg_client:
            raise RuntimeError("Database connection not available")
        
        # If no user_id, skip DB persistence (run stateless)
        effective_user_id = user_id
        if not effective_user_id:
            logger.info("No user_id provided - skipping DB persistence (stateless mode)")
            return 0  # Return 0 chunks inserted since we're not persisting
        
        inserted_count = 0
        use_v2 = self.config.sec_embedding_provider == 'voyage'
        
        logger.info(f"[SEC DB] Attempting to upsert chunks with user_id={effective_user_id}")
        
        async with self.pg_client.acquire_with_user_context(effective_user_id) as conn:
            # Verify RLS context was set correctly
            try:
                rls_user = await conn.fetchval("SELECT current_setting('app.current_user_id', true)")
                logger.info(f"[SEC DB] RLS context verified: app.current_user_id='{rls_user}', inserting user_id='{effective_user_id}'")
                if rls_user != effective_user_id:
                    logger.error(f"[SEC DB] MISMATCH! RLS user '{rls_user}' != insert user '{effective_user_id}'")
            except Exception as e:
                logger.warning(f"[SEC DB] Could not verify RLS context: {e}")
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Convert embedding to text literal for safer binding
                embedding_vec = f"[{','.join(map(str, embedding))}]"
                metadata_json = json.dumps(chunk.get('metadata', {}))
                
                # Truncate section name to avoid index size limit (PostgreSQL btree max ~2700 bytes)
                section_name = chunk.get('section', 'BODY')
                if len(section_name) > 100:
                    section_name = section_name[:97] + '...'
                
                if use_v2:
                    # Write to v2 column for Voyage
                    await conn.execute(f"""
                        INSERT INTO sec_filing_embeddings (
                            user_id, ticker, filing_type, filing_date, 
                            accession_number, filing_url, section_name, 
                            chunk_index, chunk_preview, embedding_v2, embedding_version, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::vector, $11, $12::jsonb)
                        ON CONFLICT (accession_number, section_name, chunk_index)
                        DO UPDATE SET 
                            embedding_v2 = EXCLUDED.embedding_v2,
                            embedding_version = EXCLUDED.embedding_version,
                            chunk_preview = EXCLUDED.chunk_preview,
                            last_updated = NOW()
                    """, 
                    effective_user_id, filing_meta['ticker'], filing_meta['filing_type'],
                    filing_meta['filing_date'], filing_meta['accession_number'],
                    filing_meta['filing_url'], section_name,  # Use truncated section name
                    i, chunk['text'][:500], embedding_vec, 'v2', metadata_json)
                else:
                    # Legacy path for OpenAI embeddings
                    cast_type = self.config.sec_vector_cast
                    await conn.execute(f"""
                        INSERT INTO sec_filing_embeddings (
                            user_id, ticker, filing_type, filing_date, 
                            accession_number, filing_url, section_name, 
                            chunk_index, chunk_preview, embedding, embedding_version, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::{cast_type}, $11, $12::jsonb)
                        ON CONFLICT (accession_number, section_name, chunk_index)
                        DO UPDATE SET 
                            embedding = EXCLUDED.embedding,
                            embedding_version = EXCLUDED.embedding_version,
                            chunk_preview = EXCLUDED.chunk_preview,
                            last_updated = NOW()
                    """, 
                    effective_user_id, filing_meta['ticker'], filing_meta['filing_type'],
                    filing_meta['filing_date'], filing_meta['accession_number'],
                    filing_meta['filing_url'], section_name,  # Use truncated section name
                    i, chunk['text'][:500], embedding_vec, 'v1', metadata_json)
                
                inserted_count += 1
        
        logger.info(f"Upserted {inserted_count} chunks for {filing_meta['accession_number']}")
        return inserted_count
    
    async def validate_embedding_type(self):
        """Validate that the configured embedding type matches the database"""
        await self.ensure_connection()
        
        if not self.pg_client:
            return
        
        try:
            async with self.pg_client.pool.acquire() as conn:
                # Check if halfvec type exists
                has_halfvec = await conn.fetchval(
                    "SELECT to_regtype('halfvec') IS NOT NULL"
                )
                
                # Check table embedding column type if table exists
                table_type = await conn.fetchval("""
                    SELECT typname
                    FROM pg_type t
                    JOIN pg_attribute a ON t.oid = a.atttypid
                    JOIN pg_class c ON a.attrelid = c.oid
                    WHERE c.relname = 'sec_filing_embeddings'
                    AND a.attname = 'embedding'
                """)
                
                # Validate configuration matches capabilities
                if self.config.sec_embedding_type == 'halfvec' and not has_halfvec:
                    raise RuntimeError(
                        "SEC_EMBEDDING_TYPE=halfvec but PostgreSQL doesn't have halfvec type. "
                        "Either upgrade pgvector to 0.7.0+ or set SEC_EMBEDDING_TYPE=vector"
                    )
                
                # If table exists, check type matches
                if table_type:
                    if self.config.sec_embedding_type != table_type:
                        logger.warning(
                            f"Config embedding type ({self.config.sec_embedding_type}) doesn't match "
                            f"database type ({table_type}). Using database type."
                        )
                        # Override config to match database
                        self.config.sec_embedding_type = table_type
                        self.config.sec_vector_cast = table_type
                        self.config.sec_vector_ops = f"{table_type}_cosine_ops"
                        
                        # Adjust dimensions if needed
                        if table_type == 'vector':
                            self.config.sec_embedding_model = 'text-embedding-3-small'
                            self.config.sec_embedding_dims = 1536
                        else:
                            self.config.sec_embedding_model = 'text-embedding-3-large'
                            self.config.sec_embedding_dims = 3072
                
                logger.info(f"Embedding type validated: {self.config.sec_embedding_type}")
                
        except Exception as e:
            logger.warning(f"Could not validate embedding type: {e}")
            # Continue anyway - migration will handle it