"""
025_tasks

Revision ID: de3857f13f6c
Revises: f1694311dd09
Create Date: 2025-12-31T16:05:17.191167

Original SQL file: 025_tasks.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "de3857f13f6c"
down_revision = "f1694311dd09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 025_tasks.sql."""
    op.execute("""
-- Tasks Feature Tables with Row-Level Security (RLS)
-- Migration: 025_tasks.sql
-- Purpose: Persist scheduled task definitions and execution history with full tenant isolation.

-- ===== MAIN TASKS TABLE =====

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'paused', 'archived')),

    schedule_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    delivery_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    canvas_data JSONB NOT NULL DEFAULT '{"nodes": [], "edges": []}'::jsonb,
    agent_config JSONB NOT NULL DEFAULT '{}'::jsonb,

    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT tasks_name_not_empty CHECK (btrim(name) <> '')
);

-- ===== TASK RUNS TABLE =====

CREATE TABLE IF NOT EXISTS task_runs (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    trigger_type TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (trigger_type IN ('scheduled', 'manual')),

    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    delivery_results JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===== INDEXES =====

CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_next_run_at_active
    ON tasks(next_run_at)
    WHERE status = 'active' AND next_run_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_runs_task_id ON task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_user_id ON task_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status);
CREATE INDEX IF NOT EXISTS idx_task_runs_created_at_desc ON task_runs(created_at DESC);

-- ===== ROW LEVEL SECURITY =====

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;

ALTER TABLE task_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_runs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tasks_isolation ON tasks;
CREATE POLICY tasks_isolation ON tasks
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) != ''
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) != ''
        AND user_id = current_setting('app.current_user_id', true)
    );

DROP POLICY IF EXISTS task_runs_isolation ON task_runs;
CREATE POLICY task_runs_isolation ON task_runs
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) != ''
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) != ''
        AND user_id = current_setting('app.current_user_id', true)
    );

-- ===== UPDATED_AT TRIGGERS =====

DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks;
CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_task_runs_updated_at ON task_runs;
CREATE TRIGGER update_task_runs_updated_at
    BEFORE UPDATE ON task_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ===== GRANTS (OPTIONAL APPLICATION ROLE) =====

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
        GRANT ALL PRIVILEGES ON tasks TO binomial_app;
        GRANT ALL PRIVILEGES ON task_runs TO binomial_app;
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
