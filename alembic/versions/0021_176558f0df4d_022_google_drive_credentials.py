"""
022_google_drive_credentials

Revision ID: 176558f0df4d
Revises: d42de9823793
Create Date: 2025-12-31T16:05:17.188167

Original SQL file: 022_google_drive_credentials.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "176558f0df4d"
down_revision = "d42de9823793"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 022_google_drive_credentials.sql."""
    op.execute("""
-- Google Drive Credentials Table with RLS
-- Stores encrypted refresh tokens per user with full row-level security

CREATE TABLE IF NOT EXISTS google_drive_credentials (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    drive_user_id TEXT NOT NULL,
    drive_email TEXT,
    refresh_token_encrypted TEXT NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT '{}'::text[],
    token_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure one credential per user/Drive account pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_google_drive_credentials_user_drive
    ON google_drive_credentials(user_id, drive_user_id);

CREATE INDEX IF NOT EXISTS idx_google_drive_credentials_user_id
    ON google_drive_credentials(user_id);

-- Enable RLS and force it for all roles
ALTER TABLE google_drive_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE google_drive_credentials FORCE ROW LEVEL SECURITY;

-- Isolation policy: users only see their own Drive credentials
DROP POLICY IF EXISTS google_drive_credentials_isolation ON google_drive_credentials;
CREATE POLICY google_drive_credentials_isolation ON google_drive_credentials
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Maintain updated_at column automatically
CREATE OR REPLACE FUNCTION update_google_drive_credentials_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_google_drive_credentials_updated_at ON google_drive_credentials;
CREATE TRIGGER trg_google_drive_credentials_updated_at
    BEFORE UPDATE ON google_drive_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_google_drive_credentials_updated_at();

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
