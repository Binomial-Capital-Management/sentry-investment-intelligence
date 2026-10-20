"""
071_memory_chunks

Revision ID: memory_chunks_001
Revises: memory_notes_001
Create Date: 2026-01-20

Memory Chunks table for semantic chunking and vector retrieval.
Large memory notes are split into chunks, embedded, and stored here for
retrieval via vector similarity search at context injection time.

See docs/memory-notebook-feature-spec.md for full specification.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "memory_chunks_001"
down_revision = "memory_notes_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create memory_chunks table with vector column and RLS."""
    op.execute("""
-- =============================================================================
-- Memory Chunks Table
-- Semantic chunking for large memory notes with vector retrieval
-- =============================================================================

-- Create the memory chunks table
CREATE TABLE IF NOT EXISTS memory_chunks (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    
    -- Parent reference (cascades on delete)
    memory_note_id UUID NOT NULL REFERENCES chat_memory_notes(id) ON DELETE CASCADE,
    
    -- Scoping (denormalized for RLS performance)
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    
    -- Chunk data
    chunk_idx INT NOT NULL,              -- Sequence number within the note
    content TEXT NOT NULL,               -- Chunk text content
    token_count INT DEFAULT 0,           -- Tokens in this chunk
    
    -- Vector embedding (1024 dims for Voyage, 3072 for OpenAI text-embedding-3-large)
    -- Using 1024 to match existing file embedding configuration
    embedding vector(1024),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure unique chunk ordering per note
    UNIQUE(memory_note_id, chunk_idx)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_memory_chunks_note ON memory_chunks(memory_note_id);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_session ON memory_chunks(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_user ON memory_chunks(user_id);

-- Vector index for fast similarity search (IVFFlat)
-- Using 100 lists is good for up to ~100k vectors per session
CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding ON memory_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Enable Row Level Security
ALTER TABLE memory_chunks ENABLE ROW LEVEL SECURITY;

-- Drop existing policy if it exists (idempotent)
DROP POLICY IF EXISTS memory_chunks_user_isolation ON memory_chunks;

-- RLS Policy: Users can only access their own chunks
CREATE POLICY memory_chunks_user_isolation ON memory_chunks
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Grant permissions to application role if it exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON memory_chunks TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

-- Add is_chunked flag to chat_memory_notes for quick filtering
ALTER TABLE chat_memory_notes 
    ADD COLUMN IF NOT EXISTS is_chunked BOOLEAN DEFAULT FALSE;

-- Index for filtering chunked vs non-chunked notes
CREATE INDEX IF NOT EXISTS idx_memory_notes_chunked ON chat_memory_notes(session_id, is_chunked);

-- Add comments for documentation
COMMENT ON TABLE memory_chunks IS 'Semantic chunks for large memory notes. Used for vector retrieval at context injection time.';
COMMENT ON COLUMN memory_chunks.chunk_idx IS 'Sequence number of chunk within parent note (0-indexed)';
COMMENT ON COLUMN memory_chunks.embedding IS 'Vector embedding (1024 dims) for semantic similarity search';
COMMENT ON COLUMN memory_chunks.token_count IS 'Token count for budget tracking';
COMMENT ON COLUMN chat_memory_notes.is_chunked IS 'True if this note has been split into chunks for semantic retrieval';
""")


def downgrade() -> None:
    """Remove memory_chunks table and is_chunked column."""
    op.execute("""
-- Drop index on is_chunked
DROP INDEX IF EXISTS idx_memory_notes_chunked;

-- Remove is_chunked column from chat_memory_notes
ALTER TABLE chat_memory_notes DROP COLUMN IF EXISTS is_chunked;

-- Drop policy
DROP POLICY IF EXISTS memory_chunks_user_isolation ON memory_chunks;

-- Drop indexes
DROP INDEX IF EXISTS idx_memory_chunks_embedding;
DROP INDEX IF EXISTS idx_memory_chunks_note;
DROP INDEX IF EXISTS idx_memory_chunks_session;
DROP INDEX IF EXISTS idx_memory_chunks_user;

-- Drop table
DROP TABLE IF EXISTS memory_chunks;
""")

