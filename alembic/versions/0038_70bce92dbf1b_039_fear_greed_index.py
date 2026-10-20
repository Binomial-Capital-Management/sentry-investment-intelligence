"""
039_fear_greed_index

Revision ID: 70bce92dbf1b
Revises: c9b1a5abba74
Create Date: 2025-12-31T16:05:17.197390

Original SQL file: 039_fear_greed_index.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "70bce92dbf1b"
down_revision = "c9b1a5abba74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 039_fear_greed_index.sql."""
    op.execute("""
-- Migration 039: Add Fear and Greed Index table
-- This table stores market sentiment data from CNN Fear & Greed Index
-- No RLS policies needed - this is public market data for all users

CREATE TABLE IF NOT EXISTS fear_greed_index (
    id SERIAL PRIMARY KEY,
    value INT NOT NULL CHECK (value >= 0 AND value <= 100),
    value_text VARCHAR(50) NOT NULL,
    previous_close_value INT CHECK (previous_close_value >= 0 AND previous_close_value <= 100),
    previous_close_text VARCHAR(50),
    last_updated TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP DEFAULT NOW()
);

-- Index for quick lookup of latest data
CREATE INDEX IF NOT EXISTS idx_fgi_fetched_at ON fear_greed_index(fetched_at DESC);

-- Add comment for documentation
COMMENT ON TABLE fear_greed_index IS 'Stores CNN Fear & Greed Index data updated at 8am and 2pm ET on weekdays';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
