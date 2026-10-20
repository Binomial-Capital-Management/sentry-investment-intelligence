"""
034_add_broker_portfolio_link

Revision ID: abc62b9a663e
Revises: 1c061000fab8
Create Date: 2025-12-31T16:05:17.195388

Original SQL file: 034_add_broker_portfolio_link.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "abc62b9a663e"
down_revision = "1c061000fab8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 034_add_broker_portfolio_link.sql."""
    op.execute("""
-- Migration 034: Add broker portfolio linkage
-- Purpose: Link portfolios to broker connections and support multiple IBKR accounts per user
-- Date: 2025-01-10

-- Step 1: Remove unique constraint from broker_connections to allow multiple IBKR accounts per user
DROP INDEX IF EXISTS idx_broker_connections_user_broker;

-- Step 2: Add connection_name field to identify multiple broker accounts
ALTER TABLE broker_connections
ADD COLUMN connection_name TEXT NOT NULL DEFAULT 'My IBKR Account';

-- Step 3: Create new index for user-based lookups (non-unique)
CREATE INDEX idx_broker_connections_user ON broker_connections(user_id);

-- Step 4: Add broker link columns to portfolios table
ALTER TABLE portfolios
ADD COLUMN broker_connection_id UUID REFERENCES broker_connections(id) ON DELETE SET NULL;

ALTER TABLE portfolios
ADD COLUMN source_type TEXT NOT NULL DEFAULT 'manual'
CHECK (source_type IN ('manual', 'broker'));

ALTER TABLE portfolios
ADD COLUMN synced_at TIMESTAMPTZ;

-- Step 5: Create indexes for efficient filtering and joins
CREATE INDEX idx_portfolios_broker_connection ON portfolios(broker_connection_id);
CREATE INDEX idx_portfolios_source_type ON portfolios(source_type);

-- Step 6: Add helpful comments
COMMENT ON COLUMN portfolios.broker_connection_id IS 'Foreign key to broker_connections; NULL if manual portfolio';
COMMENT ON COLUMN portfolios.source_type IS 'Whether positions are manually entered (manual) or synced from broker (broker)';
COMMENT ON COLUMN portfolios.synced_at IS 'Last time positions were synced from broker; NULL if manual or never synced';
COMMENT ON COLUMN broker_connections.connection_name IS 'User-friendly name for broker account (e.g., "My IRA", "Trading Account")';

-- Step 7: Ensure RLS policies still work with new columns
-- RLS policies on portfolios table should already cover broker_connection_id
-- because they filter by user_id, which is inherited through the FK relationship

-- Verification: Check that existing manual portfolios are not affected
-- All existing portfolios should have:
--   - broker_connection_id = NULL
--   - source_type = 'manual' (from DEFAULT)
--   - synced_at = NULL

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
