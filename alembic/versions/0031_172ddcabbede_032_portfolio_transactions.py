"""
032_portfolio_transactions

Revision ID: 172ddcabbede
Revises: ec0ca6dea7fd
Create Date: 2025-12-31T16:05:17.194388

Original SQL file: 032_portfolio_transactions.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "172ddcabbede"
down_revision = "ec0ca6dea7fd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 032_portfolio_transactions.sql."""
    op.execute("""
-- Migration 032: Add portfolio_transactions table for proper accounting
-- This table records every buy and sell transaction with realized P&L tracking

CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,

    -- Transaction details
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
    ticker TEXT NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL CHECK (quantity > 0),
    price DECIMAL(20, 8) NOT NULL CHECK (price >= 0),
    total_amount DECIMAL(20, 8) NOT NULL,

    -- Date tracking
    transaction_date TIMESTAMP NOT NULL DEFAULT NOW(),

    -- For sells: realized P&L tracking
    cost_basis DECIMAL(20, 8), -- Total cost of shares sold (only for SELL)
    realized_gain_loss DECIMAL(20, 8), -- Proceeds - cost_basis (only for SELL)

    -- Lot tracking for audit trail
    lots_affected JSONB, -- Array of {lotId, quantity, purchasePrice, purchaseDate}

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_portfolio_transactions_portfolio ON portfolio_transactions(portfolio_id);
CREATE INDEX idx_portfolio_transactions_user ON portfolio_transactions(user_id);
CREATE INDEX idx_portfolio_transactions_ticker ON portfolio_transactions(ticker);
CREATE INDEX idx_portfolio_transactions_date ON portfolio_transactions(transaction_date DESC);
CREATE INDEX idx_portfolio_transactions_type ON portfolio_transactions(transaction_type);

-- Enable RLS
ALTER TABLE portfolio_transactions ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own transactions
CREATE POLICY portfolio_transactions_isolation_policy ON portfolio_transactions
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', TRUE));

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON portfolio_transactions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON portfolio_transactions TO anon;

-- Comments for documentation
COMMENT ON TABLE portfolio_transactions IS 'Complete audit trail of all portfolio buy and sell transactions with realized P&L tracking';
COMMENT ON COLUMN portfolio_transactions.transaction_type IS 'BUY or SELL';
COMMENT ON COLUMN portfolio_transactions.cost_basis IS 'Total cost basis of shares sold (only populated for SELL transactions)';
COMMENT ON COLUMN portfolio_transactions.realized_gain_loss IS 'Actual profit/loss on sale: proceeds - cost_basis (only for SELL)';
COMMENT ON COLUMN portfolio_transactions.lots_affected IS 'JSON array tracking which purchase lots were involved in the transaction';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
