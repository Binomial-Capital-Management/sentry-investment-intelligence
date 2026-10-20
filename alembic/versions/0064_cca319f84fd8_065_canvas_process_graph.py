"""
065_canvas_process_graph

Revision ID: cca319f84fd8
Revises: e462aa469f11
Create Date: 2025-12-31T16:05:17.210389

Original SQL file: 065_canvas_process_graph.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cca319f84fd8"
down_revision = "e462aa469f11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 065_canvas_process_graph.sql."""
    op.execute("""
-- Add graph columns to canvas_processes for storing process steps and edges
-- This enables the tensor-based primitive system [type, instance] coordinates

ALTER TABLE canvas_processes ADD COLUMN IF NOT EXISTS graph_steps JSONB;
ALTER TABLE canvas_processes ADD COLUMN IF NOT EXISTS graph_edges JSONB;

COMMENT ON COLUMN canvas_processes.graph_steps IS 'Array of process steps with [primitive_type, instance] coordinates';
COMMENT ON COLUMN canvas_processes.graph_edges IS 'Array of edges connecting steps by their coordinates';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
