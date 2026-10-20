"""
057_portfolio_postmortems

Revision ID: 1be72938d15f
Revises: 1e89a5ee31e5
Create Date: 2025-12-31T16:05:17.206388

Original SQL file: 057_portfolio_postmortems.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1be72938d15f"
down_revision = "1e89a5ee31e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 057_portfolio_postmortems.sql."""
    op.execute("""
-- Migration: Create portfolio_postmortems table
-- Purpose: Store saved post-mortem analyses of trading transactions

-- Create portfolio_postmortems table
CREATE TABLE IF NOT EXISTS portfolio_postmortems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    transaction_ids TEXT[] NOT NULL,  -- Array of transaction IDs
    title TEXT,  -- Optional title for the post-mortem
    notes TEXT,  -- User notes or AI-generated insights
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_portfolio_postmortems_user_id ON portfolio_postmortems(user_id);
CREATE INDEX idx_portfolio_postmortems_created_at ON portfolio_postmortems(created_at DESC);

-- Enable RLS
ALTER TABLE portfolio_postmortems ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own post-mortems
CREATE POLICY postmortems_isolation_policy ON portfolio_postmortems
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

-- Grant permissions (only if role exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON portfolio_postmortems TO binomial_app;
    END IF;
END $$;

-- Add comment
COMMENT ON TABLE portfolio_postmortems IS 'Stores post-mortem analyses of trading transactions for review and insights';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
