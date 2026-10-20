"""
059_postmortem_transactions_junction

Revision ID: 15e8ad494012
Revises: 03057220d7ee
Create Date: 2025-12-31T16:05:17.207388

Original SQL file: 059_postmortem_transactions_junction.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "15e8ad494012"
down_revision = "03057220d7ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 059_postmortem_transactions_junction.sql."""
    op.execute("""
-- Migration 059: Create postmortem_transactions junction table
-- Purpose: Many-to-many relationship between post-mortems and transactions

CREATE TABLE IF NOT EXISTS postmortem_transactions (
    postmortem_id UUID NOT NULL REFERENCES portfolio_postmortems(id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES portfolio_transactions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (postmortem_id, transaction_id)
);

-- Indexes for efficient lookups
CREATE INDEX idx_postmortem_transactions_postmortem ON postmortem_transactions(postmortem_id);
CREATE INDEX idx_postmortem_transactions_transaction ON postmortem_transactions(transaction_id);

-- Enable RLS
ALTER TABLE postmortem_transactions ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own transaction associations
CREATE POLICY postmortem_transactions_isolation ON postmortem_transactions
    FOR ALL
    USING (
        postmortem_id IN (
            SELECT id FROM portfolio_postmortems
            WHERE user_id = current_setting('app.current_user_id', true)
        )
    );

-- Grant permissions (only if role exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON postmortem_transactions TO binomial_app;
    END IF;
END $$;

COMMENT ON TABLE postmortem_transactions IS 'Junction table linking post-mortems to transactions';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
