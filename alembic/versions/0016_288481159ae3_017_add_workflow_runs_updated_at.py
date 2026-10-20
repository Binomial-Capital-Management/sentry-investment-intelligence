"""
017_add_workflow_runs_updated_at

Revision ID: 288481159ae3
Revises: 6af870c10848
Create Date: 2025-12-31T16:05:17.186165

Original SQL file: 017_add_workflow_runs_updated_at.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "288481159ae3"
down_revision = "6af870c10848"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 017_add_workflow_runs_updated_at.sql."""
    op.execute("""
-- Add missing updated_at column to workflow_runs table
-- Migration: 017_add_workflow_runs_updated_at.sql
-- Date: 2025-10-09
-- Purpose: Fix missing updated_at column causing 500 errors in workflow execution

-- Add updated_at column to workflow_runs
ALTER TABLE workflow_runs
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Create trigger to auto-update the timestamp
DROP TRIGGER IF EXISTS update_workflow_runs_updated_at ON workflow_runs;
CREATE TRIGGER update_workflow_runs_updated_at
    BEFORE UPDATE ON workflow_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comment documenting the column
COMMENT ON COLUMN workflow_runs.updated_at IS 'Timestamp of last update to workflow run record';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
