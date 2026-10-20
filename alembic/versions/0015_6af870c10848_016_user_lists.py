"""
016_user_lists

Revision ID: 6af870c10848
Revises: bdf62a89fc8e
Create Date: 2025-12-31T16:05:17.186165

Original SQL file: 016_user_lists.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6af870c10848"
down_revision = "bdf62a89fc8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 016_user_lists.sql."""
    op.execute("""
-- User Lists Migration (Tracker Lists + Screeners)
-- Following CODING_RULES.md: KISS, MVP first, no over-engineering
-- October 2025

-- Create user_lists table for both tracker lists (manual) and screeners (filtered)
CREATE TABLE IF NOT EXISTS user_lists (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,  -- Clerk user ID
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('tracker', 'screener')),

    -- For tracker lists: manual tickers array
    tickers TEXT[],

    -- For screeners: FMP filter parameters as JSONB
    screener_filters JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Validation: trackers must have tickers, screeners must have filters
    CONSTRAINT check_tracker_has_tickers CHECK (
        (type = 'tracker' AND tickers IS NOT NULL AND array_length(tickers, 1) > 0) OR
        type = 'screener'
    ),
    CONSTRAINT check_screener_has_filters CHECK (
        (type = 'screener' AND screener_filters IS NOT NULL) OR
        type = 'tracker'
    )
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_lists_user_id ON user_lists(user_id);
CREATE INDEX IF NOT EXISTS idx_user_lists_type ON user_lists(type);
CREATE INDEX IF NOT EXISTS idx_user_lists_user_type ON user_lists(user_id, type);

-- Enable RLS
ALTER TABLE user_lists ENABLE ROW LEVEL SECURITY;

-- Drop existing policy if exists
DROP POLICY IF EXISTS user_lists_isolation ON user_lists;

-- Create RLS policy for user isolation
CREATE POLICY user_lists_isolation ON user_lists
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Create updated_at trigger function if not exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger for updated_at
DROP TRIGGER IF EXISTS update_user_lists_updated_at ON user_lists;
CREATE TRIGGER update_user_lists_updated_at
    BEFORE UPDATE ON user_lists
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
