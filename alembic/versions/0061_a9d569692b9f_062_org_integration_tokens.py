"""
062_org_integration_tokens

Revision ID: a9d569692b9f
Revises: 69a63db95da5
Create Date: 2025-12-31T16:05:17.208390

Original SQL file: 062_org_integration_tokens.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9d569692b9f"
down_revision = "69a63db95da5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 062_org_integration_tokens.sql."""
    op.execute("""
-- Add org_id to OneDrive and Google Drive credentials for org-level tokens
-- Personal tokens: org_id = '' (empty string)
-- Org tokens: org_id = 'org_xxx' (Clerk org ID)

-- OneDrive
ALTER TABLE onedrive_credentials ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_onedrive_credentials_org_id ON onedrive_credentials(org_id);

-- Update unique constraint to allow one credential per user OR per org
DROP INDEX IF EXISTS idx_onedrive_credentials_user_drive;
CREATE UNIQUE INDEX idx_onedrive_credentials_user_org_drive 
    ON onedrive_credentials(user_id, org_id, drive_user_id);

-- Update RLS: users see their personal tokens OR their org's shared token
DROP POLICY IF EXISTS onedrive_credentials_isolation ON onedrive_credentials;
CREATE POLICY onedrive_credentials_isolation ON onedrive_credentials
    FOR ALL
    USING (
        -- Personal token (org_id empty, user matches)
        (org_id = '' AND user_id = current_setting('app.current_user_id', true))
        OR
        -- Org token (org_id matches current org context)
        (org_id != '' AND org_id = current_setting('app.current_org_id', true))
    );

-- Google Drive (same pattern)
ALTER TABLE google_drive_credentials ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_google_drive_credentials_org_id ON google_drive_credentials(org_id);

DROP INDEX IF EXISTS idx_google_drive_credentials_user_drive;
CREATE UNIQUE INDEX idx_google_drive_credentials_user_org_drive 
    ON google_drive_credentials(user_id, org_id, drive_user_id);

DROP POLICY IF EXISTS google_drive_credentials_isolation ON google_drive_credentials;
CREATE POLICY google_drive_credentials_isolation ON google_drive_credentials
    FOR ALL
    USING (
        (org_id = '' AND user_id = current_setting('app.current_user_id', true))
        OR
        (org_id != '' AND org_id = current_setting('app.current_org_id', true))
    );

COMMENT ON COLUMN onedrive_credentials.org_id IS 'Empty for personal tokens, org ID for shared org tokens';
COMMENT ON COLUMN google_drive_credentials.org_id IS 'Empty for personal tokens, org ID for shared org tokens';


""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
