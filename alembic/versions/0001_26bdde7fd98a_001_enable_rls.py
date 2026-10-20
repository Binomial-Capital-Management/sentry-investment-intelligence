"""
001_enable_rls

Revision ID: 26bdde7fd98a
Revises: 8c9fa9c085bf
Create Date: 2025-12-31T16:05:17.177902

Original SQL file: 001_enable_rls.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "26bdde7fd98a"
down_revision = "8c9fa9c085bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 001_enable_rls.sql."""
    op.execute("""
-- RLS Migration for Binomial Risk Analyst V6
-- Following CODING_RULES.md: KISS, MVP first, no over-engineering
-- August 2025 best practice: Use runtime context instead of PostgreSQL users

-- Use safe UUID generator function defined in 000; attempt extension quietly
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp') THEN
    BEGIN
      CREATE EXTENSION "uuid-ossp";
    EXCEPTION
      WHEN insufficient_privilege THEN
        RAISE NOTICE 'Skipping uuid-ossp extension creation (insufficient privileges)';
      WHEN undefined_file THEN
        RAISE NOTICE 'uuid-ossp extension not available on this server';
      WHEN feature_not_supported THEN
        RAISE NOTICE 'uuid-ossp extension not installed on this server';
      WHEN OTHERS THEN
        RAISE NOTICE 'Could not create uuid-ossp extension: %', SQLERRM;
    END;
  END IF;
END
$$;

-- Create portfolios table (KISS - only essential fields)
-- Note: Weights validation done in application layer (PostgreSQL doesn't allow subqueries in CHECK constraints)
CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    tickers TEXT[] NOT NULL,
    weights FLOAT[] NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Update risk_analyses table if exists, create if not
CREATE TABLE IF NOT EXISTS risk_analyses (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE SET NULL,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    analysis_type VARCHAR(50) NOT NULL,
    tickers TEXT[],
    results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance (KISS - only essential indexes)
CREATE INDEX IF NOT EXISTS idx_portfolios_user_id ON portfolios(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_risk_analyses_user_id ON risk_analyses(user_id);

-- Enable RLS on all user tables
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_analyses ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS portfolios_isolation ON portfolios;
DROP POLICY IF EXISTS chat_sessions_isolation ON chat_sessions;
DROP POLICY IF EXISTS chat_messages_isolation ON chat_messages;
DROP POLICY IF EXISTS risk_analyses_isolation ON risk_analyses;

-- Create simple RLS policies (KISS - user sees only their data)
-- Using current_setting for runtime context (Aug 2025 best practice)
CREATE POLICY portfolios_isolation ON portfolios
    FOR ALL
    USING (user_id::text = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', true));

CREATE POLICY chat_sessions_isolation ON chat_sessions
    FOR ALL
    USING (user_id::text = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', true));

CREATE POLICY chat_messages_isolation ON chat_messages
    FOR ALL
    USING (user_id::text = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', true));

CREATE POLICY risk_analyses_isolation ON risk_analyses
    FOR ALL
    USING (user_id::text = current_setting('app.current_user_id', true))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', true));

-- Use the updated_at trigger function from 000_initial_schema.sql
-- (Function already exists, no need to recreate)

-- Apply updated_at triggers
DROP TRIGGER IF EXISTS update_portfolios_updated_at ON portfolios;
CREATE TRIGGER update_portfolios_updated_at
    BEFORE UPDATE ON portfolios
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grant necessary permissions (MVP - single app user)
-- Grant minimal privileges to application role if it exists; avoid PUBLIC grants
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON portfolios TO binomial_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON chat_sessions TO binomial_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON chat_messages TO binomial_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON risk_analyses TO binomial_app;
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
