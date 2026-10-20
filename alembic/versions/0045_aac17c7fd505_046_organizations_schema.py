"""
046_organizations_schema

Revision ID: aac17c7fd505
Revises: 629da5e21f0e
Create Date: 2025-12-31T16:05:17.201390

Original SQL file: 046_organizations_schema.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aac17c7fd505"
down_revision = "629da5e21f0e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 046_organizations_schema.sql."""
    op.execute("""
-- Migration 046: Organizations Schema
-- Creates organizations and organization_members tables with RLS policies

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    creator_id TEXT REFERENCES users(clerk_user_id) ON DELETE SET NULL,
    usage_credits INTEGER DEFAULT 1000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    public_metadata JSONB DEFAULT '{}',
    private_metadata JSONB DEFAULT '{}'
);

-- Organization members table
CREATE TABLE IF NOT EXISTS organization_members (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('org:admin', 'org:member')),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_creator ON organizations(creator_id);
CREATE INDEX IF NOT EXISTS idx_org_members_org_id ON organization_members(org_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user_id ON organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_role ON organization_members(org_id, role);

-- Enable RLS
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;

-- RLS Policies for organizations
-- Users can view organizations they are members of
CREATE POLICY org_member_access ON organizations
    FOR ALL
    USING (
        id IN (
            SELECT org_id
            FROM organization_members
            WHERE user_id = current_setting('app.current_user_id', true)::TEXT
        )
    );

-- RLS Policies for organization_members
-- Users can view their own memberships and other members of their orgs
CREATE POLICY members_view_own_memberships ON organization_members
    FOR SELECT
    USING (
        user_id = current_setting('app.current_user_id', true)::TEXT
        OR
        EXISTS (
            SELECT 1 FROM organization_members om
            WHERE om.org_id = organization_members.org_id
            AND om.user_id = current_setting('app.current_user_id', true)::TEXT
            LIMIT 1
        )
    );

-- Only admins can insert/update/delete members
CREATE POLICY members_admin_manage ON organization_members
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM organization_members om
            WHERE om.org_id = organization_members.org_id
            AND om.user_id = current_setting('app.current_user_id', true)::TEXT
            AND om.role = 'org:admin'
            LIMIT 1
        )
    );

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_organizations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER organizations_updated_at_trigger
    BEFORE UPDATE ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_organizations_updated_at();

-- Comments for documentation
COMMENT ON TABLE organizations IS 'Organization accounts for team collaboration';
COMMENT ON TABLE organization_members IS 'Members belonging to organizations with roles';
COMMENT ON COLUMN organizations.slug IS 'Unique URL-safe identifier for the organization';
COMMENT ON COLUMN organizations.usage_credits IS 'Shared credit pool for organization usage';
COMMENT ON COLUMN organization_members.role IS 'Member role: org:admin or org:member';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
