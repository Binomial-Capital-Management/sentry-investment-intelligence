"""
038_user_insights

Revision ID: c9b1a5abba74
Revises: b9e44963a742
Create Date: 2025-12-31T16:05:17.197390

Original SQL file: 038_user_insights.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9b1a5abba74"
down_revision = "b9e44963a742"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 038_user_insights.sql."""
    op.execute("""
-- User Insights Migration for AI-Generated Dashboard Insights
-- Following CODING_RULES.md: KISS, MVP first, no hardcoding
-- Stores personalized insights generated daily by InsightGeneratorAgent
-- January 2025

-- Create user_insights table
-- page_type: 'markets', 'crypto', or 'macro' (matches dashboard pills)
-- priority: 1-10 (higher = more important, used for ranking/sorting)
-- content: Flexible JSONB for different insight structures
-- expires_at: Auto-cleanup old insights (default 24 hours)
CREATE TABLE IF NOT EXISTS user_insights (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,  -- Clerk user ID (text format)
    page_type VARCHAR(20) NOT NULL CHECK (page_type IN ('markets', 'crypto', 'macro')),
    title TEXT NOT NULL,
    content JSONB NOT NULL,  -- Flexible structure: { "text": "...", "data": {...}, "source": "..." }
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    is_read BOOLEAN DEFAULT FALSE,
    metadata JSONB,  -- Extensible for future fields (tags, categories, etc.)
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours'),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance (KISS - only essential indexes)
-- Index for fetching user's insights by page type (most common query)
CREATE INDEX IF NOT EXISTS idx_user_insights_user_page ON user_insights(user_id, page_type, priority DESC, generated_at DESC);

-- Index for cleanup job (delete expired insights)
CREATE INDEX IF NOT EXISTS idx_user_insights_expires_at ON user_insights(expires_at);

-- Index for unread insights query
CREATE INDEX IF NOT EXISTS idx_user_insights_unread ON user_insights(user_id, is_read, generated_at DESC) WHERE NOT is_read;

-- Enable RLS on user_insights table
ALTER TABLE user_insights ENABLE ROW LEVEL SECURITY;

-- Drop existing policy if it exists (idempotent)
DROP POLICY IF EXISTS user_insights_isolation ON user_insights;

-- Create RLS policy (KISS - user sees only their data)
-- Using current_setting for runtime context (August 2025 best practice)
CREATE POLICY user_insights_isolation ON user_insights
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Apply updated_at trigger (function already exists from 000_initial_schema.sql)
DROP TRIGGER IF EXISTS update_user_insights_updated_at ON user_insights;
CREATE TRIGGER update_user_insights_updated_at
    BEFORE UPDATE ON user_insights
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Grant necessary permissions (MVP - single app user)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON user_insights TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

-- Add comment for documentation
COMMENT ON TABLE user_insights IS 'AI-generated personalized insights for dashboard Quick Insights section. Generated daily by InsightScheduler at 6 AM ET. Auto-expires after 24 hours.';
COMMENT ON COLUMN user_insights.page_type IS 'Dashboard pill type: markets, crypto, or macro';
COMMENT ON COLUMN user_insights.priority IS 'Priority 1-10 (higher = more important) for ranking insights';
COMMENT ON COLUMN user_insights.content IS 'Flexible JSONB structure: { "text": "insight text", "data": {...}, "source": "..." }';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
