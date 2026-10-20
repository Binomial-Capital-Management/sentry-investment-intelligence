"""
026_slack_integrations

Revision ID: 623f3295de9d
Revises: de3857f13f6c
Create Date: 2025-12-31T16:05:17.191167

Original SQL file: 026_slack_integrations.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "623f3295de9d"
down_revision = "de3857f13f6c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 026_slack_integrations.sql."""
    op.execute("""
-- Slack integrations storage with RLS
CREATE TABLE IF NOT EXISTS slack_integrations (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    team_name TEXT,
    bot_user_id TEXT,
    authed_user_id TEXT,
    access_token_encrypted TEXT NOT NULL,
    scope TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_slack_integrations_user_team
    ON slack_integrations(user_id, team_id);

ALTER TABLE slack_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_integrations FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS slack_integrations_isolation ON slack_integrations;
CREATE POLICY slack_integrations_isolation ON slack_integrations
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

DROP TRIGGER IF EXISTS update_slack_integrations_updated_at ON slack_integrations;
CREATE TRIGGER update_slack_integrations_updated_at
    BEFORE UPDATE ON slack_integrations
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
