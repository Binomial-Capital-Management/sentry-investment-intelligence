"""
074_institution_universe

Revision ID: institution_universe_001
Revises: studio_artifacts_001
Create Date: 2026-02-04

Institution Universe Migration - creates searchable database of 13F filers
Mirrors ticker_universe pattern for fuzzy search
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "institution_universe_001"
down_revision = "studio_artifacts_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create institution_universe table for 13F filer search."""
    op.execute("""
-- Institution Universe Migration
-- Creates master institutional investor database for fuzzy search
-- Mirrors ticker_universe pattern
-- February 2026

-- Institution universe table
-- Fields from FMP /api/v4/institutional-ownership/list endpoint
CREATE TABLE IF NOT EXISTS institution_universe (
    -- Primary identifier (SEC CIK number)
    cik VARCHAR(20) PRIMARY KEY,
    
    -- Institution name from FMP
    name VARCHAR(500) NOT NULL,
    
    -- Normalized name for better search matching
    name_normalized VARCHAR(500),
    
    -- Metadata
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast fuzzy search using pg_trgm
CREATE INDEX IF NOT EXISTS idx_institution_cik_trgm
    ON institution_universe USING gin (cik gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_institution_name_trgm
    ON institution_universe USING gin (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_institution_name_normalized_trgm
    ON institution_universe USING gin (name_normalized gin_trgm_ops);

-- B-tree index for exact CIK lookups
CREATE INDEX IF NOT EXISTS idx_institution_cik_btree
    ON institution_universe(cik);

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_institution_universe_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_institution_universe_timestamp ON institution_universe;
CREATE TRIGGER update_institution_universe_timestamp
    BEFORE UPDATE ON institution_universe
    FOR EACH ROW
    EXECUTE FUNCTION update_institution_universe_timestamp();

-- Function to normalize institution names for better search
CREATE OR REPLACE FUNCTION normalize_institution_name(name TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN UPPER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                name,
                '(,? ?(LLC|LP|L\.P\.|INC|INC\.|CORP|CORPORATION|LTD|LIMITED|CO|COMPANY|PARTNERS|MANAGEMENT|ADVISORS|CAPITAL|INVESTMENTS|HOLDINGS|GROUP|FUND|TRUST|NA|N\.A\.))+$',
                '',
                'gi'
            ),
            '[^A-Z0-9 ]',
            '',
            'g'
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger to auto-populate normalized name
CREATE OR REPLACE FUNCTION set_institution_name_normalized()
RETURNS TRIGGER AS $$
BEGIN
    NEW.name_normalized = normalize_institution_name(NEW.name);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_institution_name_normalized ON institution_universe;
CREATE TRIGGER set_institution_name_normalized
    BEFORE INSERT OR UPDATE ON institution_universe
    FOR EACH ROW
    EXECUTE FUNCTION set_institution_name_normalized();

""")


def downgrade() -> None:
    """Drop institution_universe table and related objects."""
    op.execute("""
DROP TRIGGER IF EXISTS update_institution_universe_timestamp ON institution_universe;
DROP TRIGGER IF EXISTS set_institution_name_normalized ON institution_universe;
DROP FUNCTION IF EXISTS update_institution_universe_timestamp();
DROP FUNCTION IF EXISTS set_institution_name_normalized();
DROP FUNCTION IF EXISTS normalize_institution_name(TEXT);
DROP TABLE IF EXISTS institution_universe;
""")
