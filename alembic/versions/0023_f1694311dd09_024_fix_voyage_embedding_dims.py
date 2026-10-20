"""
024_fix_voyage_embedding_dims

Revision ID: f1694311dd09
Revises: 3e13edbf635a
Create Date: 2025-12-31T16:05:17.190169

Original SQL file: 024_fix_voyage_embedding_dims.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1694311dd09"
down_revision = "3e13edbf635a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 024_fix_voyage_embedding_dims.sql."""
    op.execute("""
-- Migration: Ensure Voyage embeddings use vector(1024)
-- Date: 2025-02-15
-- Purpose: Align sec_filing_embeddings.embedding_v2 with Voyage defaults
--          (voyage-3-large, 1024 dims) and recreate the IVFFlat index.

DO $$
DECLARE
    table_exists BOOLEAN;
    col_type TEXT;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'sec_filing_embeddings'
          AND table_schema = 'public'
    ) INTO table_exists;
    
    IF NOT table_exists THEN
        RAISE NOTICE 'sec_filing_embeddings table missing - skipping Voyage embedding fix';
        RETURN;
    END IF;
    
    -- Drop any existing index so we can recreate it with vector(1024)
    EXECUTE 'DROP INDEX IF EXISTS sec_filing_embeddings_v2_idx';
    
    SELECT format_type(a.atttypid, a.atttypmod) INTO col_type
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'sec_filing_embeddings'
      AND a.attname = 'embedding_v2'
      AND a.attnum > 0
      AND NOT a.attisdropped;
    
    IF col_type IS NULL THEN
        RAISE NOTICE 'embedding_v2 missing - adding vector(1024) column';
        EXECUTE 'ALTER TABLE public.sec_filing_embeddings ADD COLUMN embedding_v2 vector(1024)';
    ELSIF col_type <> 'vector(1024)' THEN
        RAISE NOTICE 'Converting embedding_v2 from % to vector(1024); existing values will be reset to NULL', col_type;
        EXECUTE '
            ALTER TABLE public.sec_filing_embeddings
            ALTER COLUMN embedding_v2 TYPE vector(1024)
            USING NULL
        ';
    ELSE
        RAISE NOTICE 'embedding_v2 already vector(1024); no change needed';
    END IF;
END $$;

DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'sec_filing_embeddings'
          AND table_schema = 'public'
    ) INTO table_exists;
    
    IF NOT table_exists THEN
        RETURN;
    END IF;
    
    BEGIN
        EXECUTE '
            CREATE INDEX sec_filing_embeddings_v2_idx
            ON public.sec_filing_embeddings
            USING ivfflat (embedding_v2 vector_cosine_ops)
            WITH (lists = 100)
        ';
    EXCEPTION
        WHEN duplicate_table THEN
            RAISE NOTICE 'sec_filing_embeddings_v2_idx already exists';
    END;
END $$;

-- Add comment only if table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sec_filing_embeddings' AND table_schema = 'public') THEN
        COMMENT ON COLUMN public.sec_filing_embeddings.embedding_v2 IS
            'Voyage-3-large embeddings (1024 dims) used for SEC filing retrieval.';
    END IF;
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
