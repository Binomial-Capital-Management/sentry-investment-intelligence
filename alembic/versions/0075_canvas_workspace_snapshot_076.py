"""
076_canvas_workspace_snapshot

Revision ID: workspace_snapshot_001
Revises: canvas_chat_pinned_001
Create Date: 2026-02-18

Add workspace_snapshot JSONB column to canvas_chat_threads for chat-workspace binding.
Stores tab configurations (not data) that can be restored when loading a chat from history.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "workspace_snapshot_001"
down_revision = "canvas_chat_pinned_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add workspace_snapshot JSONB column to canvas_chat_threads."""
    op.execute("""
-- =============================================================================
-- Add workspace_snapshot column to canvas_chat_threads
-- =============================================================================

-- Add workspace_snapshot JSONB column for storing tab configurations
-- Structure: { captured_at: ISO timestamp, tabs: WorkspaceTab[], activeTabId: string }
ALTER TABLE canvas_chat_threads ADD COLUMN IF NOT EXISTS workspace_snapshot JSONB;

-- Add comment explaining the column purpose
COMMENT ON COLUMN canvas_chat_threads.workspace_snapshot IS 
    'Stores workspace tab configurations (not data) for chat-workspace binding. '
    'Allows restoring AI-created tabs when loading a chat from history.';
""")


def downgrade() -> None:
    """Remove workspace_snapshot column."""
    op.execute("""
-- Drop workspace_snapshot column
ALTER TABLE canvas_chat_threads DROP COLUMN IF EXISTS workspace_snapshot;
""")
