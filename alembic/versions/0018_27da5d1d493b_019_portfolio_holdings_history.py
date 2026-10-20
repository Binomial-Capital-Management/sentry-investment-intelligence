"""
019_portfolio_holdings_history

Revision ID: 27da5d1d493b
Revises: 2e441cb85f24
Create Date: 2025-12-31T16:05:17.187166

Original SQL file: 019_portfolio_holdings_history.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27da5d1d493b"
down_revision = "2e441cb85f24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 019_portfolio_holdings_history.sql."""
    op.execute("""
-- Migration 019: Portfolio Holdings with Purchase History
-- Adds holdings JSONB column to store detailed purchase history per ticker
-- Enables proper portfolio tracking with cost basis and gain/loss calculations

-- Add holdings column to store purchase history
-- Structure: [{"ticker": "AAPL", "quantity": 100, "purchasePrice": 150.00, "purchaseDate": "2024-01-15"}, ...]
ALTER TABLE IF EXISTS portfolios
    ADD COLUMN IF NOT EXISTS holdings JSONB DEFAULT '[]'::jsonb;

-- Add index for holdings queries (for searching within JSONB)
CREATE INDEX IF NOT EXISTS idx_portfolios_holdings_gin
    ON portfolios USING gin(holdings);

-- Add comment explaining the holdings structure
COMMENT ON COLUMN portfolios.holdings IS
'Array of holding objects with purchase history: [{"ticker": "AAPL", "quantity": 100, "purchasePrice": 150.00, "purchaseDate": "2024-01-15"}]';

-- Optional: Add a constraint to ensure holdings is always an array
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'holdings_is_array'
    ) THEN
        ALTER TABLE portfolios
            ADD CONSTRAINT holdings_is_array
            CHECK (jsonb_typeof(holdings) = 'array');
    END IF;
END
$$;

-- No RLS policy changes required; existing policies apply to new column

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
