"""
074_canvas_action_results

Revision ID: action_results_001
Revises: studio_artifacts_001
Create Date: 2026-02-11

Canvas Action Results - Stores results from frontend action execution for AI feedback loop.
When AI performs actions via agent_action events, the frontend reports success/failure here
so the AI can learn from outcomes on next turn.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "action_results_001"
down_revision = "studio_artifacts_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create canvas_action_results table with RLS for AI feedback loop."""
    op.execute("""
-- =============================================================================
-- Canvas Action Results Table
-- Stores results from frontend action execution for AI feedback loop
-- =============================================================================

CREATE TABLE IF NOT EXISTS canvas_action_results (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    thread_id UUID NOT NULL REFERENCES canvas_chat_threads(id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,           -- From SSE event actionId or generated
    action_type TEXT NOT NULL,         -- e.g., 'add_dataset', 'remove_dataset', 'create_chart'
    symbol TEXT,                       -- Optional, for dataset-related actions
    success BOOLEAN NOT NULL,
    error TEXT,                        -- Error message if failed
    cancelled BOOLEAN DEFAULT FALSE,   -- True if user cancelled confirmation
    data JSONB,                        -- Optional additional result data
    user_id TEXT NOT NULL,
    org_id TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE    -- Set true after injected into AI context
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_canvas_action_results_thread ON canvas_action_results(thread_id, processed);
CREATE INDEX IF NOT EXISTS idx_canvas_action_results_user ON canvas_action_results(user_id);
CREATE INDEX IF NOT EXISTS idx_canvas_action_results_created ON canvas_action_results(created_at DESC);

-- Enable Row Level Security
ALTER TABLE canvas_action_results ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their own action results
DROP POLICY IF EXISTS canvas_action_results_isolation ON canvas_action_results;
CREATE POLICY canvas_action_results_isolation ON canvas_action_results
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Grant permissions to application role if it exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'binomial_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON canvas_action_results TO binomial_app;
  ELSE
    RAISE NOTICE 'binomial_app role not found; skipping grants';
  END IF;
END $$;

-- Documentation comments
COMMENT ON TABLE canvas_action_results IS 'Frontend action execution results for AI feedback loop';
COMMENT ON COLUMN canvas_action_results.action_id IS 'Correlates with SSE event actionId';
COMMENT ON COLUMN canvas_action_results.processed IS 'Set true after AI receives feedback to prevent duplicate injection';
""")


def downgrade() -> None:
    """Remove canvas_action_results table."""
    op.execute("""
-- Drop policy
DROP POLICY IF EXISTS canvas_action_results_isolation ON canvas_action_results;

-- Drop indexes
DROP INDEX IF EXISTS idx_canvas_action_results_thread;
DROP INDEX IF EXISTS idx_canvas_action_results_user;
DROP INDEX IF EXISTS idx_canvas_action_results_created;

-- Drop table
DROP TABLE IF EXISTS canvas_action_results;
""")
