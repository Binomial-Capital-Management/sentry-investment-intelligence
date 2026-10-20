"""
030_add_cash_balance_to_portfolios

Revision ID: 2ab6a94fdc66
Revises: 3f5b05c0522a
Create Date: 2025-12-31T16:05:17.193382

Original SQL file: 030_add_cash_balance_to_portfolios.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2ab6a94fdc66"
down_revision = "3f5b05c0522a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 030_add_cash_balance_to_portfolios.sql."""
    op.execute("""
-- Migration: Add cash_balance to portfolios table
-- Description: Enable cash management and buy/sell trading functionality
-- Date: 2025-01-08

-- Add cash_balance column to portfolios table
ALTER TABLE portfolios
ADD COLUMN IF NOT EXISTS cash_balance NUMERIC DEFAULT 0 NOT NULL;

-- Add check constraint to prevent negative cash balances
ALTER TABLE portfolios
ADD CONSTRAINT portfolios_cash_balance_check CHECK (cash_balance >= 0);

-- Create index for performance on cash balance queries
CREATE INDEX IF NOT EXISTS idx_portfolios_cash_balance ON portfolios(cash_balance);

-- Add comment for documentation
COMMENT ON COLUMN portfolios.cash_balance IS 'Cash balance in USD available for trading';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
