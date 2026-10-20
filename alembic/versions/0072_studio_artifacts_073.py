"""
073_studio_artifacts

Revision ID: studio_artifacts_001
Revises: add_reference_types_072
Create Date: 2026-01-24

Studio Artifacts persistence - mindmaps, reports, data tables per chat thread.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "studio_artifacts_001"
down_revision = "add_ref_types_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create studio_artifacts table with RLS for per-thread artifact persistence."""
    op.execute(
        """
-- =============================================================================
-- Studio Artifacts Table
-- Per-thread persistence for generated mindmaps, reports, and data tables
-- =============================================================================

-- Create the studio artifacts table
CREATE TABLE IF NOT EXISTS studio_artifacts (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    
    -- Scoping: per-thread (session_id required)
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    org_id TEXT,
    
    -- Artifact type and content
    type VARCHAR(20) NOT NULL CHECK (type IN ('mindmap', 'report', 'datatable')),
    title VARCHAR(255),
    content JSONB NOT NULL,
    
    -- Generation context
    description TEXT,
    format VARCHAR(50),
    source_note_ids UUID[],
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_studio_artifacts_session ON studio_artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_studio_artifacts_user ON studio_artifacts(user_id);
CREATE INDEX IF NOT EXISTS idx_studio_artifacts_type ON studio_artifacts(type);
CREATE INDEX IF NOT EXISTS idx_studio_artifacts_created ON studio_artifacts(session_id, created_at DESC);

-- Enable Row Level Security
ALTER TABLE studio_artifacts ENABLE ROW LEVEL SECURITY;

-- Drop existing policy if it exists (idempotent)
DROP POLICY IF EXISTS studio_artifacts_user_isolation ON studio_artifacts;

-- RLS Policy: Users can only access their own artifacts
CREATE POLICY studio_artifacts_user_isolation ON studio_artifacts
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Auto-update timestamp trigger
DROP TRIGGER IF EXISTS update_studio_artifacts_updated_at ON studio_artifacts;
CREATE TRIGGER update_studio_artifacts_updated_at
    BEFORE UPDATE ON studio_artifacts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grant permissions to application role if it exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON studio_artifacts TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

-- Add comments
COMMENT ON TABLE studio_artifacts IS 'Studio Artifacts: Persisted mindmaps, reports, and data tables per chat thread.';
COMMENT ON COLUMN studio_artifacts.type IS 'Artifact type: mindmap, report, or datatable';
COMMENT ON COLUMN studio_artifacts.content IS 'Full artifact content as JSONB (nodes for mindmap, markdown for report, rows/cols for datatable)';
"""
    )


def downgrade() -> None:
    """Remove studio_artifacts table."""
    op.execute(
        """
-- Drop trigger first
DROP TRIGGER IF EXISTS update_studio_artifacts_updated_at ON studio_artifacts;

-- Drop policy
DROP POLICY IF EXISTS studio_artifacts_user_isolation ON studio_artifacts;

-- Drop indexes
DROP INDEX IF EXISTS idx_studio_artifacts_session;
DROP INDEX IF EXISTS idx_studio_artifacts_user;
DROP INDEX IF EXISTS idx_studio_artifacts_type;
DROP INDEX IF EXISTS idx_studio_artifacts_created;

-- Drop table
DROP TABLE IF EXISTS studio_artifacts;
"""
    )
