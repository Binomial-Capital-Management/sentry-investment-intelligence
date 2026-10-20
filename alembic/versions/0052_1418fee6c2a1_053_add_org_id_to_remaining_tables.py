"""
053_add_org_id_to_remaining_tables

Revision ID: 1418fee6c2a1
Revises: 8268865e2fe9
Create Date: 2025-12-31T16:05:17.204389

Original SQL file: 053_add_org_id_to_remaining_tables.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1418fee6c2a1"
down_revision = "8268865e2fe9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 053_add_org_id_to_remaining_tables.sql."""
    op.execute("""
-- Migration 053: Add org_id to Remaining Tables
-- Adds org_id column to tables that don't have it yet for organization support
-- Includes: chat_sessions, chat_messages, tasks, task_runs, risk_analyses

-- Add org_id to chat_sessions
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_org_id ON chat_sessions(org_id);

-- Add org_id to chat_messages
ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_chat_messages_org_id ON chat_messages(org_id);

-- Add org_id to tasks (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tasks') THEN
        ALTER TABLE tasks
            ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;

        CREATE INDEX IF NOT EXISTS idx_tasks_org_id ON tasks(org_id);
    END IF;
END $$;

-- Add org_id to task_runs (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'task_runs') THEN
        ALTER TABLE task_runs
            ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;

        CREATE INDEX IF NOT EXISTS idx_task_runs_org_id ON task_runs(org_id);
    END IF;
END $$;

-- Add org_id to risk_analyses
ALTER TABLE risk_analyses
    ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_risk_analyses_org_id ON risk_analyses(org_id);

-- Comments for documentation
COMMENT ON COLUMN chat_sessions.org_id IS 'Organization ID for shared chat sessions (NULL for personal sessions)';
COMMENT ON COLUMN chat_messages.org_id IS 'Organization ID for shared chat messages (NULL for personal messages)';
COMMENT ON COLUMN risk_analyses.org_id IS 'Organization ID for shared risk analyses (NULL for personal analyses)';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tasks') THEN
        EXECUTE 'COMMENT ON COLUMN tasks.org_id IS ''Organization ID for shared tasks (NULL for personal tasks)''';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'task_runs') THEN
        EXECUTE 'COMMENT ON COLUMN task_runs.org_id IS ''Organization ID for shared task runs (NULL for personal task runs)''';
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
