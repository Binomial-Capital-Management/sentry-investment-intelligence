"""
070_chat_memory_notes

Revision ID: memory_notes_001
Revises: a16376251f46
Create Date: 2026-01-18

Memory Notebook feature - per-thread context persistence that survives compaction.
See docs/memory-notebook-feature-spec.md for full specification.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "memory_notes_001"
down_revision = "a16376251f46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create chat_memory_notes table with RLS for per-thread memory notebook."""
    op.execute("""
-- =============================================================================
-- Memory Notebook Table
-- Per-thread context persistence that survives compaction and provider switches
-- See docs/memory-notebook-feature-spec.md
-- =============================================================================

-- Create the memory notes table
CREATE TABLE IF NOT EXISTS chat_memory_notes (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    
    -- Scoping: STRICTLY per-thread (session_id is required, NOT NULL)
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,           -- Clerk user ID (for RLS)
    org_id TEXT,                     -- Organization context (NULL = personal workspace)
    
    -- Content
    section VARCHAR(50) DEFAULT 'general'
        CHECK (section IN ('entities', 'decisions', 'preferences', 'context', 'general')),
    content TEXT NOT NULL,           -- The actual note content
    summary TEXT,                    -- Optional AI-generated condensed version
    
    -- Reference system (for non-text notes)
    reference_type VARCHAR(20) DEFAULT 'text'
        CHECK (reference_type IN ('text', 'message_excerpt', 'file', 'portfolio', 'chart', 'table')),
    reference_id UUID,               -- Foreign key to referenced object (polymorphic)
    reference_metadata JSONB,        -- Additional context (offsets, config, etc.)
    
    -- Provenance
    source VARCHAR(20) DEFAULT 'user'
        CHECK (source IN ('user', 'ai', 'tool')),
    source_message_id UUID,          -- Which message triggered this note
    
    -- Ordering
    priority INT DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    -- Higher priority = injected earlier in context
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_memory_notes_session ON chat_memory_notes(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_notes_user ON chat_memory_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_notes_section ON chat_memory_notes(section);
CREATE INDEX IF NOT EXISTS idx_memory_notes_priority ON chat_memory_notes(session_id, priority DESC);

-- Enable Row Level Security
ALTER TABLE chat_memory_notes ENABLE ROW LEVEL SECURITY;

-- Drop existing policy if it exists (idempotent)
DROP POLICY IF EXISTS memory_notes_user_isolation ON chat_memory_notes;

-- RLS Policy: Users can only access their own notes
-- Uses current_setting for runtime context (consistent with other tables)
CREATE POLICY memory_notes_user_isolation ON chat_memory_notes
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Auto-update timestamp trigger (uses existing function from 000_initial_schema)
DROP TRIGGER IF EXISTS update_memory_notes_updated_at ON chat_memory_notes;
CREATE TRIGGER update_memory_notes_updated_at
    BEFORE UPDATE ON chat_memory_notes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grant permissions to application role if it exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON chat_memory_notes TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

-- Add comment for documentation
COMMENT ON TABLE chat_memory_notes IS 'Memory Notebook: User-controlled context persistence per chat thread. Never compacted, survives provider switches.';
COMMENT ON COLUMN chat_memory_notes.section IS 'Category: entities, decisions, preferences, context, or general';
COMMENT ON COLUMN chat_memory_notes.reference_type IS 'Type of content: text, message_excerpt, file, portfolio, chart, or table';
COMMENT ON COLUMN chat_memory_notes.priority IS 'Injection order (1-10): higher priority notes appear first in context';
""")


def downgrade() -> None:
    """Remove chat_memory_notes table."""
    op.execute("""
-- Drop trigger first
DROP TRIGGER IF EXISTS update_memory_notes_updated_at ON chat_memory_notes;

-- Drop policy
DROP POLICY IF EXISTS memory_notes_user_isolation ON chat_memory_notes;

-- Drop indexes
DROP INDEX IF EXISTS idx_memory_notes_session;
DROP INDEX IF EXISTS idx_memory_notes_user;
DROP INDEX IF EXISTS idx_memory_notes_section;
DROP INDEX IF EXISTS idx_memory_notes_priority;

-- Drop table
DROP TABLE IF EXISTS chat_memory_notes;
""")

