"""
020_portfolio_value_history

Revision ID: f6488f380271
Revises: 27da5d1d493b
Create Date: 2025-12-31T16:05:17.187166

Original SQL file: 020_portfolio_value_history.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6488f380271"
down_revision = "27da5d1d493b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 020_portfolio_value_history.sql."""
    op.execute("""
-- Migration: Portfolio Value History Tracking
-- Purpose: Track daily portfolio values for charting and performance analysis
-- Created: 2025-01-19

-- Create portfolio_value_history table
CREATE TABLE IF NOT EXISTS portfolio_value_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    snapshot_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_value NUMERIC(20, 2) NOT NULL,
    holdings_snapshot JSONB NOT NULL,
    prices_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create unique index: one snapshot per portfolio per day (using immutable date cast)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_portfolio_date
    ON portfolio_value_history(portfolio_id, CAST((snapshot_date AT TIME ZONE 'UTC') AS date));

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_portfolio_value_history_portfolio_id
    ON portfolio_value_history(portfolio_id);

CREATE INDEX IF NOT EXISTS idx_portfolio_value_history_user_id
    ON portfolio_value_history(user_id);

CREATE INDEX IF NOT EXISTS idx_portfolio_value_history_date
    ON portfolio_value_history(snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_portfolio_value_history_user_date
    ON portfolio_value_history(user_id, snapshot_date DESC);

-- Create GIN indexes for JSONB columns
CREATE INDEX IF NOT EXISTS idx_portfolio_value_history_holdings_gin
    ON portfolio_value_history USING gin(holdings_snapshot);

CREATE INDEX IF NOT EXISTS idx_portfolio_value_history_prices_gin
    ON portfolio_value_history USING gin(prices_snapshot);

-- Enable Row Level Security
ALTER TABLE portfolio_value_history ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own portfolio history
CREATE POLICY portfolio_value_history_user_isolation ON portfolio_value_history
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', TRUE));

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON portfolio_value_history TO postgres;

-- Add comment
COMMENT ON TABLE portfolio_value_history IS 'Daily snapshots of portfolio values for historical tracking and charting';
COMMENT ON COLUMN portfolio_value_history.snapshot_date IS 'Timestamp of the snapshot (typically 5 PM ET on weekdays)';
COMMENT ON COLUMN portfolio_value_history.total_value IS 'Total portfolio value at snapshot time';
COMMENT ON COLUMN portfolio_value_history.holdings_snapshot IS 'Full holdings data at snapshot time';
COMMENT ON COLUMN portfolio_value_history.prices_snapshot IS 'Market prices at snapshot time';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
