"""
018_ticker_universe

Revision ID: 2e441cb85f24
Revises: 288481159ae3
Create Date: 2025-12-31T16:05:17.187166

Original SQL file: 018_ticker_universe.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2e441cb85f24"
down_revision = "288481159ae3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 018_ticker_universe.sql."""
    op.execute("""
-- Ticker Universe Migration
-- Creates master ticker database for fuzzy search
-- Following CODING_RULES.md: no hardcoding, discover fields dynamically from FMP API
-- January 2025

-- Enable pg_trgm extension for fuzzy text search (with graceful fallback)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'Skipping pg_trgm extension (insufficient privileges)';
    WHEN undefined_file THEN
        RAISE NOTICE 'pg_trgm extension not available';
    WHEN feature_not_supported THEN
        RAISE NOTICE 'pg_trgm extension not installed on this server';
    WHEN OTHERS THEN
        RAISE NOTICE 'Could not create pg_trgm extension: %', SQLERRM;
END $$;

-- Ticker universe table
-- Fields discovered from FMP /v3/stock/list and /v3/profile endpoints
CREATE TABLE IF NOT EXISTS ticker_universe (
    -- Primary identifier
    symbol VARCHAR(20) PRIMARY KEY,

    -- Core info from stock/list endpoint
    name VARCHAR(500) NOT NULL,
    exchange VARCHAR(100),
    exchange_short VARCHAR(20),
    type VARCHAR(20),  -- stock, etf, fund, etc
    price DECIMAL(20, 4),

    -- Extended metadata from profile endpoint (populated on-demand)
    sector VARCHAR(100),
    industry VARCHAR(200),
    market_cap BIGINT,
    description TEXT,
    country VARCHAR(10),
    currency VARCHAR(10),
    ipo_date DATE,
    is_actively_trading BOOLEAN DEFAULT true,

    -- Metadata
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast fuzzy search using pg_trgm
CREATE INDEX IF NOT EXISTS idx_ticker_symbol_trgm
    ON ticker_universe USING gin (symbol gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_ticker_name_trgm
    ON ticker_universe USING gin (name gin_trgm_ops);

-- Indexes for filtering
CREATE INDEX IF NOT EXISTS idx_ticker_exchange
    ON ticker_universe(exchange_short);

CREATE INDEX IF NOT EXISTS idx_ticker_type
    ON ticker_universe(type);

CREATE INDEX IF NOT EXISTS idx_ticker_sector
    ON ticker_universe(sector);

CREATE INDEX IF NOT EXISTS idx_ticker_market_cap
    ON ticker_universe(market_cap DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_ticker_active
    ON ticker_universe(is_actively_trading)
    WHERE is_actively_trading = true;

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_ticker_search_combo
    ON ticker_universe(exchange_short, type, is_actively_trading);

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_ticker_universe_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_ticker_universe_timestamp ON ticker_universe;
CREATE TRIGGER update_ticker_universe_timestamp
    BEFORE UPDATE ON ticker_universe
    FOR EACH ROW
    EXECUTE FUNCTION update_ticker_universe_timestamp();

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
