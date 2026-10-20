"""
056_portfolio_transactions_source_external_id

Revision ID: 1e89a5ee31e5
Revises: 0e0ecf070ffb
Create Date: 2025-12-31T16:05:17.205393

Original SQL file: 056_portfolio_transactions_source_external_id.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1e89a5ee31e5"
down_revision = "0e0ecf070ffb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 056_portfolio_transactions_source_external_id.sql."""
    op.execute("""
-- Migration 056: Extend portfolio_transactions for broker imports
-- Adds source/external_id for deduping IBKR trades and org_id alignment

ALTER TABLE portfolio_transactions
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS external_id TEXT,
    ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE;

-- Unique per-portfolio, only when external_id is present (manual entries remain unaffected)
CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_transactions_external
    ON portfolio_transactions (portfolio_id, external_id)
    WHERE external_id IS NOT NULL;

-- Helpful lookups
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_source ON portfolio_transactions(source);
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_org ON portfolio_transactions(org_id);

COMMENT ON COLUMN portfolio_transactions.source IS 'Origin of transaction (manual, ibkr, etc.)';
COMMENT ON COLUMN portfolio_transactions.external_id IS 'External trade identifier for deduplication';
COMMENT ON COLUMN portfolio_transactions.org_id IS 'Organization scope for RLS-aware broker imports';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
