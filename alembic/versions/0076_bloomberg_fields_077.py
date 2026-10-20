"""
077_bloomberg_fields

Revision ID: bloomberg_fields_001
Revises: excel_chat_001
Create Date: 2026-02-09

Bloomberg field catalog with pgvector embeddings for semantic search.
Shared catalog — no RLS (not user data).
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "bloomberg_fields_001"
down_revision = "excel_chat_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create bloomberg_fields table with pgvector embedding column."""
    op.execute(
        """
-- =============================================================================
-- Bloomberg Fields Catalog
-- Shared reference table for Bloomberg Terminal field mnemonics.
-- Agent searches this via pgvector cosine similarity to find correct fields.
-- No RLS — this is a shared, static catalog.
-- =============================================================================

CREATE TABLE IF NOT EXISTS bloomberg_fields (
    id SERIAL PRIMARY KEY,
    mnemonic TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    data_type TEXT,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bbg_fields_mnemonic ON bloomberg_fields(mnemonic);
CREATE INDEX IF NOT EXISTS idx_bbg_fields_category ON bloomberg_fields(category);

-- Vector index for similarity search (IVFFlat, good for <100k rows)
-- NOTE: IVFFlat requires at least (lists * 10) rows to build.
-- With lists=20 we need 200+ rows. Seed script must insert before this index helps.
CREATE INDEX IF NOT EXISTS idx_bbg_fields_embedding ON bloomberg_fields
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);

-- Grants
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON bloomberg_fields TO binomial_app;
    GRANT USAGE, SELECT ON SEQUENCE bloomberg_fields_id_seq TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

COMMENT ON TABLE bloomberg_fields IS 'Bloomberg Terminal field mnemonics catalog with vector embeddings for semantic search.';
COMMENT ON COLUMN bloomberg_fields.mnemonic IS 'Bloomberg field mnemonic e.g. PX_LAST, PE_RATIO';
COMMENT ON COLUMN bloomberg_fields.embedding IS 'Vector embedding (1536 dims, text-embedding-3-small) for cosine similarity search.';
"""
    )


def downgrade() -> None:
    """Remove bloomberg_fields table."""
    op.execute(
        """
DROP INDEX IF EXISTS idx_bbg_fields_embedding;
DROP INDEX IF EXISTS idx_bbg_fields_category;
DROP INDEX IF EXISTS idx_bbg_fields_mnemonic;
DROP TABLE IF EXISTS bloomberg_fields;
"""
    )
