"""
051_disable_org_members_rls

Revision ID: de9c56f47a3a
Revises: 582d68a689da
Create Date: 2025-12-31T16:05:17.203389

Original SQL file: 051_disable_org_members_rls.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "de9c56f47a3a"
down_revision = "582d68a689da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 051_disable_org_members_rls.sql."""
    op.execute("""
-- Migration 051: Disable RLS on organization_members to prevent recursion
-- organization_members is not sensitive data (just membership relationships)
-- Security is enforced at the organizations table level

-- Drop all existing policies on organization_members
DROP POLICY IF EXISTS members_view_own_memberships ON organization_members;
DROP POLICY IF EXISTS members_admin_manage ON organization_members;
DROP POLICY IF EXISTS members_view_org_members ON organization_members;

-- Disable RLS on organization_members table
-- This prevents all recursion issues since no policies will be checked
ALTER TABLE organization_members DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE organization_members IS
'Organization membership relationships. RLS disabled to prevent policy recursion. Security enforced at organizations table level.';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
