"""
069_canvas_process_type

Revision ID: a16376251f46
Revises: 73b31fa4e66f
Create Date: 2025-12-31T16:05:17.211389

Original SQL file: 069_canvas_process_type.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a16376251f46"
down_revision = "73b31fa4e66f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 069_canvas_process_type.sql."""
    op.execute("""
-- Add process_type column to canvas_processes for distinguishing tool vs data_workspace
-- Default to 'tool' for existing records

ALTER TABLE canvas_processes ADD COLUMN IF NOT EXISTS process_type TEXT DEFAULT 'tool';

-- Add config column for storing data workspace configuration
ALTER TABLE canvas_processes ADD COLUMN IF NOT EXISTS config JSONB DEFAULT '{}';

-- Index for filtering by process type
CREATE INDEX IF NOT EXISTS idx_canvas_processes_process_type ON canvas_processes(process_type);

-- Comment on new columns
COMMENT ON COLUMN canvas_processes.process_type IS 'Type of process: tool (analysis) or data_workspace (unified data table)';
COMMENT ON COLUMN canvas_processes.config IS 'Configuration for data workspace: objects, date_from, date_to, frequency, columns';


""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
