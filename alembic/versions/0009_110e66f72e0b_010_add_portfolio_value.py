"""
010_add_portfolio_value

Revision ID: 110e66f72e0b
Revises: 8e70ddaa4ca4
Create Date: 2025-12-31T16:05:17.183169

Original SQL file: 010_add_portfolio_value.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "110e66f72e0b"
down_revision = "8e70ddaa4ca4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 010_add_portfolio_value.sql."""
    op.execute("""
-- Migration 010: Add portfolio value and metadata columns
-- Adds value field to track portfolio total value
-- Adds metadata JSONB for future extensibility

-- Add value column with default of 1,000,000 USD
ALTER TABLE portfolios 
    ADD COLUMN IF NOT EXISTS value DECIMAL(20, 2) DEFAULT 1000000;

-- Add metadata column (referenced in code but was missing)
ALTER TABLE portfolios 
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Create index on value for performance when filtering/sorting by portfolio size
CREATE INDEX IF NOT EXISTS idx_portfolios_value ON portfolios(value);

-- Update existing portfolios to have explicit value if needed
-- (Default already handles this, but being explicit for clarity)
UPDATE portfolios 
SET value = 1000000 
WHERE value IS NULL;
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
