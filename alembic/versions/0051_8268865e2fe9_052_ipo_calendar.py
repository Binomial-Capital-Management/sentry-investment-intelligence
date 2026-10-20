"""
052_ipo_calendar

Revision ID: 8268865e2fe9
Revises: de9c56f47a3a
Create Date: 2025-12-31T16:05:17.203389

Original SQL file: 052_ipo_calendar.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8268865e2fe9"
down_revision = "de9c56f47a3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 052_ipo_calendar.sql."""
    op.execute("""
-- IPO Calendar Table
-- Stores upcoming and recent IPO data from FMP API
-- Updated weekly by Lambda function

CREATE TABLE IF NOT EXISTS ipo_calendar (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    company TEXT,
    exchange VARCHAR(50),
    actions VARCHAR(50),  -- 'Expected', 'Priced', 'Filed', etc.
    shares BIGINT,
    price_range VARCHAR(100),
    market_cap BIGINT,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ipo_calendar_symbol ON ipo_calendar(symbol);
CREATE INDEX IF NOT EXISTS idx_ipo_calendar_date ON ipo_calendar(date);
CREATE INDEX IF NOT EXISTS idx_ipo_calendar_exchange ON ipo_calendar(exchange);
CREATE INDEX IF NOT EXISTS idx_ipo_calendar_actions ON ipo_calendar(actions);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_ipo_calendar_date_exchange ON ipo_calendar(date, exchange);

COMMENT ON TABLE ipo_calendar IS 'IPO calendar data from FMP API, refreshed weekly';
COMMENT ON COLUMN ipo_calendar.symbol IS 'Stock ticker symbol';
COMMENT ON COLUMN ipo_calendar.date IS 'IPO date';
COMMENT ON COLUMN ipo_calendar.company IS 'Company name';
COMMENT ON COLUMN ipo_calendar.exchange IS 'Exchange (NYSE, NASDAQ, etc.)';
COMMENT ON COLUMN ipo_calendar.actions IS 'IPO status (Expected, Priced, Filed, etc.)';
COMMENT ON COLUMN ipo_calendar.shares IS 'Number of shares offered';
COMMENT ON COLUMN ipo_calendar.price_range IS 'Expected price range (e.g., "10.00 - 12.00")';
COMMENT ON COLUMN ipo_calendar.market_cap IS 'Expected market capitalization';
COMMENT ON COLUMN ipo_calendar.last_updated IS 'Last update from FMP API';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
