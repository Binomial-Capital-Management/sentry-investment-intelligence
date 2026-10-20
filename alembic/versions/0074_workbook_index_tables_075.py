"""
075_workbook_index_tables

Revision ID: workbook_index_001
Revises: transcript_ref_001
Create Date: 2026-02-09

Workbook index tables for the Excel Agent.
Stores semantic chunks of Excel workbooks with vector embeddings for retrieval.
Uses pgvector for similarity search, RLS for user isolation.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "workbook_index_001"
down_revision = "studio_artifacts_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create workbook_registry and workbook_chunks tables with pgvector + RLS."""
    op.execute(
        """
-- =============================================================================
-- Workbook Registry
-- One row per workbook per user. Tracks indexing state and content hash.
-- =============================================================================

CREATE TABLE IF NOT EXISTS workbook_registry (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    org_id TEXT,
    workbook_hash TEXT NOT NULL,
    workbook_name TEXT,
    content_hash TEXT,
    total_chunks INT DEFAULT 0,
    summary TEXT,
    last_indexed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, workbook_hash)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workbook_registry_user ON workbook_registry(user_id);
CREATE INDEX IF NOT EXISTS idx_workbook_registry_hash ON workbook_registry(workbook_hash);

-- RLS
ALTER TABLE workbook_registry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workbook_registry_user_isolation ON workbook_registry;
CREATE POLICY workbook_registry_user_isolation ON workbook_registry
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Auto-update timestamp
DROP TRIGGER IF EXISTS update_workbook_registry_updated_at ON workbook_registry;
CREATE TRIGGER update_workbook_registry_updated_at
    BEFORE UPDATE ON workbook_registry
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grants
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON workbook_registry TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

COMMENT ON TABLE workbook_registry IS 'Tracks indexed Excel workbooks per user for the Excel Agent.';
COMMENT ON COLUMN workbook_registry.workbook_hash IS 'Stable identity hash (filename + user_id).';
COMMENT ON COLUMN workbook_registry.content_hash IS 'Hash of workbook content for staleness detection.';

-- =============================================================================
-- Workbook Chunks
-- Semantic chunks of workbook content with vector embeddings.
-- Uses same vector dimensions as configured embedding provider.
-- =============================================================================

CREATE TABLE IF NOT EXISTS workbook_chunks (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    workbook_id UUID NOT NULL REFERENCES workbook_registry(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    org_id TEXT,
    sheet_name TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    cell_range TEXT,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Standard indexes
CREATE INDEX IF NOT EXISTS idx_workbook_chunks_workbook ON workbook_chunks(workbook_id);
CREATE INDEX IF NOT EXISTS idx_workbook_chunks_user ON workbook_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_workbook_chunks_sheet ON workbook_chunks(workbook_id, sheet_name);
CREATE INDEX IF NOT EXISTS idx_workbook_chunks_type ON workbook_chunks(chunk_type);

-- Vector index for similarity search (IVFFlat, good up to ~100k vectors)
CREATE INDEX IF NOT EXISTS idx_workbook_chunks_embedding ON workbook_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- RLS
ALTER TABLE workbook_chunks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workbook_chunks_user_isolation ON workbook_chunks;
CREATE POLICY workbook_chunks_user_isolation ON workbook_chunks
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Grants
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON workbook_chunks TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

COMMENT ON TABLE workbook_chunks IS 'Semantic chunks of Excel workbooks with vector embeddings for the Excel Agent.';
COMMENT ON COLUMN workbook_chunks.chunk_type IS 'One of: sheet_summary, row, formula_cluster, data_region, global_summary';
COMMENT ON COLUMN workbook_chunks.embedding IS 'Vector embedding (1536 dims, text-embedding-3-small) for cosine similarity search.';
COMMENT ON COLUMN workbook_chunks.metadata IS 'Structured metadata: values, formulas, dependsOn, dependedBy, dataType, format.';
"""
    )


def downgrade() -> None:
    """Remove workbook index tables."""
    op.execute(
        """
-- Drop triggers
DROP TRIGGER IF EXISTS update_workbook_registry_updated_at ON workbook_registry;

-- Drop policies
DROP POLICY IF EXISTS workbook_chunks_user_isolation ON workbook_chunks;
DROP POLICY IF EXISTS workbook_registry_user_isolation ON workbook_registry;

-- Drop indexes
DROP INDEX IF EXISTS idx_workbook_chunks_embedding;
DROP INDEX IF EXISTS idx_workbook_chunks_type;
DROP INDEX IF EXISTS idx_workbook_chunks_sheet;
DROP INDEX IF EXISTS idx_workbook_chunks_user;
DROP INDEX IF EXISTS idx_workbook_chunks_workbook;
DROP INDEX IF EXISTS idx_workbook_registry_hash;
DROP INDEX IF EXISTS idx_workbook_registry_user;

-- Drop tables (chunks first due to FK)
DROP TABLE IF EXISTS workbook_chunks;
DROP TABLE IF EXISTS workbook_registry;
"""
    )
