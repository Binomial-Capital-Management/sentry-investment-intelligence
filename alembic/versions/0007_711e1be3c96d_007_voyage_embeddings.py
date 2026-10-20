"""
007_voyage_embeddings

Revision ID: 711e1be3c96d
Revises: 6060e18f50ce
Create Date: 2025-12-31T16:05:17.182169

Original SQL file: 007_voyage_embeddings.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "711e1be3c96d"
down_revision = "6060e18f50ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 007_voyage_embeddings.sql."""
    op.execute("""
-- Migration: Safe dual-column approach for Voyage embeddings
-- This allows rollback and gradual transition without data loss
-- Per GPT-5 review: P0 fix for unsafe migration

DO $$
BEGIN
    -- Check if sec_filing_embeddings table exists
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'sec_filing_embeddings'
    ) THEN
        -- Add new column for Voyage embeddings (if not exists)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'sec_filing_embeddings' 
            AND column_name = 'embedding_v2'
        ) THEN
            -- Add new column for 1024-dim embeddings
            ALTER TABLE sec_filing_embeddings 
            ADD COLUMN embedding_v2 vector(1024) DEFAULT NULL;
            
            -- Add column to track which embedding version is active
            ALTER TABLE sec_filing_embeddings 
            ADD COLUMN embedding_version TEXT DEFAULT 'v1';
            
            RAISE NOTICE 'Added embedding_v2 column for Voyage embeddings';
        END IF;
        
        -- Create index CONCURRENTLY (non-blocking) if not exists
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'sec_filing_embeddings' 
            AND indexname = 'sec_filing_embeddings_v2_idx'
        ) THEN
            -- Use ivfflat for compatibility (HNSW requires vector limit)
            -- Note: Removed CONCURRENTLY as it cannot run inside transaction block
            CREATE INDEX IF NOT EXISTS sec_filing_embeddings_v2_idx 
            ON sec_filing_embeddings 
            USING ivfflat (embedding_v2 vector_cosine_ops)
            WITH (lists = 100);
            
            RAISE NOTICE 'Created ivfflat index for embedding_v2';
        END IF;
        
        -- Add comment explaining the dual-column approach
        COMMENT ON COLUMN sec_filing_embeddings.embedding_v2 IS 
        'Voyage-3-large embeddings (1024 dims) - gradual migration from v1';
        
        COMMENT ON COLUMN sec_filing_embeddings.embedding_version IS 
        'Tracks which embedding version to use: v1 (OpenAI) or v2 (Voyage)';
        
        RAISE NOTICE 'Safe migration prepared. Use dual-write strategy and flip reads via config.';
        
    ELSE
        RAISE NOTICE 'Table sec_filing_embeddings does not exist, skipping migration';
    END IF;
END $$;

-- Rollback script (keep for reference)
-- ALTER TABLE sec_filing_embeddings DROP COLUMN IF EXISTS embedding_v2;
-- ALTER TABLE sec_filing_embeddings DROP COLUMN IF EXISTS embedding_version;
-- DROP INDEX IF EXISTS sec_filing_embeddings_v2_idx;
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
