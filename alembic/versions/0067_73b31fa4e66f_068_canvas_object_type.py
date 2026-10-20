"""
068_canvas_object_type

Revision ID: 73b31fa4e66f
Revises: f0604ebbbdbf
Create Date: 2025-12-31T16:05:17.211389

Original SQL file: 068_canvas_object_type.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "73b31fa4e66f"
down_revision = "f0604ebbbdbf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 068_canvas_object_type.sql."""
    op.execute("""
-- Add object_type column to canvas_processes
-- Tracks what type of object was analyzed (equity, portfolio, crypto, etc.)
-- Enables filtering and proper capability matching

ALTER TABLE canvas_processes 
ADD COLUMN IF NOT EXISTS object_type TEXT;

-- Index for filtering by object type
CREATE INDEX IF NOT EXISTS idx_canvas_processes_object_type 
ON canvas_processes(object_type) 
WHERE object_type IS NOT NULL;

COMMENT ON COLUMN canvas_processes.object_type IS 'Object type from Canvas registry (equity, portfolio, crypto, etf, forex, commodity, macro_series)';


""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
