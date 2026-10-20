"""
066_canvas_process_params

Revision ID: bf2fad7a698b
Revises: cca319f84fd8
Create Date: 2025-12-31T16:05:17.210389

Original SQL file: 066_canvas_process_params.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bf2fad7a698b"
down_revision = "cca319f84fd8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 066_canvas_process_params.sql."""
    op.execute("""
-- Add params column to canvas_processes for storing original run parameters
-- This enables re-running processes with the same or modified params

ALTER TABLE canvas_processes ADD COLUMN IF NOT EXISTS params JSONB DEFAULT '{}';

COMMENT ON COLUMN canvas_processes.params IS 'Original parameters used to run the tool (for re-run/edit functionality)';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
