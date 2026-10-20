"""
063_canvas_processes

Revision ID: 7f5022a80271
Revises: a9d569692b9f
Create Date: 2025-12-31T16:05:17.209389

Original SQL file: 063_canvas_processes.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f5022a80271"
down_revision = "a9d569692b9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 063_canvas_processes.sql."""
    op.execute("""
-- Canvas Processes table for persisting analysis results
-- Stores Monte Carlo, DCF, and other Canvas tool outputs

CREATE TABLE IF NOT EXISTS canvas_processes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,  -- No FK, same pattern as portfolio_postmortems
    org_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Process metadata
    name TEXT,
    tool_id TEXT NOT NULL,
    tickers TEXT[] DEFAULT '{}',
    weights NUMERIC[] DEFAULT '{}',
    
    -- Results stored as JSONB for flexibility
    metrics JSONB DEFAULT '{}',
    stats_table JSONB DEFAULT '[]',
    charts JSONB DEFAULT '{}',
    
    -- Tool-specific data
    hmm_enabled BOOLEAN DEFAULT FALSE,
    current_regime TEXT,
    regime_params JSONB,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_canvas_processes_user_id ON canvas_processes(user_id);
CREATE INDEX IF NOT EXISTS idx_canvas_processes_org_id ON canvas_processes(org_id);
CREATE INDEX IF NOT EXISTS idx_canvas_processes_tool_id ON canvas_processes(tool_id);
CREATE INDEX IF NOT EXISTS idx_canvas_processes_created_at ON canvas_processes(created_at DESC);

-- Enable RLS
ALTER TABLE canvas_processes ENABLE ROW LEVEL SECURITY;

-- RLS Policies (same pattern as other tables)
-- Users can see their own processes or org processes they belong to
CREATE POLICY canvas_processes_select_policy ON canvas_processes
    FOR SELECT
    USING (
        user_id = current_setting('app.current_user_id', true)
        OR (
            org_id IS NOT NULL 
            AND org_id = current_setting('app.current_org_id', true)
            AND current_setting('app.current_org_id', true) != ''
        )
    );

-- Users can insert their own processes
CREATE POLICY canvas_processes_insert_policy ON canvas_processes
    FOR INSERT
    WITH CHECK (
        user_id = current_setting('app.current_user_id', true)
    );

-- Users can update their own processes
CREATE POLICY canvas_processes_update_policy ON canvas_processes
    FOR UPDATE
    USING (
        user_id = current_setting('app.current_user_id', true)
    );

-- Users can delete their own processes
CREATE POLICY canvas_processes_delete_policy ON canvas_processes
    FOR DELETE
    USING (
        user_id = current_setting('app.current_user_id', true)
    );

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_canvas_processes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER canvas_processes_updated_at_trigger
    BEFORE UPDATE ON canvas_processes
    FOR EACH ROW
    EXECUTE FUNCTION update_canvas_processes_updated_at();

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
