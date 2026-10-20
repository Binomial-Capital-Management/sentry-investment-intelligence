"""
054_fix_org_workspace_isolation

Revision ID: d898096e0410
Revises: 1418fee6c2a1
Create Date: 2025-12-31T16:05:17.204389

Original SQL file: 054_fix_org_workspace_isolation.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d898096e0410"
down_revision = "1418fee6c2a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 054_fix_org_workspace_isolation.sql."""
    op.execute("""
-- Migration 054: Fix Organization Workspace Isolation
-- Fixes RLS policies to properly filter by workspace context
-- Ensures personal workspace shows only org_id IS NULL data
-- Ensures organization workspace shows only matching org_id data

-- ========================================
-- PORTFOLIOS TABLE
-- ========================================
-- Drop old conflicting policies
DROP POLICY IF EXISTS portfolios_isolation ON portfolios;
DROP POLICY IF EXISTS portfolios_dual_access ON portfolios;

-- Create proper dual-access policy with workspace filtering
CREATE POLICY portfolios_dual_access ON portfolios
    FOR ALL
    USING (
        -- Personal workspace: show only personal data (org_id IS NULL)
        (current_setting('app.current_org_id', true) = '' AND
         org_id IS NULL AND
         user_id = current_setting('app.current_user_id', true)::TEXT)
        OR
        -- Organization workspace: show only org data (org_id matches)
        (current_setting('app.current_org_id', true) != '' AND
         org_id = current_setting('app.current_org_id', true)::TEXT AND
         org_id IN (
             SELECT org_id FROM organization_members
             WHERE user_id = current_setting('app.current_user_id', true)::TEXT
         ))
    );

-- ========================================
-- CHAT_SESSIONS TABLE
-- ========================================
DROP POLICY IF EXISTS chat_sessions_isolation ON chat_sessions;

CREATE POLICY chat_sessions_dual_access ON chat_sessions
    FOR ALL
    USING (
        -- Personal workspace: show only personal data (org_id IS NULL)
        (current_setting('app.current_org_id', true) = '' AND
         org_id IS NULL AND
         user_id = current_setting('app.current_user_id', true)::TEXT)
        OR
        -- Organization workspace: show only org data (org_id matches)
        (current_setting('app.current_org_id', true) != '' AND
         org_id = current_setting('app.current_org_id', true)::TEXT AND
         org_id IN (
             SELECT org_id FROM organization_members
             WHERE user_id = current_setting('app.current_user_id', true)::TEXT
         ))
    );

-- ========================================
-- CHAT_MESSAGES TABLE
-- ========================================
DROP POLICY IF EXISTS chat_messages_isolation ON chat_messages;

CREATE POLICY chat_messages_dual_access ON chat_messages
    FOR ALL
    USING (
        -- Personal workspace: show only personal data (org_id IS NULL)
        (current_setting('app.current_org_id', true) = '' AND
         org_id IS NULL AND
         user_id = current_setting('app.current_user_id', true)::TEXT)
        OR
        -- Organization workspace: show only org data (org_id matches)
        (current_setting('app.current_org_id', true) != '' AND
         org_id = current_setting('app.current_org_id', true)::TEXT AND
         org_id IN (
             SELECT org_id FROM organization_members
             WHERE user_id = current_setting('app.current_user_id', true)::TEXT
         ))
    );

-- ========================================
-- RISK_ANALYSES TABLE
-- ========================================
DROP POLICY IF EXISTS risk_analyses_isolation ON risk_analyses;

CREATE POLICY risk_analyses_dual_access ON risk_analyses
    FOR ALL
    USING (
        -- Personal workspace: show only personal data (org_id IS NULL)
        (current_setting('app.current_org_id', true) = '' AND
         org_id IS NULL AND
         user_id = current_setting('app.current_user_id', true)::TEXT)
        OR
        -- Organization workspace: show only org data (org_id matches)
        (current_setting('app.current_org_id', true) != '' AND
         org_id = current_setting('app.current_org_id', true)::TEXT AND
         org_id IN (
             SELECT org_id FROM organization_members
             WHERE user_id = current_setting('app.current_user_id', true)::TEXT
         ))
    );

-- ========================================
-- TASKS TABLE (if exists)
-- ========================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tasks') THEN
        DROP POLICY IF EXISTS tasks_isolation ON tasks;

        EXECUTE 'CREATE POLICY tasks_dual_access ON tasks
            FOR ALL
            USING (
                -- Personal workspace: show only personal data (org_id IS NULL)
                (current_setting(''app.current_org_id'', true) = '''' AND
                 org_id IS NULL AND
                 user_id = current_setting(''app.current_user_id'', true)::TEXT)
                OR
                -- Organization workspace: show only org data (org_id matches)
                (current_setting(''app.current_org_id'', true) != '''' AND
                 org_id = current_setting(''app.current_org_id'', true)::TEXT AND
                 org_id IN (
                     SELECT org_id FROM organization_members
                     WHERE user_id = current_setting(''app.current_user_id'', true)::TEXT
                 ))
            )';
    END IF;
END $$;

-- ========================================
-- TASK_RUNS TABLE (if exists)
-- ========================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'task_runs') THEN
        DROP POLICY IF EXISTS task_runs_isolation ON task_runs;

        EXECUTE 'CREATE POLICY task_runs_dual_access ON task_runs
            FOR ALL
            USING (
                -- Personal workspace: show only personal data (org_id IS NULL)
                (current_setting(''app.current_org_id'', true) = '''' AND
                 org_id IS NULL AND
                 user_id = current_setting(''app.current_user_id'', true)::TEXT)
                OR
                -- Organization workspace: show only org data (org_id matches)
                (current_setting(''app.current_org_id'', true) != '''' AND
                 org_id = current_setting(''app.current_org_id'', true)::TEXT AND
                 org_id IN (
                     SELECT org_id FROM organization_members
                     WHERE user_id = current_setting(''app.current_user_id'', true)::TEXT
                 ))
            )';
    END IF;
END $$;

-- ========================================
-- FILES TABLE (if exists)
-- ========================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        DROP POLICY IF EXISTS files_user_access ON files;
        DROP POLICY IF EXISTS files_dual_access ON files;

        EXECUTE 'CREATE POLICY files_dual_access ON files
            FOR ALL
            USING (
                -- Personal workspace: show only personal data (org_id IS NULL)
                (current_setting(''app.current_org_id'', true) = '''' AND
                 org_id IS NULL AND
                 user_id = current_setting(''app.current_user_id'', true)::TEXT)
                OR
                -- Organization workspace: show only org data (org_id matches)
                (current_setting(''app.current_org_id'', true) != '''' AND
                 org_id = current_setting(''app.current_org_id'', true)::TEXT AND
                 org_id IN (
                     SELECT org_id FROM organization_members
                     WHERE user_id = current_setting(''app.current_user_id'', true)::TEXT
                 ))
            )';
    END IF;
END $$;

-- Comments for documentation
COMMENT ON POLICY portfolios_dual_access ON portfolios IS 'Allows access to personal portfolios (org_id NULL) in personal workspace and org portfolios (org_id matches) in org workspace';
COMMENT ON POLICY chat_sessions_dual_access ON chat_sessions IS 'Allows access to personal chat sessions (org_id NULL) in personal workspace and org sessions (org_id matches) in org workspace';
COMMENT ON POLICY chat_messages_dual_access ON chat_messages IS 'Allows access to personal chat messages (org_id NULL) in personal workspace and org messages (org_id matches) in org workspace';
COMMENT ON POLICY risk_analyses_dual_access ON risk_analyses IS 'Allows access to personal risk analyses (org_id NULL) in personal workspace and org analyses (org_id matches) in org workspace';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
