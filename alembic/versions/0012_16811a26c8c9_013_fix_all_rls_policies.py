"""
013_fix_all_rls_policies

Revision ID: 16811a26c8c9
Revises: b5965227dcb5
Create Date: 2025-12-31T16:05:17.185167

Original SQL file: 013_fix_all_rls_policies.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "16811a26c8c9"
down_revision = "b5965227dcb5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 013_fix_all_rls_policies.sql."""
    op.execute("""
-- Critical RLS Security Fix for ALL Tenant Tables
-- Date: 2025-09-02
-- Purpose: Apply FORCE RLS, NULL-safe policies, and revoke PUBLIC access
-- CRITICAL: This fixes a security vulnerability where superuser bypassed all RLS

-- ===== REVOKE DANGEROUS PUBLIC GRANTS =====
-- These were granted in migration 001_enable_rls.sql
REVOKE ALL ON portfolios FROM PUBLIC;
REVOKE ALL ON chat_sessions FROM PUBLIC;
REVOKE ALL ON chat_messages FROM PUBLIC;
REVOKE ALL ON risk_analyses FROM PUBLIC;

-- Revoke from files table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'files') THEN
        REVOKE ALL ON files FROM PUBLIC;
    END IF;
END $$;

-- ===== FORCE ROW LEVEL SECURITY ON ALL TENANT TABLES =====
-- FORCE makes RLS apply even to table owners (but not superusers)

ALTER TABLE portfolios FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE risk_analyses FORCE ROW LEVEL SECURITY;

-- Force RLS on files table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'files') THEN
        ALTER TABLE files FORCE ROW LEVEL SECURITY;
    END IF;
END $$;

-- ===== DROP OLD WEAK POLICIES =====
DROP POLICY IF EXISTS portfolios_isolation ON portfolios;
DROP POLICY IF EXISTS chat_sessions_isolation ON chat_sessions;
DROP POLICY IF EXISTS chat_messages_isolation ON chat_messages;
DROP POLICY IF EXISTS risk_analyses_isolation ON risk_analyses;
DROP POLICY IF EXISTS files_isolation ON files;

-- ===== CREATE NULL-SAFE RLS POLICIES =====
-- These policies require context to be explicitly set (no NULL bypass)

-- Portfolios: user can only see their own portfolios
CREATE POLICY portfolios_isolation ON portfolios
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Chat sessions: user can only see their own sessions
CREATE POLICY chat_sessions_isolation ON chat_sessions
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Chat messages: user can only see their own messages
CREATE POLICY chat_messages_isolation ON chat_messages
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Risk analyses: user can only see their own analyses
CREATE POLICY risk_analyses_isolation ON risk_analyses
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Files: user can only see their own files (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'files') THEN
        CREATE POLICY files_isolation ON files
            FOR ALL
            USING (
                current_setting('app.current_user_id', true) IS NOT NULL
                AND user_id = current_setting('app.current_user_id', true)
            )
            WITH CHECK (
                current_setting('app.current_user_id', true) IS NOT NULL
                AND user_id = current_setting('app.current_user_id', true)
            );
    END IF;
END $$;

-- ===== FIX workflow_run_steps SCHEMA =====
-- Option A: Drop user_id column and derive from run_id
-- This prevents inconsistency and reduces redundancy

-- First, drop the existing policy
DROP POLICY IF EXISTS workflow_run_steps_isolation ON workflow_run_steps;

-- Drop the user_id column from workflow_run_steps
-- User isolation will be enforced through the run_id relationship
ALTER TABLE workflow_run_steps DROP COLUMN IF EXISTS user_id;

-- Recreate the policy using only run_id
CREATE POLICY workflow_run_steps_isolation ON workflow_run_steps
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND run_id IN (
            SELECT id FROM workflow_runs
            WHERE user_id = current_setting('app.current_user_id', true)
        )
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND run_id IN (
            SELECT id FROM workflow_runs
            WHERE user_id = current_setting('app.current_user_id', true)
        )
    );

-- Drop the now-unused index
DROP INDEX IF EXISTS idx_workflow_run_steps_user_id;

-- ===== GRANT PROPER PERMISSIONS TO APP ROLE =====
-- Only grant to the application role, not PUBLIC

-- IMPORTANT: The binomial_app role must be created via infrastructure/secrets management
-- Requirements for the role:
--   - NOSUPERUSER (REQUIRED - superuser bypasses all RLS)
--   - NOBYPASSRLS (REQUIRED - must respect RLS policies)
--   - LOGIN (needed for application connections)
--   - NOCREATEDB (security best practice)
--   - NOCREATEROLE (security best practice)
--   - NOINHERIT (security best practice)
--
-- Example role creation (run via infrastructure, not migration):
-- CREATE ROLE binomial_app LOGIN PASSWORD 'use_secure_password_from_secrets'
--   NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
--
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
        -- Verify the role has safe security settings (notice only in migration)
        IF EXISTS (
            SELECT 1 FROM pg_roles 
            WHERE rolname = 'binomial_app' 
            AND (rolsuper = true OR rolbypassrls = true)
        ) THEN
            RAISE NOTICE 'Role binomial_app has dangerous privileges (superuser or bypassrls) - please fix via infrastructure.';
        END IF;

        -- Grant permissions to binomial_app safely
        GRANT USAGE ON SCHEMA public TO binomial_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO binomial_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO binomial_app;

        -- Set default privileges for future tables
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO binomial_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT USAGE, SELECT ON SEQUENCES TO binomial_app;
    ELSE
        RAISE NOTICE 'Role binomial_app does not exist - skipping grants.';
    END IF;
END $$;

-- ===== VERIFICATION QUERIES =====
-- Run these after migration to verify:

-- 1. Check no PUBLIC grants remain:
-- SELECT tablename, privileges FROM information_schema.role_table_grants 
-- WHERE grantee = 'PUBLIC' AND schemaname = 'public';

-- 2. Verify FORCE RLS is enabled:
-- SELECT tablename, relforcerowsecurity 
-- FROM pg_tables t JOIN pg_class c ON t.tablename = c.relname 
-- WHERE schemaname = 'public' AND tablename IN ('portfolios', 'chat_sessions', 'workflows');

-- 3. Verify app role has no dangerous privileges:
-- SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'binomial_app';
-- Should return: rolsuper = false, rolbypassrls = false
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
