"""
055_org_metadata_and_fk_fix

Revision ID: 0e0ecf070ffb
Revises: d898096e0410
Create Date: 2025-12-31T16:05:17.205393

Original SQL file: 055_org_metadata_and_fk_fix.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0e0ecf070ffb"
down_revision = "d898096e0410"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 055_org_metadata_and_fk_fix.sql."""
    op.execute("""
-- Migration 055: Fix organization FK race condition and ensure metadata defaults
--
-- Fixes:
-- 1. Drop FK constraint on organizations.creator_id to prevent webhook race condition
-- 2. Ensure public_metadata and private_metadata have proper defaults
--
-- Date: 2025-11-17

-- Drop the problematic foreign key constraint
ALTER TABLE organizations
DROP CONSTRAINT IF EXISTS organizations_creator_id_fkey;

-- Ensure metadata columns have proper defaults (should already exist from migration 046)
ALTER TABLE organizations
ALTER COLUMN public_metadata SET DEFAULT '{}'::jsonb,
ALTER COLUMN private_metadata SET DEFAULT '{}'::jsonb;

-- Add index on creator_id for performance (still useful even without FK)
CREATE INDEX IF NOT EXISTS idx_organizations_creator_id ON organizations(creator_id);

-- Add comment explaining why we don't have FK
COMMENT ON COLUMN organizations.creator_id IS 'Clerk user ID of organization creator. No FK constraint to avoid webhook race conditions.';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
