"""
035_portfolio_history_unique_constraint

Revision ID: 52a1353a9d9d
Revises: abc62b9a663e
Create Date: 2025-12-31T16:05:17.195388

Original SQL file: 035_portfolio_history_unique_constraint.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "52a1353a9d9d"
down_revision = "abc62b9a663e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 035_portfolio_history_unique_constraint.sql."""
    op.execute("""
-- Migration 035: Add unique constraint to portfolio_value_history
-- Prevents duplicate snapshots for the same portfolio on the same day

-- Create unique index on portfolio_id + snapshot_date
-- The application will truncate timestamps to midnight before inserting
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_portfolio_date
ON portfolio_value_history (portfolio_id, snapshot_date);

-- Add comment for documentation
COMMENT ON INDEX idx_unique_portfolio_date IS
'Ensures only one value snapshot per portfolio per timestamp (application truncates to midnight)';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
