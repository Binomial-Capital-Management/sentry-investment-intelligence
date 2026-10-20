"""
047_add_org_id_to_resources

Revision ID: c5a0627a9437
Revises: aac17c7fd505
Create Date: 2025-12-31T16:05:17.201390

Original SQL file: 047_add_org_id_to_resources.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c5a0627a9437"
down_revision = "aac17c7fd505"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 047_add_org_id_to_resources.sql."""
    op.execute("""
-- Migration 047: Add org_id to Resource Tables
-- Adds org_id column to portfolios and files tables for organization support
-- Updates RLS policies to support both personal and organization resources

-- Add org_id column to portfolios
ALTER TABLE portfolios
    ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;

-- Add org_id column to files (if files table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        ALTER TABLE files
            ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create indexes for org_id lookups
CREATE INDEX IF NOT EXISTS idx_portfolios_org_id ON portfolios(org_id);
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        CREATE INDEX IF NOT EXISTS idx_files_org_id ON files(org_id);
    END IF;
END $$;

-- Drop existing RLS policies for portfolios
DROP POLICY IF EXISTS portfolios_user_access ON portfolios;

-- Create new dual-access RLS policy for portfolios
-- Users can access:
-- 1. Their personal portfolios (org_id IS NULL AND user_id matches)
-- 2. Organization portfolios they are members of (org_id matches their org membership)
CREATE POLICY portfolios_dual_access ON portfolios
    FOR ALL
    USING (
        -- Personal portfolios: no org_id and user owns it
        (org_id IS NULL AND user_id = current_setting('app.current_user_id', true)::TEXT)
        OR
        -- Organization portfolios: org_id exists and user is member
        (org_id IS NOT NULL AND org_id IN (
            SELECT org_id
            FROM organization_members
            WHERE user_id = current_setting('app.current_user_id', true)::TEXT
        ))
    );

-- Update files table RLS policies if the table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        -- Drop existing policy
        DROP POLICY IF EXISTS files_user_access ON files;

        -- Create new dual-access policy
        EXECUTE 'CREATE POLICY files_dual_access ON files
            FOR ALL
            USING (
                (org_id IS NULL AND user_id = current_setting(''app.current_user_id'', true)::TEXT)
                OR
                (org_id IS NOT NULL AND org_id IN (
                    SELECT org_id
                    FROM organization_members
                    WHERE user_id = current_setting(''app.current_user_id'', true)::TEXT
                ))
            )';
    END IF;
END $$;

-- Add check constraint to ensure either user_id or org_id is set (not both)
-- This maintains clean separation between personal and org resources
ALTER TABLE portfolios
    ADD CONSTRAINT portfolios_owner_check
    CHECK (
        (user_id IS NOT NULL AND org_id IS NULL) OR
        (user_id IS NULL AND org_id IS NOT NULL)
    );

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        ALTER TABLE files
            ADD CONSTRAINT files_owner_check
            CHECK (
                (user_id IS NOT NULL AND org_id IS NULL) OR
                (user_id IS NULL AND org_id IS NOT NULL)
            );
    END IF;
END $$;

-- Comments for documentation
COMMENT ON COLUMN portfolios.org_id IS 'Organization ID for shared portfolios (NULL for personal portfolios)';
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        EXECUTE 'COMMENT ON COLUMN files.org_id IS ''Organization ID for shared files (NULL for personal files)''';
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
