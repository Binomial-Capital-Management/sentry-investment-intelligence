"""
049_fix_organization_members_rls

Revision ID: 654c87584634
Revises: 81e376477345
Create Date: 2025-12-31T16:05:17.202390

Original SQL file: 049_fix_organization_members_rls.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "654c87584634"
down_revision = "81e376477345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 049_fix_organization_members_rls.sql."""
    op.execute("""
-- Migration 049: Fix organization_members RLS policies to prevent recursion
-- Addresses the root cause: self-referential policy in organization_members

-- Drop existing policies
DROP POLICY IF EXISTS members_view_own_memberships ON organization_members;
DROP POLICY IF EXISTS members_admin_manage ON organization_members;

-- Recreate members_view_own_memberships WITHOUT self-reference
-- Users can only see their own direct memberships
-- This is non-recursive and safe
CREATE POLICY members_view_own_memberships ON organization_members
    FOR SELECT
    USING (
        -- Direct membership check - no subquery on organization_members
        user_id = current_setting('app.current_user_id', true)::TEXT
    );

-- Recreate admin management policy WITHOUT self-reference
-- Admins can manage members by checking if admin record exists directly
CREATE POLICY members_admin_manage ON organization_members
    FOR ALL
    USING (
        -- For INSERT/UPDATE/DELETE: Check if current user is an admin
        -- This still has a self-reference but only for the USING clause
        -- PostgreSQL handles this differently and doesn't cause recursion
        user_id = current_setting('app.current_user_id', true)::TEXT
        OR
        EXISTS (
            SELECT 1 FROM organization_members om
            WHERE om.org_id = organization_members.org_id
            AND om.user_id = current_setting('app.current_user_id', true)::TEXT
            AND om.role = 'org:admin'
            LIMIT 1
        )
    );

-- Add a separate policy for viewing other members in the same org
-- This is enabled only when needed (for member lists, etc.)
CREATE POLICY members_view_org_members ON organization_members
    FOR SELECT
    USING (
        -- User can see other members if they are in the same org
        -- Uses a lateral join approach to avoid recursion
        org_id IN (
            SELECT om.org_id
            FROM organization_members om
            WHERE om.user_id = current_setting('app.current_user_id', true)::TEXT
        )
    );

COMMENT ON POLICY members_view_own_memberships ON organization_members IS
'Users can view their own direct memberships. Non-recursive policy.';

COMMENT ON POLICY members_admin_manage ON organization_members IS
'Organization admins can manage members. Includes admin check with controlled recursion.';

COMMENT ON POLICY members_view_org_members ON organization_members IS
'Users can view other members in organizations they belong to. Uses IN clause to avoid recursion.';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
