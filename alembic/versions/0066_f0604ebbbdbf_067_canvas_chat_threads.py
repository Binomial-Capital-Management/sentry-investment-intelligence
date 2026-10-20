"""
067_canvas_chat_threads

Revision ID: f0604ebbbdbf
Revises: bf2fad7a698b
Create Date: 2025-12-31T16:05:17.210389

Original SQL file: 067_canvas_chat_threads.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f0604ebbbdbf"
down_revision = "bf2fad7a698b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 067_canvas_chat_threads.sql."""
    op.execute("""
-- Canvas Chat Threads
-- Separate chat system for Canvas analysis (isolated from main chat)
-- Threads can span multiple tools/processes

CREATE TABLE IF NOT EXISTS canvas_chat_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL DEFAULT '',
    title TEXT,
    -- Optional: track last process for display, but not a hard FK
    last_process_id UUID,
    last_tool_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS canvas_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES canvas_chat_threads(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    -- Track which process context was active when message was sent
    process_id UUID,
    tool_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_thread FOREIGN KEY (thread_id) REFERENCES canvas_chat_threads(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_canvas_chat_threads_user ON canvas_chat_threads(user_id);
CREATE INDEX IF NOT EXISTS idx_canvas_chat_threads_org ON canvas_chat_threads(org_id) WHERE org_id != '';
CREATE INDEX IF NOT EXISTS idx_canvas_chat_threads_created ON canvas_chat_threads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_canvas_chat_messages_thread ON canvas_chat_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_canvas_chat_messages_created ON canvas_chat_messages(created_at ASC);

-- RLS Policies
ALTER TABLE canvas_chat_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE canvas_chat_messages ENABLE ROW LEVEL SECURITY;

-- Users can only see their own threads
DROP POLICY IF EXISTS canvas_chat_threads_isolation ON canvas_chat_threads;
CREATE POLICY canvas_chat_threads_isolation ON canvas_chat_threads
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

-- Users can only see messages from their own threads
DROP POLICY IF EXISTS canvas_chat_messages_isolation ON canvas_chat_messages;
CREATE POLICY canvas_chat_messages_isolation ON canvas_chat_messages
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

COMMENT ON TABLE canvas_chat_threads IS 'Chat threads for Canvas analysis - can span multiple tools/processes';
COMMENT ON TABLE canvas_chat_messages IS 'Messages within Canvas chat threads';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
