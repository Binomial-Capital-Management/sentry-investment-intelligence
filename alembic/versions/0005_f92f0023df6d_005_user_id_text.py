"""
005_user_id_text

Revision ID: f92f0023df6d
Revises: 483e9f54e9e1
Create Date: 2025-12-31T16:05:17.181179

Original SQL file: 005_user_id_text.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f92f0023df6d"
down_revision = "483e9f54e9e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 005_user_id_text.sql."""
    op.execute("""
-- Migration 005: Change user_id columns from UUID to TEXT for Clerk compatibility
-- Clerk user IDs are strings like 'user_2aBcDeFgHiJkLmNoPqRsTuVwXyZ', not UUIDs

-- DROP all policies FIRST (before ALTER TABLE)
DROP POLICY IF EXISTS portfolios_isolation ON portfolios;
DROP POLICY IF EXISTS chat_sessions_isolation ON chat_sessions;
DROP POLICY IF EXISTS chat_messages_isolation ON chat_messages;
DROP POLICY IF EXISTS risk_analyses_isolation ON risk_analyses;

-- Drop ALL files policies if table exists
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'files') THEN
        DROP POLICY IF EXISTS files_isolation ON files;
        DROP POLICY IF EXISTS files_select_own ON files;
        DROP POLICY IF EXISTS files_insert_own ON files;
        DROP POLICY IF EXISTS files_update_own ON files;
        DROP POLICY IF EXISTS files_delete_own ON files;
    END IF;
END $$;

-- DROP foreign key constraints BEFORE changing column types
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_user_id_fkey;
ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_user_id_fkey;
ALTER TABLE portfolios DROP CONSTRAINT IF EXISTS portfolios_user_id_fkey;
ALTER TABLE risk_analyses DROP CONSTRAINT IF EXISTS risk_analyses_user_id_fkey;

-- Drop files foreign key if table exists
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'files') THEN
        ALTER TABLE files DROP CONSTRAINT IF EXISTS files_user_id_fkey;
    END IF;
END $$;

-- ALTER all user_id columns to TEXT (using explicit cast)
ALTER TABLE chat_sessions ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE chat_messages ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE portfolios ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE risk_analyses ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;


-- Safely alter files.user_id to TEXT (only if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'files') THEN
        IF EXISTS (SELECT FROM information_schema.columns 
                   WHERE table_name = 'files' AND column_name = 'user_id') THEN
            ALTER TABLE files ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
        END IF;
    END IF;
END $$;

-- Recreate files isolation policy if table exists
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'files') THEN
        -- Create the isolation policy
        EXECUTE 'CREATE POLICY files_isolation ON files
            FOR ALL
            USING (user_id = current_setting(''app.current_user_id'', true))
            WITH CHECK (user_id = current_setting(''app.current_user_id'', true))';
    END IF;
EXCEPTION
    WHEN duplicate_object THEN
        -- Policy already exists, ignore
        NULL;
END $$;

-- DROP and RE-CREATE RLS policies to compare TEXT to TEXT (no casts)
DROP POLICY IF EXISTS portfolios_isolation ON portfolios;
CREATE POLICY portfolios_isolation ON portfolios
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS chat_sessions_isolation ON chat_sessions;
CREATE POLICY chat_sessions_isolation ON chat_sessions
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS chat_messages_isolation ON chat_messages;
CREATE POLICY chat_messages_isolation ON chat_messages
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS risk_analyses_isolation ON risk_analyses;
CREATE POLICY risk_analyses_isolation ON risk_analyses
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Recreate files RLS policy (text-to-text comparison)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'files') THEN
    DROP POLICY IF EXISTS files_isolation ON files;
    CREATE POLICY files_isolation ON files
      FOR ALL
      USING (user_id = current_setting('app.current_user_id', true))
      WITH CHECK (user_id = current_setting('app.current_user_id', true));
  END IF;
END $$;

-- STEP 4: CREATE indexes for better performance on TEXT columns
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id_text ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id_text ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_user_id_text ON portfolios(user_id);
CREATE INDEX IF NOT EXISTS idx_risk_analyses_user_id_text ON risk_analyses(user_id);

-- Ensure index exists on files.user_id (idempotent)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'files' AND column_name = 'user_id') THEN
    CREATE INDEX IF NOT EXISTS idx_files_user_id_text ON files(user_id);
  END IF;
END $$;

-- STEP 5: Update the RLS helper function to accept TEXT instead of UUID
CREATE OR REPLACE FUNCTION set_user_context(user_id TEXT) 
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_user_id', user_id, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
