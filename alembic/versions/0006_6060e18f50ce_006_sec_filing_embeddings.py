"""
006_sec_filing_embeddings

Revision ID: 6060e18f50ce
Revises: f92f0023df6d
Create Date: 2025-12-31T16:05:17.181179

Original SQL file: 006_sec_filing_embeddings.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6060e18f50ce"
down_revision = "f92f0023df6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 006_sec_filing_embeddings.sql."""
    op.execute("""
-- Migration: SEC Filing Embeddings with Vector Search
-- Date: 2025-08-23
-- Purpose: Add support for SEC filing semantic search using pgvector
-- Supports: halfvec(3072) when available, falls back to vector(1536)

-- Enable required extensions
DO $$
BEGIN
  BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
  EXCEPTION
    WHEN insufficient_privilege THEN
      RAISE NOTICE 'Skipping vector extension (insufficient privileges)';
    WHEN undefined_file THEN
      RAISE NOTICE 'vector extension not available';
    WHEN feature_not_supported THEN
      RAISE NOTICE 'vector extension not installed on this server';
    WHEN OTHERS THEN
      RAISE NOTICE 'Could not create vector extension: %', SQLERRM;
  END;
  BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For keyword search
  EXCEPTION
    WHEN insufficient_privilege THEN
      RAISE NOTICE 'Skipping pg_trgm extension (insufficient privileges)';
    WHEN undefined_file THEN
      RAISE NOTICE 'pg_trgm extension not available';
    WHEN feature_not_supported THEN
      RAISE NOTICE 'pg_trgm extension not installed on this server';
    WHEN OTHERS THEN
      RAISE NOTICE 'Could not create pg_trgm extension: %', SQLERRM;
  END;
END $$;

-- Detect pgvector capabilities and create/migrate table
DO $$
DECLARE
    has_halfvec boolean;
    has_vector boolean;
    has_hnsw boolean;
    has_trgm boolean;
    table_exists boolean;
    current_type text;
BEGIN
    -- Check if halfvec type is available (pgvector >= 0.7.0)
    SELECT to_regtype('halfvec') IS NOT NULL INTO has_halfvec;
    -- Check if vector type is available
    SELECT to_regtype('vector') IS NOT NULL INTO has_vector;
    
    -- Check if HNSW is available
    SELECT EXISTS (
        SELECT 1 FROM pg_am WHERE amname = 'hnsw'
    ) INTO has_hnsw;
    
    -- Check if pg_trgm is available (for trigram indexes)
    SELECT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
    ) INTO has_trgm;
    
    -- Check if table already exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'sec_filing_embeddings'
    ) INTO table_exists;
    
    IF has_halfvec THEN
        RAISE NOTICE 'halfvec type detected - using 3072 dimensions with HNSW support';
        
        IF table_exists THEN
            -- Check current column type
            SELECT data_type INTO current_type
            FROM information_schema.columns
            WHERE table_name = 'sec_filing_embeddings' 
            AND column_name = 'embedding';
            
            IF current_type = 'USER-DEFINED' THEN
                -- Need to check actual type name
                SELECT typname INTO current_type
                FROM pg_type t
                JOIN pg_attribute a ON t.oid = a.atttypid
                JOIN pg_class c ON a.attrelid = c.oid
                WHERE c.relname = 'sec_filing_embeddings'
                AND a.attname = 'embedding';
            END IF;
            
            IF current_type != 'halfvec' THEN
                RAISE NOTICE 'Migrating from % to halfvec(3072)', current_type;
                
                -- Drop existing index before type change
                DROP INDEX IF EXISTS idx_sec_embeddings_vector;
                
                -- Convert existing vector column to halfvec
                ALTER TABLE sec_filing_embeddings
                    ALTER COLUMN embedding TYPE halfvec(3072)
                    USING embedding::halfvec;
                
                -- Create HNSW index with halfvec operators
                CREATE INDEX idx_sec_embeddings_vector
                    ON sec_filing_embeddings 
                    USING hnsw (embedding halfvec_cosine_ops);
                    
                RAISE NOTICE 'Migration to halfvec complete';
            ELSE
                RAISE NOTICE 'Table already uses halfvec';
            END IF;
        ELSE
            -- Create new table with halfvec
            CREATE TABLE sec_filing_embeddings (
                id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
                user_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                filing_type TEXT NOT NULL,
                filing_date DATE NOT NULL,
                accession_number TEXT NOT NULL,
                filing_url TEXT NOT NULL,
                section_name TEXT,
                chunk_index INTEGER,
                chunk_preview TEXT,  -- 500 chars for keyword search
                embedding halfvec(3072),  -- halfvec for 3072 dimensions
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                last_updated TIMESTAMPTZ DEFAULT NOW(),
                
                -- Unique constraint to prevent duplicates
                CONSTRAINT sec_filing_unique UNIQUE(accession_number, section_name, chunk_index)
            );
            
            -- Create HNSW index with halfvec operators
            CREATE INDEX idx_sec_embeddings_vector
                ON sec_filing_embeddings 
                USING hnsw (embedding halfvec_cosine_ops);
                
            RAISE NOTICE 'Created table with halfvec(3072) and HNSW index';
        END IF;
        
    ELSE
        -- Fallback to vector(1536) for text-embedding-3-small
        IF NOT has_vector THEN
            RAISE NOTICE 'pgvector not available - skipping sec_filing_embeddings migration entirely';
            RETURN;
        END IF;
        RAISE NOTICE 'halfvec not available - using vector(1536) for text-embedding-3-small';
        
        IF NOT table_exists THEN
            CREATE TABLE sec_filing_embeddings (
                id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
                user_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                filing_type TEXT NOT NULL,
                filing_date DATE NOT NULL,
                accession_number TEXT NOT NULL,
                filing_url TEXT NOT NULL,
                section_name TEXT,
                chunk_index INTEGER,
                chunk_preview TEXT,  -- 500 chars for keyword search
                embedding vector(1536),  -- Standard vector for 1536 dimensions
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                last_updated TIMESTAMPTZ DEFAULT NOW(),
                
                -- Unique constraint to prevent duplicates
                CONSTRAINT sec_filing_unique UNIQUE(accession_number, section_name, chunk_index)
            );
            
            -- Create index based on available index types
            IF has_hnsw THEN
                CREATE INDEX idx_sec_embeddings_vector
                    ON sec_filing_embeddings 
                    USING hnsw (embedding vector_cosine_ops);
                RAISE NOTICE 'Created table with vector(1536) and HNSW index';
            ELSE
                CREATE INDEX idx_sec_embeddings_vector
                    ON sec_filing_embeddings 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                RAISE NOTICE 'Created table with vector(1536) and IVFFlat index';
            END IF;
        ELSE
            RAISE NOTICE 'Table already exists with vector type';
        END IF;
    END IF;
END $$;

-- Only create indexes, RLS policies, etc. if the table was actually created
DO $$
BEGIN
    -- Skip everything if table doesn't exist (pgvector not available)
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sec_filing_embeddings') THEN
        RAISE NOTICE 'sec_filing_embeddings table not created (pgvector not available) - skipping indexes and policies';
        RETURN;
    END IF;
    
    -- Keyword search index using trigram (only if pg_trgm available)
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        CREATE INDEX IF NOT EXISTS idx_sec_preview_trgm
            ON sec_filing_embeddings USING gin (chunk_preview gin_trgm_ops);
    ELSE
        RAISE NOTICE 'pg_trgm not available - skipping trigram index on chunk_preview';
    END IF;
    
    -- Full-text search index
    CREATE INDEX IF NOT EXISTS idx_sec_preview_fts
        ON sec_filing_embeddings USING gin (to_tsvector('english', chunk_preview));
    
    -- Standard indexes for filtering
    CREATE INDEX IF NOT EXISTS idx_sec_ticker_date
        ON sec_filing_embeddings(ticker, filing_date DESC);
    
    CREATE INDEX IF NOT EXISTS idx_sec_filing_type
        ON sec_filing_embeddings(filing_type, filing_date DESC);
    
    -- Enable RLS
    ALTER TABLE sec_filing_embeddings ENABLE ROW LEVEL SECURITY;
    
    -- Create RLS policies
    DROP POLICY IF EXISTS sec_embeddings_read ON sec_filing_embeddings;
    CREATE POLICY sec_embeddings_read ON sec_filing_embeddings
        FOR SELECT USING (true);
    
    DROP POLICY IF EXISTS sec_embeddings_write ON sec_filing_embeddings;
    CREATE POLICY sec_embeddings_write ON sec_filing_embeddings
        FOR INSERT WITH CHECK (user_id = current_setting('app.current_user_id', true));
    
    DROP POLICY IF EXISTS sec_embeddings_update ON sec_filing_embeddings;
    CREATE POLICY sec_embeddings_update ON sec_filing_embeddings
        FOR UPDATE USING (user_id = current_setting('app.current_user_id', true));
    
    DROP POLICY IF EXISTS sec_embeddings_delete ON sec_filing_embeddings;
    CREATE POLICY sec_embeddings_delete ON sec_filing_embeddings
        FOR DELETE USING (user_id = current_setting('app.current_user_id', true));
    
    -- Grant permissions if authenticated role exists
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT SELECT ON sec_filing_embeddings TO authenticated;
        GRANT INSERT, UPDATE, DELETE ON sec_filing_embeddings TO authenticated;
        RAISE NOTICE 'Granted permissions to authenticated role';
    END IF;
    
    -- Add comments
    COMMENT ON TABLE sec_filing_embeddings IS 'Stores embeddings of SEC filing chunks for semantic search. No raw documents stored.';
    COMMENT ON COLUMN sec_filing_embeddings.embedding IS 'OpenAI embeddings - halfvec(3072) for text-embedding-3-large or vector(1536) for text-embedding-3-small';
    COMMENT ON COLUMN sec_filing_embeddings.chunk_preview IS 'First 500 chars of chunk for keyword search';
    
    RAISE NOTICE 'sec_filing_embeddings table setup complete';
END $$;
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
