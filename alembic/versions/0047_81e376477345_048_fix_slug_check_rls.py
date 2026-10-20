"""
048_fix_slug_check_rls

Revision ID: 81e376477345
Revises: c5a0627a9437
Create Date: 2025-12-31T16:05:17.202390

Original SQL file: 048_fix_slug_check_rls.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "81e376477345"
down_revision = "c5a0627a9437"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 048_fix_slug_check_rls.sql."""
    op.execute("""
-- Migration 048: Fix slug availability check to bypass RLS
-- Creates a SECURITY DEFINER function for public slug checking

-- Drop existing function if it exists
DROP FUNCTION IF EXISTS public.check_organization_slug_available(TEXT);

-- Create SECURITY DEFINER function to check slug availability
-- This bypasses RLS policies safely since it only returns a boolean
-- No sensitive data is exposed
CREATE OR REPLACE FUNCTION public.check_organization_slug_available(slug_to_check TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Return TRUE if slug is available (not exists), FALSE if taken
    RETURN NOT EXISTS(
        SELECT 1
        FROM organizations
        WHERE slug = slug_to_check
    );
END;
$$;

-- Grant execute permission to authenticated users (if role exists)
-- For public endpoints, this should be accessible without auth
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.check_organization_slug_available(TEXT) TO authenticated;
    END IF;
END $$;

-- Grant execute to public for unauthenticated access
GRANT EXECUTE ON FUNCTION public.check_organization_slug_available(TEXT) TO PUBLIC;

COMMENT ON FUNCTION public.check_organization_slug_available(TEXT) IS
'Checks if an organization slug is available. Returns TRUE if available, FALSE if taken. Bypasses RLS for public slug validation.';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
