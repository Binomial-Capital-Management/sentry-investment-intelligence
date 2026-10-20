"""
050_earnings_calendar

Revision ID: 582d68a689da
Revises: 654c87584634
Create Date: 2025-12-31T16:05:17.203389

Original SQL file: 050_earnings_calendar.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "582d68a689da"
down_revision = "654c87584634"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 050_earnings_calendar.sql."""
    op.execute("""
-- Migration 050: Earnings Calendar Table
-- Stores upcoming earnings events for the next 60 days
-- Refreshed weekly by scheduler

CREATE TABLE IF NOT EXISTS earnings_calendar (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    eps_actual DECIMAL(10, 4),
    eps_estimated DECIMAL(10, 4),
    revenue_actual BIGINT,
    revenue_estimated BIGINT,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(symbol, date)
);

-- Index for fast date range queries
CREATE INDEX IF NOT EXISTS idx_earnings_calendar_date ON earnings_calendar(date);

-- Index for symbol lookups
CREATE INDEX IF NOT EXISTS idx_earnings_calendar_symbol ON earnings_calendar(symbol);

-- Index for combined date + symbol queries
CREATE INDEX IF NOT EXISTS idx_earnings_calendar_date_symbol ON earnings_calendar(date, symbol);

COMMENT ON TABLE earnings_calendar IS 'Stores upcoming earnings events for the next 60 days, refreshed weekly';
COMMENT ON COLUMN earnings_calendar.symbol IS 'Stock ticker symbol';
COMMENT ON COLUMN earnings_calendar.date IS 'Earnings report date';
COMMENT ON COLUMN earnings_calendar.eps_actual IS 'Actual EPS reported (null if not yet reported)';
COMMENT ON COLUMN earnings_calendar.eps_estimated IS 'Estimated/consensus EPS';
COMMENT ON COLUMN earnings_calendar.revenue_actual IS 'Actual revenue reported (null if not yet reported)';
COMMENT ON COLUMN earnings_calendar.revenue_estimated IS 'Estimated/consensus revenue';
COMMENT ON COLUMN earnings_calendar.last_updated IS 'When this record was last updated from FMP API';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
