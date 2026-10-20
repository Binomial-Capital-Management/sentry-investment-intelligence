"""
058_postmortem_chat_threads

Revision ID: 03057220d7ee
Revises: 1be72938d15f
Create Date: 2025-12-31T16:05:17.206388

Original SQL file: 058_postmortem_chat_threads.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "03057220d7ee"
down_revision = "1be72938d15f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 058_postmortem_chat_threads.sql."""
    op.execute("""
-- Post-Mortem Chat Threads
-- Separate chat system for post-mortem analysis (isolated from main chat)

CREATE TABLE IF NOT EXISTS postmortem_chat_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    postmortem_id UUID NOT NULL REFERENCES portfolio_postmortems(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL DEFAULT '',
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_postmortem FOREIGN KEY (postmortem_id) REFERENCES portfolio_postmortems(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS postmortem_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES postmortem_chat_threads(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_thread FOREIGN KEY (thread_id) REFERENCES postmortem_chat_threads(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_postmortem_chat_threads_postmortem ON postmortem_chat_threads(postmortem_id);
CREATE INDEX idx_postmortem_chat_threads_user ON postmortem_chat_threads(user_id);
CREATE INDEX idx_postmortem_chat_threads_created ON postmortem_chat_threads(created_at DESC);
CREATE INDEX idx_postmortem_chat_messages_thread ON postmortem_chat_messages(thread_id);
CREATE INDEX idx_postmortem_chat_messages_created ON postmortem_chat_messages(created_at ASC);

-- RLS Policies
ALTER TABLE postmortem_chat_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE postmortem_chat_messages ENABLE ROW LEVEL SECURITY;

-- Users can only see their own threads
CREATE POLICY postmortem_chat_threads_isolation ON postmortem_chat_threads
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

-- Users can only see messages from their own threads
CREATE POLICY postmortem_chat_messages_isolation ON postmortem_chat_messages
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

COMMENT ON TABLE postmortem_chat_threads IS 'Chat threads for post-mortem analysis - isolated from main chat interface';
COMMENT ON TABLE postmortem_chat_messages IS 'Messages within post-mortem chat threads';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
