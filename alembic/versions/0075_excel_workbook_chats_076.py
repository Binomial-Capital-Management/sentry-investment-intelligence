"""
076_excel_workbook_chats

Revision ID: excel_chat_001
Revises: workbook_index_001
Create Date: 2026-02-09

Excel workbook chat threads and messages.
Separate from the main chat system, linked to workbook_registry.
Follows the same pattern as postmortem_chat_threads.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "excel_chat_001"
down_revision = "workbook_index_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create excel_chat_threads and excel_chat_messages tables with RLS."""
    op.execute("""
-- =============================================================================
-- Excel Workbook Chat Threads
-- Separate chat system for Excel agent conversations (isolated from main chat).
-- Each thread is linked to a workbook_registry entry.
-- =============================================================================

CREATE TABLE IF NOT EXISTS excel_chat_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workbook_id UUID NOT NULL REFERENCES workbook_registry(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL DEFAULT '',
    title TEXT,
    model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Excel Workbook Chat Messages
-- =============================================================================

CREATE TABLE IF NOT EXISTS excel_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES excel_chat_threads(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'plan')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_excel_chat_threads_workbook ON excel_chat_threads(workbook_id);
CREATE INDEX IF NOT EXISTS idx_excel_chat_threads_user ON excel_chat_threads(user_id);
CREATE INDEX IF NOT EXISTS idx_excel_chat_threads_created ON excel_chat_threads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_excel_chat_messages_thread ON excel_chat_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_excel_chat_messages_created ON excel_chat_messages(created_at ASC);

-- RLS
ALTER TABLE excel_chat_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE excel_chat_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS excel_chat_threads_isolation ON excel_chat_threads;
CREATE POLICY excel_chat_threads_isolation ON excel_chat_threads
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS excel_chat_messages_isolation ON excel_chat_messages;
CREATE POLICY excel_chat_messages_isolation ON excel_chat_messages
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Auto-update timestamp
DROP TRIGGER IF EXISTS update_excel_chat_threads_updated_at ON excel_chat_threads;
CREATE TRIGGER update_excel_chat_threads_updated_at
    BEFORE UPDATE ON excel_chat_threads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grants
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON excel_chat_threads TO binomial_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON excel_chat_messages TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

COMMENT ON TABLE excel_chat_threads IS 'Chat threads for Excel agent conversations - isolated from main chat interface';
COMMENT ON TABLE excel_chat_messages IS 'Messages within Excel workbook chat threads';
COMMENT ON COLUMN excel_chat_threads.model IS 'Model ID used for this chat thread (e.g. gpt-5.1)';
COMMENT ON COLUMN excel_chat_messages.role IS 'user, assistant, system, or plan (for inline plan cards)';
COMMENT ON COLUMN excel_chat_messages.metadata IS 'Plan JSON, step results, or other structured data';
""")


def downgrade() -> None:
    """Drop excel chat tables."""
    op.execute("""
DROP TRIGGER IF EXISTS update_excel_chat_threads_updated_at ON excel_chat_threads;
DROP POLICY IF EXISTS excel_chat_messages_isolation ON excel_chat_messages;
DROP POLICY IF EXISTS excel_chat_threads_isolation ON excel_chat_threads;
DROP INDEX IF EXISTS idx_excel_chat_messages_created;
DROP INDEX IF EXISTS idx_excel_chat_messages_thread;
DROP INDEX IF EXISTS idx_excel_chat_threads_created;
DROP INDEX IF EXISTS idx_excel_chat_threads_user;
DROP INDEX IF EXISTS idx_excel_chat_threads_workbook;
DROP TABLE IF EXISTS excel_chat_messages;
DROP TABLE IF EXISTS excel_chat_threads;
""")
