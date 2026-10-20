"""
044_export_styles

Revision ID: 4f962021da59
Revises: d532aeb24d17
Create Date: 2025-12-31T16:05:17.200391

Original SQL file: 044_export_styles.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4f962021da59"
down_revision = "d532aeb24d17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 044_export_styles.sql."""
    op.execute("""
-- Export Styles Migration
-- Converts single global export settings to multiple named styles (presets)
-- Following CODING_RULES.md: KISS, MVP first, no hardcoding
-- January 2025

-- Step 1: Create new table with updated schema
CREATE TABLE IF NOT EXISTS user_export_styles_new (
    user_id TEXT NOT NULL,
    style_name TEXT NOT NULL CHECK (LENGTH(style_name) > 0 AND LENGTH(style_name) <= 50),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, style_name)
);

-- Step 2: Create index for quick default style lookup
CREATE INDEX IF NOT EXISTS idx_user_export_styles_default ON user_export_styles_new(user_id, is_default) WHERE is_default = true;

-- Step 3: Create index for updated_at (useful for admin queries)
CREATE INDEX IF NOT EXISTS idx_user_export_styles_updated_at ON user_export_styles_new(updated_at DESC);

-- Step 4: Add unique constraint - only one default style per user
-- PostgreSQL partial unique index serves as the constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_export_styles_one_default
    ON user_export_styles_new(user_id)
    WHERE is_default = true;

-- Step 5: Migrate existing data from old table to new table as "Default" style
-- Only if old table exists and has data
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_export_settings') THEN
        -- Migrate existing settings to "Default" style
        INSERT INTO user_export_styles_new (user_id, style_name, settings, is_default, created_at, updated_at)
        SELECT
            user_id,
            'Default' as style_name,
            settings,
            true as is_default,
            created_at,
            updated_at
        FROM user_export_settings
        ON CONFLICT (user_id, style_name) DO NOTHING;

        RAISE NOTICE 'Migrated existing export settings to Default style';
    ELSE
        RAISE NOTICE 'No existing user_export_settings table to migrate';
    END IF;
END $$;

-- Step 6: Drop old table and rename new table
DROP TABLE IF EXISTS user_export_settings CASCADE;
ALTER TABLE user_export_styles_new RENAME TO user_export_settings;

-- Step 7: Enable RLS on new table
ALTER TABLE user_export_settings ENABLE ROW LEVEL SECURITY;

-- Step 8: Drop old policy if it exists (from migration 043)
DROP POLICY IF EXISTS user_export_settings_isolation ON user_export_settings;

-- Step 9: Create RLS policy (user sees only their own styles)
CREATE POLICY user_export_settings_isolation ON user_export_settings
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Step 10: Add constraint function to limit max 10 styles per user
CREATE OR REPLACE FUNCTION check_max_export_styles()
RETURNS TRIGGER AS $$
DECLARE
    style_count INTEGER;
BEGIN
    -- Count existing styles for this user
    SELECT COUNT(*) INTO style_count
    FROM user_export_settings
    WHERE user_id = NEW.user_id;

    -- Allow if updating existing style
    IF TG_OP = 'UPDATE' THEN
        RETURN NEW;
    END IF;

    -- Check limit for new inserts
    IF style_count >= 10 THEN
        RAISE EXCEPTION 'Maximum 10 export styles per user. Delete an existing style before creating a new one.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 11: Create trigger to enforce max styles limit
DROP TRIGGER IF EXISTS enforce_max_export_styles ON user_export_settings;
CREATE TRIGGER enforce_max_export_styles
    BEFORE INSERT ON user_export_settings
    FOR EACH ROW
    EXECUTE FUNCTION check_max_export_styles();

-- Step 12: Add constraint function to prevent deleting last/default style
CREATE OR REPLACE FUNCTION prevent_delete_default_style()
RETURNS TRIGGER AS $$
DECLARE
    style_count INTEGER;
BEGIN
    -- Count remaining styles for this user
    SELECT COUNT(*) INTO style_count
    FROM user_export_settings
    WHERE user_id = OLD.user_id;

    -- Prevent deletion if it's the only style
    IF style_count = 1 THEN
        RAISE EXCEPTION 'Cannot delete the only export style. Create another style first.';
    END IF;

    -- Prevent deletion if it's the default style
    IF OLD.is_default = true THEN
        RAISE EXCEPTION 'Cannot delete the default export style. Set another style as default first.';
    END IF;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Step 13: Create trigger to prevent default style deletion
DROP TRIGGER IF EXISTS prevent_default_style_deletion ON user_export_settings;
CREATE TRIGGER prevent_default_style_deletion
    BEFORE DELETE ON user_export_settings
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete_default_style();

-- Step 14: Apply updated_at trigger (function already exists from 000_initial_schema.sql)
DROP TRIGGER IF EXISTS update_user_export_settings_updated_at ON user_export_settings;
CREATE TRIGGER update_user_export_settings_updated_at
    BEFORE UPDATE ON user_export_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Step 15: Grant necessary permissions (MVP - single app user)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON user_export_settings TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

-- Step 16: Add comments for documentation
COMMENT ON TABLE user_export_settings IS 'User export style presets for Gamma API (themes, logos, prompts, language, verbosity, tone, audience). Each user can save up to 10 named styles. One style must be marked as default.';
COMMENT ON COLUMN user_export_settings.style_name IS 'User-defined name for this export style (max 50 chars). Examples: "Default", "Executive Summary", "Technical Deep Dive".';
COMMENT ON COLUMN user_export_settings.settings IS 'JSONB structure: {custom_prompt, theme_id, logo_source, logo_file_id, logo_url, logo_position, logo_size, language, verbosity, tone, audience}';
COMMENT ON COLUMN user_export_settings.is_default IS 'Whether this is the default style used when no style explicitly selected. Only one default per user.';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
