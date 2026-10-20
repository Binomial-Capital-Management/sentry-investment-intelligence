"""
042_tasks_indexes

Revision ID: 9f65c2c4a527
Revises: 7cff1ac22973
Create Date: 2025-12-31T16:05:17.199389

Original SQL file: 042_tasks_indexes.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f65c2c4a527"
down_revision = "7cff1ac22973"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 042_tasks_indexes.sql."""
    op.execute("""
-- Performance Indexes for Tasks Feature
-- Migration: 042_tasks_indexes.sql
-- Purpose: Add composite indexes to optimize common queries and prevent table scans

-- Composite index for list_run_history query
-- Optimizes: WHERE task_id = $1 AND user_id = $2 ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_task_runs_task_user_created
    ON task_runs(task_id, user_id, created_at DESC);

-- Index for task_saved_outputs lookup by run_id
-- Optimizes: WHERE task_run_id = ANY($1::uuid[])
CREATE INDEX IF NOT EXISTS idx_task_saved_outputs_run
    ON task_saved_outputs(task_run_id);

-- Composite index for active tasks by user
-- Optimizes: WHERE status = 'active' AND user_id = $1
CREATE INDEX IF NOT EXISTS idx_tasks_status_user
    ON tasks(status, user_id) WHERE status = 'active';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
