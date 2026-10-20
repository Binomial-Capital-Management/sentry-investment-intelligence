"""
060_add_org_id_to_postmortems

Revision ID: 4fe8d2e62c25
Revises: 15e8ad494012
Create Date: 2025-12-31T16:05:17.207388

Original SQL file: 060_add_org_id_to_postmortems.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4fe8d2e62c25"
down_revision = "15e8ad494012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 060_add_org_id_to_postmortems.sql."""
    op.execute("""
-- Migration: Add org_id to portfolio_postmortems for organization isolation
-- Purpose: Enable organization-scoped post-mortem analyses

-- Add org_id column to portfolio_postmortems
ALTER TABLE portfolio_postmortems ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';

-- Create index for org_id
CREATE INDEX IF NOT EXISTS idx_portfolio_postmortems_org_id ON portfolio_postmortems(org_id);

-- Drop existing RLS policy
DROP POLICY IF EXISTS postmortems_isolation_policy ON portfolio_postmortems;

-- Create new RLS policy that checks both user_id and org_id
-- Personal workspace: org_id is empty, match by user_id
-- Organization workspace: org_id matches current org setting
CREATE POLICY postmortems_isolation_policy ON portfolio_postmortems
    FOR ALL
    USING (
        user_id = current_setting('app.current_user_id', true)
        AND (
            -- Personal workspace: org_id is empty and no org context set
            (org_id = '' AND COALESCE(current_setting('app.current_org_id', true), '') = '')
            OR
            -- Organization workspace: org_id matches current org context
            (org_id != '' AND org_id = current_setting('app.current_org_id', true))
        )
    );

-- Also update postmortem_transactions junction table if it doesn't have org_id
-- (It inherits access through postmortem_id FK, but adding org_id for direct queries)
ALTER TABLE postmortem_transactions ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_postmortem_transactions_org_id ON postmortem_transactions(org_id);

COMMENT ON COLUMN portfolio_postmortems.org_id IS 'Organization ID for workspace isolation. Empty string for personal workspace.';


""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
