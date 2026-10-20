"""
027_teams_integrations

Revision ID: 50f8c335bf4a
Revises: 623f3295de9d
Create Date: 2025-12-31T16:05:17.191167

Original SQL file: 027_teams_integrations.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "50f8c335bf4a"
down_revision = "623f3295de9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 027_teams_integrations.sql."""
    op.execute("""
-- Microsoft Teams integrations with RLS
CREATE TABLE IF NOT EXISTS teams_integrations (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    tenant_name TEXT,
    team_id TEXT,
    team_name TEXT,
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT,
    scope TEXT,
    token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_teams_integrations_user_tenant
    ON teams_integrations(user_id, tenant_id);

ALTER TABLE teams_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams_integrations FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS teams_integrations_isolation ON teams_integrations;
CREATE POLICY teams_integrations_isolation ON teams_integrations
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

DROP TRIGGER IF EXISTS update_teams_integrations_updated_at ON teams_integrations;
CREATE TRIGGER update_teams_integrations_updated_at
    BEFORE UPDATE ON teams_integrations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
