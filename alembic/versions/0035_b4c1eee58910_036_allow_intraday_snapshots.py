"""
036_allow_intraday_snapshots

Revision ID: b4c1eee58910
Revises: 52a1353a9d9d
Create Date: 2025-12-31T16:05:17.196388

Original SQL file: 036_allow_intraday_snapshots.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4c1eee58910"
down_revision = "52a1353a9d9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 036_allow_intraday_snapshots.sql."""
    op.execute("""
-- Migration 036: Allow multiple portfolio snapshots per day
-- Changes unique constraint to allow intraday snapshots with different timestamps
-- This enables:
--   1. Testing/development with manual snapshots
--   2. Building historical data quickly
--   3. Future intraday tracking feature

-- Drop the old unique constraint that only allowed one snapshot per day
DROP INDEX IF EXISTS idx_unique_portfolio_date;

-- Create new index that allows multiple snapshots per day
-- But still prevents exact duplicate timestamps (which would be a bug)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_portfolio_timestamp
ON portfolio_value_history (portfolio_id, snapshot_date);

-- Add index for efficient date-based queries (used by history API)
CREATE INDEX IF NOT EXISTS idx_portfolio_history_date
ON portfolio_value_history (portfolio_id, snapshot_date DESC);

-- Add comment for documentation
COMMENT ON INDEX idx_unique_portfolio_timestamp IS
'Allows multiple snapshots per portfolio per day, but prevents duplicate timestamps';

COMMENT ON INDEX idx_portfolio_history_date IS
'Optimizes portfolio history queries by date range';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
