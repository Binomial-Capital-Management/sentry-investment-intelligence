"""
061_add_org_id_to_all_tables

Revision ID: 69a63db95da5
Revises: 4fe8d2e62c25
Create Date: 2025-12-31T16:05:17.208390

Original SQL file: 061_add_org_id_to_all_tables.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "69a63db95da5"
down_revision = "4fe8d2e62c25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 061_add_org_id_to_all_tables.sql."""
    op.execute("""
-- Migration: Add org_id to all tables for organization isolation
-- Purpose: Enable organization-scoped data across the platform
-- Tables affected: user_lists, workflows, workflow_runs, files, broker_connections

-- =====================================================
-- 1. USER_LISTS TABLE
-- =====================================================
ALTER TABLE user_lists ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_user_lists_org_id ON user_lists(org_id);

-- Drop existing RLS policy if exists
DROP POLICY IF EXISTS user_lists_isolation_policy ON user_lists;

-- Create new RLS policy with org_id check
CREATE POLICY user_lists_isolation_policy ON user_lists
    FOR ALL
    USING (
        user_id = current_setting('app.current_user_id', true)
        AND (
            (org_id = '' AND COALESCE(current_setting('app.current_org_id', true), '') = '')
            OR
            (org_id != '' AND org_id = current_setting('app.current_org_id', true))
        )
    );

-- =====================================================
-- 2. WORKFLOWS TABLE
-- =====================================================
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_workflows_org_id ON workflows(org_id);

-- Drop existing RLS policy if exists
DROP POLICY IF EXISTS workflows_isolation_policy ON workflows;

-- Create new RLS policy with org_id check
CREATE POLICY workflows_isolation_policy ON workflows
    FOR ALL
    USING (
        user_id = current_setting('app.current_user_id', true)
        AND (
            (org_id = '' AND COALESCE(current_setting('app.current_org_id', true), '') = '')
            OR
            (org_id != '' AND org_id = current_setting('app.current_org_id', true))
        )
    );

-- =====================================================
-- 3. WORKFLOW_RUNS TABLE
-- =====================================================
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_workflow_runs_org_id ON workflow_runs(org_id);

-- Drop existing RLS policy if exists
DROP POLICY IF EXISTS workflow_runs_isolation_policy ON workflow_runs;

-- Create new RLS policy with org_id check
CREATE POLICY workflow_runs_isolation_policy ON workflow_runs
    FOR ALL
    USING (
        user_id = current_setting('app.current_user_id', true)
        AND (
            (org_id = '' AND COALESCE(current_setting('app.current_org_id', true), '') = '')
            OR
            (org_id != '' AND org_id = current_setting('app.current_org_id', true))
        )
    );

-- =====================================================
-- 4. FILES TABLE
-- =====================================================
ALTER TABLE files ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_files_org_id ON files(org_id);

-- Drop existing RLS policy if exists
DROP POLICY IF EXISTS files_isolation_policy ON files;

-- Create new RLS policy with org_id check
CREATE POLICY files_isolation_policy ON files
    FOR ALL
    USING (
        user_id = current_setting('app.current_user_id', true)
        AND (
            (org_id = '' AND COALESCE(current_setting('app.current_org_id', true), '') = '')
            OR
            (org_id != '' AND org_id = current_setting('app.current_org_id', true))
        )
    );

-- =====================================================
-- 5. BROKER_CONNECTIONS TABLE
-- =====================================================
ALTER TABLE broker_connections ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_broker_connections_org_id ON broker_connections(org_id);

-- Drop existing RLS policy if exists
DROP POLICY IF EXISTS broker_connections_isolation_policy ON broker_connections;

-- Create new RLS policy with org_id check
CREATE POLICY broker_connections_isolation_policy ON broker_connections
    FOR ALL
    USING (
        user_id = current_setting('app.current_user_id', true)
        AND (
            (org_id = '' AND COALESCE(current_setting('app.current_org_id', true), '') = '')
            OR
            (org_id != '' AND org_id = current_setting('app.current_org_id', true))
        )
    );

-- =====================================================
-- COMMENTS
-- =====================================================
COMMENT ON COLUMN user_lists.org_id IS 'Organization ID for workspace isolation. Empty string for personal workspace.';
COMMENT ON COLUMN workflows.org_id IS 'Organization ID for workspace isolation. Empty string for personal workspace.';
COMMENT ON COLUMN workflow_runs.org_id IS 'Organization ID for workspace isolation. Empty string for personal workspace.';
COMMENT ON COLUMN files.org_id IS 'Organization ID for workspace isolation. Empty string for personal workspace.';
COMMENT ON COLUMN broker_connections.org_id IS 'Organization ID for workspace isolation. Empty string for personal workspace.';


""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
