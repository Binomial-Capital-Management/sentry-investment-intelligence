"""
021_knowledge_graph_tables

Revision ID: d42de9823793
Revises: f6488f380271
Create Date: 2025-12-31T16:05:17.188167

Original SQL file: 021_knowledge_graph_tables.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d42de9823793"
down_revision = "f6488f380271"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 021_knowledge_graph_tables.sql."""
    op.execute("""
-- Migration 018: Knowledge Graph Saved Tables
-- Purpose: Store user-prepared tables with Excel-like configuration

-- Create saved_tables table
CREATE TABLE IF NOT EXISTS saved_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    -- File metadata
    file_name TEXT NOT NULL,
    file_size INTEGER,

    -- Table structure
    row_count INTEGER NOT NULL,
    column_count INTEGER NOT NULL,

    -- Excel configuration (stored as JSONB)
    selections JSONB NOT NULL, -- {headerCells, identifierCells, dataRegion}
    raw_data JSONB NOT NULL,   -- The actual table data

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_name CHECK (name ~ '^[a-zA-Z0-9_\\s-]+$'),
    CONSTRAINT valid_row_count CHECK (row_count > 0),
    CONSTRAINT valid_column_count CHECK (column_count > 0)
);

-- Create index on user_id for fast lookup
CREATE INDEX idx_saved_tables_user_id ON saved_tables(user_id);

-- Create index on created_at for sorting
CREATE INDEX idx_saved_tables_created_at ON saved_tables(created_at DESC);

-- Create compound index for user search
CREATE INDEX idx_saved_tables_user_name ON saved_tables(user_id, name);

-- Enable RLS
ALTER TABLE saved_tables ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own tables
CREATE POLICY saved_tables_isolation_policy ON saved_tables
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

-- RLS Policy: Users can insert their own tables
CREATE POLICY saved_tables_insert_policy ON saved_tables
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- RLS Policy: Users can update their own tables
CREATE POLICY saved_tables_update_policy ON saved_tables
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- RLS Policy: Users can delete their own tables
CREATE POLICY saved_tables_delete_policy ON saved_tables
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true));

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_saved_tables_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER saved_tables_updated_at_trigger
    BEFORE UPDATE ON saved_tables
    FOR EACH ROW
    EXECUTE FUNCTION update_saved_tables_updated_at();

-- Add comment for documentation
COMMENT ON TABLE saved_tables IS 'Stores user-prepared Excel tables with structure configuration for Knowledge Graph import';
COMMENT ON COLUMN saved_tables.selections IS 'Excel configuration: {headerCells: string[], identifierCells: string[], dataRegion: {startRow, endRow, startCol, endCol}}';
COMMENT ON COLUMN saved_tables.raw_data IS 'Raw table data as 2D array of cell values';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
