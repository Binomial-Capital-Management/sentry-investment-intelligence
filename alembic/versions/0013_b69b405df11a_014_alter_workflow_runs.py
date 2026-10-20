"""
014_alter_workflow_runs

Revision ID: b69b405df11a
Revises: 16811a26c8c9
Create Date: 2025-12-31T16:05:17.185167

Original SQL file: 014_alter_workflow_runs.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b69b405df11a"
down_revision = "16811a26c8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 014_alter_workflow_runs.sql."""
    op.execute("""
-- PR1 Completion: Update workflow_runs table to match spec
-- Date: 2025-09-04
-- Purpose: Add snapshot fields, rename columns, update status enum

-- Add snapshot columns with defaults (non-breaking change)
ALTER TABLE workflow_runs 
  ADD COLUMN IF NOT EXISTS snapshot_nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS snapshot_edges JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Rename error_message to error (matches spec)
ALTER TABLE workflow_runs 
  RENAME COLUMN error_message TO error;

-- Add summary column (keeping input_data/output_data for compatibility)
ALTER TABLE workflow_runs 
  ADD COLUMN IF NOT EXISTS summary JSONB;

-- Migrate existing status values to match spec
UPDATE workflow_runs 
  SET status = 'succeeded' WHERE status = 'completed';
UPDATE workflow_runs 
  SET status = 'canceled' WHERE status = 'cancelled';

-- Drop and recreate CHECK constraint with new values
ALTER TABLE workflow_runs 
  DROP CONSTRAINT IF EXISTS workflow_runs_status_check;
ALTER TABLE workflow_runs 
  ADD CONSTRAINT workflow_runs_status_check 
  CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'canceled'));

-- Update workflow_run_steps status values similarly
UPDATE workflow_run_steps
  SET status = 'succeeded' WHERE status = 'completed';

-- Drop and recreate CHECK constraint for steps
ALTER TABLE workflow_run_steps
  DROP CONSTRAINT IF EXISTS workflow_run_steps_status_check;
ALTER TABLE workflow_run_steps
  ADD CONSTRAINT workflow_run_steps_status_check
  CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'skipped'));

-- Add index for performance on status queries
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_status ON workflow_run_steps(status);

-- Add comment documenting the schema changes
COMMENT ON COLUMN workflow_runs.snapshot_nodes IS 'Snapshot of workflow nodes at time of run';
COMMENT ON COLUMN workflow_runs.snapshot_edges IS 'Snapshot of workflow edges at time of run';
COMMENT ON COLUMN workflow_runs.summary IS 'Run summary data (replaces output_data)';
COMMENT ON COLUMN workflow_runs.error IS 'Error message if run failed (renamed from error_message)';
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
