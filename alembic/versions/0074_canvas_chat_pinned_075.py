"""
075_canvas_chat_pinned

Revision ID: canvas_chat_pinned_001
Revises: action_results_001
Create Date: 2026-02-13

Add pinned column to canvas_chat_threads for pinning favorite conversations.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "canvas_chat_pinned_001"
down_revision = "action_results_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add pinned column and index to canvas_chat_threads."""
    op.execute("""
-- =============================================================================
-- Add pinned column to canvas_chat_threads
-- =============================================================================

-- Add pinned column with default false
ALTER TABLE canvas_chat_threads ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE;

-- Create index for efficient sorting (pinned first, then by updated_at)
CREATE INDEX IF NOT EXISTS idx_canvas_chat_threads_pinned_updated 
ON canvas_chat_threads(user_id, org_id, pinned DESC, updated_at DESC);
""")


def downgrade() -> None:
    """Remove pinned column and index."""
    op.execute("""
-- Drop index
DROP INDEX IF EXISTS idx_canvas_chat_threads_pinned_updated;

-- Drop column
ALTER TABLE canvas_chat_threads DROP COLUMN IF EXISTS pinned;
""")
