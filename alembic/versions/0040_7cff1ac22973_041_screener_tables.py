"""
041_screener_tables

Revision ID: 7cff1ac22973
Revises: a347d3b9e86a
Create Date: 2025-12-31T16:05:17.199389

Original SQL file: 041_screener_tables.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7cff1ac22973"
down_revision = "a347d3b9e86a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 041_screener_tables.sql."""
    op.execute("""
-- Migration 041: Screener Tables
-- Creates dedicated tables for AI Stock Screener feature
-- Following CODING_RULES.md: KISS, MVP first, RLS isolation

-- Create screener_sessions table
CREATE TABLE IF NOT EXISTS screener_sessions (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create screener_messages table
CREATE TABLE IF NOT EXISTS screener_messages (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    session_id UUID NOT NULL REFERENCES screener_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_screener_sessions_user_id ON screener_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_screener_messages_session_id ON screener_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_screener_messages_user_id ON screener_messages(user_id);

-- Enable RLS on both tables
ALTER TABLE screener_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE screener_messages ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS screener_sessions_isolation ON screener_sessions;
DROP POLICY IF EXISTS screener_messages_isolation ON screener_messages;

-- Create RLS policies (user sees only their data)
CREATE POLICY screener_sessions_isolation ON screener_sessions
    FOR ALL
    USING (user_id::text = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', true));

CREATE POLICY screener_messages_isolation ON screener_messages
    FOR ALL
    USING (user_id::text = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', true));

-- Apply updated_at trigger to screener_sessions
DROP TRIGGER IF EXISTS update_screener_sessions_updated_at ON screener_sessions;
CREATE TRIGGER update_screener_sessions_updated_at
    BEFORE UPDATE ON screener_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grant necessary permissions to application role
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON screener_sessions TO binomial_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON screener_messages TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
