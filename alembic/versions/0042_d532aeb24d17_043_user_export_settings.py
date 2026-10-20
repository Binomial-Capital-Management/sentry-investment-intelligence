"""
043_user_export_settings

Revision ID: d532aeb24d17
Revises: 9f65c2c4a527
Create Date: 2025-12-31T16:05:17.199389

Original SQL file: 043_user_export_settings.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d532aeb24d17"
down_revision = "9f65c2c4a527"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 043_user_export_settings.sql."""
    op.execute("""
-- User Export Settings Migration
-- Following CODING_RULES.md: KISS, MVP first, no hardcoding
-- Stores user preferences for Gamma API exports (themes, logos, prompts, language)
-- Settings stored as JSONB for flexibility
-- Logos stored in S3 via existing uploads infrastructure
-- January 2025

-- Create user_export_settings table
-- Single row per user (PRIMARY KEY on user_id)
-- Settings column: JSONB with export customization preferences
CREATE TABLE IF NOT EXISTS user_export_settings (
    user_id TEXT PRIMARY KEY,  -- Clerk user ID (text format)
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,  -- Export customization settings
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for updated_at (useful for admin queries)
CREATE INDEX IF NOT EXISTS idx_user_export_settings_updated_at ON user_export_settings(updated_at DESC);

-- Enable RLS on user_export_settings table
ALTER TABLE user_export_settings ENABLE ROW LEVEL SECURITY;

-- Drop existing policy if it exists (idempotent)
DROP POLICY IF EXISTS user_export_settings_isolation ON user_export_settings;

-- Create RLS policy (user sees only their own settings)
-- Using current_setting for runtime context (best practice)
CREATE POLICY user_export_settings_isolation ON user_export_settings
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Apply updated_at trigger (function already exists from 000_initial_schema.sql)
DROP TRIGGER IF EXISTS update_user_export_settings_updated_at ON user_export_settings;
CREATE TRIGGER update_user_export_settings_updated_at
    BEFORE UPDATE ON user_export_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grant necessary permissions (MVP - single app user)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON user_export_settings TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

-- Add comment for documentation
COMMENT ON TABLE user_export_settings IS 'User export customization settings for Gamma API (themes, logos, prompts, language, verbosity, tone, audience). Logos stored in S3 via uploads table.';
COMMENT ON COLUMN user_export_settings.settings IS 'JSONB structure: {custom_prompt, theme_id, logo_source, logo_file_id, logo_url, logo_position, logo_size, language, verbosity, tone, audience}';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
